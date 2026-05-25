#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache

SECTIONS=("4.1","4.2","4.3","4.4","4.6")

def parse_args(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--examples', type=int, default=20)
    return p.parse_args(argv)

def main(argv=None)->int:
    args=parse_args(argv)
    with SessionLocal() as db:
        cns=[str(r['cn']) for r in db.execute(text('SELECT cn FROM v_gft_publicada ORDER BY cn')).mappings().all()]
        cset=set(cns)
        cima={row.cn: row for row in db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns)).all()} if cns else {}
        summary={row.cn: row for row in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(cns)).all()} if cns else {}
        coverage={s:set() for s in SECTIONS}
        if cns:
            rows=db.query(CimaFichaTecnicaCache.cn,CimaFichaTecnicaCache.seccion).filter(CimaFichaTecnicaCache.cn.in_(cns),CimaFichaTecnicaCache.sync_status=='ok',CimaFichaTecnicaCache.seccion.in_(SECTIONS),CimaFichaTecnicaCache.contenido_texto.is_not(None),text("trim(contenido_texto) <> ''")).all()
            for r in rows: coverage[r.seccion].add(r.cn)

    con_cima_cache_ok=sum(1 for cn in cns if cn in cima and cima[cn].sync_status=='ok')
    con_nregistro=sum(1 for cn in cns if cn in cima and cima[cn].sync_status=='ok' and (cima[cn].nregistro or '').strip())
    source_counts={'ok':0,'partial':0,'missing':0}
    con_resumen=0
    cr=ch=ce=cl=0
    pend_sync=[]; pend_res=[]; miss_cima=[]; miss_nr=[]
    for cn in cns:
      s=summary.get(cn)
      if s:
        con_resumen += 1
        st=s.source_status
        source_counts['ok' if st=='ok' else 'partial' if st=='partial' else 'missing'] +=1
        if (s.resumen_ajuste_renal or '').strip(): cr+=1
        if (s.resumen_ajuste_hepatico or '').strip(): ch+=1
        if (s.resumen_embarazo or '').strip(): ce+=1
        if (s.resumen_lactancia or '').strip(): cl+=1
      if not (cn in cima and cima[cn].sync_status=='ok') and len(miss_cima)<args.examples: miss_cima.append(cn)
      if cn in cima and cima[cn].sync_status=='ok' and not (cima[cn].nregistro or '').strip() and len(miss_nr)<args.examples: miss_nr.append(cn)
      if any(cn not in coverage[sx] for sx in SECTIONS) and len(pend_sync)<args.examples: pend_sync.append(cn)
      if cn not in summary and len(pend_res)<args.examples: pend_res.append(cn)

    payload={"total_publicados":len(cns),"con_cima_cache_ok":con_cima_cache_ok,"con_nregistro":con_nregistro,
      "coverage_by_section":{s:len(coverage[s]) for s in SECTIONS},"con_resumen_clinico":con_resumen,
      "resumen_source_status_counts":source_counts,"con_ajuste_renal_auto":cr,"con_ajuste_hepatico_auto":ch,
      "con_embarazo_auto":ce,"con_lactancia_auto":cl,"pendientes_sync":len([cn for cn in cns if any(cn not in coverage[sx] for sx in SECTIONS)]),
      "pendientes_resumen":len(cset-set(summary.keys())),"blocked_missing_cima":len([cn for cn in cns if not (cn in cima and cima[cn].sync_status=='ok')]),
      "blocked_missing_nregistro":len([cn for cn in cns if cn in cima and cima[cn].sync_status=='ok' and not (cima[cn].nregistro or '').strip()]),
      "examples_pendientes_sync":pend_sync,"examples_pendientes_resumen":pend_res}
    print(json.dumps(payload,ensure_ascii=False,indent=2 if args.json_output else None))
    return 0

if __name__=='__main__': raise SystemExit(main())
