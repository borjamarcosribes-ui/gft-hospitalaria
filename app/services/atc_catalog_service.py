from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.atc_code import AtcCode

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "atc_titles.json"
_ATC_LEVEL_LENGTHS = {1: 1, 3: 2, 4: 3, 5: 4, 7: 5}


@lru_cache(maxsize=1)
def _seed_records() -> tuple[dict[str, Any], ...]:
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        records = json.load(fh)
    return tuple(
        {
            "code": str(record["code"]).strip().upper(),
            "level": int(record["level"]),
            "title": str(record["title"]).strip(),
            "parent_code": (
                _normalize_atc_code(record.get("parent_code"))
                if record.get("parent_code") is not None
                else None
            ),
        }
        for record in records
        if str(record.get("code") or "").strip() and str(record.get("title") or "").strip()
    )


@lru_cache(maxsize=1)
def _seed_titles_map() -> dict[str, str]:
    return {record["code"]: record["title"] for record in _seed_records()}


@lru_cache(maxsize=1)
def _seed_parent_map() -> dict[str, str | None]:
    return {record["code"]: record["parent_code"] for record in _seed_records()}


@lru_cache(maxsize=1)
def _seed_level_map() -> dict[str, int]:
    return {record["code"]: record["level"] for record in _seed_records()}


def _normalize_atc_code(code: str | None) -> str:
    if code is None:
        return ""
    return "".join(str(code).strip().upper().split())


def infer_atc_level(code: str | None) -> int | None:
    normalized = _normalize_atc_code(code)
    if not normalized:
        return None
    if len(normalized) >= 7:
        return 5
    return _ATC_LEVEL_LENGTHS.get(len(normalized))


def infer_atc_parent_code(code: str | None) -> str | None:
    normalized = _normalize_atc_code(code)
    if len(normalized) >= 7:
        return normalized[:5]
    if len(normalized) == 5:
        return normalized[:4]
    if len(normalized) == 4:
        return normalized[:3]
    if len(normalized) == 3:
        return normalized[:1]
    return None


def _db_catalog_available(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(AtcCode.__tablename__)
    except (OperationalError, ProgrammingError):
        return False


def ensure_atc_catalog_seeded(db: Session) -> None:
    """Create/update the DB-backed ATC catalog from the versioned backend seed."""
    if not _db_catalog_available(db):
        return

    existing_count = db.scalar(select(AtcCode).limit(1))
    if existing_count is not None:
        return

    db.bulk_insert_mappings(AtcCode, list(_seed_records()))
    db.flush()


def get_atc_titles_map(db: Session | None = None) -> dict[str, str]:
    if db is None or not _db_catalog_available(db):
        return dict(_seed_titles_map())

    ensure_atc_catalog_seeded(db)
    rows = db.execute(select(AtcCode.code, AtcCode.title).order_by(AtcCode.code)).all()
    return {str(code): str(title) for code, title in rows}


def get_atc_title(code: str | None, db: Session | None = None) -> str | None:
    normalized = _normalize_atc_code(code)
    if not normalized:
        return None

    if db is not None and _db_catalog_available(db):
        ensure_atc_catalog_seeded(db)
        title = db.scalar(select(AtcCode.title).where(AtcCode.code == normalized))
        if title:
            return str(title)

    return _seed_titles_map().get(normalized)


def get_atc_parent_code(code: str | None, db: Session | None = None) -> str | None:
    normalized = _normalize_atc_code(code)
    if not normalized:
        return None

    if db is not None and _db_catalog_available(db):
        ensure_atc_catalog_seeded(db)
        parent_code = db.scalar(select(AtcCode.parent_code).where(AtcCode.code == normalized))
        if parent_code is not None:
            return str(parent_code) if parent_code else None

    return _seed_parent_map().get(normalized, infer_atc_parent_code(normalized))


def get_atc_level(code: str | None, db: Session | None = None) -> int | None:
    normalized = _normalize_atc_code(code)
    if not normalized:
        return None

    if db is not None and _db_catalog_available(db):
        ensure_atc_catalog_seeded(db)
        level = db.scalar(select(AtcCode.level).where(AtcCode.code == normalized))
        if level is not None:
            return int(level)

    return _seed_level_map().get(normalized, infer_atc_level(normalized))


def get_atc_catalog(db: Session | None = None) -> list[dict[str, Any]]:
    if db is not None and _db_catalog_available(db):
        ensure_atc_catalog_seeded(db)
        rows = db.execute(select(AtcCode).order_by(AtcCode.code)).scalars().all()
        return [
            {
                "code": row.code,
                "level": row.level,
                "title": row.title,
                "parent_code": row.parent_code,
            }
            for row in rows
        ]

    return [dict(record) for record in _seed_records()]


def build_atc_tree(db: Session | None = None) -> list[dict[str, Any]]:
    records = get_atc_catalog(db)
    nodes = {
        record["code"]: {
            "code": record["code"],
            "level": record["level"],
            "title": record["title"],
            "parent_code": record["parent_code"],
            "children": [],
        }
        for record in records
    }
    roots: list[dict[str, Any]] = []
    for code in sorted(nodes):
        node = nodes[code]
        parent_code = node["parent_code"]
        parent = nodes.get(parent_code)
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def atc_catalog_fingerprint(db: Session | None = None) -> str:
    catalog = get_atc_catalog(db)
    canonical = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
