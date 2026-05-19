from html import escape

from app.services.gft_pdf_export_service import (
    EXPORT_TITLE,
    GFTPDFATCGroup,
    GFTPDFExportData,
    GFTPDFMedication,
)


_SUBTITLE = "Exportación completa de medicamentos publicados"


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _export_groups(export_data: GFTPDFExportData) -> list[GFTPDFATCGroup]:
    return getattr(export_data, "atc_groups", export_data.groups)


def _group_label(group: GFTPDFATCGroup) -> str:
    return f"{group.codigo} · {group.nombre}"


def _render_index_group(group: GFTPDFATCGroup, depth: int = 0) -> list[str]:
    css_class = "index-group index-group-child" if depth else "index-group"
    lines = [
        f'<li class="{css_class}">'
        f'<span class="atc-code">{_e(group.codigo)}</span> '
        f'<span class="atc-name">{_e(group.nombre)}</span> '
        f'<span class="atc-level">{_e(group.nivel)}</span> '
        f'<span class="atc-count">{_e(group.count)} medicamentos</span>'
    ]
    if group.children:
        lines.append('<ul class="index-list index-list-child">')
        for child in group.children:
            lines.extend(_render_index_group(child, depth + 1))
        lines.append("</ul>")
    lines.append("</li>")
    return lines


def _render_medication_field(label: str, value: str) -> str:
    return (
        '<div class="medication-field">'
        f'<dt>{_e(label)}</dt>'
        f'<dd>{_e(value)}</dd>'
        "</div>"
    )


def _render_medication(medication: GFTPDFMedication) -> str:
    fields = [
        ("Principio activo", medication.principio_activo),
        ("Forma farmacéutica", medication.forma_farmaceutica),
        ("Vía de administración", medication.via_administracion),
        ("CN", medication.cn),
        ("Código ATC", medication.codigo_atc),
        ("Descripción ATC", medication.descripcion_atc),
        ("Indicaciones en ficha técnica", medication.indicaciones_ficha_tecnica),
        ("Restricciones hospitalarias", medication.restricciones_hospitalarias),
        ("Ajuste por insuficiencia renal", medication.ajuste_insuficiencia_renal),
        ("Ajuste por insuficiencia hepática", medication.ajuste_insuficiencia_hepatica),
        ("Precauciones en embarazo", medication.precauciones_embarazo),
        ("Precauciones en lactancia", medication.precauciones_lactancia),
        ("Observaciones", medication.observaciones_publicables),
        ("Situación de financiación BIFIMED", medication.situacion_financiacion_bifimed),
        ("URL ficha técnica", medication.url_ficha_tecnica),
        ("URL prospecto", medication.url_prospecto),
    ]
    rendered_fields = "\n".join(_render_medication_field(label, value) for label, value in fields)
    return (
        '<article class="medication-card">\n'
        f'<h3>{_e(medication.nombre_comercial)}</h3>\n'
        '<dl class="medication-grid">\n'
        f"{rendered_fields}\n"
        "</dl>\n"
        "</article>"
    )


def _render_medication_group(group: GFTPDFATCGroup, depth: int = 0) -> list[str]:
    heading_level = "h2" if depth == 0 else "h3"
    section_class = "atc-section" if depth == 0 else "atc-section atc-section-child"
    lines = [
        f'<section class="{section_class}">',
        f'<{heading_level}>{_e(_group_label(group))}</{heading_level}>',
        f'<p class="group-meta">{_e(group.nivel)} · {_e(group.count)} medicamentos publicados</p>',
    ]
    for medication in group.medicamentos:
        lines.append(_render_medication(medication))
    for child in group.children:
        lines.extend(_render_medication_group(child, depth + 1))
    lines.append("</section>")
    return lines


def render_gft_pdf_html(export_data: GFTPDFExportData) -> str:
    groups = _export_groups(export_data)
    index_lines: list[str] = []
    body_lines: list[str] = []
    for group in groups:
        index_lines.extend(_render_index_group(group))
        body_lines.extend(_render_medication_group(group))

    index_html = (
        "\n".join(index_lines) if index_lines else '<li class="empty-state">No hay grupos ATC publicados.</li>'
    )
    body_html = (
        "\n".join(body_lines) if body_lines else '<p class="empty-state">No hay medicamentos publicados.</p>'
    )

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>{_e(EXPORT_TITLE)}</title>
  <style>
    @page {{ margin: 18mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #243447;
      background: #ffffff;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 12px;
      line-height: 1.55;
    }}
    h1, h2, h3 {{ color: #0f4c81; line-height: 1.25; margin: 0 0 0.5rem; }}
    h1 {{ font-size: 30px; }}
    h2 {{ border-bottom: 2px solid #b8d8ea; font-size: 20px; padding-bottom: 0.35rem; }}
    h3 {{ font-size: 15px; }}
    .cover {{
      min-height: 45vh;
      padding: 3rem 2rem;
      background: #edf6fa;
      border: 1px solid #cfe5ef;
      display: flex;
      flex-direction: column;
      justify-content: center;
      page-break-after: always;
    }}
    .subtitle {{ color: #4f6477; font-size: 16px; margin: 0 0 2rem; }}
    .total-box {{
      align-self: flex-start;
      background: #ffffff;
      border-left: 5px solid #2b7fab;
      padding: 1rem 1.25rem;
    }}
    .total-number {{ display: block; color: #0f4c81; font-size: 26px; font-weight: 700; }}
    .document-section {{ margin: 0 0 2rem; page-break-before: always; }}
    .index-list {{ list-style: none; margin: 0; padding: 0; }}
    .index-list-child {{ margin-top: 0.35rem; padding-left: 1rem; }}
    .index-group {{ margin: 0 0 0.55rem; padding: 0.35rem 0; }}
    .index-group-child {{ border-left: 3px solid #d9eaf2; padding-left: 0.75rem; }}
    .atc-code {{ font-weight: 700; color: #0f4c81; }}
    .atc-level, .atc-count {{ color: #5b6b7a; font-size: 11px; margin-left: 0.4rem; }}
    .atc-section {{ margin: 0 0 1.5rem; }}
    .atc-section-child {{ margin-left: 0.25rem; }}
    .group-meta {{ color: #5b6b7a; margin: 0 0 0.75rem; }}
    .medication-card {{
      border: 1px solid #d7e3ea;
      border-left: 5px solid #79aeca;
      border-radius: 4px;
      margin: 0 0 1rem;
      padding: 0.9rem 1rem;
      page-break-inside: avoid;
      break-inside: avoid;
      background: #ffffff;
    }}
    .medication-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem 1rem; margin: 0; }}
    .medication-field {{ page-break-inside: avoid; }}
    dt {{ color: #526273; font-size: 10px; font-weight: 700; text-transform: uppercase; }}
    dd {{ margin: 0.1rem 0 0; white-space: pre-wrap; }}
    .empty-state {{ color: #5b6b7a; font-style: italic; }}
    @media print {{
      body {{ font-size: 11px; }}
      .cover {{ min-height: 60vh; }}
    }}
  </style>
</head>
<body>
  <section class="cover">
    <h1>{_e(export_data.title)}</h1>
    <p class="subtitle">{_e(_SUBTITLE)}</p>
    <div class="total-box">
      <span>Total de medicamentos publicados</span>
      <span class="total-number">{_e(export_data.total_medicamentos)}</span>
    </div>
  </section>
  <main>
    <section class="document-section" aria-labelledby="indice-atc">
      <h2 id="indice-atc">Índice ATC</h2>
      <ul class="index-list">
{index_html}
      </ul>
    </section>
    <section class="document-section" aria-labelledby="cuerpo-medicamentos">
      <h2 id="cuerpo-medicamentos">Cuerpo de medicamentos</h2>
{body_html}
    </section>
  </main>
</body>
</html>"""
