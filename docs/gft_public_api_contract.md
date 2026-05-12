# Contrato de la API pública `/gft`

## A. Finalidad

La API pública `/gft` representa la Guía Farmacoterapéutica (GFT) publicada del hospital.

Su objetivo es exponer únicamente medicamentos:

- incluidos en guía;
- publicados editorialmente;
- compuestos desde las fuentes internas validadas para consulta pública.

La API pública no es una API de administración, importación ni auditoría. Por diseño, no debe exponer datos técnicos internos, payloads crudos, errores de sincronización ni estados intermedios.

## B. Endpoints actuales

### `GET /gft/medicamentos`

Devuelve el listado paginado de medicamentos publicados en GFT.

Este endpoint representa la colección pública de medicamentos que cumplen las reglas de publicación vigentes. El listado puede incluir campos clínicos y documentales públicos ya disponibles, como metadatos CIMA, ATC, principios activos, enlaces documentales, financiación resumida e indicaciones de ficha técnica cuando estén sincronizadas correctamente.

### `GET /gft/medicamentos/{cn}`

Devuelve el detalle de un medicamento publicado en GFT por su Código Nacional (CN).

El parámetro `{cn}` identifica la presentación publicada que se desea consultar. Si el CN no corresponde a un medicamento incluido y publicado, no debe aparecer como recurso público de GFT.

## C. Reglas de publicación

La fuente pública se basa en la vista SQL `v_gft_publicada`.

Las condiciones obligatorias para que un medicamento se publique son:

- `g.estado_gft = 'incluido'`
- `g.estado_editorial = 'publicado'`

No se publican:

- medicamentos excluidos;
- medicamentos pendientes de revisión;
- borradores;
- registros con errores de importación no aplicados;
- medicamentos sin `apply` final a `gft_estado_presentacion`.

Estas reglas convierten `v_gft_publicada` en la frontera contractual entre los procesos internos de carga/revisión y la API pública `/gft`.

## D. Identidad

- `cn` es la clave pública principal del medicamento en la GFT.
- `cn` se usa para resolver el detalle `GET /gft/medicamentos/{cn}`.
- `nregistro` no es clave pública de GFT; se usa internamente como clave técnica de CIMA para localizar la ficha técnica segmentada.
- `nregistro` no sustituye al `cn` ni debe usarse como identificador público principal de la GFT.

## E. Campos públicos actuales

| Campo público | Origen | Observaciones |
| --- | --- | --- |
| `cn` | `gft_estado_presentacion.cn` | Clave pública principal. |
| `nemonico` | `gft_estado_presentacion.nemonico` | Nemónico hospitalario asociado a la presentación, cuando exista. |
| `nombre` | `cima_medicamento_cache.nombre` | Nombre del medicamento procedente de CIMA. |
| `presentacion` | `cima_medicamento_cache.presentacion` | Presentación procedente de CIMA. |
| `forma_farmaceutica` | `cima_medicamento_cache.forma_farmaceutica` | Forma farmacéutica original procedente de CIMA. |
| `forma_farmaceutica_simplificada` | `cima_medicamento_cache.forma_farmaceutica_simplificada` | Forma simplificada procedente de CIMA, cuando esté disponible. |
| `vias_administracion` | `cima_medicamento_cache.vias_administracion_json` | Se publica como lista normalizada por el servicio de consulta GFT. |
| `codigo_atc` | Derivado de `cima_medicamento_cache.atc_json` / servicio de consulta GFT | Código ATC utilizable para filtros o agregaciones. En el schema público actual el ATC se expone como objetos dentro de `atc`. |
| `atc` | `cima_medicamento_cache.atc_json` | Lista de referencias ATC normalizadas por el servicio de consulta GFT. |
| `principios_activos` | `cima_medicamento_cache.principios_activos_json` y/o tablas de relación de principios activos | Lista pública de principios activos, normalizada por el servicio de consulta GFT. |
| `documentos` | `cima_medicamento_cache.documentos_json` | Disponible en el detalle del medicamento; contiene referencias documentales públicas normalizadas. |
| `url_ficha_tecnica` | `cima_medicamento_cache.url_ficha_tecnica` | URL pública de la ficha técnica, cuando exista. |
| `url_prospecto` | `cima_medicamento_cache.url_prospecto` | URL pública del prospecto, cuando exista. |
| `fecha_ficha_tecnica` | `cima_medicamento_cache.fecha_ficha_tecnica` | Fecha asociada a la ficha técnica en CIMA, cuando exista. |
| `fecha_prospecto` | `cima_medicamento_cache.fecha_prospecto` | Fecha asociada al prospecto en CIMA, cuando exista. |
| `indicaciones_ficha_tecnica` | `cima_ficha_tecnica_cache.contenido_texto` | Texto oficial de la sección 4.1 de ficha técnica. Se incorpora mediante join por `cima_medicamento_cache.nregistro` y solo para `tipo_documento = 1`, `seccion = '4.1'` y `sync_status = 'ok'`. No expone `contenido_html`, `raw_data`, `sync_status` ni `sync_error`. |
| `situacion_financiacion` | `bifimed_cache.situacion_financiacion` | Resumen de situación de financiación disponible en listado y detalle. |
| `financiacion_detalle` | `bifimed_cache` | Disponible en el detalle; agrupa `situacion_financiacion`, `condiciones_financiacion_restringidas`, `condiciones_especiales_financiacion`, `estado_nomenclator`, `aportacion_usuario` y `subgrupo_atc`. |
| `restricciones_hospitalarias` | `gft_estado_presentacion.restricciones_hospitalarias` | Restricciones hospitalarias publicadas actualmente como texto. |
| `observaciones_internas_publicables` | `gft_estado_presentacion.observaciones_internas` | Disponible en el detalle. El schema público actual lo expone con nombre publicable; si en el futuro existen observaciones internas no publicables, deberán separarse explícitamente. |

## F. Campos técnicos que NO se exponen

La API pública `/gft` no debe exponer campos técnicos internos ni payloads de auditoría. En particular, no se exponen:

- `raw_data`;
- `raw_payload`;
- `contenido_html` de ficha técnica segmentada;
- `sync_status`;
- `sync_error`;
- `validation_errors`;
- `raw_payload` de staging;
- `detalle_financiacion_json` completo si no está expuesto por el schema público;
- observaciones internas no publicables si existieran en el futuro.

## G. Fuentes internas principales

### `gft_estado_presentacion`

Fuente del estado GFT, estado editorial, CN, nemónico, restricciones hospitalarias y observaciones actualmente mapeadas como publicables en el detalle.

### `cima_medicamento_cache`

Fuente de metadatos CIMA por CN: nombre, presentación, forma farmacéutica, vías de administración, ATC, principios activos, documentos, URLs, fechas documentales y `nregistro`.

### `cima_ficha_tecnica_cache`

Fuente de secciones segmentadas de ficha técnica por `nregistro`, `tipo_documento` y `seccion`. Para las indicaciones públicas se usa la sección `4.1` de ficha técnica (`tipo_documento = 1`) solo cuando `sync_status = 'ok'`.

### `bifimed_cache`

Fuente de financiación y condiciones de financiación: situación, restricciones, condiciones especiales, estado de nomenclátor, aportación de usuario y subgrupo ATC.

### `v_gft_publicada`

Vista SQL de composición pública. Une las fuentes internas necesarias y aplica las reglas obligatorias de publicación antes de que la API `/gft` lea los datos.

## H. Orden recomendado del flujo de publicación

1. Importar Excel a staging.
2. Revisar summary.
3. Sincronizar CIMA medicamento por batch.
4. Sincronizar CIMA ficha técnica segmentada por batch.
5. Sincronizar BIFIMED por batch.
6. Aplicar batch a GFT.
7. Consultar `/gft`.

## I. Pendiente de implementar

- Ajuste por insuficiencia renal.
- Ajuste por insuficiencia hepática.
- Embarazo.
- Lactancia.
- Restricciones hospitalarias estructuradas/enriquecidas.
- Panel de administración editorial.
- Exportación PDF.
- Frontend público completo.
- Roles/seguridad/despliegue.

## J. Decisiones de diseño relevantes

- La GFT pública prioriza datos visibles y útiles para consulta, no ocultos en exceso.
- `cn` es la clave pública principal.
- `nregistro` es una clave técnica CIMA.
- Las indicaciones de ficha técnica proceden del texto oficial de la sección 4.1, pero no sustituyen futuros resúmenes clínicos hospitalarios.
- Los campos clínicos editoriales propios deben añadirse de forma separada, explícita y revisable.
