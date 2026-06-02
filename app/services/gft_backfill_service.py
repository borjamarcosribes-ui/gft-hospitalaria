from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services import bifimed_sync_service, cima_sync_service
from app.services.gft_canonical_payload_service import audit_gft_coverage, build_gft_canonical_payload
from app.services.cima_clinical_extraction_service import (
    NO_INFORMADO as CLINICAL_NO_INFORMADO,
    clinical_extraction_hash,
    extract_clinical_fields_from_cima_row,
)
from app.services.normalization_service import NormalizationError, normalize_cn, normalize_cn_or_raise

BACKFILL_STATUSES = {
    "pending",
    "skipped_existing",
    "skipped",
    "success",
    "not_found",
    "no_data",
    "error",
    "unchanged",
}
SOURCE_CHOICES = {"cima", "bifimed", "clinical", "all"}
MODE_CHOICES = {"dry-run", "run"}
SCOPE_GFT_PUBLICADA = "gft-publicada"
SCOPE_ALL_IMPORTED = "all-imported"
SCOPE_EXCEL_MASTER = "excel-master"
SCOPE_CHOICES = {SCOPE_GFT_PUBLICADA, SCOPE_EXCEL_MASTER, SCOPE_ALL_IMPORTED}
MASTER_SCOPES = {SCOPE_EXCEL_MASTER, SCOPE_ALL_IMPORTED}
DEFAULT_SLEEP_SECONDS = 0.5
RETRYABLE_SYNC_STATUSES = {"error", "timeout"}
NON_RETRYABLE_TERMINAL_STATUSES = {"success", "not_found", "no_data", "unchanged", "skipped_existing", "skipped"}

_CIMA_USEFUL_FIELDS = (
    "nregistro",
    "nombre",
    "presentacion",
    "forma_farmaceutica",
    "forma_farmaceutica_simplificada",
    "vias_administracion_json",
    "atc_json",
    "principios_activos_json",
    "documentos_json",
    "url_ficha_tecnica",
    "url_prospecto",
    "raw_data",
)
_BIFIMED_USEFUL_FIELDS = (
    "situacion_financiacion",
    "condiciones_financiacion_restringidas",
    "condiciones_especiales_financiacion",
    "estado_nomenclator",
    "aportacion_usuario",
    "subgrupo_atc",
    "detalle_financiacion_json",
    "indicaciones_autorizadas_json",
    "raw_data",
)
_CLINICAL_USEFUL_FIELDS = (
    "resumen_general",
    "resumen_indicaciones",
    "resumen_posologia",
    "resumen_ajuste_renal",
    "resumen_ajuste_hepatico",
    "resumen_contraindicaciones",
    "resumen_advertencias",
    "resumen_embarazo",
    "resumen_lactancia",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _snapshot(row: Any | None, fields: Iterable[str]) -> dict[str, Any]:
    field_list = list(fields)
    if row is None:
        return {field: None for field in field_list}
    return {field: getattr(row, field, None) for field in field_list}


def _useful_fields(snapshot: dict[str, Any]) -> set[str]:
    return {field for field, value in snapshot.items() if _has_value(value)}


def _is_retryable_sync_status(sync_status: str | None) -> bool:
    return bool(sync_status and sync_status in RETRYABLE_SYNC_STATUSES)


def _has_cima_cache_util(row: CimaMedicamentoCache | None) -> bool:
    return bool(row and row.sync_status == "ok" and _useful_fields(_snapshot(row, _CIMA_USEFUL_FIELDS)))


def _has_bifimed_cache_util(row: BifimedCache | None) -> bool:
    return bool(row and row.sync_status == "ok" and _useful_fields(_snapshot(row, _BIFIMED_USEFUL_FIELDS)))


def _restore_useful_fields(row: Any, previous: dict[str, Any]) -> list[str]:
    restored: list[str] = []
    for field, value in previous.items():
        if _has_value(value) and not _has_value(getattr(row, field, None)):
            setattr(row, field, value)
            restored.append(field)
    return restored


@dataclass(frozen=True)
class BackfillCandidate:
    cn: str
    source: str
    nombre: str | None = None
    reason: str = "missing"

    @property
    def key(self) -> str:
        return f"{self.source}:{self.cn}"


def expand_sources(source: str, *, scope: str = SCOPE_GFT_PUBLICADA) -> list[str]:
    if source == "all":
        # Clinical summaries are derived from published-GFT payload/section coverage. For
        # master-import scopes, keep the mass cache operation limited to source caches.
        if scope in MASTER_SCOPES:
            return ["cima", "bifimed"]
        return ["cima", "bifimed", "clinical"]
    return [source]


def _has_bifimed_indications(row: BifimedCache | None) -> bool:
    if row is None:
        return False
    if _has_value(row.indicaciones_autorizadas_json):
        return True
    detalle = row.detalle_financiacion_json
    if isinstance(detalle, dict):
        return _has_value(detalle.get("indicaciones"))
    return False


def _has_cima_incomplete_cache(row: CimaMedicamentoCache | None) -> bool:
    if row is None:
        return False
    if row.sync_status != "ok":
        return True
    return not _has_value(row.url_ficha_tecnica)


def _master_universe_rows(db: Session) -> tuple[list[dict[str, Any]], int]:
    rows = db.query(GFTEstadoPresentacion).order_by(GFTEstadoPresentacion.cn).all()
    by_cn: dict[str, dict[str, Any]] = {}
    skipped_invalid_cn = 0
    for row in rows:
        try:
            cn = normalize_cn_or_raise(row.cn)
        except NormalizationError:
            skipped_invalid_cn += 1
            continue
        by_cn.setdefault(
            cn,
            {
                "cn": cn,
                "nombre": row.nombre_comercial_importado or row.nemonico,
                "estado_gft": row.estado_gft,
                "estado_editorial": row.estado_editorial,
            },
        )
    return [by_cn[cn] for cn in sorted(by_cn)], skipped_invalid_cn


def _select_published_gft_candidates(
    db: Session,
    *,
    source: str,
    only_missing: bool,
    include_incomplete: bool,
    force: bool,
    cn: str | None,
) -> list[BackfillCandidate]:
    requested_sources = expand_sources(source, scope=SCOPE_GFT_PUBLICADA)
    rows: list[dict[str, Any]] = []
    if cn:
        payload = build_gft_canonical_payload(db, cn)
        if payload is None:
            return []
        rows = [payload]
    else:
        rows = audit_gft_coverage(db).get("items", [])

    candidates: list[BackfillCandidate] = []
    for item in rows:
        item_cn = normalize_cn(item.get("cn"))
        if not item_cn:
            continue
        payload = item if "estado_resumen_clinico" in item else build_gft_canonical_payload(db, item_cn)
        if payload is None:
            continue
        nombre = payload.get("nombre_comercial") or payload.get("nombre")
        missing_fields = set(payload.get("campos_faltantes") or [])
        for item_source in requested_sources:
            reason: str | None = None
            if item_source == "cima":
                cache = db.get(CimaMedicamentoCache, item_cn)
                if not only_missing or force:
                    reason = "force_or_full_scan"
                elif cache is None:
                    reason = "sin_cima" if payload.get("estado_cima") != "disponible" else None
                elif _is_retryable_sync_status(cache.sync_status):
                    reason = "cima_error_reintentable"
                elif cache.sync_status == "not_found":
                    reason = None
                elif payload.get("estado_cima") != "disponible" and cache.sync_status != "ok":
                    reason = "sin_cima"
                elif include_incomplete and "indicaciones_ficha_tecnica" in missing_fields:
                    reason = "sin_indicaciones_cima"
            elif item_source == "bifimed":
                cache = db.get(BifimedCache, item_cn)
                if not only_missing or force:
                    reason = "force_or_full_scan"
                elif cache is None:
                    reason = "sin_bifimed_cache" if not payload.get("bifimed_cache_presente") else None
                elif _is_retryable_sync_status(cache.sync_status):
                    reason = "bifimed_error_reintentable"
                elif cache.sync_status == "not_found":
                    reason = None
                elif not payload.get("bifimed_cache_presente") and cache.sync_status != "ok":
                    reason = "sin_bifimed_cache"
                elif include_incomplete and not payload.get("indicaciones_bifimed"):
                    reason = "bifimed_sin_indicaciones"
            elif item_source == "clinical":
                if not only_missing or force:
                    reason = "force_or_full_scan"
                elif payload.get("estado_resumen_clinico") in {None, "", "no_informado"}:
                    reason = "sin_resumen_clinico"
                elif include_incomplete and payload.get("estado_resumen_clinico") not in {"ok", "partial"}:
                    reason = "resumen_clinico_incompleto"
            if reason:
                candidates.append(BackfillCandidate(cn=item_cn, source=item_source, nombre=nombre, reason=reason))
    return candidates


def _select_master_candidates(
    db: Session,
    *,
    source: str,
    only_missing: bool,
    include_incomplete: bool,
    force: bool,
    cn: str | None,
) -> list[BackfillCandidate]:
    requested_sources = expand_sources(source, scope=SCOPE_ALL_IMPORTED)
    rows, _skipped_invalid_cn = _master_universe_rows(db)
    if cn:
        try:
            requested_cn = normalize_cn_or_raise(cn)
        except NormalizationError:
            return []
        rows = [row for row in rows if row["cn"] == requested_cn]

    cima_by_cn = {row.cn: row for row in db.query(CimaMedicamentoCache).all()}
    bifimed_by_cn = {row.cn: row for row in db.query(BifimedCache).all()}

    candidates: list[BackfillCandidate] = []
    for item in rows:
        item_cn = item["cn"]
        nombre = item.get("nombre")
        for item_source in requested_sources:
            reason: str | None = None
            if item_source == "cima":
                cache = cima_by_cn.get(item_cn)
                if not only_missing or force:
                    reason = "force_or_full_scan"
                elif cache is None:
                    reason = "sin_cima"
                elif _is_retryable_sync_status(cache.sync_status):
                    reason = "cima_error_reintentable"
                elif cache.sync_status == "not_found":
                    reason = None
                elif include_incomplete and _has_cima_incomplete_cache(cache):
                    reason = "cima_cache_incompleto"
            elif item_source == "bifimed":
                cache = bifimed_by_cn.get(item_cn)
                if not only_missing or force:
                    reason = "force_or_full_scan"
                elif cache is None:
                    reason = "sin_bifimed_cache"
                elif _is_retryable_sync_status(cache.sync_status):
                    reason = "bifimed_error_reintentable"
                elif cache.sync_status == "not_found":
                    reason = None
                elif include_incomplete and not _has_bifimed_indications(cache):
                    reason = "bifimed_sin_indicaciones"
            elif item_source == "clinical":
                # Clinical backfill remains scoped to the published-GFT payload.
                reason = None
            if reason:
                candidates.append(BackfillCandidate(cn=item_cn, source=item_source, nombre=nombre, reason=reason))
    return candidates


def select_backfill_candidates(
    db: Session,
    *,
    source: str = "all",
    scope: str = SCOPE_GFT_PUBLICADA,
    only_missing: bool = True,
    include_incomplete: bool = False,
    force: bool = False,
    cn: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[BackfillCandidate]:
    """Select CNs that need enrichment for the requested backfill scope.

    ``gft-publicada`` preserves the existing behavior: only published GFT rows are
    selected from the canonical payload/audit. ``excel-master`` and ``all-imported``
    use the canonical applied import table (``gft_estado_presentacion``) so CIMA and
    BIFIMED cache can be filled for non-published articles without changing GFT
    publication rules.
    """
    if scope not in SCOPE_CHOICES:
        raise ValueError(f"Unsupported scope: {scope}")

    if scope == SCOPE_GFT_PUBLICADA:
        candidates = _select_published_gft_candidates(
            db,
            source=source,
            only_missing=only_missing,
            include_incomplete=include_incomplete,
            force=force,
            cn=cn,
        )
    else:
        candidates = _select_master_candidates(
            db,
            source=source,
            only_missing=only_missing,
            include_incomplete=include_incomplete,
            force=force,
            cn=cn,
        )

    if offset:
        candidates = candidates[max(0, offset) :]
    if limit is not None:
        candidates = candidates[: max(0, limit)]
    return candidates


def _safe_scope_for_path(scope: str) -> str:
    return scope.replace("/", "-")


def default_checkpoint_path(source: str, *, scope: str = SCOPE_GFT_PUBLICADA) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("data/output") / f"backfill_{source}_{_safe_scope_for_path(scope)}_{stamp}.json"


def default_log_path(source: str, *, scope: str = SCOPE_GFT_PUBLICADA) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("data/output") / f"backfill_{source}_{_safe_scope_for_path(scope)}_{stamp}.jsonl"


def build_backfill_coverage_summary(db: Session, *, scope: str) -> dict[str, int]:
    if scope in MASTER_SCOPES:
        rows, skipped_invalid_cn = _master_universe_rows(db)
        cns = [row["cn"] for row in rows]
        cima_by_cn = {row.cn: row for row in db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns)).all()} if cns else {}
        bifimed_by_cn = {row.cn: row for row in db.query(BifimedCache).filter(BifimedCache.cn.in_(cns)).all()} if cns else {}
        total_publicados = sum(1 for row in rows if row.get("estado_gft") == "incluido" and row.get("estado_editorial") == "publicado")
        cima_scope_rows = [cima_by_cn[cn] for cn in cns if cn in cima_by_cn]
        bifimed_scope_rows = [bifimed_by_cn[cn] for cn in cns if cn in bifimed_by_cn]
        return {
            "total_universe": len(cns),
            "total_con_cima_cache": sum(1 for cn in cns if cn in cima_by_cn),
            "total_sin_cima_cache": sum(1 for cn in cns if cn not in cima_by_cn),
            "total_con_cima_cache_util": sum(1 for row in cima_scope_rows if _has_cima_cache_util(row)),
            "total_cima_not_found": sum(1 for row in cima_scope_rows if row.sync_status == "not_found"),
            "total_cima_error": sum(1 for row in cima_scope_rows if _is_retryable_sync_status(row.sync_status)),
            "total_cima_no_data": sum(1 for row in cima_scope_rows if row.sync_status == "ok" and not _has_cima_cache_util(row)),
            "total_con_bifimed_cache": sum(1 for cn in cns if cn in bifimed_by_cn),
            "total_sin_bifimed_cache": sum(1 for cn in cns if cn not in bifimed_by_cn),
            "total_con_bifimed_cache_util": sum(1 for row in bifimed_scope_rows if _has_bifimed_cache_util(row)),
            "total_bifimed_not_found": sum(1 for row in bifimed_scope_rows if row.sync_status == "not_found"),
            "total_bifimed_error": sum(1 for row in bifimed_scope_rows if _is_retryable_sync_status(row.sync_status)),
            "total_bifimed_no_data": sum(1 for row in bifimed_scope_rows if row.sync_status == "ok" and not _has_bifimed_cache_util(row)),
            "total_con_indicaciones_bifimed": sum(1 for row in bifimed_by_cn.values() if _has_bifimed_indications(row)),
            "total_skipped_invalid_cn": skipped_invalid_cn,
            "total_publicados_gft": total_publicados,
            "total_no_publicados": len(cns) - total_publicados,
        }

    audit = audit_gft_coverage(db)
    summary = audit.get("summary", {})
    cns = [normalize_cn(item.get("cn")) for item in audit.get("items", []) if normalize_cn(item.get("cn"))]
    cima_by_cn = {row.cn: row for row in db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns)).all()} if cns else {}
    bifimed_by_cn = {row.cn: row for row in db.query(BifimedCache).filter(BifimedCache.cn.in_(cns)).all()} if cns else {}
    cima_scope_rows = [cima_by_cn[cn] for cn in cns if cn in cima_by_cn]
    bifimed_scope_rows = [bifimed_by_cn[cn] for cn in cns if cn in bifimed_by_cn]
    total_publicados = int(summary.get("total_medicamentos_publicados") or summary.get("total") or len(audit.get("items", [])))
    return {
        "total_universe": total_publicados,
        "total_con_cima_cache": int(summary.get("con_cima") or 0),
        "total_sin_cima_cache": int(summary.get("sin_cima") or 0),
        "total_con_cima_cache_util": sum(1 for row in cima_scope_rows if _has_cima_cache_util(row)),
        "total_cima_not_found": sum(1 for row in cima_scope_rows if row.sync_status == "not_found"),
        "total_cima_error": sum(1 for row in cima_scope_rows if _is_retryable_sync_status(row.sync_status)),
        "total_cima_no_data": sum(1 for row in cima_scope_rows if row.sync_status == "ok" and not _has_cima_cache_util(row)),
        "total_con_bifimed_cache": int(summary.get("con_bifimed_cache") or 0),
        "total_sin_bifimed_cache": int(summary.get("sin_bifimed_cache") or 0),
        "total_con_bifimed_cache_util": sum(1 for row in bifimed_scope_rows if _has_bifimed_cache_util(row)),
        "total_bifimed_not_found": sum(1 for row in bifimed_scope_rows if row.sync_status == "not_found"),
        "total_bifimed_error": sum(1 for row in bifimed_scope_rows if _is_retryable_sync_status(row.sync_status)),
        "total_bifimed_no_data": sum(1 for row in bifimed_scope_rows if row.sync_status == "ok" and not _has_bifimed_cache_util(row)),
        "total_con_indicaciones_bifimed": int(summary.get("con_indicaciones_bifimed") or 0),
        "total_skipped_invalid_cn": 0,
        "total_publicados_gft": total_publicados,
        "total_no_publicados": 0,
    }


def initial_checkpoint(
    *,
    source: str,
    scope: str,
    mode: str,
    only_missing: bool,
    include_incomplete: bool,
    candidates: list[BackfillCandidate],
    coverage_summary: dict[str, int],
) -> dict[str, Any]:
    return {
        "started_at": utc_now_iso(),
        "finished_at": None,
        "source": source,
        "scope": scope,
        "mode": mode,
        "only_missing": only_missing,
        "include_incomplete": include_incomplete,
        "total_candidates": len(candidates),
        **coverage_summary,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "last_cn": None,
        "items": {
            candidate.key: {
                "cn": candidate.cn,
                "source": candidate.source,
                "scope": scope,
                "nombre": candidate.nombre,
                "status": "pending",
                "reason": candidate.reason,
            }
            for candidate in candidates
        },
    }


def load_checkpoint(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(checkpoint, fh, ensure_ascii=False, indent=2, default=str)
    tmp_path.replace(path)


def merge_resume_checkpoint(
    checkpoint: dict[str, Any],
    candidates: list[BackfillCandidate],
    *,
    source: str,
    scope: str,
    mode: str,
    only_missing: bool,
    include_incomplete: bool,
    coverage_summary: dict[str, int],
) -> dict[str, Any]:
    checkpoint.setdefault("started_at", utc_now_iso())
    checkpoint["finished_at"] = None
    checkpoint["source"] = checkpoint.get("source") or source
    checkpoint["scope"] = scope
    checkpoint["mode"] = mode
    checkpoint["only_missing"] = only_missing
    checkpoint["include_incomplete"] = include_incomplete
    checkpoint["total_candidates"] = len(candidates)
    checkpoint.update(coverage_summary)
    items = checkpoint.setdefault("items", {})
    for candidate in candidates:
        items.setdefault(
            candidate.key,
            {
                "cn": candidate.cn,
                "source": candidate.source,
                "scope": scope,
                "nombre": candidate.nombre,
                "status": "pending",
                "reason": candidate.reason,
            },
        )
    return checkpoint


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def audit_snapshot(db: Session, path: Path) -> dict[str, Any]:
    result = audit_gft_coverage(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, default=str)
    return result


def audit_path(kind: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("data/output") / f"backfill_audit_{kind}_{stamp}.json"


def calculate_audit_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    if not before or not after:
        return {}
    before_summary = before.get("summary", {})
    after_summary = after.get("summary", {})
    keys = sorted(set(before_summary) | set(after_summary))
    return {
        key: {
            "before": int(before_summary.get(key) or 0),
            "after": int(after_summary.get(key) or 0),
            "delta": int(after_summary.get(key) or 0) - int(before_summary.get(key) or 0),
        }
        for key in keys
    }


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [field for field, old in before.items() if after.get(field) != old]


def _status_from_sync_status(sync_status: str | None, *, before_useful: set[str], after_useful: set[str]) -> str:
    if sync_status == "ok":
        if not after_useful:
            return "no_data"
        if before_useful == after_useful:
            return "unchanged"
        return "success"
    if sync_status == "not_found":
        return "not_found"
    if _is_retryable_sync_status(sync_status):
        return "error"
    return "error"


def _existing_complete(db: Session, candidate: BackfillCandidate) -> bool:
    payload = build_gft_canonical_payload(db, candidate.cn)
    if payload is None:
        return False
    missing_fields = set(payload.get("campos_faltantes") or [])
    if candidate.source == "cima":
        return payload.get("estado_cima") == "disponible" and "indicaciones_ficha_tecnica" not in missing_fields
    if candidate.source == "bifimed":
        return bool(payload.get("bifimed_cache_presente")) and bool(payload.get("indicaciones_bifimed"))
    if candidate.source == "clinical":
        return payload.get("estado_resumen_clinico") in {"ok", "partial"}
    return False


def _run_cima(db: Session, candidate: BackfillCandidate, *, force: bool) -> tuple[str, list[str], str]:
    existing = db.get(CimaMedicamentoCache, candidate.cn)
    before = _snapshot(existing, _CIMA_USEFUL_FIELDS)
    before_useful = _useful_fields(before)
    row = cima_sync_service.sync_cn(db, candidate.cn, force=force)
    restored = _restore_useful_fields(row, before)
    if restored:
        db.commit()
    after = _snapshot(row, _CIMA_USEFUL_FIELDS)
    status = _status_from_sync_status(row.sync_status, before_useful=before_useful, after_useful=_useful_fields(after))
    changed = _changed_fields(before, after)
    if restored and status in {"success", "no_data"}:
        status = "unchanged"
    message = f"cima sync_status={row.sync_status}"
    if restored:
        message += f"; restored useful fields: {', '.join(restored)}"
    return status, changed, message


def _run_bifimed(db: Session, candidate: BackfillCandidate, *, force: bool) -> tuple[str, list[str], str]:
    existing = db.get(BifimedCache, candidate.cn)
    before = _snapshot(existing, _BIFIMED_USEFUL_FIELDS)
    before_useful = _useful_fields(before)
    row = bifimed_sync_service.sync_bifimed_cn(db, candidate.cn, force=force)
    restored = _restore_useful_fields(row, before)
    if restored:
        db.commit()
    after = _snapshot(row, _BIFIMED_USEFUL_FIELDS)
    status = _status_from_sync_status(row.sync_status, before_useful=before_useful, after_useful=_useful_fields(after))
    changed = _changed_fields(before, after)
    if restored and status in {"success", "no_data"}:
        status = "unchanged"
    message = f"bifimed sync_status={row.sync_status}"
    if restored:
        message += f"; restored useful fields: {', '.join(restored)}"
    return status, changed, message


def _clinical_text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == CLINICAL_NO_INFORMADO:
        return None
    return text


def _run_clinical(db: Session, candidate: BackfillCandidate, *, force: bool) -> tuple[str, list[str], str]:
    current = db.get(GftClinicalSummaryCache, candidate.cn)
    before = _snapshot(current, (*_CLINICAL_USEFUL_FIELDS, "source_status", "source_hash"))
    before_useful = _useful_fields({field: before.get(field) for field in _CLINICAL_USEFUL_FIELDS})
    if current and not force and current.source_status in {"ok", "partial"}:
        return "skipped_existing", [], "clinical summary already available"

    cima = db.get(CimaMedicamentoCache, candidate.cn)
    result = extract_clinical_fields_from_cima_row(cima)
    source_status = result.status
    if source_status == "no_data" and before_useful:
        return "unchanged", [], "empty clinical source; preserved existing summary"

    row = current or GftClinicalSummaryCache(cn=candidate.cn)

    def new_or_existing(new_value: str | None, field: str) -> str | None:
        value = _clinical_text_or_none(new_value)
        if value is not None:
            return value
        previous = before.get(field)
        if _has_value(previous):
            return previous
        return None

    row.source_status = source_status
    row.generated_at = datetime.now(timezone.utc)
    row.source_sections_json = result.extracted_sections
    row.source_hash = clinical_extraction_hash(result)
    row.resumen_general = None
    row.resumen_indicaciones = new_or_existing(result.indicaciones_ficha_tecnica, "resumen_indicaciones")
    row.resumen_posologia = new_or_existing(None, "resumen_posologia")
    row.resumen_ajuste_renal = new_or_existing(result.ajuste_insuficiencia_renal, "resumen_ajuste_renal")
    row.resumen_ajuste_hepatico = new_or_existing(result.ajuste_insuficiencia_hepatica, "resumen_ajuste_hepatico")
    row.resumen_contraindicaciones = new_or_existing(None, "resumen_contraindicaciones")
    row.resumen_advertencias = new_or_existing(None, "resumen_advertencias")
    row.resumen_embarazo = new_or_existing(result.precauciones_embarazo, "resumen_embarazo")
    row.resumen_lactancia = new_or_existing(result.precauciones_lactancia, "resumen_lactancia")
    row.resumen_fuente_json = result.to_summary_source()
    row.warnings_json = result.warnings
    row.error_message = result.error
    if current is None:
        db.add(row)
    db.commit()
    after = _snapshot(row, (*_CLINICAL_USEFUL_FIELDS, "source_status", "source_hash"))
    after_useful = _useful_fields({field: after.get(field) for field in _CLINICAL_USEFUL_FIELDS})
    if source_status in {"ok", "partial"} and after_useful:
        status = "success" if before != after else "unchanged"
    elif source_status == "no_data":
        status = "no_data"
    else:
        status = "error"
    message = f"clinical source_status={source_status}"
    if source_status == "partial":
        message += "; clinical partial extraction"
    if result.error:
        message += f"; error={result.error[:120]}"
    return status, _changed_fields(before, after), message


def execute_candidate(db: Session, candidate: BackfillCandidate, *, mode: str, only_missing: bool, force: bool) -> tuple[str, list[str], str]:
    if mode == "dry-run":
        return "pending", [], f"dry-run candidate reason={candidate.reason}"
    if only_missing and not force and _existing_complete(db, candidate):
        return "skipped_existing", [], "complete data already available; skipped without --force"
    if candidate.source == "cima":
        return _run_cima(db, candidate, force=force)
    if candidate.source == "bifimed":
        return _run_bifimed(db, candidate, force=force)
    if candidate.source == "clinical":
        return _run_clinical(db, candidate, force=force)
    raise ValueError(f"Unsupported source: {candidate.source}")


def _is_failure(status: str) -> bool:
    return status == "error"


def recompute_checkpoint_counts(checkpoint: dict[str, Any]) -> None:
    counts = Counter(item.get("status", "pending") for item in checkpoint.get("items", {}).values())
    checkpoint["succeeded"] = counts["success"]
    checkpoint["failed"] = counts["error"]
    checkpoint["skipped"] = counts["skipped_existing"] + counts["skipped"]
    checkpoint["processed"] = sum(counts[status] for status in BACKFILL_STATUSES if status != "pending")


def run_backfill(
    db: Session,
    *,
    source: str,
    mode: str = "dry-run",
    scope: str = SCOPE_GFT_PUBLICADA,
    limit: int | None = None,
    offset: int = 0,
    cn: str | None = None,
    resume: bool = False,
    checkpoint_path: Path | None = None,
    log_path: Path | None = None,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    only_missing: bool = True,
    force: bool = False,
    stop_on_error: bool = False,
    audit_before: bool = False,
    audit_after: bool = False,
    include_incomplete: bool = False,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    candidates = select_backfill_candidates(
        db,
        source=source,
        scope=scope,
        only_missing=only_missing,
        include_incomplete=include_incomplete,
        force=force,
        cn=cn,
        limit=limit,
        offset=offset,
    )
    checkpoint_path = checkpoint_path or default_checkpoint_path(source, scope=scope)
    log_path = log_path or default_log_path(source, scope=scope)
    coverage_summary = build_backfill_coverage_summary(db, scope=scope)

    before_audit = None
    before_path = None
    if audit_before:
        before_path = audit_path("before")
        before_audit = audit_snapshot(db, before_path)

    if resume and checkpoint_path.exists():
        checkpoint = merge_resume_checkpoint(
            load_checkpoint(checkpoint_path),
            candidates,
            source=source,
            scope=scope,
            mode=mode,
            only_missing=only_missing,
            include_incomplete=include_incomplete,
            coverage_summary=coverage_summary,
        )
    else:
        checkpoint = initial_checkpoint(
            source=source,
            scope=scope,
            mode=mode,
            only_missing=only_missing,
            include_incomplete=include_incomplete,
            candidates=candidates,
            coverage_summary=coverage_summary,
        )
    write_checkpoint(checkpoint_path, checkpoint)

    stopped = False
    for idx, candidate in enumerate(candidates):
        item = checkpoint["items"].setdefault(candidate.key, {"cn": candidate.cn, "source": candidate.source, "status": "pending"})
        if resume and item.get("status") in NON_RETRYABLE_TERMINAL_STATUSES:
            continue
        started = time.perf_counter()
        status = "error"
        changed_fields: list[str] = []
        message = ""
        error = None
        try:
            status, changed_fields, message = execute_candidate(db, candidate, mode=mode, only_missing=only_missing, force=force)
        except Exception as exc:  # noqa: BLE001 - logged and optionally stops operator-controlled backfill
            db.rollback()
            error = f"{type(exc).__name__}: {exc}"[:500]
            message = "candidate failed"
            status = "error"
        duration_ms = int((time.perf_counter() - started) * 1000)
        item.update(
            {
                "cn": candidate.cn,
                "source": candidate.source,
                "scope": scope,
                "nombre": candidate.nombre,
                "status": status,
                "reason": candidate.reason,
                "message": message,
                "changed_fields": changed_fields,
                "error": error,
                "updated_at": utc_now_iso(),
            }
        )
        checkpoint["last_cn"] = candidate.cn
        recompute_checkpoint_counts(checkpoint)
        write_checkpoint(checkpoint_path, checkpoint)
        append_jsonl(
            log_path,
            {
                "timestamp": utc_now_iso(),
                "cn": candidate.cn,
                "nombre": candidate.nombre,
                "source": candidate.source,
                "scope": scope,
                "action": "dry_run" if mode == "dry-run" else "sync",
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
                "changed_fields": changed_fields or None,
                "reason": candidate.reason,
                "error": error,
            },
        )
        if stop_on_error and _is_failure(status):
            stopped = True
            break
        if idx < len(candidates) - 1 and sleep_seconds > 0:
            sleeper(sleep_seconds)

    after_audit = None
    after_path = None
    if audit_after:
        after_path = audit_path("after")
        after_audit = audit_snapshot(db, after_path)

    checkpoint["finished_at"] = utc_now_iso()
    recompute_checkpoint_counts(checkpoint)
    write_checkpoint(checkpoint_path, checkpoint)
    return {
        "source": source,
        "scope": scope,
        "mode": mode,
        "only_missing": only_missing,
        "include_incomplete": include_incomplete,
        "force": force,
        "total_candidates": len(candidates),
        **coverage_summary,
        "checkpoint_path": str(checkpoint_path),
        "log_path": str(log_path),
        "audit_before_path": str(before_path) if before_path else None,
        "audit_after_path": str(after_path) if after_path else None,
        "audit_delta": calculate_audit_delta(before_audit, after_audit),
        "stopped_on_error": stopped,
        "checkpoint": checkpoint,
    }
