"""align cima model and public GFT view

Revision ID: 0004_align_cima_public_view
Revises: 0003_gft_public_detail_metadata
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_align_cima_public_view'
down_revision = '0003_gft_public_detail_metadata'
branch_labels = None
depends_on = None


CIMA_DOCUMENT_COLUMNS = (
    sa.Column('url_ficha_tecnica', sa.Text(), nullable=True),
    sa.Column('url_prospecto', sa.Text(), nullable=True),
    sa.Column('fecha_ficha_tecnica', sa.Date(), nullable=True),
    sa.Column('fecha_prospecto', sa.Date(), nullable=True),
)

UPGRADED_VIEW_SQL = """
CREATE VIEW v_gft_publicada AS
SELECT
  g.cn,
  g.nemonico,
  c.nombre,
  c.presentacion,
  c.forma_farmaceutica,
  c.forma_farmaceutica_simplificada,
  c.vias_administracion_json,
  c.atc_json,
  c.principios_activos_json,
  c.documentos_json,
  c.url_ficha_tecnica,
  c.url_prospecto,
  c.fecha_ficha_tecnica,
  c.fecha_prospecto,
  b.situacion_financiacion,
  b.condiciones_financiacion_restringidas,
  b.condiciones_especiales_financiacion,
  b.estado_nomenclator,
  b.aportacion_usuario,
  b.subgrupo_atc,
  g.restricciones_hospitalarias,
  g.observaciones_internas
FROM gft_estado_presentacion g
LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
LEFT JOIN bifimed_cache b ON b.cn = g.cn
WHERE g.estado_gft = 'incluido'
  AND g.estado_editorial = 'publicado'
"""

DOWNGRADED_VIEW_SQL = """
CREATE VIEW v_gft_publicada AS
SELECT
  g.cn,
  g.nemonico,
  c.nombre,
  c.presentacion,
  c.forma_farmaceutica,
  c.forma_farmaceutica_simplificada,
  c.vias_administracion_json,
  c.atc_json,
  c.principios_activos_json,
  c.documentos_json,
  b.situacion_financiacion,
  g.restricciones_hospitalarias,
  g.observaciones_internas
FROM gft_estado_presentacion g
LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
LEFT JOIN bifimed_cache b ON b.cn = g.cn
WHERE g.estado_gft = 'incluido'
  AND g.estado_editorial = 'publicado'
"""


def _existing_cima_columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column['name'] for column in inspector.get_columns('cima_medicamento_cache')}


def upgrade():
    existing_columns = _existing_cima_columns()
    for column in CIMA_DOCUMENT_COLUMNS:
        if column.name not in existing_columns:
            op.add_column('cima_medicamento_cache', column.copy())

    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.execute(UPGRADED_VIEW_SQL)


def downgrade():
    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.execute(DOWNGRADED_VIEW_SQL)

    existing_columns = _existing_cima_columns()
    with op.batch_alter_table('cima_medicamento_cache') as batch_op:
        for column in reversed(CIMA_DOCUMENT_COLUMNS):
            if column.name in existing_columns:
                batch_op.drop_column(column.name)
