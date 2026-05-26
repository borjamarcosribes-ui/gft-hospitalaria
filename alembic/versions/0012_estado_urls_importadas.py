"""add imported URL columns to gft_estado_presentacion

Revision ID: 0012_estado_urls_importadas
Revises: 0011_bifimed_indicaciones
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_estado_urls_importadas'
down_revision = '0011_bifimed_indicaciones'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col['name'] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column('gft_estado_presentacion', 'url_ficha_tecnica_importada'):
        op.add_column('gft_estado_presentacion', sa.Column('url_ficha_tecnica_importada', sa.Text(), nullable=True))
    if not _has_column('gft_estado_presentacion', 'url_prospecto_importado'):
        op.add_column('gft_estado_presentacion', sa.Column('url_prospecto_importado', sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column('gft_estado_presentacion', 'url_prospecto_importado'):
        op.drop_column('gft_estado_presentacion', 'url_prospecto_importado')
    if _has_column('gft_estado_presentacion', 'url_ficha_tecnica_importada'):
        op.drop_column('gft_estado_presentacion', 'url_ficha_tecnica_importada')
