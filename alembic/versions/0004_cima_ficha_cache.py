"""prepare cima ficha tecnica segmented cache

Revision ID: 0004_cima_ficha_cache
Revises: 0003_gft_public_detail_metadata
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_cima_ficha_cache'
down_revision = '0003_gft_public_detail_metadata'
branch_labels = None
depends_on = None


TABLE_NAME = 'cima_ficha_tecnica_cache'
UNIQUE_CONSTRAINT_NAME = 'uq_cima_ficha_tecnica_cache_nregistro_tipo_seccion'
INDEX_NAME = 'ix_cima_ficha_tecnica_cache_nregistro_tipo_seccion'
IDENTITY_COLUMNS = ['nregistro', 'tipo_documento', 'seccion']


def upgrade():
    with op.batch_alter_table(TABLE_NAME) as batch_op:
        batch_op.add_column(sa.Column('raw_data', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'sync_status',
                sa.String(length=32),
                nullable=False,
                server_default='not_synced',
            )
        )
        batch_op.add_column(sa.Column('sync_error', sa.Text(), nullable=True))
        batch_op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, IDENTITY_COLUMNS)
        batch_op.create_index(INDEX_NAME, IDENTITY_COLUMNS)


def downgrade():
    with op.batch_alter_table(TABLE_NAME) as batch_op:
        batch_op.drop_index(INDEX_NAME)
        batch_op.drop_constraint(UNIQUE_CONSTRAINT_NAME, type_='unique')
        batch_op.drop_column('sync_error')
        batch_op.drop_column('sync_status')
        batch_op.drop_column('raw_data')
