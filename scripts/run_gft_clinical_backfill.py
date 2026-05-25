#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from scripts import sync_gft_clinical_sections as sync_mod
from scripts import generate_gft_clinical_summaries as sum_mod
from scripts import gft_clinical_coverage_audit as audit_mod

def parse_args(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true'); p.add_argument('--confirm-write', action='store_true')
    p.add_argument('--batch-size', type=int, default=20); p.add_argument('--max-batches', type=int, default=1)
    p.add_argument('--sections', nargs='*', default=['4.2','4.3','4.4','4.6']); p.add_argument('--only-missing', action='store_true')
    p.add_argument('--candidate-mode', default='syncable'); p.add_argument('--summary-candidate-mode', default='summary_ready')
    p.add_argument('--examples', type=int, default=20); p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--stop-on-error', action='store_true'); p.add_argument('--sleep-seconds', type=float, default=0)
    p.add_argument('--cn', action='append', default=[])
    return p.parse_args(argv)

def _parse_json_output(fn, argv):
    import io, contextlib
    b=io.StringIO()
    with contextlib.redirect_stdout(b):
        fn(argv)
    return json.loads(b.getvalue() or '{}')

def main(argv=None):
    a=parse_args(argv)
    if not a.dry_run and not a.confirm_write: raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
    if a.confirm_write and not a.cn and (a.batch_size is None or a.max_batches is None):
        raise SystemExit('Con --confirm-write indique límites de lote o --cn explícitos.')
    cov_before=_parse_json_output(audit_mod.main,['--json','--examples',str(a.examples)])
    if a.dry_run:
        sync_plan=_parse_json_output(sync_mod.main,['--dry-run','--candidate-mode',a.candidate_mode,'--sections',*a.sections,'--only-missing','--limit',str(a.batch_size*a.max_batches),'--json'])
        sum_plan=_parse_json_output(sum_mod.main,['--dry-run','--candidate-mode',a.summary_candidate_mode,'--only-missing','--limit',str(a.batch_size*a.max_batches),'--json'])
        out={'dry_run':True,'batch_size':a.batch_size,'max_batches':a.max_batches,'sections':a.sections,'sync_plan':sync_plan,'summary_plan':sum_plan,'coverage_before':cov_before,'coverage_after_estimate':cov_before}
    else:
        batches=[]
        for i in range(a.max_batches):
            limit=a.batch_size
            sync_args=['--confirm-write','--candidate-mode',a.candidate_mode,'--sections',*a.sections,'--only-missing','--limit',str(limit),'--json']
            sum_args=['--confirm-write','--candidate-mode',a.summary_candidate_mode,'--only-missing','--limit',str(limit),'--json']
            if a.cn: sync_args=['--confirm-write','--sections',*a.sections,'--only-missing','--json']+sum([['--cn',cn] for cn in a.cn],[]); sum_args=['--confirm-write','--only-missing','--json']+sum([['--cn',cn] for cn in a.cn],[])
            s=_parse_json_output(sync_mod.main,sync_args); m=_parse_json_output(sum_mod.main,sum_args)
            batches.append({'batch_number':i+1,'sync':{'processed_cn':s.get('processed_cn',0),'processed_operations':s.get('processed_operations',0),'by_status':s.get('by_status',{})},'summaries':{'processed':m.get('processed',0),'written':m.get('written',0),'by_source_status':m.get('by_source_status',{})}})
            if a.cn: break
        out={'dry_run':False,'confirm_write':True,'batches':batches,'coverage_before':cov_before,'coverage_after':_parse_json_output(audit_mod.main,['--json','--examples',str(a.examples)])}
    print(json.dumps(out,ensure_ascii=False,indent=2 if a.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
