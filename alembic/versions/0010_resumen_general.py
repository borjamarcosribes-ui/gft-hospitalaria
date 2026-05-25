"""add resumen_general to clinical summary cache

Revision ID: 0010_resumen_general
Revises: 0009_gft_clinical_summary_cache
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_resumen_general'
down_revision = '0009_gft_clinical_summary_cache'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('gft_clinical_summary_cache', sa.Column('resumen_general', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('gft_clinical_summary_cache', 'resumen_general')
