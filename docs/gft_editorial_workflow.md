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
- `comentario_revision`

## Reglas del flujo interno

- La edición se realiza sobre `gft_estado_presentacion` por `CN`.
- No cambia `estado_gft` ni `estado_editorial`.
- No crea medicamentos nuevos ni filas nuevas en `gft_estado_presentacion`.
- No modifica el contenido procedente de CIMA o BIFIMED.
- No modifica las reglas de publicación de la GFT pública.

## Endpoint admin de consulta editorial

La API interna permite consultar los campos clínicos/editoriales actuales de un medicamento GFT existente mediante:

```http
GET /admin/gft/medicamentos/{cn}/editorial
X-Admin-API-Key: <ADMIN_API_KEY>
```

El endpoint requiere el header `X-Admin-API-Key` y utiliza la protección admin común. Sirve para cargar el formulario de edición antes de enviar cambios con `PATCH /admin/gft/medicamentos/{cn}/editorial`.

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
- `comentario_revision`

`revisado_por` puede enviarse como metadato de revisión, pero no es un campo clínico. Cuando se informa, se normaliza y actualiza junto con la fecha de revisión.

Restricciones del endpoint:

- No permite cambiar `estado_gft` ni `estado_editorial`.
- No permite cambiar `cn` desde el cuerpo de la petición.
- No crea medicamentos nuevos: si el `CN` no existe en `gft_estado_presentacion`, responde 404.
- Los cambios son visibles en `/gft` si el medicamento está incluido y publicado.

Los campos omitidos se conservan sin cambios. Un campo permitido enviado explícitamente como `null` se limpia.

## Pendiente

- Crear un panel de administración para la edición clínica/editorial hospitalaria.
