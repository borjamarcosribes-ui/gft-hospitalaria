#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from app.core.database import SessionLocal
from app.services.gft_clinical_pipeline_service import ClinicalPipelineParams, build_clinical_pipeline_dry_run

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--sections', nargs='*', default=['4.1','4.2','4.3','4.4','4.6'])
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--force', action='store_true')
    p.add_argument('--limit', type=int)
    p.add_argument('--examples', type=int, default=20)
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--confirm-write', action='store_true')
    p.add_argument('--allow-default-db', action='store_true')
    p.add_argument('--only-missing', action='store_true')
    return p.parse_args()

def main()->int:
    args=parse_args()
    if not os.getenv('DATABASE_URL') and not args.allow_default_db:
        raise SystemExit('WARNING: DATABASE_URL no definido. Bloqueado salvo --allow-default-db')
    if not args.dry_run and not args.confirm_write:
        raise SystemExit('Safe abort: requiere --confirm-write para escritura real.')
    with SessionLocal() as db:
        payload=build_clinical_pipeline_dry_run(db, ClinicalPipelineParams(limit=args.limit, examples=args.examples, sections=tuple(args.sections), only_missing=args.only_missing))
        summary={
            'dry_run': args.dry_run,
            'requested_sections': payload['sync_plan']['requested_sections'],
            'total_publicados': payload['audit']['total_publicados'],
            'total_con_cima_cache_ok': payload['audit']['total_con_cima_cache_ok'],
            'total_con_nregistro': payload['audit']['total_con_nregistro'],
            'would_sync_total': payload['sync_plan']['would_sync_total'],
            'would_sync_by_section': payload['sync_plan']['would_sync_by_section'],
            'skipped_existing_ok_by_section': payload['sync_plan']['skipped_existing_ok_by_section'],
            'skipped_missing_cima_cache': payload['sync_plan']['skipped_missing_cima_cache'],
            'skipped_missing_nregistro': payload['sync_plan']['skipped_missing_nregistro'],
            'planned_examples': payload['sync_plan']['planned_examples'],
            'examples_problematic_cn': sorted(set(payload['audit']['examples_missing_cima_cache']+payload['audit']['examples_missing_nregistro']))[:args.examples],
        }
        if not args.dry_run:
            raise SystemExit('Safe abort: en este PR el flujo clínico es solo dry-run.')
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
