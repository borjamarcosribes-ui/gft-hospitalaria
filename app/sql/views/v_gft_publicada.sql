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
  AND g.estado_editorial = 'publicado';
