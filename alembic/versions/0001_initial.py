"""initial

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'import_batch',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('sha256', sa.String()),
        sa.Column('total_rows', sa.Integer()),
        sa.Column('processed_rows', sa.Integer()),
        sa.Column('ok_rows', sa.Integer()),
        sa.Column('error_rows', sa.Integer()),
        sa.Column('warning_rows', sa.Integer()),
        sa.Column('error_summary', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'gft_estado_presentacion',
        sa.Column('cn', sa.String(32), primary_key=True),
        sa.Column('estado_gft', sa.String(32), nullable=False),
        sa.Column('estado_editorial', sa.String(32), nullable=False),
        sa.Column('nemonico', sa.Text()),
        sa.Column('restricciones_hospitalarias', sa.Text()),
        sa.Column('observaciones_internas', sa.Text()),
        sa.Column('comentario_revision', sa.Text()),
        sa.Column('revisado_por', sa.Text()),
        sa.Column('fecha_revision', sa.Date()),
        sa.Column('last_import_batch_id', sa.Uuid(), sa.ForeignKey('import_batch.id')),
        sa.Column('last_imported_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'import_row_staging',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('batch_id', sa.Uuid(), sa.ForeignKey('import_batch.id'), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('cn_raw', sa.Text()),
        sa.Column('cn_normalized', sa.String(32)),
        sa.Column('observaciones_revision_raw', sa.Text()),
        sa.Column('estado_editorial_raw', sa.Text()),
        sa.Column('nemonico_raw', sa.Text()),
        sa.Column('restricciones_hospitalarias_raw', sa.Text()),
        sa.Column('observaciones_internas_raw', sa.Text()),
        sa.Column('comentario_revision_raw', sa.Text()),
        sa.Column('revisado_por_raw', sa.Text()),
        sa.Column('fecha_revision_raw', sa.Text()),
        sa.Column('estado_gft', sa.String(32), nullable=False),
        sa.Column('estado_editorial', sa.String(32)),
        sa.Column('validation_errors', sa.JSON()),
        sa.Column('validation_warnings', sa.JSON()),
        sa.Column('raw_payload', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    op.create_table('cima_medicamento_cache',
        sa.Column('cn', sa.String(32), primary_key=True),
        sa.Column('nregistro', sa.String(64)), sa.Column('nombre', sa.Text()), sa.Column('presentacion', sa.Text()),
        sa.Column('forma_farmaceutica', sa.Text()), sa.Column('forma_farmaceutica_simplificada', sa.Text()),
        sa.Column('vias_administracion_json', sa.JSON()), sa.Column('atc_json', sa.JSON()),
        sa.Column('principios_activos_json', sa.JSON()), sa.Column('documentos_json', sa.JSON()), sa.Column('raw_data', sa.JSON()),
        sa.Column('sync_status', sa.String(32), nullable=False), sa.Column('sync_error', sa.Text()), sa.Column('last_synced_at', sa.DateTime(timezone=True)),
    )
    op.create_table('cima_ficha_tecnica_cache',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('cn', sa.Text()), sa.Column('nregistro', sa.Text(), nullable=False),
        sa.Column('tipo_documento', sa.Integer(), nullable=False), sa.Column('seccion', sa.Text(), nullable=False), sa.Column('titulo', sa.Text(), nullable=False),
        sa.Column('contenido_html', sa.Text()), sa.Column('contenido_texto', sa.Text()), sa.Column('fecha_documento', sa.Date()), sa.Column('last_synced_at', sa.DateTime(timezone=True)),
    )
    op.create_table('bifimed_cache',
        sa.Column('cn', sa.String(32), primary_key=True), sa.Column('situacion_financiacion', sa.Text()),
        sa.Column('condiciones_financiacion_restringidas', sa.Text()), sa.Column('condiciones_especiales_financiacion', sa.Text()),
        sa.Column('estado_nomenclator', sa.Text()), sa.Column('aportacion_usuario', sa.Text()), sa.Column('subgrupo_atc', sa.Text()),
        sa.Column('detalle_financiacion_json', sa.JSON()), sa.Column('raw_data', sa.JSON()), sa.Column('sync_status', sa.String(32), nullable=False),
        sa.Column('sync_error', sa.Text()), sa.Column('last_synced_at', sa.DateTime(timezone=True)),
    )
    op.create_table('principio_activo',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('nombre_normalizado', sa.Text(), unique=True, nullable=False),
        sa.Column('nombre_display', sa.Text(), nullable=False), sa.Column('slug', sa.Text(), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('principio_activo_alias',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('alias_raw', sa.Text(), nullable=False),
        sa.Column('alias_normalizado', sa.Text(), nullable=False), sa.Column('principio_activo_id', sa.Uuid(), sa.ForeignKey('principio_activo.id'), nullable=False),
        sa.Column('source', sa.Text()), sa.Column('confidence', sa.Text()), sa.Column('review_status', sa.Text()), sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_table('medicamento_principio_activo',
        sa.Column('cn', sa.Text(), primary_key=True), sa.Column('principio_activo_id', sa.Uuid(), sa.ForeignKey('principio_activo.id'), primary_key=True), sa.Column('orden', sa.Integer()),
    )

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


def downgrade():
    op.execute('DROP VIEW IF EXISTS v_gft_publicada;')
    op.drop_table('medicamento_principio_activo')
    op.drop_table('principio_activo_alias')
    op.drop_table('principio_activo')
    op.drop_table('bifimed_cache')
    op.drop_table('cima_ficha_tecnica_cache')
    op.drop_table('cima_medicamento_cache')
    op.drop_table('import_row_staging')
    op.drop_table('gft_estado_presentacion')
    op.drop_table('import_batch')
