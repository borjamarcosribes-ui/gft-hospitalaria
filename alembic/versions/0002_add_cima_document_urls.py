"""add cima document urls

Revision ID: 0002_add_cima_document_urls
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_add_cima_document_urls'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('cima_medicamento_cache', sa.Column('url_ficha_tecnica', sa.Text(), nullable=True))
    op.add_column('cima_medicamento_cache', sa.Column('url_prospecto', sa.Text(), nullable=True))
    op.add_column('cima_medicamento_cache', sa.Column('fecha_ficha_tecnica', sa.Date(), nullable=True))
    op.add_column('cima_medicamento_cache', sa.Column('fecha_prospecto', sa.Date(), nullable=True))
    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.execute("""
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
      b.situacion_financiacion,
      g.restricciones_hospitalarias,
      g.observaciones_internas
    FROM gft_estado_presentacion g
    LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
    LEFT JOIN bifimed_cache b ON b.cn = g.cn
    WHERE g.estado_gft = 'incluido'
      AND g.estado_editorial = 'publicado'
    """)


def downgrade():
    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.execute("""
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
    """)
    op.drop_column('cima_medicamento_cache', 'fecha_prospecto')
    op.drop_column('cima_medicamento_cache', 'fecha_ficha_tecnica')
    op.drop_column('cima_medicamento_cache', 'url_prospecto')
    op.drop_column('cima_medicamento_cache', 'url_ficha_tecnica')
