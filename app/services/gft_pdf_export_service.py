from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_query_service import _build_clinical_summary_payload
from app.services.gft_query_service import (
    _extract_atc_items_from_row,
    _get_principios_for_cns,
    _infer_atc_level,
    _normalize_atc_code,
    _parse_vias,
    _row_get,
)

NO_INFORMADO = "No informado"
EXPORT_TITLE = "Guía Farmacoterapéutica Hospitalaria"


@dataclass
class GFTPDFMedication:
    nombre_comercial: str
    principio_activo: str
    forma_farmaceutica: str
    via_administracion: str
    nemonico: str
    cn: str
    codigo_atc: str
    descripcion_atc: str
    situacion_financiacion_bifimed: str
    url_ficha_tecnica: str
    url_prospecto: str
    indicaciones_ficha_tecnica: str = ""
    ajuste_insuficiencia_renal: str = ""
    ajuste_insuficiencia_hepatica: str = ""
    precauciones_embarazo: str = ""
    precauciones_lactancia: str = ""
    restricciones_hospitalarias: str = ""
    observaciones_publicables: str = ""
    resumen_clinico_auto: dict[str, Any] | None = None


@dataclass
class GFTPDFATCGroup:
    codigo: str
    nombre: str
    nivel: str
    count: int = 0
    children: list["GFTPDFATCGroup"] = field(default_factory=list)
    medicamentos: list[GFTPDFMedication] = field(default_factory=list)


@dataclass
class GFTPDFExportData:
    generated_at: datetime
    title: str
    total_medicamentos: int
    groups: list[GFTPDFATCGroup] = field(default_factory=list)


def _public_text(value: Any) -> str:
    if value is None:
        return NO_INFORMADO
    text_value = str(value).strip()
    return text_value if text_value else NO_INFORMADO


def _join_public_text(values: list[str]) -> str:
    clean_values = [value.strip() for value in values if value and value.strip()]
    return ", ".join(clean_values) if clean_values else NO_INFORMADO


def _atc_sort_code(code: str | None) -> str:
    value = (code or "").strip().upper()
    return value if value and value != NO_INFORMADO.upper() else "ZZZ"


def _primary_atc(atc_items: list[dict]) -> dict[str, str | None]:
    if not atc_items:
        return {"codigo": None, "nombre": None, "nivel": None}
    return atc_items[0]


def _atc_name_by_code(atc_items: list[dict]) -> dict[str, str]:
    names: dict[str, str] = {}
    for item in atc_items:
        code = _normalize_atc_code(str(item.get("codigo") or ""))
        name = str(item.get("nombre") or "").strip()
        if code and name:
            names.setdefault(code, name)
    return names


def _atc_hierarchy_from_code(
    code: str | None, atc_items: list[dict]
) -> list[dict[str, str]]:
    normalized_code = _normalize_atc_code(code)
    if not normalized_code:
        return [{"codigo": NO_INFORMADO, "nombre": NO_INFORMADO, "nivel": "L1"}]

    names = _atc_name_by_code(atc_items)
    hierarchy: list[dict[str, str]] = []
    for length in (1, 3, 4, 5, 7):
        if len(normalized_code) < length:
            continue
        prefix = normalized_code[:length]
        level = _infer_atc_level(prefix)
        if level is None:
            continue
        hierarchy.append(
            {
                "codigo": prefix,
                "nombre": names.get(prefix, NO_INFORMADO),
                "nivel": level,
            }
        )

    if not hierarchy:
        return [
            {
                "codigo": normalized_code,
                "nombre": names.get(normalized_code, NO_INFORMADO),
                "nivel": "L1",
            }
        ]

    most_specific = hierarchy[-1]
    if (
        most_specific["codigo"] == normalized_code
        and most_specific["nombre"] == NO_INFORMADO
    ):
        full_name = (
            names.get(normalized_code)
            or str(_primary_atc(atc_items).get("nombre") or "").strip()
        )
        if full_name:
            most_specific["nombre"] = full_name
    return hierarchy


def _row_to_medication(
    row,
    principios: list[dict],
    mode: str,
    resumen_clinico_auto: dict[str, Any] | None = None,
) -> tuple[GFTPDFMedication, list[dict[str, str]]]:
    atc_items = _extract_atc_items_from_row(row)
    primary_atc = _primary_atc(atc_items)
    primary_atc_code = _normalize_atc_code(str(primary_atc.get("codigo") or ""))
    atc_hierarchy = _atc_hierarchy_from_code(primary_atc_code, atc_items)

    principio_activo = _join_public_text(
        [
            str(principio.get("nombre") or "")
            for principio in principios
            if isinstance(principio, dict)
        ]
    )
    if principio_activo == NO_INFORMADO:
        principio_activo = _public_text(_row_get(row, "principio_activo_importado"))

    via_administracion = _join_public_text(
        _parse_vias(_row_get(row, "vias_administracion_json"))
    )
    if via_administracion == NO_INFORMADO:
        via_administracion = _public_text(_row_get(row, "via_administracion_importada"))

    include_long_fields = mode in {"full", "narrative"}
    medication = GFTPDFMedication(
        nombre_comercial=_public_text(
            _row_get(row, "nombre") or _row_get(row, "nombre_comercial_importado")
        ),
        principio_activo=principio_activo,
        forma_farmaceutica=_public_text(
            _row_get(row, "forma_farmaceutica")
            or _row_get(row, "forma_farmaceutica_importada")
        ),
        via_administracion=via_administracion,
        nemonico=_public_text(_row_get(row, "nemonico")),
        cn=_public_text(_row_get(row, "cn")),
        codigo_atc=_public_text(primary_atc_code),
        descripcion_atc=_public_text(
            primary_atc.get("nombre") or _row_get(row, "descripcion_atc_importada")
        ),
        indicaciones_ficha_tecnica=(
            _public_text(_row_get(row, "indicaciones_ficha_tecnica"))
            if include_long_fields
            else ""
        ),
        ajuste_insuficiencia_renal=(
            _public_text(_row_get(row, "ajuste_insuficiencia_renal"))
            if include_long_fields
            else ""
        ),
        ajuste_insuficiencia_hepatica=(
            _public_text(_row_get(row, "ajuste_insuficiencia_hepatica"))
            if include_long_fields
            else ""
        ),
        precauciones_embarazo=(
            _public_text(_row_get(row, "precauciones_embarazo"))
            if include_long_fields
            else ""
        ),
        precauciones_lactancia=(
            _public_text(_row_get(row, "precauciones_lactancia"))
            if include_long_fields
            else ""
        ),
        restricciones_hospitalarias=(
            _public_text(_row_get(row, "restricciones_hospitalarias"))
            if include_long_fields
            else ""
        ),
        observaciones_publicables=(
            _public_text(_row_get(row, "observaciones_publicables"))
            if include_long_fields
            else ""
        ),
        resumen_clinico_auto=resumen_clinico_auto,
        situacion_financiacion_bifimed=_public_text(
            _row_get(row, "situacion_financiacion")
        ),
        url_ficha_tecnica=_public_text(
            _row_get(row, "url_ficha_tecnica")
            or _row_get(row, "url_ficha_tecnica_importada")
        ),
        url_prospecto=_public_text(
            _row_get(row, "url_prospecto") or _row_get(row, "url_prospecto_importado")
        ),
    )
    return medication, atc_hierarchy


def _medication_sort_key(item: tuple[GFTPDFMedication, list[dict[str, str]]]):
    medication, hierarchy = item
    hierarchy_codes = tuple(_atc_sort_code(level["codigo"]) for level in hierarchy)
    return (
        hierarchy_codes,
        _atc_sort_code(medication.codigo_atc),
        medication.principio_activo.casefold(),
        medication.nombre_comercial.casefold(),
        medication.cn.casefold(),
    )


def _find_or_create_child(
    parent: GFTPDFATCGroup, group_data: dict[str, str]
) -> GFTPDFATCGroup:
    child = next(
        (
            candidate
            for candidate in parent.children
            if candidate.codigo == group_data["codigo"]
        ),
        None,
    )
    if child is not None:
        return child
    child = GFTPDFATCGroup(
        codigo=group_data["codigo"],
        nombre=group_data["nombre"],
        nivel=group_data["nivel"],
    )
    parent.children.append(child)
    return child


def _append_to_groups(
    groups_by_code: dict[str, GFTPDFATCGroup],
    medication: GFTPDFMedication,
    hierarchy: list[dict[str, str]],
) -> None:
    l1_data = (
        hierarchy[0]
        if hierarchy
        else {"codigo": NO_INFORMADO, "nombre": NO_INFORMADO, "nivel": "L1"}
    )
    current_group = groups_by_code.setdefault(
        l1_data["codigo"],
        GFTPDFATCGroup(
            codigo=l1_data["codigo"], nombre=l1_data["nombre"], nivel=l1_data["nivel"]
        ),
    )

    for group_data in hierarchy[1:]:
        current_group = _find_or_create_child(current_group, group_data)
    current_group.medicamentos.append(medication)


def _finalize_counts(group: GFTPDFATCGroup) -> int:
    child_count = sum(_finalize_counts(child) for child in group.children)
    group.count = len(group.medicamentos) + child_count
    group.children.sort(key=lambda child: _atc_sort_code(child.codigo))
    return group.count


def build_gft_pdf_export_data(db: Session, mode: str = "narrative") -> GFTPDFExportData:
    normalized_mode = "table" if mode == "compact" else mode
    if normalized_mode not in {"narrative", "table", "full"}:
        raise ValueError(
            "Invalid mode. Allowed values: narrative, table, full, compact."
        )
    rows = db.execute(text("SELECT * FROM v_gft_publicada")).mappings().all()
    cns = [str(row["cn"] or "").strip() for row in rows if str(row["cn"] or "").strip()]
    principios_by_cn = _get_principios_for_cns(db, cns)
    summaries_by_cn = {
        row.cn: _build_clinical_summary_payload(row)
        for row in db.query(GftClinicalSummaryCache)
        .filter(GftClinicalSummaryCache.cn.in_(cns))
        .all()
    }

    export_rows = []
    for row in rows:
        cn = str(row["cn"] or "").strip()
        export_rows.append(
            _row_to_medication(
                row,
                principios_by_cn.get(cn, []),
                mode=normalized_mode,
                resumen_clinico_auto=summaries_by_cn.get(cn),
            )
        )

    export_rows.sort(key=_medication_sort_key)

    groups_by_code: dict[str, GFTPDFATCGroup] = {}
    for medication, hierarchy in export_rows:
        _append_to_groups(groups_by_code, medication, hierarchy)

    groups = sorted(
        groups_by_code.values(), key=lambda group: _atc_sort_code(group.codigo)
    )
    for group in groups:
        _finalize_counts(group)

    total_medicamentos = len(export_rows)
    return GFTPDFExportData(
        generated_at=datetime.now(timezone.utc),
        title=EXPORT_TITLE,
        total_medicamentos=total_medicamentos,
        groups=groups,
    )
