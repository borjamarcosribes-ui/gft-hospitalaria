from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_query_service import _build_clinical_summary_payload
from app.services.gft_query_service import _get_principios_for_cns, _parse_atc, _parse_vias, _row_get

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
    indicaciones_bifimed: Any = field(default_factory=list)


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


def _atc_group_data(atc_items: list[dict]) -> tuple[dict[str, str], dict[str, str] | None]:
    primary = _primary_atc(atc_items)
    raw_code = str(primary.get("codigo") or "").strip().upper()
    raw_name = primary.get("nombre")
    name = str(raw_name).strip() if raw_name is not None else ""

    if not raw_code:
        return {"codigo": NO_INFORMADO, "nombre": NO_INFORMADO, "nivel": "L1"}, None

    l1 = {"codigo": raw_code[:1], "nombre": name if len(raw_code) == 1 and name else NO_INFORMADO, "nivel": "L1"}
    if len(raw_code) >= 3:
        l2 = {"codigo": raw_code[:3], "nombre": name if len(raw_code) == 3 and name else NO_INFORMADO, "nivel": "L2"}
        return l1, l2
    return l1, None


def _row_to_medication(
    row,
    principios: list[dict],
    mode: str,
    resumen_clinico_auto: dict[str, Any] | None = None,
    indicaciones_bifimed: Any = None,
) -> tuple[GFTPDFMedication, dict[str, str], dict[str, str] | None]:
    atc_items = _parse_atc(row["atc_json"])
    primary_atc = _primary_atc(atc_items)
    l1_data, l2_data = _atc_group_data(atc_items)

    principio_activo = _join_public_text(
        [str(principio.get("nombre") or "") for principio in principios if isinstance(principio, dict)]
    )
    via_administracion = _join_public_text(_parse_vias(row["vias_administracion_json"]))

    include_long_fields = mode in {"full", "narrative"}
    medication = GFTPDFMedication(
        nombre_comercial=_public_text(row["nombre"]),
        principio_activo=principio_activo,
        forma_farmaceutica=_public_text(row["forma_farmaceutica"]),
        via_administracion=via_administracion,
        nemonico=_public_text(row["nemonico"]),
        cn=_public_text(row["cn"]),
        codigo_atc=_public_text(primary_atc.get("codigo")),
        descripcion_atc=_public_text(primary_atc.get("nombre")),
        indicaciones_ficha_tecnica=_public_text(_row_get(row, "indicaciones_ficha_tecnica")) if include_long_fields else "",
        ajuste_insuficiencia_renal=_public_text(_row_get(row, "ajuste_insuficiencia_renal")) if include_long_fields else "",
        ajuste_insuficiencia_hepatica=_public_text(_row_get(row, "ajuste_insuficiencia_hepatica")) if include_long_fields else "",
        precauciones_embarazo=_public_text(_row_get(row, "precauciones_embarazo")) if include_long_fields else "",
        precauciones_lactancia=_public_text(_row_get(row, "precauciones_lactancia")) if include_long_fields else "",
        restricciones_hospitalarias=_public_text(row["restricciones_hospitalarias"]) if include_long_fields else "",
        observaciones_publicables=_public_text(_row_get(row, "observaciones_publicables")) if include_long_fields else "",
        resumen_clinico_auto=resumen_clinico_auto,
        indicaciones_bifimed=indicaciones_bifimed or [],
        situacion_financiacion_bifimed=_public_text(_row_get(row, "situacion_financiacion")),
        url_ficha_tecnica=_public_text(row["url_ficha_tecnica"]),
        url_prospecto=_public_text(row["url_prospecto"]),
    )
    return medication, l1_data, l2_data


def _medication_sort_key(item: tuple[GFTPDFMedication, dict[str, str], dict[str, str] | None]):
    medication, l1_data, l2_data = item
    return (
        _atc_sort_code(l1_data["codigo"]),
        _atc_sort_code(medication.codigo_atc),
        _atc_sort_code(l2_data["codigo"] if l2_data is not None else ""),
        medication.principio_activo.casefold(),
        medication.nombre_comercial.casefold(),
        medication.cn.casefold(),
    )


def _append_to_groups(
    groups_by_code: dict[str, GFTPDFATCGroup],
    medication: GFTPDFMedication,
    l1_data: dict[str, str],
    l2_data: dict[str, str] | None,
) -> None:
    l1_group = groups_by_code.setdefault(
        l1_data["codigo"],
        GFTPDFATCGroup(codigo=l1_data["codigo"], nombre=l1_data["nombre"], nivel=l1_data["nivel"]),
    )

    if l2_data is None:
        l1_group.medicamentos.append(medication)
        return

    l2_group = next((child for child in l1_group.children if child.codigo == l2_data["codigo"]), None)
    if l2_group is None:
        l2_group = GFTPDFATCGroup(codigo=l2_data["codigo"], nombre=l2_data["nombre"], nivel=l2_data["nivel"])
        l1_group.children.append(l2_group)
    l2_group.medicamentos.append(medication)


def _finalize_counts(group: GFTPDFATCGroup) -> int:
    child_count = sum(_finalize_counts(child) for child in group.children)
    group.count = len(group.medicamentos) + child_count
    group.children.sort(key=lambda child: _atc_sort_code(child.codigo))
    return group.count


def build_gft_pdf_export_data(db: Session, mode: str = "narrative") -> GFTPDFExportData:
    normalized_mode = "table" if mode == "compact" else mode
    if normalized_mode not in {"narrative", "table", "full"}:
        raise ValueError("Invalid mode. Allowed values: narrative, table, full, compact.")
    rows = db.execute(text("SELECT * FROM v_gft_publicada")).mappings().all()
    cns = [str(row["cn"] or "").strip() for row in rows if str(row["cn"] or "").strip()]
    principios_by_cn = _get_principios_for_cns(db, cns)
    summaries_by_cn = {
        row.cn: _build_clinical_summary_payload(row)
        for row in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(cns)).all()
    }
    bifimed_indicaciones_by_cn = {
        row.cn: row.indicaciones_autorizadas_json or []
        for row in db.query(BifimedCache).filter(BifimedCache.cn.in_(cns)).all()
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
                indicaciones_bifimed=bifimed_indicaciones_by_cn.get(cn, []),
            )
        )

    export_rows.sort(key=_medication_sort_key)

    groups_by_code: dict[str, GFTPDFATCGroup] = {}
    for medication, l1_data, l2_data in export_rows:
        _append_to_groups(groups_by_code, medication, l1_data, l2_data)

    groups = sorted(groups_by_code.values(), key=lambda group: _atc_sort_code(group.codigo))
    for group in groups:
        _finalize_counts(group)

    total_medicamentos = len(export_rows)
    return GFTPDFExportData(
        generated_at=datetime.now(timezone.utc),
        title=EXPORT_TITLE,
        total_medicamentos=total_medicamentos,
        groups=groups,
    )
