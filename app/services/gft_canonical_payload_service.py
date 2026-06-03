import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.gft_query_service import (
    _build_clinical_summary_payload,
    _extract_atc_items_from_row,
    _parse_json_value,
    _parse_vias,
    _row_get,
)
from app.services.normalization_service import normalize_cn

NO_INFORMADO = "No informado"
_INDICATION_KEYS = {
    "indicacion_autorizada",
    "indicaciones_autorizadas",
    "indicaciones",
    "indicacion",
    "descripcion",
    "texto",
    "indicacion_texto",
}
_CONTEXT_KEYS = {
    "condiciones_financiacion",
    "condiciones",
    "financiacion",
    "resolucion",
    "situacion_expediente_indicacion",
    "resolucion_expediente_financiacion_indicacion",
}
_FLAG_VALUES = {"si", "sí", "no", "financiado", "no financiado", "excluido", "alta", "baja", "true", "false"}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
    else:
        cleaned = str(value).strip()
    return cleaned or None


def _parse_any_json(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return value
    return value


def _norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text)


def _is_plausible_indication(value: Any) -> bool:
    text = _text(value)
    if text is None:
        return False
    norm = _norm_text(text)
    if norm in _FLAG_VALUES:
        return False
    if len(norm) < 12:
        return False
    if re.fullmatch(r"[\d\W_]+", norm):
        return False
    return True


def _as_indication(text_value: Any, source: str, context: Mapping[str, Any] | None = None) -> dict | None:
    text = _text(text_value)
    if not text or not _is_plausible_indication(text):
        return None
    item = {"indicacion_autorizada": text, "source": source}
    if context:
        for key in _CONTEXT_KEYS:
            value = _text(context.get(key))
            if value:
                item[key] = value
    return item


def _walk_for_indications(value: Any, source: str, *, parent_key: str | None = None) -> list[dict]:
    value = _parse_any_json(value)
    out: list[dict] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_norm = str(key).strip().lower()
            if key_norm in _INDICATION_KEYS:
                if isinstance(child, (Mapping, list)):
                    out.extend(_walk_for_indications(child, source, parent_key=key_norm))
                else:
                    item = _as_indication(child, source, value)
                    if item:
                        out.append(item)
            elif key_norm in _CONTEXT_KEYS:
                out.extend(_walk_for_indications(child, source, parent_key=key_norm))
            elif isinstance(child, (Mapping, list)):
                out.extend(_walk_for_indications(child, source, parent_key=key_norm))
        return out
    if isinstance(value, list):
        for child in value:
            out.extend(_walk_for_indications(child, source, parent_key=parent_key))
        return out
    if parent_key in _INDICATION_KEYS:
        item = _as_indication(value, source)
        if item:
            out.append(item)
    return out


def _dedupe_indications(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        text = _text(item.get("indicacion_autorizada") or item.get("texto") or item.get("descripcion"))
        if not text:
            continue
        key = _norm_text(text)
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(item)
        normalized["indicacion_autorizada"] = text
        deduped.append(normalized)
    return deduped


def extract_bifimed_indicaciones(cache_row: BifimedCache | Mapping[str, Any] | None) -> list[dict]:
    if cache_row is None:
        return []
    def get(name: str):
        if isinstance(cache_row, Mapping):
            return cache_row.get(name)
        return getattr(cache_row, name, None)

    sources = [
        ("indicaciones_autorizadas_json", get("indicaciones_autorizadas_json")),
        ("detalle_financiacion_json", get("detalle_financiacion_json")),
        ("raw_data", get("raw_data")),
    ]
    for source, value in sources:
        items = _dedupe_indications(_walk_for_indications(value, source))
        if items:
            return items
    return []


def _principios_from_relation(db: Session, cns: list[str]) -> dict[str, list[dict]]:
    normalized = {normalize_cn(cn) for cn in cns if normalize_cn(cn)}
    rows = (
        db.query(
            MedicamentoPrincipioActivo.cn,
            PrincipioActivo.id,
            PrincipioActivo.slug,
            PrincipioActivo.nombre_display,
            MedicamentoPrincipioActivo.orden,
        )
        .join(PrincipioActivo, PrincipioActivo.id == MedicamentoPrincipioActivo.principio_activo_id)
        .order_by(MedicamentoPrincipioActivo.orden, PrincipioActivo.nombre_display)
        .all()
    )
    result: dict[str, list[dict]] = {}
    for row in rows:
        cn = normalize_cn(row.cn)
        if cn not in normalized:
            continue
        result.setdefault(cn, []).append({"id": row.id, "slug": row.slug, "nombre": row.nombre_display})
    return result


def _principios_from_view(row) -> tuple[str, str]:
    parsed = _parse_json_value(_row_get(row, "principios_activos_json"))
    names: list[str] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, Mapping):
                name = _text(item.get("nombre") or item.get("name") or item.get("principio_activo"))
            else:
                name = _text(item)
            if name:
                names.append(name)
    if names:
        return ", ".join(dict.fromkeys(names)), "principio_activo_from_view_json"
    for key in ("principio_activo", "principios_activos", "principio_activo_importado"):
        value = _text(_row_get(row, key))
        if value:
            return value, f"principio_activo_from_view_{key}"
    return NO_INFORMADO, "principio_activo_missing"


def _resolve_principio_activo(row, relation: list[dict]) -> tuple[str, str]:
    if relation:
        return ", ".join(item["nombre"] for item in relation if item.get("nombre")), "principio_activo_from_relation"
    return _principios_from_view(row)



def _useful_auto_text(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    norm = _norm_text(text)
    if norm in {_norm_text(NO_INFORMADO), "no data", "no_data", "missing_source"}:
        return None
    if "no localizado automaticamente" in norm or "no localizado automatic" in norm:
        return None
    return text


def _manual_or_auto(manual_value: Any, auto_value: Any) -> str | None:
    return _text(manual_value) or _useful_auto_text(auto_value)

def _available(value: Any) -> bool:
    return _text(value) is not None


def _bifimed_payload(bifimed: BifimedCache | None) -> tuple[dict, list[str], list[str]]:
    if bifimed is None:
        return {
            "bifimed_cache_presente": False,
            "situacion_financiacion_bifimed": NO_INFORMADO,
            "condiciones_financiacion_restringidas": NO_INFORMADO,
            "condiciones_especiales_financiacion": NO_INFORMADO,
            "detalle_financiacion_json": None,
            "indicaciones_bifimed": [],
            "estado_bifimed": "sin_cache",
        }, ["bifimed_cache"], ["bifimed_sin_cache"]
    indicaciones = extract_bifimed_indicaciones(bifimed)
    estado = "disponible" if indicaciones else "sin_indicaciones"
    if bifimed.sync_status and bifimed.sync_status not in {"ok", "not_implemented"}:
        estado = "error" if bifimed.sync_status == "error" else bifimed.sync_status
    missing = [] if indicaciones else ["indicaciones_bifimed"]
    flags = ["bifimed_cache_presente"]
    if not indicaciones:
        flags.append("bifimed_sin_indicaciones_extraibles")
    return {
        "bifimed_cache_presente": True,
        "situacion_financiacion_bifimed": _text(bifimed.situacion_financiacion) or NO_INFORMADO,
        "condiciones_financiacion_restringidas": _text(bifimed.condiciones_financiacion_restringidas) or NO_INFORMADO,
        "condiciones_especiales_financiacion": _text(bifimed.condiciones_especiales_financiacion) or NO_INFORMADO,
        "detalle_financiacion_json": bifimed.detalle_financiacion_json,
        "indicaciones_bifimed": indicaciones,
        "estado_bifimed": estado,
    }, missing, flags


def _build_payload(row, relation: list[dict], bifimed: BifimedCache | None, summary: GftClinicalSummaryCache | None) -> dict:
    cn = normalize_cn(_row_get(row, "cn"))
    principio, principio_flag = _resolve_principio_activo(row, relation)
    atc = _extract_atc_items_from_row(row)
    codigo_atc = atc[-1].get("codigo") if atc else _text(_row_get(row, "codigo_atc_importado"))
    descripcion_atc = atc[-1].get("nombre") if atc else _text(_row_get(row, "descripcion_atc_importada"))
    vias = _parse_vias(_row_get(row, "vias_administracion_json")) or ([_text(_row_get(row, "via_administracion_importada"))] if _text(_row_get(row, "via_administracion_importada")) else [])
    bifimed_data, bifimed_missing, bifimed_flags = _bifimed_payload(bifimed)
    indicaciones_cima = _manual_or_auto(_row_get(row, "indicaciones_ficha_tecnica"), getattr(summary, "resumen_indicaciones", None) if summary is not None else None)
    ajuste_renal = _manual_or_auto(_row_get(row, "ajuste_insuficiencia_renal"), getattr(summary, "resumen_ajuste_renal", None) if summary is not None else None)
    ajuste_hepatico = _manual_or_auto(_row_get(row, "ajuste_insuficiencia_hepatica"), getattr(summary, "resumen_ajuste_hepatico", None) if summary is not None else None)
    precauciones_embarazo = _manual_or_auto(_row_get(row, "precauciones_embarazo"), getattr(summary, "resumen_embarazo", None) if summary is not None else None)
    precauciones_lactancia = _manual_or_auto(_row_get(row, "precauciones_lactancia"), getattr(summary, "resumen_lactancia", None) if summary is not None else None)
    url_ft = _text(_row_get(row, "url_ficha_tecnica")) or _text(_row_get(row, "url_ficha_tecnica_importada"))
    url_pr = _text(_row_get(row, "url_prospecto")) or _text(_row_get(row, "url_prospecto_importado"))
    estado_cima = "disponible" if (indicaciones_cima or url_ft or url_pr) else "no_informado"
    campos_faltantes = []
    for field, value in {
        "principio_activo": None if principio == NO_INFORMADO else principio,
        "indicaciones_ficha_tecnica": indicaciones_cima,
        "url_ficha_tecnica": url_ft,
        "url_prospecto": url_pr,
        "ajuste_insuficiencia_renal": ajuste_renal,
        "ajuste_insuficiencia_hepatica": ajuste_hepatico,
        "precauciones_embarazo": precauciones_embarazo,
        "precauciones_lactancia": precauciones_lactancia,
        "restricciones_hospitalarias": _row_get(row, "restricciones_hospitalarias"),
    }.items():
        if not _available(value):
            campos_faltantes.append(field)
    campos_faltantes.extend(x for x in bifimed_missing if x not in campos_faltantes)
    fuentes = ["v_gft_publicada"]
    if relation:
        fuentes.append("principio_activo")
    if estado_cima == "disponible":
        fuentes.append("cima")
    if bifimed is not None:
        fuentes.append("bifimed")
    if summary is not None:
        fuentes.append("gft_clinical_summary")
    warnings = []
    if principio == NO_INFORMADO:
        warnings.append("Principio activo no informado en fuentes disponibles")
    if bifimed is None:
        warnings.append("Sin fila local en bifimed_cache")
    return {
        "cn": cn,
        "nombre_comercial": _text(_row_get(row, "nombre")) or _text(_row_get(row, "nombre_comercial_importado")) or NO_INFORMADO,
        "incluido_gft": True,
        "publicado": True,
        "observaciones_revision": _row_get(row, "observaciones_internas") or _row_get(row, "observaciones_publicables"),
        "estado_publicacion": _row_get(row, "estado_editorial") or "publicado",
        "principio_activo": principio,
        "forma_farmaceutica": _text(_row_get(row, "forma_farmaceutica")) or _text(_row_get(row, "forma_farmaceutica_importada")) or NO_INFORMADO,
        "via_administracion": ", ".join(vias) if vias else NO_INFORMADO,
        "nemonico": _text(_row_get(row, "nemonico")) or NO_INFORMADO,
        "codigo_atc": codigo_atc or NO_INFORMADO,
        "descripcion_atc": descripcion_atc or NO_INFORMADO,
        "jerarquia_atc": atc,
        "indicaciones_ficha_tecnica": indicaciones_cima or NO_INFORMADO,
        "url_ficha_tecnica": url_ft,
        "url_prospecto": url_pr,
        "estado_cima": estado_cima,
        **bifimed_data,
        "ajuste_insuficiencia_renal": ajuste_renal or NO_INFORMADO,
        "ajuste_insuficiencia_hepatica": ajuste_hepatico or NO_INFORMADO,
        "precauciones_embarazo": precauciones_embarazo or NO_INFORMADO,
        "precauciones_lactancia": precauciones_lactancia or NO_INFORMADO,
        "restricciones_hospitalarias": _text(_row_get(row, "restricciones_hospitalarias")) or NO_INFORMADO,
        "resumen_clinico_auto": _build_clinical_summary_payload(summary),
        "estado_resumen_clinico": summary.source_status if summary is not None else "no_informado",
        "fuentes_disponibles": fuentes,
        "campos_faltantes": sorted(dict.fromkeys(campos_faltantes)),
        "warnings": warnings,
        "data_quality_flags": [principio_flag, *bifimed_flags],
    }


def _load_published_rows(db: Session) -> list[Mapping[str, Any]]:
    return db.execute(text("SELECT * FROM v_gft_publicada")).mappings().all()


def _maps_for_rows(db: Session, rows: Sequence[Mapping[str, Any]]):
    cns = [normalize_cn(_row_get(row, "cn")) for row in rows if normalize_cn(_row_get(row, "cn"))]
    relaciones = _principios_from_relation(db, cns)
    bifimed = {normalize_cn(row.cn): row for row in db.query(BifimedCache).all() if normalize_cn(row.cn)}
    summaries = {normalize_cn(row.cn): row for row in db.query(GftClinicalSummaryCache).all() if normalize_cn(row.cn)}
    return relaciones, bifimed, summaries


def build_gft_canonical_payload(db: Session, cn: str) -> dict | None:
    cn_norm = normalize_cn(cn)
    if not cn_norm:
        return None
    rows = _load_published_rows(db)
    row = next((r for r in rows if normalize_cn(_row_get(r, "cn")) == cn_norm), None)
    if row is None:
        return None
    relaciones, bifimed, summaries = _maps_for_rows(db, [row])
    return _build_payload(row, relaciones.get(cn_norm, []), bifimed.get(cn_norm), summaries.get(cn_norm))


def audit_gft_coverage(db: Session) -> dict:
    rows = _load_published_rows(db)
    relaciones, bifimed, summaries = _maps_for_rows(db, rows)
    items = []
    summary = {
        "total_medicamentos_publicados": 0,
        "con_principio_activo": 0,
        "sin_principio_activo": 0,
        "con_cima": 0,
        "sin_cima": 0,
        "con_indicaciones_cima": 0,
        "con_bifimed_cache": 0,
        "sin_bifimed_cache": 0,
        "con_financiacion_bifimed": 0,
        "con_indicaciones_bifimed": 0,
        "sin_indicaciones_bifimed": 0,
        "con_ajuste_renal": 0,
        "con_ajuste_hepatico": 0,
        "con_embarazo": 0,
        "con_lactancia": 0,
        "con_restricciones": 0,
    }
    for row in rows:
        cn = normalize_cn(_row_get(row, "cn"))
        payload = _build_payload(row, relaciones.get(cn, []), bifimed.get(cn), summaries.get(cn))
        summary["total_medicamentos_publicados"] += 1
        if payload["principio_activo"] != NO_INFORMADO:
            summary["con_principio_activo"] += 1
            pa_status = "disponible"
        else:
            summary["sin_principio_activo"] += 1
            pa_status = "no_informado"
        if payload["estado_cima"] == "disponible":
            summary["con_cima"] += 1
        else:
            summary["sin_cima"] += 1
        if payload["indicaciones_ficha_tecnica"] != NO_INFORMADO:
            summary["con_indicaciones_cima"] += 1
        if payload["bifimed_cache_presente"]:
            summary["con_bifimed_cache"] += 1
        else:
            summary["sin_bifimed_cache"] += 1
        if payload["situacion_financiacion_bifimed"] != NO_INFORMADO:
            summary["con_financiacion_bifimed"] += 1
        if payload["indicaciones_bifimed"]:
            summary["con_indicaciones_bifimed"] += 1
            ib_status = "disponible"
        else:
            summary["sin_indicaciones_bifimed"] += 1
            ib_status = "sin_cache" if not payload["bifimed_cache_presente"] else "sin_indicaciones"
        for key, counter in (
            ("ajuste_insuficiencia_renal", "con_ajuste_renal"),
            ("ajuste_insuficiencia_hepatica", "con_ajuste_hepatico"),
            ("precauciones_embarazo", "con_embarazo"),
            ("precauciones_lactancia", "con_lactancia"),
            ("restricciones_hospitalarias", "con_restricciones"),
        ):
            if payload[key] != NO_INFORMADO:
                summary[counter] += 1
        items.append({
            "cn": cn,
            "nombre": payload["nombre_comercial"],
            "principio_activo_status": pa_status,
            "cima_status": payload["estado_cima"],
            "bifimed_status": payload["estado_bifimed"],
            "indicaciones_bifimed_status": ib_status,
            "campos_faltantes": payload["campos_faltantes"],
            "warnings": payload["warnings"],
        })
    return {"summary": summary, "items": items}
