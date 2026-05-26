"""add bifimed indicaciones autorizadas json

Revision ID: 0011_bifimed_indicaciones
Revises: 0010_resumen_general
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_bifimed_indicaciones'
down_revision = '0010_resumen_general'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('bifimed_cache', sa.Column('indicaciones_autorizadas_json', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('bifimed_cache', 'indicaciones_autorizadas_json')
