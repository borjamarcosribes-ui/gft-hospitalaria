#!/usr/bin/env python3
from __future__ import annotations
from scripts._db_guard import ensure_postgresql_database
import argparse, json
from collections import Counter
from datetime import datetime, timezone
from sqlalchemy import and_, or_, text
from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_clinical_summary_service import build_clinical_summary
from app.services.gft_clinical_pipeline_service import TARGET_SECTIONS
from app.services.gft_cn_universe_service import get_cn_universe
from app.services.gft_clinical_sections_auditability import build_auditable_section_scope_filters


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int)
    p.add_argument('--force', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--confirm-write', action='store_true')
    p.add_argument('--json', action='store_true', dest='json_output')
    p.add_argument('--only-missing', action='store_true')
    p.add_argument('--examples', type=int, default=20)
    p.add_argument('--candidate-mode', default='first', choices=['first', 'summary_ready'])
    p.add_argument('--write-missing-source', action='store_true')
    p.add_argument('--scope', default='published', choices=['published','included','pending','imported','all_known'])
    p.add_argument('--cn', action='append', default=[])
    p.add_argument("--allow-default-db", action="store_true")
    return p.parse_args(argv)


def _published_cns(db) -> list[str]:
    rows = db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
    return [str(r["cn"]) for r in rows]


def _summary_ready_cns(db, cns: list[str], prioritize_missing_summary: bool = False) -> tuple[list[str], list[str], list[str], list[str]]:
    if not cns:
        return [], [], [], []

    cima_rows = db.query(CimaMedicamentoCache.cn, CimaMedicamentoCache.nregistro).filter(
        CimaMedicamentoCache.cn.in_(cns),
        CimaMedicamentoCache.sync_status == 'ok',
    ).all()
    cn_to_nregistro = {str(cn): (nregistro or '').strip() for cn, nregistro in cima_rows if (nregistro or '').strip()}
    candidate_cns = [cn for cn in cns if cn in cn_to_nregistro]
    if not candidate_cns:
        return [], [], [], []

    nregistros = sorted({cn_to_nregistro[cn] for cn in candidate_cns})
    audit_rows = db.query(CimaFichaTecnicaCache.cn, CimaFichaTecnicaCache.nregistro).filter(
        CimaFichaTecnicaCache.sync_status == 'ok',
        CimaFichaTecnicaCache.seccion.in_(list(TARGET_SECTIONS)),
        or_(
            CimaFichaTecnicaCache.cn.in_(candidate_cns),
            CimaFichaTecnicaCache.nregistro.in_(nregistros),
        ),
    ).all()
    ready_cns: set[str] = set()
    ready_nregistros: set[str] = set()
    for row_cn, row_nregistro in audit_rows:
        if row_cn:
            ready_cns.add(str(row_cn))
        if row_nregistro:
            ready_nregistros.add(str(row_nregistro).strip())

    existing_ok_partial: set[str] = set()
    if prioritize_missing_summary:
        existing_rows = db.query(GftClinicalSummaryCache.cn).filter(
            GftClinicalSummaryCache.cn.in_(candidate_cns),
            GftClinicalSummaryCache.source_status.in_({'ok', 'partial'}),
        ).all()
        existing_ok_partial = {str(cn) for (cn,) in existing_rows}

    out: list[str] = []
    prioritized_missing: list[str] = []
    skipped_existing_known: list[str] = []
    missing_sections: list[str] = []
    for cn in candidate_cns:
        nregistro = cn_to_nregistro[cn]
        has_sections = cn in ready_cns or nregistro in ready_nregistros
        if not has_sections:
            missing_sections.append(cn)
            continue
        if prioritize_missing_summary and cn in existing_ok_partial:
            skipped_existing_known.append(cn)
            out.append(cn)
            continue
        if prioritize_missing_summary:
            prioritized_missing.append(cn)
        else:
            out.append(cn)

    if prioritize_missing_summary:
        return prioritized_missing + out, out, missing_sections, skipped_existing_known
    return out, [], missing_sections, []


def main(argv=None) -> int:
    args = parse_args(argv)
    ensure_postgresql_database(args.allow_default_db)
    if not args.dry_run and not args.confirm_write:
        raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
    if args.confirm_write and args.limit is None and not args.cn:
        raise SystemExit('Para escritura real indique --limit o --cn.')
    with SessionLocal() as db:
        scope_cns = get_cn_universe(db, args.scope)
        scope_set = set(scope_cns)
        skipped_not_public = 0
        skipped_existing_pool = []
        missing_sections_pool = []
        skipped_existing_known_pool = []
        if args.cn:
            requested_cns = get_cn_universe(db, "explicit", args.cn)
            base_cns = [cn for cn in requested_cns if cn in scope_set]
            skipped_not_public = len(requested_cns) - len(base_cns)
        else:
            candidates = scope_cns
            if args.candidate_mode == 'summary_ready':
                candidates, skipped_existing_pool, missing_sections_pool, skipped_existing_known_pool = _summary_ready_cns(db, candidates, prioritize_missing_summary=args.only_missing and not args.force)
            if args.limit is not None:
                candidates = candidates[: max(0, args.limit)]
            base_cns = candidates

        processed = written = skipped_existing = 0
        by_source = Counter()
        examples = []
        examples_selected_for_summary = []
        examples_skipped_existing = [{'cn': cn} for cn in skipped_existing_pool[: args.examples]]
        examples_missing_sections = [{'cn': cn} for cn in missing_sections_pool[: args.examples]]
        for cn in base_cns:
            current = db.get(GftClinicalSummaryCache, cn)
            if args.only_missing and not args.force and current and current.source_status in {'ok','partial'}:
                skipped_existing += 1
                if len(examples_skipped_existing) < args.examples:
                    examples_skipped_existing.append({'cn': cn})
                continue
            processed += 1
            if len(examples_selected_for_summary) < args.examples:
                examples_selected_for_summary.append({'cn': cn})
            cima = db.get(CimaMedicamentoCache, cn)
            has_cima_ok = bool(cima and cima.sync_status == 'ok')
            has_nregistro = bool(cima and (cima.nregistro or '').strip())
            rows = db.query(CimaFichaTecnicaCache).filter(build_auditable_section_scope_filters([cn], [cima.nregistro if cima else ''], list(TARGET_SECTIONS))).all()
            summary = build_clinical_summary({r.seccion: (r.contenido_texto or '') for r in rows}, has_nregistro=has_nregistro, has_cima_ok=has_cima_ok)
            source_status = summary.get('source_status', 'error')
            by_source[source_status] += 1
            if args.dry_run:
                if len(examples) < args.examples:
                    examples.append({'cn': cn, 'source_status': source_status})
                continue
            if source_status == 'missing_source' and not args.write_missing_source:
                continue
            row = current or GftClinicalSummaryCache(cn=cn)
            row.source_status = source_status
            row.generated_at = datetime.now(timezone.utc)
            row.source_sections_json = summary.get('source_sections_json')
            row.source_hash = summary.get('source_hash')
            row.resumen_general = summary.get('resumen_general')
            row.resumen_indicaciones = summary.get('resumen_indicaciones')
            row.resumen_posologia = summary.get('resumen_posologia')
            row.resumen_ajuste_renal = summary.get('resumen_ajuste_renal')
            row.resumen_ajuste_hepatico = summary.get('resumen_ajuste_hepatico')
            row.resumen_contraindicaciones = summary.get('resumen_contraindicaciones')
            row.resumen_advertencias = summary.get('resumen_advertencias')
            row.resumen_embarazo = summary.get('resumen_embarazo')
            row.resumen_lactancia = summary.get('resumen_lactancia')
            row.resumen_fuente_json = summary.get('resumen_fuente_json')
            row.warnings_json = summary.get('warnings_json')
            if current is None:
                db.add(row)
            written += 1
        if not args.dry_run:
            db.commit()

    out = {'dry_run': args.dry_run, 'confirm_write': args.confirm_write, 'candidate_mode': args.candidate_mode, 'processed': processed, 'written': written, 'would_generate': processed if args.dry_run else None, 'skipped_existing': skipped_existing, 'skipped_not_public': skipped_not_public, 'skipped_existing_known': len(skipped_existing_known_pool), 'by_source_status': dict(by_source), 'examples': examples, 'examples_selected_for_summary': examples_selected_for_summary, 'examples_skipped_existing': examples_skipped_existing, 'examples_missing_sections': examples_missing_sections, 'no_candidates': processed == 0}
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
