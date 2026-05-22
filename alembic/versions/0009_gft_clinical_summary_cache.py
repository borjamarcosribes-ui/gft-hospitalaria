"""add gft clinical summary cache

Revision ID: 0009_gft_clinical_summary_cache
Revises: 0008_gft_imported_fallback_fields
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_gft_clinical_summary_cache"
down_revision = "0008_gft_imported_fallback_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gft_clinical_summary_cache",
        sa.Column("cn", sa.String(length=32), primary_key=True),
        sa.Column("source_status", sa.String(length=32), nullable=False, server_default="missing_source"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_sections_json", sa.JSON(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("resumen_indicaciones", sa.Text(), nullable=True),
        sa.Column("resumen_posologia", sa.Text(), nullable=True),
        sa.Column("resumen_ajuste_renal", sa.Text(), nullable=True),
        sa.Column("resumen_ajuste_hepatico", sa.Text(), nullable=True),
        sa.Column("resumen_contraindicaciones", sa.Text(), nullable=True),
        sa.Column("resumen_advertencias", sa.Text(), nullable=True),
        sa.Column("resumen_embarazo", sa.Text(), nullable=True),
        sa.Column("resumen_lactancia", sa.Text(), nullable=True),
        sa.Column("resumen_fuente_json", sa.JSON(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("gft_clinical_summary_cache")
