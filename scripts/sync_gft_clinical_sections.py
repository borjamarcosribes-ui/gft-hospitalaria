#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.services.cima_segmented_sync_service import sync_cima_segmented_section
from app.services.gft_clinical_pipeline_service import ClinicalPipelineParams, build_clinical_pipeline_dry_run


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--sections', nargs='*', default=['4.1', '4.2', '4.3', '4.4', '4.6'])
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--force', action='store_true')
    p.add_argument('--limit', type=int)
    p.add_argument('--examples', type=int, default=20)
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--confirm-write', action='store_true')
    p.add_argument('--only-missing', action='store_true')
    p.add_argument('--candidate-mode', default='first', choices=['first', 'syncable'])
    p.add_argument('--cn', action='append', default=[])
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.dry_run and not args.confirm_write:
        raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
    if args.confirm_write and args.limit is None and not args.cn:
        raise SystemExit('Para escritura real indique --limit o --cn.')

    with SessionLocal() as db:
        payload = build_clinical_pipeline_dry_run(db, ClinicalPipelineParams(limit=args.limit, examples=args.examples, sections=tuple(args.sections), only_missing=args.only_missing))
        if args.dry_run:
            out = {'dry_run': True, 'confirm_write': False, 'candidate_mode': args.candidate_mode, 'requested_sections': args.sections, **payload['sync_plan']}
            print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
            return 0

        cns = args.cn[:] if args.cn else [e['cn'] for e in payload['sync_plan']['planned_examples']]
        by_status = Counter()
        examples = []
        processed_ops = 0
        for cn in cns:
            cima = db.get(CimaMedicamentoCache, cn)
            if not cima or cima.sync_status != 'ok':
                by_status['skipped_missing_cima_cache'] += 1
                continue
            if not (cima.nregistro or '').strip():
                by_status['skipped_missing_nregistro'] += 1
                continue
            for section in args.sections:
                if args.only_missing:
                    existing = db.query(CimaFichaTecnicaCache).filter(CimaFichaTecnicaCache.cn == cn, CimaFichaTecnicaCache.seccion == section, CimaFichaTecnicaCache.sync_status == 'ok').one_or_none()
                    if existing:
                        by_status['skipped_existing_ok'] += 1
                        continue
                row = sync_cima_segmented_section(db=db, nregistro=cima.nregistro, tipo_documento=1, seccion=section, cn=cn, force=args.force)
                by_status[row.sync_status if row.sync_status in {'ok','not_found','not_segmented','section_unavailable'} else 'error'] += 1
                processed_ops += 1
                if len(examples) < args.examples:
                    examples.append({'cn': cn, 'section': section, 'status': row.sync_status})

    out = {'dry_run': False, 'confirm_write': True, 'requested_sections': args.sections, 'candidate_mode': args.candidate_mode, 'processed_cn': len(cns), 'processed_operations': processed_ops, 'by_status': dict(by_status), 'examples': examples}
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
