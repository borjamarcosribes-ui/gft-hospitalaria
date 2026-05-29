import json
from collections.abc import Mapping
from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.normalization_service import normalize_cn


def _parse_json_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def _parse_vias(vias_json) -> list[str]:
    parsed = _parse_json_value(vias_json)
    if not isinstance(parsed, list):
        return []

    out: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, Mapping):
            name = str(item.get("nombre") or item.get("name") or "").strip()
        else:
            name = ""
        if name:
            out.append(name)
    return out


def _non_empty(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_atc_code(codigo: str | None) -> str:
    if codigo is None:
        return ""
    return "".join(str(codigo).strip().upper().split())


def _extract_atc_items_from_row(row) -> list[dict]:
    parsed_atc = _parse_atc(_row_get(row, "atc_json"))
    normalized_items: list[dict] = []
    for item in parsed_atc:
        code = _normalize_atc_code(str(item.get("codigo") or ""))
        if not code:
            continue
        normalized_items.append(
            {
                "codigo": code,
                "nombre": _non_empty(item.get("nombre")),
                "nivel": _non_empty(item.get("nivel")) or _infer_atc_level(code),
            }
        )
    if normalized_items:
        return normalized_items

    imported_code = _normalize_atc_code(_non_empty(_row_get(row, "codigo_atc_importado")))
    if not imported_code:
        return []
    return [
        {
            "codigo": imported_code,
            "nombre": _non_empty(_row_get(row, "descripcion_atc_importada")),
            "nivel": _infer_atc_level(imported_code),
        }
    ]




def _normalize_document_secc(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return _non_empty(value)


def _normalize_document_fecha(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 10_000_000_000:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return str(value)
    return _non_empty(value)

def _parse_atc(atc_json) -> list[dict]:
    parsed = _parse_json_value(atc_json)
    if not isinstance(parsed, list):
        return []

    out: list[dict] = []
    for item in parsed:
        if isinstance(item, str):
            code = item.strip()
            if code:
                out.append({"codigo": code, "nombre": None, "nivel": None})
            continue

        if not isinstance(item, Mapping):
            continue

        code = str(item.get("codigo") or item.get("code") or "").strip()
        if not code:
            continue
        name = item.get("nombre") or item.get("name")
        level = item.get("nivel") or item.get("level")
        out.append(
            {
                "codigo": code,
                "nombre": str(name).strip() if name is not None else None,
                "nivel": str(level).strip() if level is not None else None,
            }
        )
    return out


def _infer_atc_level(codigo: str) -> str | None:
    length = len(codigo)
    if length == 1:
        return "L1"
    if length == 3:
        return "L2"
    if length == 4:
        return "L3"
    if length == 5:
        return "L4"
    if length >= 7:
        return "L5"
    return None


def _expand_atc_code(codigo: str) -> list[tuple[str, str]]:
    code = codigo.strip().upper()
    if not code:
        return []

    expanded: list[tuple[str, str]] = []
    for length in (1, 3, 4, 5):
        if len(code) >= length:
            prefix = code[:length]
            level = _infer_atc_level(prefix)
            if level is not None:
                expanded.append((prefix, level))

    if len(code) >= 7:
        level = _infer_atc_level(code)
        if level is not None and all(prefix != code for prefix, _ in expanded):
            expanded.append((code, level))

    return expanded


def _merge_atc_index_entry(
    index: dict[str, dict],
    codigo: str,
    nivel: str,
    cn: str,
    nombre: str | None = None,
) -> None:
    entry = index.setdefault(codigo, {"codigo": codigo, "nombre": None, "nivel": nivel, "cns": set()})
    entry["cns"].add(cn)
    if nombre and entry["nombre"] is None:
        entry["nombre"] = nombre


def _get_principios_for_cns(db: Session, cns: list[str]) -> dict[str, list[dict]]:
    normalized_cns = [str(cn or "").strip() for cn in cns if str(cn or "").strip()]
    if not normalized_cns:
        return {}

    rows = (
        db.query(
            MedicamentoPrincipioActivo.cn,
            PrincipioActivo.id,
            PrincipioActivo.slug,
            PrincipioActivo.nombre_display,
            MedicamentoPrincipioActivo.orden,
        )
        .join(PrincipioActivo, PrincipioActivo.id == MedicamentoPrincipioActivo.principio_activo_id)
        .filter(func.trim(MedicamentoPrincipioActivo.cn).in_(normalized_cns))
        .order_by(MedicamentoPrincipioActivo.cn, MedicamentoPrincipioActivo.orden, PrincipioActivo.nombre_display)
        .all()
    )

    result: dict[str, list[dict]] = {}
    for row in rows:
        cn = str(row.cn or "").strip()
        result.setdefault(cn, []).append(
            {
                "id": row.id,
                "slug": row.slug,
                "nombre": row.nombre_display,
            }
        )
    return result


def _parse_documentos(documentos_json) -> list[dict]:
    parsed = _parse_json_value(documentos_json)
    if not isinstance(parsed, list):
        return []

    documentos: list[dict] = []
    for item in parsed:
        if not isinstance(item, Mapping):
            continue
        documentos.append(
            {
                "tipo": item.get("tipo"),
                "url": item.get("url"),
                "urlHtml": item.get("urlHtml"),
                "secc": _normalize_document_secc(item.get("secc")),
                "fecha": _normalize_document_fecha(item.get("fecha")),
                "titulo": item.get("titulo"),
                "nombre": item.get("nombre"),
            }
        )
    return documentos




def _build_document_links(row) -> list[dict]:
    documentos = _parse_documentos(_row_get(row, "documentos_json"))
    seen_urls: set[str] = set()

    for doc in documentos:
        url = _non_empty(doc.get("url"))
        if url:
            seen_urls.add(url)

    fallback_docs = [
        {
            "tipo": "ficha_tecnica",
            "titulo": "Ficha técnica AEMPS",
            "url": _non_empty(_row_get(row, "url_ficha_tecnica_importada")),
        },
        {
            "tipo": "prospecto",
            "titulo": "Prospecto AEMPS",
            "url": _non_empty(_row_get(row, "url_prospecto_importado")),
        },
    ]
    for fallback in fallback_docs:
        url = fallback["url"]
        if not url or url in seen_urls:
            continue
        documentos.append(fallback)
        seen_urls.add(url)

    return documentos
def _row_get(row, key: str, default=None):
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


def _build_financiacion_detalle(row) -> dict | None:
    detalle = {
        "situacion_financiacion": _row_get(row, "situacion_financiacion"),
        "condiciones_financiacion_restringidas": _row_get(row, "condiciones_financiacion_restringidas"),
        "condiciones_especiales_financiacion": _row_get(row, "condiciones_especiales_financiacion"),
        "estado_nomenclator": _row_get(row, "estado_nomenclator"),
        "aportacion_usuario": _row_get(row, "aportacion_usuario"),
        "subgrupo_atc": _row_get(row, "subgrupo_atc"),
    }
    detalle["indicaciones_autorizadas"] = []
    last_synced_at = _row_get(row, "bifimed_last_synced_at")
    if last_synced_at is not None:
        detalle["last_synced_at"] = last_synced_at
    if not any(value is not None for value in detalle.values()):
        return None
    return detalle


def _build_clinical_summary_payload(summary_row: GftClinicalSummaryCache | None) -> dict | None:
    if summary_row is None:
        return None
    return {
        "source_status": summary_row.source_status,
        "generated_at": summary_row.generated_at,
        "resumen_general": summary_row.resumen_general,
        "indicaciones": summary_row.resumen_indicaciones,
        "posologia": summary_row.resumen_posologia,
        "ajuste_renal": summary_row.resumen_ajuste_renal,
        "ajuste_hepatico": summary_row.resumen_ajuste_hepatico,
        "contraindicaciones": summary_row.resumen_contraindicaciones,
        "advertencias": summary_row.resumen_advertencias,
        "embarazo": summary_row.resumen_embarazo,
        "lactancia": summary_row.resumen_lactancia,
        "fuentes": summary_row.resumen_fuente_json or {},
        "warnings": summary_row.warnings_json or [],
    }


def _row_to_list_item(row, principios: list[dict]) -> dict:
    atc = _extract_atc_items_from_row(row)

    vias = _parse_vias(row["vias_administracion_json"])
    if not vias:
        imported_via = _non_empty(_row_get(row, "via_administracion_importada"))
        if imported_via:
            vias = [imported_via]

    if not principios:
        imported_principio = _non_empty(_row_get(row, "principio_activo_importado"))
        if imported_principio:
            principios = [{"id": None, "slug": imported_principio.lower().replace(" ", "-"), "nombre": imported_principio}]

    return {
        "cn": row["cn"],
        "nombre": _non_empty(row["nombre"]) or _non_empty(_row_get(row, "nombre_comercial_importado")),
        "presentacion": _non_empty(row["presentacion"]) or _non_empty(_row_get(row, "presentacion_importada")),
        "forma_farmaceutica": _non_empty(row["forma_farmaceutica"]) or _non_empty(_row_get(row, "forma_farmaceutica_importada")),
        "forma_farmaceutica_simplificada": _row_get(row, "forma_farmaceutica_simplificada") or _row_get(row, "forma_farmaceutica_importada"),
        "vias_administracion": vias,
        "atc": atc,
        "principios_activos": principios,
        "principio_activo_importado": _non_empty(_row_get(row, "principio_activo_importado")),
        "nemonico": _non_empty(row["nemonico"]),
        "restricciones_hospitalarias": row["restricciones_hospitalarias"],
        "ajuste_insuficiencia_renal": _row_get(row, "ajuste_insuficiencia_renal"),
        "ajuste_insuficiencia_hepatica": _row_get(row, "ajuste_insuficiencia_hepatica"),
        "precauciones_embarazo": _row_get(row, "precauciones_embarazo"),
        "precauciones_lactancia": _row_get(row, "precauciones_lactancia"),
        "situacion_financiacion": _row_get(row, "situacion_financiacion"),
        "url_ficha_tecnica": _non_empty(_row_get(row, "url_ficha_tecnica")) or _non_empty(_row_get(row, "url_ficha_tecnica_importada")),
        "url_prospecto": _non_empty(_row_get(row, "url_prospecto")) or _non_empty(_row_get(row, "url_prospecto_importado")),
        "fecha_ficha_tecnica": _row_get(row, "fecha_ficha_tecnica"),
        "fecha_prospecto": _row_get(row, "fecha_prospecto"),
        "indicaciones_ficha_tecnica": _row_get(row, "indicaciones_ficha_tecnica"),
    }


def _row_to_detail(
    row,
    principios: list[dict],
    *,
    summary_row: GftClinicalSummaryCache | None = None,
    bifimed_row: BifimedCache | None = None,
) -> dict:
    item = _row_to_list_item(row, principios)
    item["observaciones_publicables"] = _row_get(row, "observaciones_publicables")
    item["documentos"] = _build_document_links(row)
    if bifimed_row is not None:
        detalle = {
            "situacion_financiacion": bifimed_row.situacion_financiacion,
            "condiciones_financiacion_restringidas": bifimed_row.condiciones_financiacion_restringidas,
            "condiciones_especiales_financiacion": bifimed_row.condiciones_especiales_financiacion,
            "estado_nomenclator": bifimed_row.estado_nomenclator,
            "aportacion_usuario": bifimed_row.aportacion_usuario,
            "subgrupo_atc": bifimed_row.subgrupo_atc,
        }
        if bifimed_row.last_synced_at is not None:
            detalle["last_synced_at"] = bifimed_row.last_synced_at
        detalle["indicaciones_autorizadas"] = bifimed_row.indicaciones_autorizadas_json or []
        item["financiacion_detalle"] = detalle
    else:
        item["financiacion_detalle"] = _build_financiacion_detalle(row)
    item["resumen_clinico_auto"] = _build_clinical_summary_payload(summary_row)
    return item


def list_medicamentos(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
    letra: str | None = None,
    principio_activo: str | None = None,
    atc: str | None = None,
) -> dict:
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0

    rows = db.execute(
        text(
            """
            SELECT *
            FROM v_gft_publicada
            """
        )
    ).mappings().all()

    cns = [row["cn"] for row in rows]
    principios_by_cn = _get_principios_for_cns(db, cns)

    enriched = []
    for row in rows:
        principios = principios_by_cn.get(row["cn"], [])
        enriched.append((principios[0]["nombre"].lower() if principios else "", _row_to_list_item(row, principios)))

    enriched.sort(key=lambda x: (x[0], (x[1].get("nombre") or "").lower(), x[1]["cn"]))
    ordered_items = [item for _, item in enriched]
    q_norm = (q or "").strip().lower()
    letra_norm = (letra or "").strip().lower()[:1]
    principio_raw = (principio_activo or "").strip()
    principio_slug_norm = principio_raw.lower()
    atc_norm = _normalize_atc_code(atc)

    filtered_items = ordered_items
    if q_norm:
        def _matches_q(item: dict) -> bool:
            principles = item.get("principios_activos", [])
            fields = [
                item.get("cn"),
                item.get("nombre"),
                item.get("presentacion"),
                item.get("forma_farmaceutica"),
                item.get("nemonico"),
                item.get("restricciones_hospitalarias"),
                _non_empty(_row_get(item, "principio_activo_importado")),
                *[p.get("nombre") for p in principles if isinstance(p, Mapping)],
            ]
            haystack = " ".join(str(value).lower() for value in fields if value)
            return q_norm in haystack

        filtered_items = [item for item in filtered_items if _matches_q(item)]

    if letra_norm:
        filtered_items = [
            item
            for item in filtered_items
            if item.get("principios_activos")
            and str(item["principios_activos"][0].get("nombre") or "").strip().lower().startswith(letra_norm)
        ]

    if principio_raw:
        filtered_items = [
            item
            for item in filtered_items
            if any(
                str(principio.get("id")) == principio_raw
                or str(principio.get("slug") or "").lower() == principio_slug_norm
                for principio in item.get("principios_activos", [])
                if isinstance(principio, Mapping)
            )
        ]

    if atc_norm:
        filtered_items = [
            item
            for item in filtered_items
            if any(
                _normalize_atc_code(str(atc_item.get("codigo") or "")).startswith(atc_norm)
                for atc_item in item.get("atc", [])
                if isinstance(atc_item, Mapping)
            )
        ]

    total = len(filtered_items)
    items = filtered_items[offset : offset + limit]

    return {"total": int(total), "limit": limit, "offset": offset, "items": items}


def _usable_principio_name(row) -> str | None:
    nombre = str(row.nombre_display or "").strip()
    if nombre:
        return nombre

    nombre = str(row.nombre_normalizado or "").strip()
    if nombre:
        return nombre

    return None


def list_principios_activos_index(db: Session) -> dict:
    rows = db.execute(text("SELECT cn FROM v_gft_publicada")).mappings().all()
    cns = [str(row["cn"] or "").strip() for row in rows if str(row["cn"] or "").strip()]
    if not cns:
        return {"items": []}

    rows = (
        db.query(
            MedicamentoPrincipioActivo.cn,
            PrincipioActivo.id,
            PrincipioActivo.slug,
            PrincipioActivo.nombre_display,
            PrincipioActivo.nombre_normalizado,
        )
        .join(PrincipioActivo, PrincipioActivo.id == MedicamentoPrincipioActivo.principio_activo_id)
        .filter(MedicamentoPrincipioActivo.cn.in_(cns))
        .all()
    )

    index: dict[str, dict] = {}
    for row in rows:
        slug = str(row.slug or "").strip()
        if not slug:
            continue

        nombre = _usable_principio_name(row)
        if nombre is None:
            continue

        key = str(row.id)
        entry = index.setdefault(
            key,
            {
                "id": row.id,
                "slug": slug,
                "nombre": nombre,
                "sort_name": str(row.nombre_normalizado or nombre).strip().casefold(),
                "cns": set(),
            },
        )
        entry["cns"].add(str(row.cn or "").strip())

    items = []
    for entry in sorted(index.values(), key=lambda item: (item["sort_name"], item["slug"])):
        nombre = entry["nombre"]
        items.append(
            {
                "id": entry["id"],
                "slug": entry["slug"],
                "nombre": nombre,
                "letra": nombre[0].upper(),
                "count": len(entry["cns"]),
            }
        )

    return {"items": items}


def list_atc_index(db: Session) -> dict:
    rows = db.execute(
        text(
            """
            SELECT cn, atc_json, codigo_atc_importado, descripcion_atc_importada
            FROM v_gft_publicada
            """
        )
    ).mappings().all()

    index: dict[str, dict] = {}
    for row in rows:
        cn = str(row["cn"] or "").strip()
        if not cn:
            continue

        seen_for_cn: set[str] = set()
        for atc_item in _extract_atc_items_from_row(row):
            raw_code = _normalize_atc_code(str(atc_item.get("codigo") or ""))
            if not raw_code:
                continue

            exact_name = atc_item.get("nombre")
            exact_name = str(exact_name).strip() if exact_name is not None else None
            if exact_name == "":
                exact_name = None

            for codigo, nivel in _expand_atc_code(raw_code):
                if codigo in seen_for_cn:
                    continue
                seen_for_cn.add(codigo)
                nombre = exact_name if codigo == raw_code else None
                _merge_atc_index_entry(index, codigo, nivel, cn, nombre=nombre)

    items = []
    for codigo in sorted(index):
        entry = index[codigo]
        items.append(
            {
                "codigo": entry["codigo"],
                "nombre": entry["nombre"],
                "nivel": entry["nivel"],
                "count": len(entry["cns"]),
            }
        )

    return {"items": items}


def get_medicamento_by_cn(db: Session, cn: str) -> dict | None:
    cn_norm = normalize_cn(cn)

    row = db.execute(
        text("SELECT * FROM v_gft_publicada WHERE cn = :cn LIMIT 1"),
        {"cn": cn_norm},
    ).mappings().first()

    if row is None:
        return None

    principios = _get_principios_for_cns(db, [cn_norm]).get(cn_norm, [])
    summary_row = db.get(GftClinicalSummaryCache, cn_norm)
    bifimed_row = db.get(BifimedCache, cn_norm)
    return _row_to_detail(row, principios, summary_row=summary_row, bifimed_row=bifimed_row)
