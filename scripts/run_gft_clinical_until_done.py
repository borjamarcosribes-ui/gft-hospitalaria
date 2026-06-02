#!/usr/bin/env python3
from __future__ import annotations
import argparse, contextlib, io, json, time
from datetime import datetime, timezone
from pathlib import Path
from scripts import sync_gft_clinical_sections as sections_sync
from scripts import generate_gft_clinical_summaries as summaries
from scripts import gft_linkage_coverage_audit as audit

DEFAULT_SECTIONS=["4.1","4.2","4.3","4.4","4.6"]

def parse_args(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--scope', default='published', choices=['published','included','pending','imported','all_known'])
    p.add_argument('--sections', nargs='*', default=DEFAULT_SECTIONS)
    p.add_argument('--section-batch-size', type=int, default=10)
    p.add_argument('--summary-limit', type=int, default=100)
    p.add_argument('--max-runs', type=int, default=20)
    p.add_argument('--sleep-seconds', type=float, default=0.2)
    p.add_argument('--only-missing', action='store_true')
    p.add_argument('--confirm-write', action='store_true')
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--stop-on-warning', action='store_true')
    p.add_argument('--stop-on-no-progress', action='store_true')
    p.add_argument('--runtime-log-dir', default='runtime_logs')
    p.add_argument('--checkpoint-each-run', action='store_true')
    return p.parse_args(argv)

def _run_json(fn, argv):
    b=io.StringIO()
    with contextlib.redirect_stdout(b):
        fn(argv)
    return json.loads(b.getvalue() or '{}')

def _delta(before, after, sections):
    out={
        'summaries_con_resumen': after.get('summaries',{}).get('con_resumen',0)-before.get('summaries',{}).get('con_resumen',0),
        'clinical_ready': after.get('completion',{}).get('clinical_ready',0)-before.get('completion',{}).get('clinical_ready',0),
        'fully_linked_public_detail_ready': after.get('completion',{}).get('fully_linked_public_detail_ready',0)-before.get('completion',{}).get('fully_linked_public_detail_ready',0),
    }
    for s in sections:
        out[f"sections_{s.replace('.','_')}"]=after.get('sections',{}).get('coverage_by_section',{}).get(s,0)-before.get('sections',{}).get('coverage_by_section',{}).get(s,0)
    return out

def _is_blocking_warning(w):
    return bool(w)


def _exhausted_without_candidates(phase_sections, phase_summaries):
    remaining = int(phase_sections.get('remaining_syncable_candidates') or 0)
    known_unavailable = int(phase_sections.get('remaining_known_unavailable') or 0)
    no_candidates = bool(phase_summaries.get('no_candidates'))
    return remaining == 0 and no_candidates, known_unavailable

def _checkpoint_payload(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main(argv=None):
    a=parse_args(argv)
    if not a.confirm_write:
        raise SystemExit('Safe abort: requiere --confirm-write.')
    Path(a.runtime_log_dir).mkdir(exist_ok=True)
    all_runs=[]
    total_delta={}
    final_audit={}
    next_action='completed'
    log_path=Path(a.runtime_log_dir)/f"gft_clinical_until_done_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    checkpoint_path=log_path.with_name(log_path.name + '_checkpoint.json')
    for run_number in range(1,a.max_runs+1):
        run_started=time.time()
        before=_run_json(audit.main,['--scope',a.scope,'--sections',*a.sections,'--json'])
        phase_sections=_run_json(sections_sync.main,['--confirm-write','--scope',a.scope,'--sections',*a.sections,'--limit',str(a.section_batch_size),'--candidate-mode','syncable','--json',*( ['--only-missing'] if a.only_missing else [])])
        phase_summaries=_run_json(summaries.main,['--confirm-write','--scope',a.scope,'--limit',str(a.summary_limit),'--candidate-mode','summary_ready','--json',*( ['--only-missing'] if a.only_missing else [])])
        after=_run_json(audit.main,['--scope',a.scope,'--sections',*a.sections,'--json'])
        delta=_delta(before,after,a.sections)
        for k,v in delta.items(): total_delta[k]=total_delta.get(k,0)+v
        warning=None
        err_count=int((phase_sections.get('by_status',{}) or {}).get('error',0))+int((phase_summaries.get('by_source_status',{}) or {}).get('error',0))
        timeout_count=0
        section_delta_sum=sum(delta.get(f"sections_{s.replace('.','_')}",0) for s in a.sections)
        exhausted, known_unavailable = _exhausted_without_candidates(phase_sections, phase_summaries)
        remaining_syncable = int(phase_sections.get('remaining_syncable_candidates') or 0)
        if err_count>0 or timeout_count>0:
            warning={'code':'phase_error_or_timeout','error_count':err_count,'timeout_count':timeout_count}
        elif int((phase_sections.get('by_status',{}) or {}).get('written_not_auditable',0))>0:
            warning={'code':'written_not_auditable','message':'sections wrote rows that are not auditable'}
        elif section_delta_sum==0 and delta.get('summaries_con_resumen',0)==0 and not exhausted and remaining_syncable == 0:
            warning={'code':'no_progress','message':'sections and summaries delta are zero'}

        run_elapsed = time.time()-run_started
        run_obj={'run_number':run_number,'before':before,'phases':{'cima_sections':phase_sections,'summaries':phase_summaries},'after':after,'delta':delta,'clinical_phase_warning':warning,'performance':{'elapsed_seconds':run_elapsed,'error_count':err_count,'timeout_count':timeout_count},'next_action':'continue'}
        cycle_summary={
            'run_number':run_number,
            'delta_summaries':delta.get('summaries_con_resumen',0),
            'delta_sections':section_delta_sum,
            'fully_linked_delta':delta.get('fully_linked_public_detail_ready',0),
            'elapsed_seconds':run_elapsed,
            'next_action':'continue',
        }
        all_runs.append(run_obj)
        final_audit=after
        if warning and _is_blocking_warning(warning):
            next_action='stop_warning'
            run_obj['next_action']=next_action
            cycle_summary['next_action']=next_action
            print(json.dumps({'cycle_summary': cycle_summary}, ensure_ascii=False), flush=True)
            if a.checkpoint_each_run:
                _checkpoint_payload(checkpoint_path, {'runs':all_runs,'final_audit':after,'total_delta':total_delta,'next_action':next_action})
            break
        if exhausted:
            next_action='completed_exhausted' if known_unavailable>0 else 'stop_no_candidates'
            run_obj['next_action']=next_action
            cycle_summary['next_action']=next_action
            print(json.dumps({'cycle_summary': cycle_summary}, ensure_ascii=False), flush=True)
            if a.checkpoint_each_run:
                _checkpoint_payload(checkpoint_path, {'runs':all_runs,'final_audit':after,'total_delta':total_delta,'next_action':next_action})
            break
        if a.stop_on_no_progress and section_delta_sum==0 and delta.get('summaries_con_resumen',0)==0 and int(phase_sections.get('remaining_syncable_candidates') or 0) == 0:
            next_action='stop_no_progress'
            run_obj['next_action']=next_action
            cycle_summary['next_action']=next_action
            print(json.dumps({'cycle_summary': cycle_summary}, ensure_ascii=False), flush=True)
            if a.checkpoint_each_run:
                _checkpoint_payload(checkpoint_path, {'runs':all_runs,'final_audit':after,'total_delta':total_delta,'next_action':next_action})
            break
        print(json.dumps({'cycle_summary': cycle_summary}, ensure_ascii=False), flush=True)
        if a.checkpoint_each_run:
            _checkpoint_payload(checkpoint_path, {'runs':all_runs,'final_audit':after,'total_delta':total_delta,'next_action':'continue'})
        time.sleep(a.sleep_seconds)

    out={'runs':all_runs,'final_audit':final_audit,'total_delta':total_delta,'next_action':next_action}
    log_path = log_path.with_suffix('.json')
    _checkpoint_payload(log_path, out)
    out['runtime_log_path']=str(log_path)
    print(json.dumps(out,ensure_ascii=False,indent=2 if a.json_output else None))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
