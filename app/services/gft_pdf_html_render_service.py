from html import escape
from datetime import timezone

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


def _truncate(value: str, max_chars: int) -> str:
    v = value.strip()
    if len(v) <= max_chars:
        return v
    cut = v[: max_chars - 1].rsplit(". ", 1)[0].strip()
    return (cut if cut else v[: max_chars - 1].rstrip()) + "…"


def _has_informed_value(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() != "no informado"


def _optional_sentence(label: str, value: object, *, max_chars: int | None = None) -> str:
    if not _has_informed_value(value):
        return ""
    text = str(value).strip()
    if max_chars is not None:
        text = _truncate(text, max_chars)
    return f"{label}: {_e(text)}. "


def _normalize_bifimed_financiacion(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "No informado"
    if "no" in text and "financi" in text:
        return "No financiada"
    if "financi" in text:
        return "Financiada"
    return "No informado"


def _render_narrative_field(label: str, value: object, *, max_chars: int | None = None) -> str:
    if not _has_informed_value(value):
        return ""
    text = str(value).strip()
    if max_chars is not None:
        text = _truncate(text, max_chars)
    return f'<div class="med-field"><span class="label">{_e(label)}:</span> <span class="value">{_e(text)}</span></div>'


def _render_bifimed_indicaciones(med: GFTPDFMedication) -> str:
    if not med.indicaciones_bifimed:
        return ""
    items: list[str] = []
    for item in med.indicaciones_bifimed:
        if not isinstance(item, dict):
            continue
        texto = str(item.get("indicacion") or item.get("descripcion") or "").strip()
        if not texto:
            continue
        financiacion = _normalize_bifimed_financiacion(item.get("situacion_financiacion"))
        situacion = str(item.get("situacion") or item.get("resolucion") or "").strip()
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
                indicaciones = summary.get("indicaciones") or med.indicaciones_ficha_tecnica or "No informado"
                renal = summary.get("ajuste_renal") or med.ajuste_insuficiencia_renal or _AUTO_NOT_FOUND
                hepatica = summary.get("ajuste_hepatico") or med.ajuste_insuficiencia_hepatica or _AUTO_NOT_FOUND
                embarazo = summary.get("embarazo") or med.precauciones_embarazo or _AUTO_NOT_FOUND
                lactancia = summary.get("lactancia") or med.precauciones_lactancia or _AUTO_NOT_FOUND
                restricciones = med.restricciones_hospitalarias or "No informado"
                observaciones = (
                    _render_narrative_field("Observaciones", med.observaciones_publicables, max_chars=400)
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
                    f"{_render_narrative_field('Indicaciones ficha técnica/CIMA', indicaciones, max_chars=700)}"
                    f"{_render_bifimed_indicaciones(med)}"
                    f"{_render_narrative_field('Ajuste por insuficiencia renal', renal, max_chars=400)}"
                    f"{_render_narrative_field('Ajuste por insuficiencia hepática', hepatica, max_chars=400)}"
                    f"{_render_narrative_field('Embarazo', embarazo, max_chars=400)}"
                    f"{_render_narrative_field('Lactancia', lactancia, max_chars=400)}"
                    f"{_render_narrative_field('Restricciones hospitalarias', restricciones, max_chars=400)}"
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
.med-card {{ border: 1px solid #d7e1ea; border-radius: 6px; padding: 6px 8px; margin: 0.35rem 0; break-inside: avoid; page-break-inside: avoid; background: #fff; }}
.med-title {{ font-weight: 700; font-size: 11px; color: #0b395f; margin-bottom: 4px; }}
.med-field {{ margin: 2px 0; line-height: 1.35; }}
.med-field .label {{ font-weight: 600; color: #1f4f78; }}
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
