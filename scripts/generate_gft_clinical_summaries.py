#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from app.core.database import SessionLocal
from app.services.gft_clinical_pipeline_service import ClinicalPipelineParams, build_clinical_pipeline_dry_run

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--limit', type=int)
    p.add_argument('--cn')
    p.add_argument('--force', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--confirm-write', action='store_true')
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--only-missing', action='store_true')
    p.add_argument('--examples', type=int, default=20)
    return p.parse_args()

def main()->int:
    args=parse_args()
    if not args.dry_run and not args.confirm_write:
        raise SystemExit('Safe abort: requiere --confirm-write para escritura real.')
    with SessionLocal() as db:
        payload=build_clinical_pipeline_dry_run(db, ClinicalPipelineParams(limit=args.limit, examples=args.examples, only_missing=args.only_missing))
    s=payload['summary_plan']
    out={
        'dry_run': args.dry_run,
        'processed': s['processed'],
        'would_generate': s['would_generate'],
        'skipped_unchanged': s['skipped_unchanged'],
        'skipped_only_missing_existing': s['skipped_only_missing_existing'],
        'total_publicados': payload['audit']['total_publicados'],
        'source_status_counts': s['source_status_counts'],
        'examples': s['examples'],
    }
    if not args.dry_run:
        raise SystemExit('Safe abort: en este PR el flujo clínico es solo dry-run.')
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0
if __name__=='__main__':
    raise SystemExit(main())
