#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.bifimed_cache import BifimedCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_cn_universe_service import get_cn_universe

VALID_SUMMARY_SOURCE_STATUSES = {'ok', 'partial'}
PLACEHOLDER_TEXTS = {'no localizado automáticamente', 'no localizado automáticamente.', 'no informado'}


def _has_useful_text(value: str | None) -> bool:
    text_value = (value or '').strip()
    return bool(text_value) and text_value.lower() not in PLACEHOLDER_TEXTS


def parse_args(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--scope', default='published', choices=['published','included','state','imported','all_known'])
    p.add_argument('--cn', action='append', default=[])
    p.add_argument('--sections', nargs='*', default=['4.1','4.2','4.3','4.4','4.6'])
    p.add_argument('--examples', type=int, default=20)
    p.add_argument('--json', action='store_true', dest='json_output')
    return p.parse_args(argv)

def main(argv=None):
    a=parse_args(argv)
    with SessionLocal() as db:
      cns=get_cn_universe(db, a.scope, a.cn)
      bifis={r.cn:r for r in db.query(BifimedCache).filter(BifimedCache.cn.in_(cns)).all()} if cns else {}
      cimas={r.cn:r for r in db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns)).all()} if cns else {}
      sums={r.cn:r for r in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(cns)).all()} if cns else {}
      sec_rows=db.query(CimaFichaTecnicaCache.cn,CimaFichaTecnicaCache.seccion).filter(CimaFichaTecnicaCache.cn.in_(cns),CimaFichaTecnicaCache.sync_status=='ok',CimaFichaTecnicaCache.seccion.in_(a.sections),text("trim(coalesce(contenido_texto,''))<>''")).all() if cns else []
    cov={s:set() for s in a.sections}
    for r in sec_rows: cov[r.seccion].add(r.cn)
    bstat=Counter(); cstat=Counter(); sstat=Counter(); linked=Counter()
    ex_missing_sections=[]; ex_pend=[]
    for cn in cns:
      b=bifis.get(cn); c=cimas.get(cn); s=sums.get(cn)
      if b: bstat[b.sync_status or 'unknown']+=1
      if c: cstat[c.sync_status or 'unknown']+=1
      if s: sstat[s.source_status or 'missing']+=1
      has_sections=all(cn in cov[sec] for sec in a.sections)
      if not has_sections and len(ex_missing_sections)<a.examples: ex_missing_sections.append(cn)
      if has_sections and (not s or s.source_status not in {'ok','partial'}) and len(ex_pend)<a.examples: ex_pend.append(cn)
      if not c or c.sync_status!='ok': linked['blocked_missing_cima']+=1
      elif not (c.nregistro or '').strip(): linked['blocked_missing_nregistro']+=1
      elif not has_sections: linked['blocked_missing_sections']+=1
      elif not s: linked['clinical_ready' if (b and b.sync_status=='ok') else 'blocked_missing_bifimed']+=1
      elif not b or b.sync_status!='ok': linked['clinical_ready']+=1
      else: linked['full_public_ready']+=1
    out={
      'scope':a.scope,'total_cn':len(cns),
      'bifimed':{'con_cache':len(bifis),'con_situacion_financiacion':sum(1 for r in bifis.values() if (r.situacion_financiacion or '').strip()),'financiados_si':sum(1 for r in bifis.values() if (r.situacion_financiacion or '').strip().lower() in {'si','sí'}),'financiados_no':sum(1 for r in bifis.values() if (r.situacion_financiacion or '').strip().lower()=='no'),'con_condiciones_restringidas':sum(1 for r in bifis.values() if (r.condiciones_financiacion_restringidas or '').strip()),'con_condiciones_especiales':sum(1 for r in bifis.values() if (r.condiciones_especiales_financiacion or '').strip()),'sin_cache':len(cns)-len(bifis),'sync_status_counts':dict(bstat)},
      'cima':{'con_cache':len(cimas),'ok':sum(1 for r in cimas.values() if r.sync_status=='ok'),'not_found':sum(1 for r in cimas.values() if r.sync_status=='not_found'),'error':sum(1 for r in cimas.values() if r.sync_status not in {'ok','not_found'}),'con_nregistro':sum(1 for r in cimas.values() if r.sync_status=='ok' and (r.nregistro or '').strip()),'sin_nregistro':sum(1 for r in cimas.values() if r.sync_status=='ok' and not (r.nregistro or '').strip()),'sync_status_counts':dict(cstat)},
      'sections':{'coverage_by_section':{s:len(cov[s]) for s in a.sections},'complete_all_requested_sections':sum(1 for cn in cns if all(cn in cov[s] for s in a.sections)),'missing_any_requested_section':sum(1 for cn in cns if any(cn not in cov[s] for s in a.sections)),'examples_missing_sections':ex_missing_sections},
      'summaries':{'con_resumen':sum(1 for r in sums.values() if (r.source_status or '') in VALID_SUMMARY_SOURCE_STATUSES),'source_status_counts':dict(sstat),'con_resumen_general':sum(1 for r in sums.values() if (r.source_status or '') in VALID_SUMMARY_SOURCE_STATUSES and _has_useful_text(r.resumen_general)),'con_ajuste_renal':sum(1 for r in sums.values() if (r.source_status or '') in VALID_SUMMARY_SOURCE_STATUSES and _has_useful_text(r.resumen_ajuste_renal)),'con_ajuste_hepatico':sum(1 for r in sums.values() if (r.source_status or '') in VALID_SUMMARY_SOURCE_STATUSES and _has_useful_text(r.resumen_ajuste_hepatico)),'con_embarazo':sum(1 for r in sums.values() if (r.source_status or '') in VALID_SUMMARY_SOURCE_STATUSES and _has_useful_text(r.resumen_embarazo)),'con_lactancia':sum(1 for r in sums.values() if (r.source_status or '') in VALID_SUMMARY_SOURCE_STATUSES and _has_useful_text(r.resumen_lactancia)),'pendientes_resumen':sum(1 for cn in cns if cn not in sums or (sums[cn].source_status or '') not in VALID_SUMMARY_SOURCE_STATUSES),'examples_pendientes_resumen':ex_pend},
      'completion':{'bifimed_ready':sum(1 for cn in cns if cn in bifis and bifis[cn].sync_status=='ok'),'cima_ready':sum(1 for cn in cns if cn in cimas and cimas[cn].sync_status=='ok'),'clinical_ready':linked['clinical_ready']+linked['full_public_ready'],'fully_linked_public_detail_ready':linked['full_public_ready'],'blocked':len(cns)-linked['clinical_ready']-linked['full_public_ready']},
      'linked_status_counts':dict(linked),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2 if a.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
