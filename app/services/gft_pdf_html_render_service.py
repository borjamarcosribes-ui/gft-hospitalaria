from html import escape

from app.services.gft_pdf_export_service import EXPORT_TITLE, GFTPDFATCGroup, GFTPDFExportData, GFTPDFMedication

_SUBTITLE_COMPACT = "Exportación compacta de medicamentos publicados"
_SUBTITLE_FULL = "Exportación completa de medicamentos publicados"


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _format_generation_date(export_data: GFTPDFExportData) -> str:
    return export_data.generated_at.astimezone().strftime("%d/%m/%Y %H:%M UTC")


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


def render_gft_pdf_html(export_data: GFTPDFExportData, mode: str = "compact") -> str:
    if mode not in {"compact", "full"}:
        raise ValueError("Invalid mode. Allowed values: compact, full.")

    subtitle = _SUBTITLE_COMPACT if mode == "compact" else _SUBTITLE_FULL
    sections: list[str] = []
    for group, depth in _iter_groups(export_data.groups):
        heading = "h2" if depth == 0 else "h3"
        lines = [
            "<section>",
            f"<{heading}>{_e(group.codigo)} · {_e(group.nombre)} ({_e(group.count)})</{heading}>",
        ]
        if mode == "compact":
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
                lines.append(f"<article><h4>{_e(med.nombre_comercial)} ({_e(med.cn)})</h4>")
                lines.append(
                    "<p>"
                    f"Principio activo: {_e(med.principio_activo)} · Forma: {_e(med.forma_farmaceutica)} · Vía: {_e(med.via_administracion)} · "
                    f"ATC: {_e(med.codigo_atc)} · Financiación: {_e(med.situacion_financiacion_bifimed)}"
                    "</p>"
                )
                lines.append(
                    f"<p>Indicaciones: {_e(med.indicaciones_ficha_tecnica)} · Restricciones: {_e(med.restricciones_hospitalarias)} · "
                    f"Renal: {_e(med.ajuste_insuficiencia_renal)} · Hepática: {_e(med.ajuste_insuficiencia_hepatica)} · "
                    f"Embarazo: {_e(med.precauciones_embarazo)} · Lactancia: {_e(med.precauciones_lactancia)} · "
                    f"Observaciones: {_e(med.observaciones_publicables)}</p>"
                )
                lines.append("</article>")
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
</style></head><body>
<h1>{_e(export_data.title)}</h1>
<p>{_e(subtitle)}</p>
<p><strong>Fecha de generación:</strong> {_e(_format_generation_date(export_data))}</p>
<p><strong>Total de medicamentos publicados:</strong> {_e(export_data.total_medicamentos)}</p>
{body_html}
</body></html>"""
