from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache


def build_gft_export_dataset(db: Session) -> list[dict]:
    rows = db.execute(text("SELECT * FROM v_gft_publicada ORDER BY atc_principal_codigo, principio_activo, nombre")).mappings().all()
    cns = [str(r.get('cn') or '').strip() for r in rows if str(r.get('cn') or '').strip()]
    summaries = {s.cn: s for s in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(cns)).all()}
    out = []
    for row in rows:
        cn = str(row.get('cn') or '').strip()
        s = summaries.get(cn)
        out.append({
            'nombre_comercial': row.get('nombre'),
            'principio_activo': row.get('principio_activo'),
            'forma_farmaceutica': row.get('forma_farmaceutica'),
            'via_administracion': row.get('vias_administracion_json'),
            'nemonico': row.get('nemonico'),
            'cn': cn,
            'codigo_atc': row.get('atc_principal_codigo'),
            'atc_descripciones': row.get('atc_json'),
            'bifimed_status': row.get('bifimed_sync_status'),
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
            'bifimed_ok': row.get('bifimed_sync_status') == 'ok',
            'cima_ok': row.get('cima_sync_status') == 'ok',
            'sections_complete': bool(row.get('cima_sync_status') == 'ok' and row.get('cima_has_ficha_tecnica')),
            'summary_ok': bool(s and s.source_status in {'ok', 'partial'}),
            'fully_linked_public_detail_ready': bool(row.get('bifimed_sync_status') == 'ok' and row.get('cima_sync_status') == 'ok' and s and s.source_status in {'ok', 'partial'}),
        })
    return out
