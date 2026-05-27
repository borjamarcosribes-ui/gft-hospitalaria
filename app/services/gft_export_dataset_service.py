from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache


def _view_columns(db: Session) -> set[str]:
    sample = db.execute(text("SELECT * FROM v_gft_publicada LIMIT 0"))
    return set(sample.keys())


def _first_present(row: dict, names: list[str]):
    for name in names:
        if name in row:
            return row.get(name)
    return None


def build_gft_export_dataset(db: Session) -> list[dict]:
    columns = _view_columns(db)
    atc_col = next((c for c in ["codigo_atc", "atc_codigo", "codigo_atc_principal", "codigo_atc_importado", "atc_principal_codigo"] if c in columns), None)
    principio_col = next((c for c in ["principio_activo", "principio_activo_importado"] if c in columns), None)
    nombre_col = next((c for c in ["nombre", "nombre_comercial", "nombre_comercial_importado"] if c in columns), None)
    order_parts = [p for p in [atc_col, principio_col, nombre_col, "cn"] if p]
    order_sql = ", ".join(order_parts) if order_parts else "cn"
    rows = db.execute(text(f"SELECT * FROM v_gft_publicada ORDER BY {order_sql}")).mappings().all()
    cns = [str(r.get('cn') or '').strip() for r in rows if str(r.get('cn') or '').strip()]
    summaries = {s.cn: s for s in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(cns)).all()}
    out = []
    for row in rows:
        cn = str(row.get('cn') or '').strip()
        s = summaries.get(cn)
        out.append({
            'nombre_comercial': _first_present(row, ['nombre', 'nombre_comercial', 'nombre_comercial_importado']),
            'principio_activo': _first_present(row, ['principio_activo', 'principio_activo_importado']),
            'forma_farmaceutica': row.get('forma_farmaceutica'),
            'via_administracion': row.get('vias_administracion_json'),
            'nemonico': row.get('nemonico'),
            'cn': cn,
            'codigo_atc': _first_present(row, ['codigo_atc', 'atc_codigo', 'codigo_atc_principal', 'codigo_atc_importado', 'atc_principal_codigo']),
            'atc_descripciones': row.get('atc_json'),
            'bifimed_status': _first_present(row, ['bifimed_sync_status', 'bifimed_status']),
            'cima_status': _first_present(row, ['cima_sync_status', 'cima_status']),
            'condiciones_especiales': row.get('restricciones_hospitalarias'),
            'indicaciones_autorizadas_bifimed': row.get('indicaciones_autorizadas_bifimed'),
            'url_ficha_tecnica': row.get('url_ficha_tecnica'),
            'url_prospecto': row.get('url_prospecto'),
            'resumen_general': getattr(s, 'resumen_general', None),
            'resumen_indicaciones': getattr(s, 'resumen_indicaciones', None),
            'resumen_posologia': getattr(s, 'resumen_posologia', None),
            'resumen_ajuste_renal': getattr(s, 'resumen_ajuste_renal', None),
            'resumen_ajuste_hepatico': getattr(s, 'resumen_ajuste_hepatico', None),
            'resumen_contraindicaciones': getattr(s, 'resumen_contraindicaciones', None),
            'resumen_advertencias': getattr(s, 'resumen_advertencias', None),
            'resumen_embarazo': getattr(s, 'resumen_embarazo', None),
            'resumen_lactancia': getattr(s, 'resumen_lactancia', None),
            'bifimed_ok': _first_present(row, ['bifimed_sync_status', 'bifimed_status']) == 'ok',
            'cima_ok': _first_present(row, ['cima_sync_status', 'cima_status']) == 'ok',
            'sections_complete': bool(_first_present(row, ['cima_sync_status', 'cima_status']) == 'ok' and row.get('cima_has_ficha_tecnica')),
            'summary_ok': bool(s and s.source_status in {'ok', 'partial'}),
            'fully_linked_public_detail_ready': bool(_first_present(row, ['bifimed_sync_status', 'bifimed_status']) == 'ok' and _first_present(row, ['cima_sync_status', 'cima_status']) == 'ok' and s and s.source_status in {'ok', 'partial'}),
        })
    return out
