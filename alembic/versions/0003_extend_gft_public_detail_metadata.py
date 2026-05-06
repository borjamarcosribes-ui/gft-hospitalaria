"""extend gft public detail metadata

Revision ID: 0003_gft_public_detail_metadata
Revises: 0002_add_cima_document_urls
"""
from alembic import op

revision = '0003_gft_public_detail_metadata'
down_revision = '0002_add_cima_document_urls'
branch_labels = None
depends_on = None


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
"""


def upgrade():
    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.execute(UPGRADED_VIEW_SQL)


def downgrade():
    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.execute(DOWNGRADED_VIEW_SQL)
