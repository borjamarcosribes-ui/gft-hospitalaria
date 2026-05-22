from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_clinical_summary_service import build_clinical_summary

TARGET_SECTIONS = ("4.1", "4.2", "4.3", "4.4", "4.6")

@dataclass
class ClinicalPipelineParams:
    limit: int | None = None
    examples: int = 20
    sections: tuple[str, ...] = TARGET_SECTIONS
    only_missing: bool = True


def _non_empty(value: str | None) -> bool:
    return bool((value or "").strip())


def build_clinical_pipeline_dry_run(db: Session, params: ClinicalPipelineParams) -> dict:
    sections = tuple(s for s in params.sections if s in TARGET_SECTIONS) or TARGET_SECTIONS
    rows = db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
    total_publicados = len(rows)
    cns = [r["cn"] for r in rows]
    considered = cns[: max(0, params.limit)] if params.limit is not None else cns

    cima_by_cn = {row.cn: row for row in db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns)).all()} if cns else {}

    total_con_cima_cache_ok = sum(1 for cn in cns if cn in cima_by_cn and cima_by_cn[cn].sync_status == "ok")
    total_con_nregistro = sum(1 for cn in cns if cn in cima_by_cn and cima_by_cn[cn].sync_status == "ok" and _non_empty(cima_by_cn[cn].nregistro))

    coverage = {s: set() for s in TARGET_SECTIONS}
    if cns:
        for row in db.query(CimaFichaTecnicaCache.cn, CimaFichaTecnicaCache.seccion).filter(
            CimaFichaTecnicaCache.cn.in_(cns),
            CimaFichaTecnicaCache.sync_status == "ok",
            CimaFichaTecnicaCache.seccion.in_(TARGET_SECTIONS),
            CimaFichaTecnicaCache.contenido_texto.is_not(None),
            text("trim(contenido_texto) <> ''"),
        ).all():
            coverage[row.seccion].add(row.cn)

    missing_by_section = {s: sorted(set(cns) - coverage[s])[: params.examples] for s in TARGET_SECTIONS}
    missing_cima = [cn for cn in cns if cn not in cima_by_cn or cima_by_cn[cn].sync_status != "ok"]
    missing_nregistro = [cn for cn in cns if cn in cima_by_cn and cima_by_cn[cn].sync_status == "ok" and not _non_empty(cima_by_cn[cn].nregistro)]

    would_sync_total = 0
    would_sync_by_section = {s: 0 for s in sections}
    skipped_existing_ok = {s: 0 for s in sections}
    skipped_missing_cima_cache = 0
    skipped_missing_nregistro = 0
    planned_examples = []

    for cn in considered:
        c = cima_by_cn.get(cn)
        if not c or c.sync_status != "ok":
            skipped_missing_cima_cache += 1
            continue
        if not _non_empty(c.nregistro):
            skipped_missing_nregistro += 1
            continue
        for section in sections:
            has_ok = cn in coverage[section]
            if params.only_missing and has_ok:
                skipped_existing_ok[section] += 1
                continue
            would_sync_total += 1
            would_sync_by_section[section] += 1
            if len(planned_examples) < params.examples:
                planned_examples.append({"cn": cn, "section": section})

    source_status_counts = {k: 0 for k in ["ok", "partial", "missing_cima_cache", "missing_nregistro", "missing_sections", "no_sections", "error"]}
    current_by_cn = {row.cn: row for row in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(considered)).all()} if considered else {}
    processed = 0
    would_generate = 0
    skipped_unchanged = 0
    skipped_only_missing_existing = 0
    examples = {k: [] for k in ["would_generate", "skipped_unchanged", "missing_cima_cache", "missing_nregistro", "missing_sections", "partial", "ok"]}

    for cn in considered:
        processed += 1
        current = current_by_cn.get(cn)
        if params.only_missing and current and current.source_status in ("ok", "partial"):
            skipped_only_missing_existing += 1
            continue
        c = cima_by_cn.get(cn)
        has_cima_ok = bool(c and c.sync_status == "ok")
        has_nregistro = bool(c and _non_empty(c.nregistro))
        rows_ft = db.query(CimaFichaTecnicaCache).filter(CimaFichaTecnicaCache.cn == cn, CimaFichaTecnicaCache.seccion.in_(TARGET_SECTIONS), CimaFichaTecnicaCache.sync_status == "ok").all()
        data = build_clinical_summary({r.seccion: (r.contenido_texto or "") for r in rows_ft}, has_nregistro=has_nregistro, has_cima_ok=has_cima_ok)
        status = data.get("source_status", "error")
        source_status_counts[status if status in source_status_counts else "error"] += 1
        if len(examples.get(status, [])) < params.examples:
            examples.setdefault(status, []).append(cn)
        if current and current.source_hash == data["source_hash"] and current.source_status in ("ok", "partial"):
            skipped_unchanged += 1
            if len(examples["skipped_unchanged"]) < params.examples:
                examples["skipped_unchanged"].append(cn)
            continue
        would_generate += 1
        if len(examples["would_generate"]) < params.examples:
            examples["would_generate"].append(cn)

    blockers = []
    if skipped_missing_cima_cache:
        blockers.append("Falta CIMA cache OK en parte del universo publicado")
    if skipped_missing_nregistro:
        blockers.append("Falta nregistro en parte del universo publicado")

    return {
        "audit": {
            "total_publicados": total_publicados,
            "total_con_cima_cache_ok": total_con_cima_cache_ok,
            "total_con_nregistro": total_con_nregistro,
            "coverage_by_section": {s: len(coverage[s]) for s in TARGET_SECTIONS},
            "examples_missing_by_section": missing_by_section,
            "examples_missing_cima_cache": missing_cima[: params.examples],
            "examples_missing_nregistro": missing_nregistro[: params.examples],
        },
        "sync_plan": {
            "dry_run": True,
            "total_publicados_considerados": len(considered),
            "limit_aplicado": params.limit,
            "requested_sections": list(sections),
            "only_missing": params.only_missing,
            "would_sync_total": would_sync_total,
            "would_sync_by_section": would_sync_by_section,
            "skipped_existing_ok_by_section": skipped_existing_ok,
            "skipped_missing_cima_cache": skipped_missing_cima_cache,
            "skipped_missing_nregistro": skipped_missing_nregistro,
            "planned_examples": planned_examples,
        },
        "summary_plan": {
            "dry_run": True,
            "processed": processed,
            "would_generate": would_generate,
            "skipped_unchanged": skipped_unchanged,
            "skipped_only_missing_existing": skipped_only_missing_existing,
            "source_status_counts": source_status_counts,
            "examples": examples,
        },
        "recommendation": {
            "safe_to_try_small_write_batch": skipped_missing_cima_cache == 0 and skipped_missing_nregistro == 0,
            "suggested_limit": min(20, len(considered)) if considered else 0,
            "reasons": ["Ejecución en modo no destructivo para validar cobertura y bloqueos."],
            "blockers": blockers,
            "next_dry_run_commands": [
                "PYTHONPATH=. python scripts/gft_clinical_pipeline_dry_run.py --limit 20 --only-missing --json",
                "PYTHONPATH=. python scripts/sync_gft_clinical_sections.py --dry-run --limit 20 --only-missing --json",
                "PYTHONPATH=. python scripts/generate_gft_clinical_summaries.py --dry-run --limit 20 --only-missing --json",
            ],
            "future_manual_write_commands": [
                "SOLO TRAS REVISIÓN HUMANA: PYTHONPATH=. python scripts/sync_gft_clinical_sections.py --limit 20 --only-missing --confirm-write",
                "SOLO TRAS REVISIÓN HUMANA: PYTHONPATH=. python scripts/generate_gft_clinical_summaries.py --limit 20 --only-missing --confirm-write",
            ],
        },
        "safety": {
            "read_only": True,
            "writes_enabled": False,
            "source_view": "v_gft_publicada",
            "confirm_write_available_in_this_endpoint": False,
            "warning": "Este módulo no ejecuta escrituras reales. Solo calcula dry-run.",
        },
    }
