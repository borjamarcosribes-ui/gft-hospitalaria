from html import escape
from datetime import timezone

from app.services.gft_pdf_export_service import (
    EXPORT_TITLE,
    GFTPDFATCGroup,
    GFTPDFExportData,
    GFTPDFMedication,
)

_SUBTITLE_TABLE = "Exportación técnica tabular de medicamentos publicados"
_SUBTITLE_NARRATIVE = "Guía narrativa de medicamentos publicados ordenada por ATC"
_SUBTITLE_FULL = "Exportación completa de medicamentos publicados"
_AUTO_NOT_FOUND = "No localizado automáticamente"


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _format_generation_date(export_data: GFTPDFExportData) -> str:
    return export_data.generated_at.astimezone(timezone.utc).strftime(
        "%d/%m/%Y %H:%M UTC"
    )


def _iter_groups(groups: list[GFTPDFATCGroup], depth: int = 0):
    for group in groups:
        yield group, depth
        yield from _iter_groups(group.children, depth + 1)


def _render_doc_availability(medication: GFTPDFMedication) -> str:
    labels = []
    if _has_informed_value(medication.url_ficha_tecnica):
        labels.append("Ficha técnica CIMA disponible")
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


def _optional_sentence(
    label: str, value: object, *, max_chars: int | None = None
) -> str:
    if not _has_informed_value(value):
        return ""
    text = str(value).strip()
    if max_chars is not None:
        text = _truncate(text, max_chars)
    return f"{label}: {_e(text)}. "


def _render_meta_item(label: str, value: object) -> str:
    if not _has_informed_value(value):
        return ""
    return f'<span class="meta-item"><strong>{_e(label)}:</strong> {_e(str(value).strip())}</span>'


def _render_box(label: str, value: object, *, max_chars: int | None = None) -> str:
    if not _has_informed_value(value):
        return ""
    text = str(value).strip()
    if max_chars is not None:
        text = _truncate(text, max_chars)
    return f'<div class="info-box"><h4>{_e(label)}</h4><p>{_e(text)}</p></div>'


def _render_narrative_medication(med: GFTPDFMedication, mode: str) -> str:
    summary = med.resumen_clinico_auto or {}
    indicaciones = (
        summary.get("indicaciones") or med.indicaciones_ficha_tecnica or "No informado"
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
    documentos = _render_doc_availability(med)

    meta_items = "".join(
        item
        for item in [
            _render_meta_item("CN", med.cn),
            _render_meta_item("Nemónico", med.nemonico),
            _render_meta_item("Principio activo", med.principio_activo),
            _render_meta_item("ATC", med.codigo_atc),
            _render_meta_item("Forma farmacéutica", med.forma_farmaceutica),
            _render_meta_item("Vía", med.via_administracion),
            _render_meta_item("Documentación", documentos),
        ]
        if item
    )

    boxes = [
        _render_box("Indicaciones", indicaciones, max_chars=900),
        _render_box("Ajuste renal", renal, max_chars=500),
        _render_box("Ajuste hepático", hepatica, max_chars=500),
        _render_box("Embarazo", embarazo, max_chars=500),
        _render_box("Lactancia", lactancia, max_chars=500),
        _render_box("Restricciones hospitalarias", restricciones, max_chars=500),
        _render_box("Financiación", med.situacion_financiacion_bifimed, max_chars=500),
    ]
    if mode == "full":
        boxes.append(
            _render_box("Observaciones", med.observaciones_publicables, max_chars=500)
        )

    return (
        '<article class="medication">'
        f'<h4 class="med-title">{_e(med.nombre_comercial)}</h4>'
        f'<div class="metadata">{meta_items}</div>'
        f'<div class="clinical-boxes">{"".join(box for box in boxes if box)}</div>'
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
            f"<{heading}>{_e(group.codigo)} · {_e(group.nombre)} ({_e(group.count)})</{heading}>",
        ]
        if mode == "table":
            if group.medicamentos:
                lines.extend(
                    [
                        "<table><thead><tr><th>CN</th><th>Nombre comercial</th><th>Principio activo</th>"
                        "<th>Forma farmacéutica</th><th>Vía administración</th><th>Código ATC</th>"
                        "<th>Financiación BIFIMED</th><th>Documentación</th></tr></thead><tbody>",
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
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{_e(EXPORT_TITLE)}</title>
<style>
@page {{ margin: 10mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 10.5px; line-height: 1.35; color: #111; }}
h1,h2,h3,h4,h5,h6 {{ margin: 0.35rem 0; color: #0f4c81; }}
h1 {{ font-size: 20px; }}
h2 {{ font-size: 16px; border-bottom: 1px solid #b7c9da; padding-bottom: 2px; margin-top: 0.8rem; }}
h3 {{ font-size: 14px; margin-top: 0.7rem; }}
h4,h5,h6 {{ font-size: 12px; margin-top: 0.55rem; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin: 0.35rem 0 0.8rem; }}
th,td {{ border: 1px solid #cfd8e3; padding: 3px 4px; vertical-align: top; word-break: break-word; }}
th {{ background: #eef3f8; font-size: 9px; }}
p {{ margin: 0.25rem 0; }}
section {{ margin-bottom: 0.65rem; }}
.atc-depth-1 {{ margin-left: 0.08rem; }}
.atc-depth-2 {{ margin-left: 0.16rem; }}
.atc-depth-3 {{ margin-left: 0.24rem; }}
.atc-depth-4 {{ margin-left: 0.32rem; }}
.medication {{ break-inside: avoid; border: 1px solid #d8e2ec; border-radius: 4px; padding: 0.45rem 0.55rem; margin: 0.5rem 0 0.75rem; background: #fff; }}
.med-title {{ font-size: 13px; font-weight: 700; color: #082f49; margin: 0 0 0.35rem; }}
.metadata {{ display: block; margin-bottom: 0.35rem; color: #25364a; }}
.meta-item {{ display: inline-block; margin: 0 0.6rem 0.2rem 0; }}
.clinical-boxes {{ margin-top: 0.15rem; }}
.info-box {{ border-left: 3px solid #8fb3d9; background: #f8fbfe; padding: 0.25rem 0.35rem; margin: 0.35rem 0; }}
.info-box h4 {{ font-size: 10.5px; color: #0f4c81; margin: 0 0 0.15rem; }}
.info-box p {{ margin: 0; }}
</style></head><body>
<h1>{_e(export_data.title)}</h1>
<p>{_e(subtitle)}</p>
<p><strong>Fecha de generación:</strong> {_e(_format_generation_date(export_data))}</p>
<p><strong>Total de medicamentos publicados:</strong> {_e(export_data.total_medicamentos)}</p>
<p><em>Documento generado desde la misma base de datos que alimenta la GFT web.</em></p>
{body_html}
</body></html>"""
