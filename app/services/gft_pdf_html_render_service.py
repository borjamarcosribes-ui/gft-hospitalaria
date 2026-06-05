from datetime import timezone
from html import escape

from app.services.gft_pdf_export_service import (
    EXPORT_TITLE,
    GFTPDFATCGroup,
    GFTPDFExportData,
    GFTPDFMedication,
)

_SUBTITLE_TABLE = "Exportaci\u00f3n t\u00e9cnica tabular de medicamentos publicados"
_SUBTITLE_NARRATIVE = "Gu\u00eda narrativa de medicamentos publicados ordenada por ATC"
_SUBTITLE_FULL = "Exportaci\u00f3n completa de medicamentos publicados"
_AUTO_NOT_FOUND = "No localizado autom\u00e1ticamente"


def _e(value: object) -> str:
    text = str(value).replace("\u00b7", "-").replace("\ufffd", "-")
    return escape(text, quote=True)


def _format_generation_date(export_data: GFTPDFExportData) -> str:
    return export_data.generated_at.astimezone(timezone.utc).strftime(
        "%d/%m/%Y %H:%M UTC"
    )


def _iter_groups(groups: list[GFTPDFATCGroup], depth: int = 0):
    for group in groups:
        yield group, depth
        yield from _iter_groups(group.children, depth + 1)


def _has_informed_value(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() != "no informado"


def _render_doc_availability(medication: GFTPDFMedication) -> str:
    labels = []
    if _has_informed_value(medication.url_ficha_tecnica):
        labels.append("Ficha t\u00e9cnica CIMA disponible")
    if _has_informed_value(medication.url_prospecto):
        labels.append("Prospecto CIMA disponible")
    return "; ".join(labels)


def _render_compact_row(medication: GFTPDFMedication) -> str:
    def show(value: str) -> str:
        return (
            _e(value)
            if value and value.strip() and value.strip().lower() != "no informado"
            else ""
        )

    return (
        "<tr>"
        f"<td>{show(medication.cn)}</td>"
        f"<td>{show(medication.nombre_comercial)}</td>"
        f"<td>{show(medication.principio_activo)}</td>"
        f"<td>{show(medication.forma_farmaceutica)}</td>"
        f"<td>{show(medication.via_administracion)}</td>"
        f"<td>{show(medication.codigo_atc)}</td>"
        f"<td>{show(medication.situacion_financiacion_bifimed)}</td>"
        f"<td>{show(_render_doc_availability(medication))}</td>"
        "</tr>"
    )


def _meta_part(label: str, value: object) -> str:
    if not _has_informed_value(value):
        return ""
    return f"<strong>{_e(label)}:</strong> {_e(str(value).strip())}"


def _render_meta_line(medication: GFTPDFMedication) -> str:
    parts = [
        _meta_part("CN", medication.cn),
        _meta_part("Nem\u00f3nico", medication.nemonico),
        _meta_part("Principio activo", medication.principio_activo),
        _meta_part("ATC", medication.codigo_atc),
        _meta_part("Forma farmac\u00e9utica", medication.forma_farmaceutica),
        _meta_part("V\u00eda", medication.via_administracion),
        _meta_part("Documentaci\u00f3n", _render_doc_availability(medication)),
    ]
    visible_parts = [part for part in parts if part]
    if not visible_parts:
        return ""
    return f'<p class="med-meta">{" - ".join(visible_parts)}</p>'


def _render_field(label: str, value: object) -> str:
    if not _has_informed_value(value):
        return ""
    text = str(value).strip()
    return f'<p class="field"><strong>{_e(label)}:</strong> {_e(text)}</p>'


def _render_required_field(label: str, value: object) -> str:
    text = str(value).strip() if value is not None and str(value).strip() else "No informado"
    if text.lower() == "no informado":
        text = "No informado"
    return f'<p class="field"><strong>{_e(label)}:</strong> {_e(text)}</p>'


def _render_narrative_medication(med: GFTPDFMedication, mode: str) -> str:
    summary = med.resumen_clinico_auto or {}
    indicaciones = (
        med.indicaciones_ficha_tecnica or summary.get("indicaciones") or "No informado"
    )
    renal = (
        summary.get("ajuste_renal") or med.ajuste_insuficiencia_renal or _AUTO_NOT_FOUND
    )
    hepatica = (
        summary.get("ajuste_hepatico")
        or med.ajuste_insuficiencia_hepatica
        or _AUTO_NOT_FOUND
    )
    embarazo = summary.get("embarazo") or med.precauciones_embarazo or _AUTO_NOT_FOUND
    lactancia = (
        summary.get("lactancia") or med.precauciones_lactancia or _AUTO_NOT_FOUND
    )
    restricciones = med.restricciones_hospitalarias or "No informado"

    fields = [
        _render_field("Indicaciones", indicaciones),
        _render_field("Ajuste renal", renal),
        _render_field("Ajuste hep\u00e1tico", hepatica),
        _render_field("Embarazo", embarazo),
        _render_field("Lactancia", lactancia),
        _render_required_field("Restricciones hospitalarias", restricciones),
        _render_field(
            "Financiaci\u00f3n",
            med.situacion_financiacion_bifimed,
        ),
    ]
    if mode == "full":
        fields.append(
            _render_field("Observaciones", med.observaciones_publicables)
        )

    return (
        '<article class="medication">'
        f'<h4 class="med-title">{_e(med.nombre_comercial)}</h4>'
        f"{_render_meta_line(med)}"
        f'{"".join(field for field in fields if field)}'
        "</article>"
    )


def render_gft_pdf_html(export_data: GFTPDFExportData, mode: str = "narrative") -> str:
    mode = "table" if mode == "compact" else mode
    if mode not in {"narrative", "table", "full"}:
        raise ValueError(
            "Invalid mode. Allowed values: narrative, table, full, compact."
        )

    subtitle = (
        _SUBTITLE_TABLE
        if mode == "table"
        else (_SUBTITLE_FULL if mode == "full" else _SUBTITLE_NARRATIVE)
    )

    sections: list[str] = []
    for group, depth in _iter_groups(export_data.groups):
        heading_level = min(2 + depth, 6)
        heading = f"h{heading_level}"
        lines = [
            f'<section class="atc-group atc-depth-{depth}">',
            f"<{heading}>{_e(group.codigo)} - {_e(group.nombre)}</{heading}>",
        ]

        if mode == "table":
            if group.medicamentos:
                lines.extend(
                    [
                        "<table><thead><tr><th>CN</th><th>Nombre comercial</th><th>Principio activo</th>"
                        "<th>Forma farmac\u00e9utica</th><th>V\u00eda administraci\u00f3n</th><th>C\u00f3digo ATC</th>"
                        "<th>Financiaci\u00f3n BIFIMED</th><th>Documentaci\u00f3n</th></tr></thead><tbody>",
                        *[_render_compact_row(m) for m in group.medicamentos],
                        "</tbody></table>",
                    ]
                )
        else:
            lines.extend(
                _render_narrative_medication(med, mode) for med in group.medicamentos
            )

        lines.append("</section>")
        sections.append("\n".join(lines))

    body_html = (
        "\n".join(sections) if sections else "<p>No hay medicamentos publicados.</p>"
    )

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{_e(EXPORT_TITLE)}</title>
<style>
@page {{ margin: 10mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 10.2px; line-height: 1.28; color: #111; }}
h1,h2,h3,h4,h5,h6 {{ margin: 0.28rem 0; color: #0f4c81; }}
h1 {{ font-size: 20px; }}
h2 {{ font-size: 15px; border-bottom: 1px solid #b7c9da; padding-bottom: 2px; margin-top: 0.75rem; }}
h3 {{ font-size: 13px; margin-top: 0.55rem; }}
h4,h5,h6 {{ font-size: 11.4px; margin-top: 0.42rem; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin: 0.35rem 0 0.8rem; }}
th,td {{ border: 1px solid #cfd8e3; padding: 3px 4px; vertical-align: top; word-break: break-word; }}
th {{ background: #eef3f8; font-size: 9px; }}
p {{ margin: 0.16rem 0; }}
section {{ margin-bottom: 0.32rem; }}
.atc-depth-1 {{ margin-left: 0.08rem; }}
.atc-depth-2 {{ margin-left: 0.16rem; }}
.atc-depth-3 {{ margin-left: 0.24rem; }}
.atc-depth-4 {{ margin-left: 0.32rem; }}
.medication {{ border-top: 1px solid #d8e2ec; padding-top: 0.22rem; margin: 0.3rem 0 0.55rem; }}
.med-title {{ font-size: 12.8px; font-weight: 700; color: #082f49; margin: 0 0 0.16rem; }}
.med-meta {{ color: #25364a; margin-bottom: 0.18rem; }}
.field {{ text-align: justify; text-justify: inter-word; }}
.field strong {{ color: #0f4c81; }}
</style></head><body>
<h1>{_e(export_data.title)}</h1>
<p>{_e(subtitle)}</p>
<p><strong>Fecha de generaci\u00f3n:</strong> {_e(_format_generation_date(export_data))}</p>
<p><strong>Total de medicamentos publicados:</strong> {_e(export_data.total_medicamentos)}</p>
<p><em>Documento generado desde la misma base de datos que alimenta la GFT web.</em></p>
{body_html}
</body></html>"""
    return html.replace("?", "-").replace("?", "-")
