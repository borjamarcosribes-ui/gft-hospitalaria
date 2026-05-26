#!/usr/bin/env python3
from __future__ import annotations
from scripts._db_guard import ensure_postgresql_database
import argparse, json
from scripts import run_gft_bifimed_backfill as b
from scripts import run_gft_cima_medicamento_backfill as c
from scripts import run_gft_clinical_backfill as cl
from scripts import gft_linkage_coverage_audit as a

def parse_args(argv=None):
 p=argparse.ArgumentParser(); p.add_argument('--dry-run',action='store_true'); p.add_argument('--confirm-write',action='store_true'); p.add_argument('--scope',default='published',choices=['published','included','state','imported','all_known']); p.add_argument('--cn',action='append',default=[]); p.add_argument('--batch-size',type=int,default=50); p.add_argument('--max-batches',type=int,default=1); p.add_argument('--sections',nargs='*',default=['4.1','4.2','4.3','4.4','4.6']); p.add_argument('--only-missing',action='store_true'); p.add_argument('--force-bifimed',action='store_true'); p.add_argument('--force-cima',action='store_true'); p.add_argument('--force-summary',action='store_true'); p.add_argument('--retry-errors',action='store_true'); p.add_argument('--start-after-cn'); p.add_argument('--sleep-seconds',type=float,default=0); p.add_argument('--json',action='store_true',dest='json_output'); p.add_argument('--skip-bifimed',action='store_true'); p.add_argument('--skip-cima-medicamento',action='store_true'); p.add_argument('--skip-sections',action='store_true'); p.add_argument('--skip-summaries',action='store_true'); p.add_argument("--allow-default-db", action="store_true")
 return p.parse_args(argv)

def _cap(fn,args):
 import io,contextlib
 bfr=io.StringIO();
 with contextlib.redirect_stdout(bfr): fn(args)
 return json.loads(bfr.getvalue() or '{}')

def main(argv=None):
 x=parse_args(argv)
 ensure_postgresql_database(x.allow_default_db)
 if not x.dry_run and not x.confirm_write: raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
 if x.confirm_write and not x.cn and (x.batch_size is None or x.max_batches is None): raise SystemExit('Con --confirm-write indique límites o --cn explícito.')
 base=(["--allow-default-db"] if x.allow_default_db else []) + ['--scope',x.scope,'--batch-size',str(x.batch_size),'--max-batches',str(x.max_batches),'--json']+sum([['--cn',cn] for cn in x.cn],[])
 if x.only_missing: base.append('--only-missing')
 if x.retry_errors: base.append('--retry-errors')
 if x.start_after_cn: base += ['--start-after-cn',x.start_after_cn]
 mode='--dry-run' if x.dry_run else '--confirm-write'
 before=_cap(a.main,(["--allow-default-db"] if x.allow_default_db else []) + ['--scope',x.scope,'--json','--sections',*x.sections]+sum([['--cn',cn] for cn in x.cn],[]))
 out={'dry_run':x.dry_run,'confirm_write':x.confirm_write,'scope':x.scope,'before':before}
 if not x.skip_bifimed: out['bifimed']=_cap(b.main,[mode,*base,*(['--force'] if x.force_bifimed else [])])
 if not x.skip_cima_medicamento: out['cima_medicamento']=_cap(c.main,[mode,*base,*(['--force'] if x.force_cima else [])])
 out['clinical']=_cap(cl.main,[mode,*base,'--sections',*x.sections,*(['--force-summary'] if x.force_summary else []),*(['--skip-sections'] if x.skip_sections else []),*(['--skip-summaries'] if x.skip_summaries else [])])
 out['after']=_cap(a.main,(["--allow-default-db"] if x.allow_default_db else []) + ['--scope',x.scope,'--json','--sections',*x.sections]+sum([['--cn',cn] for cn in x.cn],[]))
 print(json.dumps(out,ensure_ascii=False,indent=2 if x.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
