#!/usr/bin/env python3
from __future__ import annotations
from scripts._db_guard import ensure_postgresql_database
import argparse, json
from collections import Counter
from app.core.database import SessionLocal
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.services.cima_sync_service import sync_cn
from app.services.cima_seed_service import seed_cima_from_imported_urls
from app.services.gft_cn_universe_service import get_cn_universe, normalize_cn_value
from app.models.gft_estado_presentacion import GFTEstadoPresentacion

def parse_args(argv=None):
 p=argparse.ArgumentParser(); p.add_argument('--dry-run',action='store_true'); p.add_argument('--confirm-write',action='store_true'); p.add_argument('--scope',default='published',choices=['published','included','state','imported','all_known']); p.add_argument('--cn',action='append',default=[]); p.add_argument('--batch-size',type=int,default=50); p.add_argument('--max-batches',type=int,default=1); p.add_argument('--only-missing',action='store_true'); p.add_argument('--force',action='store_true'); p.add_argument('--retry-not-found',action='store_true'); p.add_argument('--retry-errors',action='store_true'); p.add_argument('--seed-from-imported-urls',action='store_true'); p.add_argument('--repair-not-found-from-imported-url',action='store_true'); p.add_argument('--start-after-cn'); p.add_argument('--examples',type=int,default=20); p.add_argument('--sleep-seconds',type=float,default=0); p.add_argument('--json',action='store_true',dest='json_output'); p.add_argument("--allow-default-db", action="store_true")
 return p.parse_args(argv)

def main(argv=None):
 a=parse_args(argv)
 ensure_postgresql_database(a.allow_default_db)
 if not a.dry_run and not a.confirm_write: raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
 if a.confirm_write and not a.cn and (a.batch_size is None or a.max_batches is None): raise SystemExit('Con --confirm-write indique --batch-size y --max-batches o --cn explícito.')
 with SessionLocal() as db:
  universe=get_cn_universe(db,a.scope,a.cn)
  by=Counter(); ex=[]; written=processed=0
  limit=(a.batch_size*a.max_batches) if not a.cn else None
  cns=[]
  for cn in universe:
   if a.start_after_cn and cn<=a.start_after_cn: continue
   norm=normalize_cn_value(cn)
   if not norm: continue
   existing=db.get(CimaMedicamentoCache,norm)
   if a.only_missing and not (a.force or a.retry_not_found or a.retry_errors):
    if existing is None: cns.append(cn)
    elif existing.sync_status=='ok': by['skipped_existing_ok']+=1
    elif existing.sync_status=='not_found': by['skipped_existing_not_found']+=1
    else: cns.append(cn)
   elif a.retry_not_found:
    if existing and existing.sync_status=='not_found': cns.append(cn)
   else:
    cns.append(cn)
   if limit is not None and len(cns)>=limit: break

  seed_metrics={'candidates_with_imported_url':0,'seedable':0,'seeded':0,'repaired_not_found':0,'skipped_existing_ok':0,'skipped_no_nregistro':0,'examples_seeded':[],'examples_repaired':[]}
  if a.seed_from_imported_urls and not a.dry_run:
   for cn in cns:
    norm=normalize_cn_value(cn)
    estado=db.get(GFTEstadoPresentacion,norm)
    if not estado: continue
    ft=getattr(estado,'url_ficha_tecnica_importada',None); pr=getattr(estado,'url_prospecto_importado',None)
    if not ((ft or '').strip() or (pr or '').strip()): continue
    seed_metrics['candidates_with_imported_url']+=1
    existing=db.get(CimaMedicamentoCache,norm)
    if existing and existing.sync_status=='ok': seed_metrics['skipped_existing_ok']+=1; continue
    seed_metrics['seedable']+=1
    changed=seed_cima_from_imported_urls(db,norm,ft,pr,force=a.force,repair_not_found=a.repair_not_found_from_imported_url)
    if not changed: seed_metrics['skipped_no_nregistro']+=1; continue
    if existing and existing.sync_status=='not_found':
      seed_metrics['repaired_not_found']+=1
      if len(seed_metrics['examples_repaired'])<a.examples: seed_metrics['examples_repaired'].append(norm)
    else:
      seed_metrics['seeded']+=1
      if len(seed_metrics['examples_seeded'])<a.examples: seed_metrics['examples_seeded'].append(norm)
  for cn in cns:
   norm=normalize_cn_value(cn)
   if not norm: by['skipped_invalid_cn']+=1; continue
   existing=db.get(CimaMedicamentoCache,norm)
   processed+=1
   if a.dry_run: by['would_sync']+=1; continue
   row=sync_cn(db,norm,force=(a.force or a.retry_errors)); by[f"written_{row.sync_status}" if row.sync_status in {'ok','not_found'} else 'error']+=1; written+=1
   if len(ex)<a.examples: ex.append({'cn':norm,'status':row.sync_status})
 out={'scope':a.scope,'dry_run':a.dry_run,'confirm_write':a.confirm_write,'selected':len(cns),'selected_missing_cache':sum(1 for cn in cns if db.get(CimaMedicamentoCache,normalize_cn_value(cn)) is None),'selected_repair_not_found':sum(1 for cn in cns if (db.get(CimaMedicamentoCache,normalize_cn_value(cn)) and db.get(CimaMedicamentoCache,normalize_cn_value(cn)).sync_status=='not_found')),'processed':processed,'written':written,'by_status':dict(by),'seed_from_imported_urls':seed_metrics,'examples':ex}
 print(json.dumps(out,ensure_ascii=False,indent=2 if a.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
