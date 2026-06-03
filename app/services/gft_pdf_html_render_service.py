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
                lead = f"<strong>{_e(med.nemonico)}</strong> — " if _has_informed_value(med.nemonico) else ""
                links = []
                if _has_informed_value(med.url_ficha_tecnica):
                    links.append(f"Ficha técnica: {_e(str(med.url_ficha_tecnica).strip())}.")
                if _has_informed_value(med.url_prospecto):
                    links.append(f"Prospecto: {_e(str(med.url_prospecto).strip())}.")
                observaciones = ""
                if mode == "full" and _has_informed_value(med.observaciones_publicables):
                    observaciones = f"Observaciones: {_e(_truncate(str(med.observaciones_publicables).strip(), 400))}. "
                lines.append(
                    "<p>"
                    f"{lead}{_e(med.nombre_comercial)} (CN {_e(med.cn)}). "
                    f"Principio activo: {_e(med.principio_activo)}. "
                    f"{_optional_sentence('Nemónico', med.nemonico)}"
                    f"{_optional_sentence('ATC', med.codigo_atc)}"
                    f"{_optional_sentence('Forma farmacéutica', med.forma_farmaceutica)}"
                    f"{_optional_sentence('Vía', med.via_administracion)}"
                    f"{_optional_sentence('Financiación', med.situacion_financiacion_bifimed)}"
                    f"{_optional_sentence('Indicaciones', indicaciones, max_chars=700)}"
                    f"{_optional_sentence('Ajuste IR', renal, max_chars=400)}"
                    f"{_optional_sentence('Ajuste IH', hepatica, max_chars=400)}"
                    f"{_optional_sentence('Embarazo', embarazo, max_chars=400)}"
                    f"{_optional_sentence('Lactancia', lactancia, max_chars=400)}"
                    f"{_optional_sentence('Restricciones hospitalarias', restricciones, max_chars=400)}"
                    f"{observaciones}"
                    f"{' '.join(links)}"
                    "</p>"
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
</style></head><body>
<h1>{_e(export_data.title)}</h1>
<p>{_e(subtitle)}</p>
<p><strong>Fecha de generación:</strong> {_e(_format_generation_date(export_data))}</p>
<p><strong>Total de medicamentos publicados:</strong> {_e(export_data.total_medicamentos)}</p>
<p><em>Documento generado desde la misma base de datos que alimenta la GFT web.</em></p>
{body_html}
</body></html>"""
