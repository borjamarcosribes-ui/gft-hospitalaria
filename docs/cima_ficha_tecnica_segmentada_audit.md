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

El futuro módulo deberá distinguir, como mínimo:

- `ok`
- `not_found`
- `not_segmented` / `section_unavailable`
- `error`

La nomenclatura exacta entre `not_segmented` y `section_unavailable` queda pendiente de validar con respuestas reales del endpoint antes de implementar el cliente. En particular, hay que observar si CIMA diferencia entre documento no segmentado, documento inexistente y sección concreta no disponible.

## Riesgos abiertos

- No todas las fichas técnicas están segmentadas.
- La respuesta exacta de los endpoints debe verificarse con llamadas reales antes de fijar fixtures y parser.
- Puede haber varios CN asociados al mismo `nregistro`.
- Puede haber CN sin `nregistro` si CIMA medicamento no se sincronizó o falló.
- La actualización de ficha técnica puede cambiar sin que cambie el estado GFT; habrá que definir después la política de refresco.

## Fixtures contractuales

No se añaden fixtures contractuales en este PR. Antes de fijarlas se validará la forma real de la respuesta JSON del endpoint `docSegmentado` con llamadas controladas, porque la documentación disponible no es suficiente para cerrar de forma segura el contrato del parser.

Las fixtures sintéticas mínimas deberán crearse únicamente después de confirmar la estructura real de:

- el listado de secciones;
- el contenido de la sección 4.1;
- los casos sin segmentación o sin sección.

## Próximo paso técnico

- Ejecutar una prueba real controlada del endpoint `docSegmentado` con varios `nregistro`.
- Capturar la forma real de:
  - listado de secciones;
  - contenido de la sección 4.1;
  - caso sin segmentación / sin sección.
- Con esa evidencia, crear:
  - fixtures sintéticas mínimas;
  - cliente;
  - parser;
  - sync individual.
