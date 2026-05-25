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

### `GET /gft/atc`

Devuelve el índice ATC público disponible para navegación y filtrado de la GFT publicada.

### `GET /gft/principios-activos`

Devuelve el índice público de principios activos disponible para navegación y filtrado de la GFT publicada.

### `GET /gft/export/html`

Devuelve la previsualización HTML imprimible de la GFT publicada. Es una herramienta de validación visual/debug de la plantilla que alimenta el PDF y no una fuente de publicación alternativa.

### `GET /gft/export/pdf`

Devuelve la descarga pública final en PDF de la GFT publicada. El PDF se genera desde la misma cadena y fuente pública que el HTML imprimible.

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
| `ajuste_insuficiencia_renal` | `gft_estado_presentacion.ajuste_insuficiencia_renal` | Campo editorial hospitalario; no se calcula automáticamente. |
| `ajuste_insuficiencia_hepatica` | `gft_estado_presentacion.ajuste_insuficiencia_hepatica` | Campo editorial hospitalario; no se calcula automáticamente. |
| `precauciones_embarazo` | `gft_estado_presentacion.precauciones_embarazo` | Campo editorial hospitalario; no sustituye ficha técnica ni revisión clínica. |
| `precauciones_lactancia` | `gft_estado_presentacion.precauciones_lactancia` | Campo editorial hospitalario; no sustituye ficha técnica ni revisión clínica. |
| `observaciones_internas_publicables` | `gft_estado_presentacion.observaciones_internas` | Disponible en el detalle. El schema público actual lo expone con nombre publicable; si en el futuro existen observaciones internas no publicables, deberán separarse explícitamente. |

### Reglas ATC para índice y filtro público

- El servicio público usa una fuente ATC efectiva común para listado, detalle, índice global (`GET /gft/atc`) y filtro `atc` de `GET /gft/medicamentos`.
- Prioridad ATC:
  1. `cima_medicamento_cache.atc_json` cuando contiene datos válidos.
  2. Fallback importado `gft_estado_presentacion.codigo_atc_importado` + `gft_estado_presentacion.descripcion_atc_importada` cuando `atc_json` no aporta códigos.
- El índice expande cada ATC efectivo por prefijos L1-L5 y cuenta CN únicos por código/prefijo.
- El filtro `atc` se aplica por prefijo (`startswith`) sobre ATC efectivo, por lo que admite L1, L2, L3, L4 y L5.
- Los medicamentos publicados sin ATC efectivo siguen apareciendo en `/gft/medicamentos`, pero no en el índice ATC.

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

Fuente del estado GFT, estado editorial, CN, nemónico, restricciones hospitalarias, campos clínicos editoriales hospitalarios y observaciones actualmente mapeadas como publicables en el detalle.

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

## I. Estado actual y pendientes reales

### Implementado

- API pública `/gft` con listado, detalle por CN, índice ATC e índice de principios activos.
- CIMA ficha técnica segmentada para sección `4.1`, publicada como `indicaciones_ficha_tecnica` cuando existe caché válida.
- Exportación pública `GET /gft/export/html` como HTML imprimible/debug visual.
- Exportación pública `GET /gft/export/pdf` como descarga PDF final.
- Frontend público con búsqueda, filtros, índice ATC y botón de exportación PDF.
- Panel admin `/admin/gft` con resumen, listado, detalle, edición clínica/editorial y cambio de estado.

### Parcial

- Los campos clínicos/editoriales son editables y publicables, pero siguen requiriendo validación funcional con datos reales y criterio clínico.
- La seguridad admin está protegida por `X-Admin-API-Key`; no equivale a autenticación corporativa con usuarios, roles y auditoría.
- La exportación PDF está implementada, pero su operación estable depende del despliegue de WeasyPrint/pydyf y librerías de sistema.

### Pendiente para producción

- Autenticación robusta, roles y auditoría de cambios.
- Protección explícita de endpoints internos de importación/sincronización si se exponen fuera de un entorno controlado.
- Validación con datos reales y checklist funcional antes de una v1 productiva.
- Hardening de despliegue, observabilidad, gestión de secretos y dependencias de sistema.
- Política de cacheado/versionado del PDF si se requiere por volumen o trazabilidad documental.
- Separación futura entre observaciones internas publicables y no publicables si aparecen contenidos que no deban exponerse.
- Restricciones hospitalarias estructuradas/enriquecidas, si se decide evolucionar el campo de texto actual.

## J. Decisiones de diseño relevantes

- La GFT pública prioriza datos visibles y útiles para consulta, no ocultos en exceso.
- `cn` es la clave pública principal.
- `nregistro` es una clave técnica CIMA.
- Las indicaciones de ficha técnica proceden del texto oficial de la sección 4.1, pero no sustituyen futuros resúmenes clínicos hospitalarios.
- Los campos clínicos editoriales propios deben añadirse de forma separada, explícita y revisable.
