# Flujo de edición clínica/editorial GFT

La edición clínica/editorial de la GFT representa contenido hospitalario propio. No se calcula automáticamente desde CIMA ni desde BIFIMED.

## Campos editables actuales

Los campos clínicos/editoriales que se prevé mantener mediante el flujo interno son:

- `restricciones_hospitalarias`
- `ajuste_insuficiencia_renal`
- `ajuste_insuficiencia_hepatica`
- `precauciones_embarazo`
- `precauciones_lactancia`
- `observaciones_internas`

## Reglas del flujo interno

- La edición se realiza sobre `gft_estado_presentacion` por `CN`.
- No cambia `estado_gft` ni `estado_editorial`; los estados se gestionan desde un bloque independiente del panel admin mediante `PATCH /admin/gft/medicamentos/{cn}/estado`.
- No crea medicamentos nuevos ni filas nuevas en `gft_estado_presentacion`.
- No modifica el contenido procedente de CIMA o BIFIMED.
- No modifica las reglas de publicación de la GFT pública.

## Endpoint admin de listado editorial

La API interna permite listar filas editoriales de medicamentos GFT para localizar qué `CN` editar desde un futuro panel de administración mediante:

```http
GET /admin/gft/medicamentos/editorial
X-Admin-API-Key: <ADMIN_API_KEY>
```

El endpoint requiere el header `X-Admin-API-Key` y utiliza la protección admin común. Alimenta el panel admin `/admin/gft`, donde se selecciona el medicamento que se va a revisar o editar.

Comportamiento y alcance:

- Lee directamente de `gft_estado_presentacion`.
- No usa la vista pública `v_gft_publicada`.
- Incluye medicamentos publicados y no publicados, como borradores, pendientes o excluidos.
- No crea medicamentos nuevos ni filas nuevas.
- No incluye datos CIMA/BIFIMED ni construye la ficha pública completa.

Parámetros de consulta disponibles:

- `estado_gft`: filtra por el estado GFT exacto tras normalizar espacios.
- `estado_editorial`: filtra por el estado editorial exacto tras normalizar espacios.
- `q`: busca parcialmente por `CN`, `nemonico` y textos clínicos/editoriales básicos (`restricciones_hospitalarias`, `ajuste_insuficiencia_renal`, `ajuste_insuficiencia_hepatica`, `precauciones_embarazo` y `precauciones_lactancia`).
- `limit`: tamaño de página, entre 1 y 200. Por defecto, 50.
- `offset`: desplazamiento de página, mayor o igual a 0. Por defecto, 0.

La respuesta devuelve `total`, `limit`, `offset` e `items` ordenados por `CN` ascendente. Cada elemento incluye estados, nemónico, campos clínicos/editoriales básicos y metadatos de revisión/importación disponibles.

## Endpoint admin de resumen editorial

La API interna permite obtener un resumen de estados GFT/editoriales para la cabecera o cuadro de mando del panel de administración mediante:

```http
GET /admin/gft/medicamentos/editorial/summary
X-Admin-API-Key: <ADMIN_API_KEY>
```

El endpoint requiere el header `X-Admin-API-Key` y utiliza la protección admin común. Está pensado para mostrar métricas agregadas sin cargar el listado completo en `/admin/gft`.

Comportamiento y alcance:

- Lee directamente de `gft_estado_presentacion`.
- No usa la vista pública `v_gft_publicada`.
- Cuenta medicamentos publicados y no publicados, incluyendo borradores, pendientes, excluidos y retirados.
- No filtra por `estado_gft` ni por `estado_editorial`.
- No crea medicamentos nuevos ni filas nuevas.
- No cambia las reglas de publicación de la GFT pública.

La respuesta devuelve:

- `total`: número total de filas en `gft_estado_presentacion`.
- `by_estado_gft`: contador por `estado_gft`, incluyendo siempre los estados conocidos aunque su valor sea 0 y añadiendo estados no previstos si existieran en base de datos.
- `by_estado_editorial`: contador por `estado_editorial`, incluyendo siempre los estados conocidos aunque su valor sea 0 y añadiendo estados no previstos si existieran en base de datos.
- `by_combination`: contador por combinación `estado_gft|estado_editorial`.
- `publicados_en_gft`: filas con `estado_gft = "incluido"` y `estado_editorial = "publicado"`.
- `incluidos_no_publicados`: filas con `estado_gft = "incluido"` y `estado_editorial != "publicado"`.
- `pendientes_revision`: filas con `estado_gft = "pendiente_revision"`.
- `excluidos`: filas con `estado_gft = "excluido"`.

## Endpoint admin de consulta editorial

La API interna permite consultar los campos clínicos/editoriales actuales de un medicamento GFT existente mediante:

```http
GET /admin/gft/medicamentos/{cn}/editorial
X-Admin-API-Key: <ADMIN_API_KEY>
```

El endpoint requiere el header `X-Admin-API-Key` y utiliza la protección admin común. Sirve para cargar el detalle y el formulario de edición clínica/editorial del panel `/admin/gft` antes de enviar cambios con `PATCH /admin/gft/medicamentos/{cn}/editorial`.

Comportamiento y alcance:

- Lee directamente de `gft_estado_presentacion` por `CN`.
- No usa la vista pública `v_gft_publicada`.
- Puede devolver medicamentos no publicados, borradores, excluidos o pendientes.
- No filtra por `estado_gft` ni por `estado_editorial`.
- No crea medicamentos nuevos ni filas nuevas.
- Si el `CN` no existe en `gft_estado_presentacion`, responde 404.

La respuesta incluye el estado GFT/editorial, el nemónico, campos clínicos/editoriales, metadatos de revisión y metadatos de importación disponibles para el medicamento.

## Endpoint admin de edición editorial

La API interna permite actualizar campos clínicos/editoriales de un medicamento GFT existente mediante:

```http
PATCH /admin/gft/medicamentos/{cn}/editorial
X-Admin-API-Key: <ADMIN_API_KEY>
```

El endpoint requiere el header `X-Admin-API-Key` y utiliza la protección admin común.

Permite actualizar los siguientes campos:

- `restricciones_hospitalarias`
- `ajuste_insuficiencia_renal`
- `ajuste_insuficiencia_hepatica`
- `precauciones_embarazo`
- `precauciones_lactancia`
- `observaciones_internas`

Restricciones del endpoint:

- No permite cambiar `estado_gft` ni `estado_editorial`; los cambios de estado se realizan en un flujo separado mediante `PATCH /admin/gft/medicamentos/{cn}/estado`. El panel `/admin/gft` también mueve `comentario_revision` y `revisado_por` a ese bloque de estado para no mezclarlos con el formulario clínico/editorial.
- No permite cambiar `cn` desde el cuerpo de la petición.
- No crea medicamentos nuevos: si el `CN` no existe en `gft_estado_presentacion`, responde 404.
- Los cambios son visibles en `/gft` si el medicamento está incluido y publicado.

Los campos omitidos se conservan sin cambios. Un campo permitido enviado explícitamente como `null` se limpia.

## Panel admin `/admin/gft`

El panel admin `/admin/gft` ya permite seleccionar un medicamento existente, consultar sus datos identificativos y editar de forma controlada los campos clínicos/editoriales anteriores mediante `PATCH /admin/gft/medicamentos/{cn}/editorial`.

El panel mantiene como solo lectura los campos identificativos (`CN`, nombre comercial, principio activo, forma farmacéutica, vía de administración y código ATC`). Los estados GFT/editorial, `comentario_revision` y `revisado_por` se editan en un bloque independiente de "Estado de publicación" mediante `PATCH /admin/gft/medicamentos/{cn}/estado`, de modo que la edición clínica/editorial continúa separada del flujo de publicación.
