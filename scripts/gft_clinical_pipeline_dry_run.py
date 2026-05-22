#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from app.core.database import SessionLocal
from app.services.gft_clinical_pipeline_service import ClinicalPipelineParams, build_clinical_pipeline_dry_run

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--limit', type=int)
    p.add_argument('--examples', type=int, default=20)
    p.add_argument('--sections', nargs='*', default=['4.1','4.2','4.3','4.4','4.6'])
    p.add_argument('--only-missing', action='store_true', default=False)
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--allow-default-db', action='store_true')
    return p.parse_args()

def main()->int:
    args=parse_args()
    if not os.getenv('DATABASE_URL') and not args.allow_default_db:
        raise SystemExit('WARNING: DATABASE_URL no definido. Bloqueado salvo --allow-default-db')
    with SessionLocal() as db:
        payload=build_clinical_pipeline_dry_run(db, ClinicalPipelineParams(limit=args.limit, examples=args.examples, sections=tuple(args.sections), only_missing=args.only_missing))
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
