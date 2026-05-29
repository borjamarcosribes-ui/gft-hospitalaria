from datetime import timezone
from html import escape

from app.services.gft_pdf_export_service import EXPORT_TITLE, GFTPDFATCGroup, GFTPDFExportData, GFTPDFMedication

_SUBTITLE_TABLE = "Exportación técnica tabular de medicamentos publicados"
_SUBTITLE_NARRATIVE = "Guía narrativa de medicamentos publicados ordenada por ATC"
_SUBTITLE_FULL = "Exportación completa de medicamentos publicados"
_AUTO_NOT_FOUND = "No localizado automáticamente"


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _format_generation_date(export_data: GFTPDFExportData) -> str:
    return export_data.generated_at.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def _iter_groups(groups: list[GFTPDFATCGroup]):
    for group in groups:
        yield group, 0
        for child in group.children:
            yield child, 1


def _render_compact_row(medication: GFTPDFMedication) -> str:
    def show(value: str) -> str:
        return _e(value) if value and value.strip() and value.strip().lower() != "no informado" else ""

    return (
        "<tr>"
        f"<td>{show(medication.cn)}</td>"
        f"<td>{show(medication.nombre_comercial)}</td>"
        f"<td>{show(medication.principio_activo)}</td>"
        f"<td>{show(medication.forma_farmaceutica)}</td>"
        f"<td>{show(medication.via_administracion)}</td>"
        f"<td>{show(medication.codigo_atc)}</td>"
        f"<td>{show(medication.situacion_financiacion_bifimed)}</td>"
        f"<td>{show(medication.url_ficha_tecnica)}</td>"
        f"<td>{show(medication.url_prospecto)}</td>"
        "</tr>"
    )


def _has_informed_value(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() != "no informado"


def _first_informed_value(*values: object, default: str = "") -> object:
    for value in values:
        if _has_informed_value(value):
            return value
    return default


def _normalize_bifimed_financiacion(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "No informado"
    if "no" in text and "financi" in text:
        return "No financiada"
    if "financi" in text:
        return "Financiada"
    if text in {"sí", "si", "true", "1"}:
        return "Financiada"
    if text in {"false", "0"}:
        return "No financiada"
    return "No informado"


def _iter_bifimed_indicaciones(raw_indicaciones: object):
    if raw_indicaciones is None:
        return
    if isinstance(raw_indicaciones, str):
        yield raw_indicaciones
        return
    if isinstance(raw_indicaciones, list):
        for item in raw_indicaciones:
            yield item
        return
    if isinstance(raw_indicaciones, dict):
        for key in (
            "indicaciones_autorizadas",
            "indicaciones_aprobadas",
            "indicaciones",
            "items",
            "resultados",
            "data",
        ):
            value = raw_indicaciones.get(key)
            if isinstance(value, list):
                for item in value:
                    yield item
                return
        yield raw_indicaciones


def _bifimed_item_text(item: dict) -> str:
    for key in ("indicacion_autorizada", "indicacion", "descripcion", "texto", "indicacion_texto"):
        value = item.get(key)
        if _has_informed_value(value):
            return str(value).strip()
    return ""


def _render_narrative_field(label: str, value: object) -> str:
    if not _has_informed_value(value):
        return ""
    text = str(value).strip()
    return f'<div class="med-field"><span class="label">{_e(label)}:</span> <span class="value">{_e(text)}</span></div>'


def _render_bifimed_indicaciones(med: GFTPDFMedication) -> str:
    items: list[str] = []
    for item in _iter_bifimed_indicaciones(med.indicaciones_bifimed):
        if isinstance(item, str):
            texto = item.strip()
            financiacion = "No informado"
            situacion = ""
        elif isinstance(item, dict):
            texto = _bifimed_item_text(item)
            financiacion = _normalize_bifimed_financiacion(
                _first_informed_value(
                    item.get("situacion_financiacion"),
                    item.get("financiacion"),
                    item.get("financiada"),
                )
            )
            situacion = str(
                _first_informed_value(
                    item.get("situacion"),
                    item.get("resolucion"),
                    item.get("situacion_resolucion"),
                    item.get("estado"),
                )
            ).strip()
        else:
            continue
        if not texto:
            continue
        meta = [f"Financiación: {financiacion}"]
        if situacion:
            meta.append(f"Situación: {situacion}")
        items.append(
            '<li class="bifimed-item">'
            f'<div class="bifimed-text">{_e(texto)}</div>'
            f'<div class="bifimed-meta">{" · ".join(_e(m) for m in meta)}</div>'
            "</li>"
        )
    if not items:
        return ""
    return (
        '<div class="med-field med-field-block">'
        '<span class="label">Indicaciones BIFIMED:</span>'
        f'<ul class="bifimed-list">{"".join(items)}</ul>'
        "</div>"
    )


def render_gft_pdf_html(export_data: GFTPDFExportData, mode: str = "narrative") -> str:
    mode = "table" if mode == "compact" else mode
    if mode not in {"narrative", "table", "full"}:
        raise ValueError("Invalid mode. Allowed values: narrative, table, full, compact.")

    subtitle = _SUBTITLE_TABLE if mode == "table" else (_SUBTITLE_FULL if mode == "full" else _SUBTITLE_NARRATIVE)
    sections: list[str] = []
    for group, depth in _iter_groups(export_data.groups):
        heading = "h2" if depth == 0 else "h3"
        lines = [
            "<section>",
            f"<{heading}>{_e(group.codigo)} · {_e(group.nombre)} ({_e(group.count)})</{heading}>",
        ]
        if mode == "table":
            if group.medicamentos:
                lines.extend(
                    [
                        '<table><thead><tr><th>CN</th><th>Nombre comercial</th><th>Principio activo</th>'
                        "<th>Forma farmacéutica</th><th>Vía administración</th><th>Código ATC</th>"
                        "<th>Financiación BIFIMED</th><th>URL ficha técnica</th><th>URL prospecto</th></tr></thead><tbody>",
                        *[_render_compact_row(m) for m in group.medicamentos],
                        "</tbody></table>",
                    ]
                )
        else:
            for med in group.medicamentos:
                summary = med.resumen_clinico_auto or {}
                indicaciones = _first_informed_value(
                    med.indicaciones_ficha_tecnica, summary.get("indicaciones"), default="No informado"
                )
                renal = _first_informed_value(
                    med.ajuste_insuficiencia_renal, summary.get("ajuste_renal"), default=_AUTO_NOT_FOUND
                )
                hepatica = _first_informed_value(
                    med.ajuste_insuficiencia_hepatica, summary.get("ajuste_hepatico"), default=_AUTO_NOT_FOUND
                )
                embarazo = _first_informed_value(
                    med.precauciones_embarazo, summary.get("embarazo"), default=_AUTO_NOT_FOUND
                )
                lactancia = _first_informed_value(
                    med.precauciones_lactancia, summary.get("lactancia"), default=_AUTO_NOT_FOUND
                )
                restricciones = med.restricciones_hospitalarias or "No informado"
                observaciones = (
                    _render_narrative_field("Observaciones", med.observaciones_publicables)
                    if mode == "full"
                    else ""
                )
                lines.append(
                    '<article class="med-card">'
                    f'<div class="med-title">{_e(med.nombre_comercial)} — CN {_e(med.cn)}</div>'
                    f"{_render_narrative_field('Principio activo', med.principio_activo)}"
                    f"{_render_narrative_field('Forma farmacéutica', med.forma_farmaceutica)}"
                    f"{_render_narrative_field('Vía', med.via_administracion)}"
                    f"{_render_narrative_field('Nemónico', med.nemonico)}"
                    f"{_render_narrative_field('ATC', med.codigo_atc)}"
                    f"{_render_narrative_field('Financiación BIFIMED', med.situacion_financiacion_bifimed)}"
                    f"{_render_narrative_field('Indicaciones ficha técnica/CIMA', indicaciones)}"
                    f"{_render_bifimed_indicaciones(med)}"
                    f"{_render_narrative_field('Ajuste por insuficiencia renal', renal)}"
                    f"{_render_narrative_field('Ajuste por insuficiencia hepática', hepatica)}"
                    f"{_render_narrative_field('Embarazo', embarazo)}"
                    f"{_render_narrative_field('Lactancia', lactancia)}"
                    f"{_render_narrative_field('Restricciones hospitalarias', restricciones)}"
                    f"{observaciones}"
                    "</article>"
                )
        lines.append("</section>")
        sections.append("\n".join(lines))

    body_html = "\n".join(sections) if sections else "<p>No hay medicamentos publicados.</p>"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{_e(EXPORT_TITLE)}</title>
<style>
@page {{ margin: 10mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #111; }}
h1,h2,h3 {{ margin: 0.25rem 0; color: #0f4c81; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 0.5rem; }}
th,td {{ border: 1px solid #cfd8e3; padding: 2px 3px; vertical-align: top; word-break: break-word; }}
th {{ background: #eef3f8; font-size: 9px; }}
p {{ margin: 0.2rem 0; }}
section {{ margin-bottom: 0.4rem; }}
.med-card {{ border-left: 3px solid #d8e7f2; padding: 6px 8px 6px 10px; margin: 0.55rem 0; break-inside: avoid; page-break-inside: avoid; background: #fbfdff; }}
.med-title {{ font-weight: 700; font-size: 12px; color: #0b395f; margin-bottom: 5px; }}
.med-field {{ margin: 2px 0; line-height: 1.35; }}
.med-field .label {{ font-weight: 600; color: #1f4f78; }}
.med-field .value {{ white-space: pre-line; }}
.med-field-block .label {{ display: block; margin-bottom: 2px; }}
.bifimed-list {{ margin: 2px 0 0 14px; padding: 0; }}
.bifimed-item {{ margin-bottom: 3px; }}
.bifimed-text {{ margin-bottom: 1px; }}
.bifimed-meta {{ color: #435466; font-size: 9px; }}
</style></head><body>
<h1>{_e(export_data.title)}</h1>
<p>{_e(subtitle)}</p>
<p><strong>Fecha de generación:</strong> {_e(_format_generation_date(export_data))}</p>
<p><strong>Total de medicamentos publicados:</strong> {_e(export_data.total_medicamentos)}</p>
<p><em>Documento generado desde la misma base de datos que alimenta la GFT web.</em></p>
{body_html}
</body></html>"""
