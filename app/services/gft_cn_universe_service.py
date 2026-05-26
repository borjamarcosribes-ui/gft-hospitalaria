from __future__ import annotations

from sqlalchemy import text

VALID_SCOPES = {"published", "included", "pending", "imported", "all_known", "explicit", "state"}


def normalize_cn_value(value: object | None) -> str | None:
    if value is None:
        return None
    cn = str(value).strip()
    return cn or None


def _unique_sorted(values: list[object | None]) -> list[str]:
    cleaned = {cn for v in values if (cn := normalize_cn_value(v))}
    return sorted(cleaned)


def get_cn_universe(db, scope: str = "published", explicit_cn: list[str] | None = None) -> list[str]:
    explicit_cn = explicit_cn or []
    if explicit_cn:
        return _unique_sorted(explicit_cn)
    if scope == "state":
        scope = "included"
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope: {scope}")

    if scope == "published":
        rows = db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
        return _unique_sorted([r["cn"] for r in rows])
    if scope == "included":
        rows = db.execute(text("SELECT cn FROM gft_estado_presentacion WHERE estado_gft='incluido' ORDER BY cn")).mappings().all()
        return _unique_sorted([r["cn"] for r in rows])
    if scope == "pending":
        rows = db.execute(text("SELECT cn FROM gft_estado_presentacion WHERE estado_gft='pendiente_revision' ORDER BY cn")).mappings().all()
        return _unique_sorted([r["cn"] for r in rows])
    if scope == "imported":
        rows = db.execute(text("SELECT cn_normalized AS cn FROM import_row_staging WHERE cn_normalized IS NOT NULL ORDER BY cn_normalized")).mappings().all()
        return _unique_sorted([r["cn"] for r in rows])
    if scope == "all_known":
        rows = db.execute(text(
            """
            SELECT cn FROM gft_estado_presentacion
            UNION ALL
            SELECT cn_normalized AS cn FROM import_row_staging
            UNION ALL
            SELECT cn FROM cima_medicamento_cache
            UNION ALL
            SELECT cn FROM bifimed_cache
            """
        )).mappings().all()
        return _unique_sorted([r["cn"] for r in rows])
    return []
