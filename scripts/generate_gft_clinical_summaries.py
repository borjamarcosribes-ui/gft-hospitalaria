#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime, timezone
from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_clinical_summary_service import build_clinical_summary
from app.services.gft_clinical_pipeline_service import TARGET_SECTIONS


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
    p.add_argument('--cn', action='append', default=[])
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.dry_run and not args.confirm_write:
        raise SystemExit('Safe abort: requiere --dry-run o --confirm-write.')
    if args.confirm_write and args.limit is None and not args.cn:
        raise SystemExit('Para escritura real indique --limit o --cn.')
    with SessionLocal() as db:
        base_cns = args.cn or [r.cn for r in db.query(CimaMedicamentoCache.cn).order_by(CimaMedicamentoCache.cn).limit(args.limit or 999999).all()]
        processed = written = skipped_existing = 0
        by_source = Counter()
        examples = []
        for cn in base_cns:
            processed += 1
            current = db.get(GftClinicalSummaryCache, cn)
            if args.only_missing and not args.force and current and current.source_status in {'ok','partial'}:
                skipped_existing += 1
                continue
            cima = db.get(CimaMedicamentoCache, cn)
            has_cima_ok = bool(cima and cima.sync_status == 'ok')
            has_nregistro = bool(cima and (cima.nregistro or '').strip())
            rows = db.query(CimaFichaTecnicaCache).filter(CimaFichaTecnicaCache.cn == cn, CimaFichaTecnicaCache.sync_status == 'ok', CimaFichaTecnicaCache.seccion.in_(TARGET_SECTIONS)).all()
            summary = build_clinical_summary({r.seccion: (r.contenido_texto or '') for r in rows}, has_nregistro=has_nregistro, has_cima_ok=has_cima_ok)
            by_source[summary.get('source_status', 'error')] += 1
            if args.dry_run:
                if len(examples) < args.examples:
                    examples.append({'cn': cn, 'source_status': summary.get('source_status')})
                continue
            row = current or GftClinicalSummaryCache(cn=cn)
            row.source_status = summary.get('source_status', 'error')
            row.generated_at = datetime.now(timezone.utc)
            row.source_sections_json = summary.get('source_sections_json')
            row.source_hash = summary.get('source_hash')
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

    out = {'dry_run': args.dry_run, 'confirm_write': args.confirm_write, 'candidate_mode': args.candidate_mode, 'processed': processed, 'written': written, 'would_generate': processed if args.dry_run else None, 'skipped_existing': skipped_existing, 'by_source_status': dict(by_source), 'examples': examples}
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
