#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from app.core.database import SessionLocal
from app.models.bifimed_cache import BifimedCache
from app.services.bifimed_sync_service import sync_bifimed_cn
from app.services.gft_cn_universe_service import get_cn_universe, normalize_cn_value

def parse_args(argv=None):
 p=argparse.ArgumentParser(); p.add_argument('--dry-run',action='store_true'); p.add_argument('--confirm-write',action='store_true'); p.add_argument('--scope',default='published',choices=['published','included','state','imported','all_known']); p.add_argument('--cn',action='append',default=[]); p.add_argument('--batch-size',type=int,default=50); p.add_argument('--max-batches',type=int,default=1); p.add_argument('--only-missing',action='store_true'); p.add_argument('--force',action='store_true'); p.add_argument('--retry-errors',action='store_true'); p.add_argument('--start-after-cn'); p.add_argument('--examples',type=int,default=20); p.add_argument('--sleep-seconds',type=float,default=0); p.add_argument('--json',action='store_true',dest='json_output'); return p.parse_args(argv)

def main(argv=None):
 a=parse_args(argv)
 if not a.dry_run and not a.confirm_write: raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
 if a.confirm_write and not a.cn and (a.batch_size is None or a.max_batches is None): raise SystemExit('Con --confirm-write indique --batch-size y --max-batches o --cn explícito.')
 with SessionLocal() as db:
  cns=get_cn_universe(db,a.scope,a.cn)
  if a.start_after_cn: cns=[cn for cn in cns if cn>a.start_after_cn]
  cns=cns[:a.batch_size*a.max_batches] if not a.cn else cns
  by=Counter(); ex=[]; written=0; processed=0; skipped_existing=0
  for cn in cns:
   norm=normalize_cn_value(cn)
   if not norm: by['skipped_invalid_cn']+=1; continue
   existing=db.get(BifimedCache,norm)
   if a.only_missing and existing and (existing.situacion_financiacion or '').strip() and not a.force and not (a.retry_errors and existing.sync_status=='error'):
    by['skipped_existing']+=1; skipped_existing+=1; continue
   processed+=1
   if a.dry_run:
    by['would_sync']+=1; continue
   row=sync_bifimed_cn(db, norm, force=(a.force or a.retry_errors))
   by[row.sync_status if row.sync_status in {'ok','not_found'} else 'error']+=1
   written+=1
   if len(ex)<a.examples: ex.append({'cn':norm,'status':row.sync_status})
 out={'scope':a.scope,'dry_run':a.dry_run,'confirm_write':a.confirm_write,'selected':len(cns),'processed':processed,'written':written,'skipped_existing':skipped_existing,'by_status':dict(by),'examples':ex}
 print(json.dumps(out,ensure_ascii=False,indent=2 if a.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
