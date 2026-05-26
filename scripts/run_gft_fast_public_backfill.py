#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from scripts._db_guard import ensure_postgresql_database
from scripts import run_gft_linkage_backfill as linkage

def parse_args(argv=None):
 p=argparse.ArgumentParser(); p.add_argument('--dry-run',action='store_true'); p.add_argument('--confirm-write',action='store_true'); p.add_argument('--scope',default='published'); p.add_argument('--batch-size',type=int,default=100); p.add_argument('--max-batches',type=int,default=1); p.add_argument('--sections',nargs='*',default=['4.1','4.2','4.3','4.4','4.6']); p.add_argument('--only-missing',action='store_true'); p.add_argument('--json',action='store_true',dest='json_output'); p.add_argument('--skip-bifimed',action='store_true'); p.add_argument('--skip-cima-med',action='store_true'); p.add_argument('--skip-cima-sections',action='store_true'); p.add_argument('--skip-summaries',action='store_true'); p.add_argument('--seed-from-imported-urls',action='store_true'); p.add_argument('--repair-not-found-from-imported-url',action='store_true'); p.add_argument('--allow-default-db',action='store_true'); return p.parse_args(argv)

def main(argv=None):
 a=parse_args(argv); ensure_postgresql_database(a.allow_default_db)
 if not a.dry_run and not a.confirm_write: raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
 if a.confirm_write and (a.batch_size <=0 or a.max_batches<=0): raise SystemExit('Con --confirm-write exige límites válidos.')
 mode='--dry-run' if a.dry_run else '--confirm-write'
 args=[mode,'--scope',a.scope,'--batch-size',str(a.batch_size),'--max-batches',str(a.max_batches),'--sections',*a.sections,'--json']
 if a.only_missing: args.append('--only-missing')
 if a.skip_bifimed: args.append('--skip-bifimed')
 if a.skip_cima_med: args.append('--skip-cima-medicamento')
 if a.skip_cima_sections: args.append('--skip-sections')
 if a.skip_summaries: args.append('--skip-summaries')
 if a.allow_default_db: args.append('--allow-default-db')
 payload={'scope':a.scope,'dry_run':a.dry_run,'phases':{'seed_cima_from_imported_urls':{'enabled':a.seed_from_imported_urls,'repair_not_found':a.repair_not_found_from_imported_url}},'next_recommended_command':'PYTHONPATH=. python scripts/run_gft_fast_public_backfill.py --confirm-write --scope published --batch-size 100 --max-batches 5 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --seed-from-imported-urls --repair-not-found-from-imported-url --json'}
 import io,contextlib
 b=io.StringIO()
 with contextlib.redirect_stdout(b): linkage.main(args)
 payload['linkage']=json.loads(b.getvalue() or '{}')
 print(json.dumps(payload,ensure_ascii=False,indent=2 if a.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
