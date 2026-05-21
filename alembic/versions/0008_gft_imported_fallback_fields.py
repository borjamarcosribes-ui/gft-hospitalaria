"""add imported fallback fields for gft public view

Revision ID: 0008_gft_imported_fallback
Revises: 0007_gft_obs_public
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_gft_imported_fallback"
down_revision = "0007_gft_obs_public"
branch_labels = None
depends_on = None

UPGRADED_VIEW_SQL = """
CREATE VIEW v_gft_publicada AS
SELECT
  g.cn,
  g.nemonico,
  g.nombre_comercial_importado,
  g.principio_activo_importado,
  g.presentacion_importada,
  g.forma_farmaceutica_importada,
  g.via_administracion_importada,
  g.codigo_atc_importado,
  g.descripcion_atc_importada,
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
  ft41.contenido_texto AS indicaciones_ficha_tecnica,
  g.restricciones_hospitalarias,
  g.ajuste_insuficiencia_renal,
  g.ajuste_insuficiencia_hepatica,
  g.precauciones_embarazo,
  g.precauciones_lactancia,
  g.observaciones_publicables
FROM gft_estado_presentacion g
LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
LEFT JOIN bifimed_cache b ON b.cn = g.cn
LEFT JOIN cima_ficha_tecnica_cache ft41
  ON ft41.nregistro = c.nregistro
 AND ft41.tipo_documento = 1
 AND ft41.seccion = '4.1'
 AND ft41.sync_status = 'ok'
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
  c.fecha_ficha_tecnica,
  c.fecha_prospecto,
  b.situacion_financiacion,
  b.condiciones_financiacion_restringidas,
  b.condiciones_especiales_financiacion,
  b.estado_nomenclator,
  b.aportacion_usuario,
  b.subgrupo_atc,
  ft41.contenido_texto AS indicaciones_ficha_tecnica,
  g.restricciones_hospitalarias,
  g.ajuste_insuficiencia_renal,
  g.ajuste_insuficiencia_hepatica,
  g.precauciones_embarazo,
  g.precauciones_lactancia,
  g.observaciones_publicables
FROM gft_estado_presentacion g
LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
LEFT JOIN bifimed_cache b ON b.cn = g.cn
LEFT JOIN cima_ficha_tecnica_cache ft41
  ON ft41.nregistro = c.nregistro
 AND ft41.tipo_documento = 1
 AND ft41.seccion = '4.1'
 AND ft41.sync_status = 'ok'
WHERE g.estado_gft = 'incluido'
  AND g.estado_editorial = 'publicado'
"""


def upgrade():
    op.execute("DROP VIEW IF EXISTS v_gft_publicada;")
    with op.batch_alter_table("gft_estado_presentacion") as batch_op:
        batch_op.add_column(sa.Column("nombre_comercial_importado", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("principio_activo_importado", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("presentacion_importada", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("forma_farmaceutica_importada", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("via_administracion_importada", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("codigo_atc_importado", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("descripcion_atc_importada", sa.Text(), nullable=True))
    op.execute(UPGRADED_VIEW_SQL)


def downgrade():
    op.execute("DROP VIEW IF EXISTS v_gft_publicada;")
    with op.batch_alter_table("gft_estado_presentacion") as batch_op:
        batch_op.drop_column("descripcion_atc_importada")
        batch_op.drop_column("codigo_atc_importado")
        batch_op.drop_column("via_administracion_importada")
        batch_op.drop_column("forma_farmaceutica_importada")
        batch_op.drop_column("presentacion_importada")
        batch_op.drop_column("principio_activo_importado")
        batch_op.drop_column("nombre_comercial_importado")
    op.execute(DOWNGRADED_VIEW_SQL)
