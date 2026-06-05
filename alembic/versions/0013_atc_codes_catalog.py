"""add canonical ATC code catalog

Revision ID: 0013_atc_codes_catalog
Revises: 0012_estado_urls_importadas
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
import json
from pathlib import Path

revision = "0013_atc_codes_catalog"
down_revision = "0012_estado_urls_importadas"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("atc_codes"):
        op.create_table(
            "atc_codes",
            sa.Column("code", sa.String(length=16), primary_key=True),
            sa.Column("level", sa.Integer(), nullable=False, index=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("parent_code", sa.String(length=16), nullable=True, index=True),
        )

    atc_table = sa.table(
        "atc_codes",
        sa.column("code", sa.String),
        sa.column("level", sa.Integer),
        sa.column("title", sa.Text),
        sa.column("parent_code", sa.String),
    )
    seed_path = Path(__file__).resolve().parents[2] / "app" / "data" / "atc_titles.json"
    if seed_path.is_file():
        records = json.loads(seed_path.read_text(encoding="utf-8"))
        existing = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM atc_codes")).scalar()
        if not existing:
            op.bulk_insert(atc_table, records)


def downgrade() -> None:
    if _has_table("atc_codes"):
        op.drop_table("atc_codes")
