# Auditoría técnica CIMA ficha técnica segmentada

## Objetivo funcional

- Incorporar de forma automática a la GFT, en una primera versión, el texto oficial de “Indicaciones terapéuticas” de ficha técnica.
- Mapear inicialmente la sección 4.1 de ficha técnica al futuro campo público: `indicaciones_ficha_tecnica`.

## Fuente oficial observada

- CIMA REST API.
- Endpoints documentados:
  - `GET docSegmentado/secciones/{tipoDoc}?nregistro=...`
  - `GET docSegmentado/contenido/{tipoDoc}?nregistro=...&seccion=...`
- `tipoDoc`:
  - `1` = ficha técnica
  - `2` = prospecto
- El endpoint de contenido puede devolver JSON, HTML o texto según `Accept`.
- Nota: aproximadamente el 80% de fichas técnicas/prospectos están fraccionados, por lo que la ausencia de documento segmentado debe tratarse como caso esperado, no como excepción imposible.

## Decisión de identidad

- La GFT pública se organiza por CN, pero la ficha técnica segmentada se consulta por `nregistro`.
- La identidad lógica futura de una sección debe ser: `nregistro + tipo_documento + seccion`.
- El CN no debe formar parte de la identidad de la sección.
- El CN podrá conservarse como referencia de origen/trazabilidad si se desea.
- Justificación: varias presentaciones pueden compartir un mismo `nregistro`.

## Flujo futuro

El flujo E2E futuro deberá incorporar la ficha técnica segmentada después de disponer de `nregistro` desde CIMA medicamento:

```text
Excel
→ staging
→ summary
→ CIMA medicamento batch
→ CIMA ficha técnica segmentada batch
→ BIFIMED batch
→ apply
→ GFT pública
```

La sincronización de CIMA ficha técnica segmentada depende de que CIMA medicamento haya proporcionado antes `nregistro`. Por tanto, no debe ejecutarse antes del sync CIMA de medicamento.

El batch futuro deberá operar sobre `nregistro` únicos derivados de los CN incluidos válidos con caché CIMA correcta. La deduplicación por `nregistro` evitará llamadas y escrituras redundantes cuando varias presentaciones compartan la misma ficha técnica.

## Alcance v1

| Sección | Uso previsto | ¿Publicar automáticamente en v1? |
| --- | --- | --- |
| 4.1 Indicaciones terapéuticas | Publicar automáticamente como `indicaciones_ficha_tecnica`. | Sí |
| 4.6 Fertilidad, embarazo y lactancia | Candidata futura para texto oficial. | No |
| 4.2 Posología y forma de administración | Candidata futura. | No |
| Otras secciones | Fuera de v1. | No |

La sección 4.1 sí es un campo mínimo ya requerido en la GFT. La sección 4.6 puede aportar texto oficial, pero no sustituye por sí sola un futuro resumen hospitalario práctico de embarazo/lactancia. Ajuste renal y hepático no se asumirán automáticamente de una única sección en v1.

## Revisión del modelo actual existente

El modelo `app/models/cima_ficha_tecnica_cache.py` ya existe y define la tabla `cima_ficha_tecnica_cache`. Actualmente contiene los campos:

- `id`
- `cn`
- `nregistro`
- `tipo_documento`
- `seccion`
- `titulo`
- `contenido_html`
- `contenido_texto`
- `fecha_documento`
- `last_synced_at`

Decisiones y requisitos para una futura implementación:

- Probable unicidad lógica por `(nregistro, tipo_documento, seccion)`.
- Conviene añadir `sync_status` y `sync_error`.
- Valorar `raw_data` para trazabilidad.
- `cn` debe ser opcional y no parte de la identidad.
- La futura exposición pública deberá unir:

```text
gft_estado_presentacion.cn
-> cima_medicamento_cache.nregistro
-> cima_ficha_tecnica_cache.nregistro + tipo_documento=1 + seccion='4.1'
```

Esta tabla deberá revisarse antes de usarse en producción para alinear restricciones, estados de sincronización y trazabilidad con la semántica real observada del endpoint segmentado.

## Estados previstos

El núcleo puro debe distinguir, como mínimo:

- `ok`
- `not_found`
- `not_segmented` para ausencia de listado segmentado o respuesta de error en el endpoint de secciones
- `section_unavailable` para ausencia de una sección concreta o respuesta de error en el endpoint de contenido
- `error`

## Hallazgos de prueba real controlada

La prueba real controlada contra CIMA `docSegmentado` permitió fijar el contrato mínimo del parser y del cliente segmentado:

- CN probados: `661406`, `689877`, `767418`.
- `nregistro` observados desde CIMA medicamento: `70030`, `55211`, `1241885003`.
- Los documentos de ficha técnica (`tipo=1`) mostraron `secc=True` en los tres casos.
- `GET /docSegmentado/secciones/1?nregistro=70030` con `Accept: application/json` devolvió HTTP 200 y una lista JSON de secciones con campos como `seccion`, `titulo` y `orden`.
- `GET /docSegmentado/contenido/1?nregistro=70030&seccion=4.1` con `Accept: application/json` devolvió HTTP 200 y una lista JSON con `contenido` en HTML.
- La misma llamada de contenido con `Accept: text/plain` devolvió texto plano limpio.
- Una sección inexistente, por ejemplo `9.9`, devolvió HTTP 200 con `{"error":"No existen secciones para el medicamento indicado"}`.
- Implicación técnica: HTTP 200 con un objeto `error` no debe tratarse como `ok`; debe mapearse a `not_segmented` en el endpoint de secciones y a `section_unavailable` en el endpoint de contenido.

## Riesgos abiertos

- No todas las fichas técnicas están segmentadas.
- La respuesta del endpoint puede evolucionar; las fixtures fijan únicamente el contrato mínimo observado para parser y cliente.
- Puede haber varios CN asociados al mismo `nregistro`.
- Puede haber CN sin `nregistro` si CIMA medicamento no se sincronizó o falló.
- La actualización de ficha técnica puede cambiar sin que cambie el estado GFT; habrá que definir después la política de refresco.

## Fixtures contractuales

Se añaden fixtures sintéticas mínimas basadas en la forma real observada del endpoint `docSegmentado`. No son copias completas de respuestas oficiales y se usan únicamente para fijar el contrato de parser y cliente sin llamadas reales en tests:

- listado de secciones;
- contenido JSON de la sección 4.1;
- contenido `text/plain` de la sección 4.1;
- objeto de error para sección no disponible.

## Próximo paso técnico

- Implementar sync individual usando `cima_ficha_tecnica_cache`, previa revisión/migración del modelo.
- Alinear la tabla con la identidad lógica `(nregistro, tipo_documento, seccion)` y con estados de sincronización explícitos.
- Integrar el sync después de CIMA medicamento para partir de `nregistro` únicos ya conocidos.
