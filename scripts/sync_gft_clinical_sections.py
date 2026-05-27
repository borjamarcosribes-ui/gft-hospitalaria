#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.services.cima_segmented_sync_service import sync_cima_segmented_section
from app.services.gft_clinical_pipeline_service import ClinicalPipelineParams, build_clinical_pipeline_dry_run
from app.services.gft_cn_universe_service import get_cn_universe


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
    p.add_argument('--scope', default='published', choices=['published','included','pending','imported','all_known'])
    p.add_argument('--cn', action='append', default=[])
    return p.parse_args(argv)


def _published_cns(db) -> list[str]:
    rows = db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
    return [str(r["cn"]) for r in rows]


def _has_content(row: CimaFichaTecnicaCache | None) -> bool:
    if row is None:
        return False
    return bool((row.contenido_texto or "").strip() or (row.contenido_html or "").strip())


def _find_auditable_row(db, cn: str, section: str) -> CimaFichaTecnicaCache | None:
    return db.query(CimaFichaTecnicaCache).filter(
        CimaFichaTecnicaCache.cn == cn,
        CimaFichaTecnicaCache.seccion == section,
        CimaFichaTecnicaCache.sync_status == 'ok',
        text("trim(coalesce(contenido_texto,''))<>'' OR trim(coalesce(contenido_html,''))<>''"),
    ).one_or_none()


def _candidate_syncable_cns(db, cns: list[str], sections: list[str], only_missing: bool) -> list[str]:
    selected: list[str] = []
    for cn in cns:
        cima = db.get(CimaMedicamentoCache, cn)
        if not cima or cima.sync_status != 'ok':
            continue
        if not (cima.nregistro or '').strip():
            continue
        has_pending = False
        for section in sections:
            existing = db.query(CimaFichaTecnicaCache).filter(
                CimaFichaTecnicaCache.cn == cn,
                CimaFichaTecnicaCache.seccion == section,
                CimaFichaTecnicaCache.sync_status == 'ok',
            ).one_or_none()
            if not only_missing or not _has_content(existing):
                has_pending = True
                break
        if has_pending:
            selected.append(cn)
    return selected


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.dry_run and not args.confirm_write:
        raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
    if args.confirm_write and args.limit is None and not args.cn:
        raise SystemExit('Para escritura real indique --limit o --cn.')

    with SessionLocal() as db:
        published_cns = get_cn_universe(db, args.scope, args.cn)
        if args.cn:
            base_cns = published_cns
        elif args.candidate_mode == 'syncable':
            base_cns = _candidate_syncable_cns(db, published_cns, args.sections, args.only_missing)
            if args.limit is not None:
                base_cns = base_cns[: max(0, args.limit)]
        else:
            base_cns = published_cns[: max(0, args.limit)] if args.limit is not None else published_cns

        payload = build_clinical_pipeline_dry_run(db, ClinicalPipelineParams(limit=None, examples=args.examples, sections=tuple(args.sections), only_missing=args.only_missing))
        if args.candidate_mode == 'syncable':
            planned_examples = []
            would_sync_by_section = {s: 0 for s in args.sections}
            for cn in base_cns:
                for section in args.sections:
                    existing = db.query(CimaFichaTecnicaCache).filter(
                        CimaFichaTecnicaCache.cn == cn,
                        CimaFichaTecnicaCache.seccion == section,
                        CimaFichaTecnicaCache.sync_status == 'ok',
                    ).one_or_none()
                    if args.only_missing and _has_content(existing):
                        continue
                    would_sync_by_section[section] += 1
                    if len(planned_examples) < args.examples:
                        planned_examples.append({'cn': cn, 'section': section})
            payload['sync_plan']['planned_examples'] = planned_examples
            payload['sync_plan']['would_sync_by_section'] = would_sync_by_section
            payload['sync_plan']['would_sync_total'] = sum(would_sync_by_section.values())
            payload['sync_plan']['total_publicados_considerados'] = len(base_cns)
        if args.dry_run:
            out = {'dry_run': True, 'confirm_write': False, 'candidate_mode': args.candidate_mode, 'requested_sections': args.sections, **payload['sync_plan']}
            print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
            return 0

        cns = base_cns
        by_status = Counter()
        examples = []
        examples_written_not_auditable = []
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
                existing = db.query(CimaFichaTecnicaCache).filter(
                    CimaFichaTecnicaCache.cn == cn,
                    CimaFichaTecnicaCache.seccion == section,
                    CimaFichaTecnicaCache.sync_status == 'ok',
                ).one_or_none()
                if args.only_missing and _has_content(existing):
                    by_status['skipped_existing_ok'] += 1
                    continue

                existed_auditable_before_sync = _find_auditable_row(db, cn, section) is not None
                row = sync_cima_segmented_section(db=db, nregistro=cima.nregistro, tipo_documento=1, seccion=section, cn=cn, force=args.force)
                if row.sync_status == 'ok':
                    auditable_row = _find_auditable_row(db, cn, section)
                    if auditable_row is not None:
                        by_status['updated_existing_auditable' if existed_auditable_before_sync else 'written_new_auditable'] += 1
                    else:
                        by_status['written_not_auditable'] += 1
                        if len(examples_written_not_auditable) < args.examples:
                            examples_written_not_auditable.append({
                                'cn': cn,
                                'section': section,
                                'nregistro': cima.nregistro,
                                'row_cn': row.cn,
                                'row_sync_status': row.sync_status,
                                'has_text': bool((row.contenido_texto or '').strip()),
                                'has_html': bool((row.contenido_html or '').strip()),
                            })
                elif row.sync_status in {'section_unavailable'}:
                    by_status['section_unavailable'] += 1
                else:
                    by_status['error'] += 1
                processed_ops += 1
                if len(examples) < args.examples:
                    examples.append({'cn': cn, 'section': section, 'status': row.sync_status})

    out = {'dry_run': False, 'confirm_write': True, 'requested_sections': args.sections, 'candidate_mode': args.candidate_mode, 'processed_cn': len(cns), 'processed_operations': processed_ops, 'by_status': dict(by_status), 'examples': examples, 'examples_written_not_auditable': examples_written_not_auditable}
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
