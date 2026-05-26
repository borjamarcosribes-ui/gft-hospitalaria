from __future__ import annotations

import os
from sqlalchemy.engine.url import make_url

DB_GUARD_MESSAGE = (
    "DATABASE_URL no apunta a PostgreSQL. Exporta DATABASE_URL=postgresql+psycopg://gft:gft@localhost:5432/gft "
    "o usa --allow-default-db solo en tests/desarrollo controlado."
)


def ensure_postgresql_database(allow_default_db: bool = False) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        if allow_default_db:
            return
        raise SystemExit(DB_GUARD_MESSAGE)

    try:
        dialect = make_url(database_url).get_backend_name()
    except Exception:
        dialect = ""

    if dialect != "postgresql" and not allow_default_db:
        raise SystemExit(DB_GUARD_MESSAGE)
