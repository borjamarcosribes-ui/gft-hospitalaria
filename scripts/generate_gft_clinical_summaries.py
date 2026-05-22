#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_clinical_summary_service import build_clinical_summary

TARGET=("4.1","4.2","4.3","4.4","4.6")

def parse():
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int);p.add_argument('--cn');p.add_argument('--force',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--confirm-write',action='store_true');p.add_argument('--json',action='store_true',dest='json_output');p.add_argument('--only-missing',action='store_true');return p.parse_args()

def main():
 a=parse()
 if not a.dry_run and not a.confirm_write: raise SystemExit('Safe abort: requiere --confirm-write para escritura real.')
 s={"processed":0,"generated":0,"skipped_unchanged":0,"total_publicados":0}
 with SessionLocal() as db:
  cns=[r['cn'] for r in db.execute(text('SELECT cn FROM v_gft_publicada ORDER BY cn')).mappings().all()]
  s['total_publicados']=len(cns)
  if a.cn: cns=[a.cn] if a.cn in cns else []
  if a.limit: cns=cns[:max(0,a.limit)]
  for cn in cns:
   s['processed']+=1
   current=db.get(GftClinicalSummaryCache,cn)
   if a.only_missing and current and current.source_status in ('ok','partial'): continue
   cmap=db.get(CimaMedicamentoCache,cn)
   has_cima_ok=bool(cmap and cmap.sync_status=='ok')
   has_nregistro=bool((cmap.nregistro if cmap else '') or '')
   rows=db.query(CimaFichaTecnicaCache).filter(CimaFichaTecnicaCache.cn==cn,CimaFichaTecnicaCache.seccion.in_(TARGET),CimaFichaTecnicaCache.sync_status=='ok').all()
   sections={r.seccion:(r.contenido_texto or '') for r in rows}
   data=build_clinical_summary(sections, has_nregistro=has_nregistro, has_cima_ok=has_cima_ok)
   if current and current.source_hash==data['source_hash'] and current.source_status in ('ok','partial') and not a.force:
    s['skipped_unchanged']+=1; continue
   if not a.dry_run:
    row=current or GftClinicalSummaryCache(cn=cn)
    for k,v in data.items():
      if not k.startswith('_'): setattr(row,k,v)
    db.add(row)
   s['generated']+=1
  if not a.dry_run: db.commit()
 print(json.dumps(s,ensure_ascii=False,indent=2) if a.json_output else json.dumps(s,ensure_ascii=False))
 return 0
if __name__=='__main__': raise SystemExit(main())
