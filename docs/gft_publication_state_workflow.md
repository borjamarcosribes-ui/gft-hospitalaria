# Flujo de estado de publicación GFT

Este flujo interno controla únicamente los estados de publicación de una presentación en la GFT:

- `estado_gft`
- `estado_editorial`

No edita campos clínicos ni editoriales descriptivos. Esos cambios pertenecen al flujo de edición clínica/editorial existente.

## Alcance

- No crea medicamentos nuevos.
- No crea filas nuevas en `gft_estado_presentacion`.
- Usa el CN como clave de búsqueda y actualización.
- Trabaja solo con los enums internos ya definidos.

## Estados permitidos

### Estados GFT

- `incluido`
- `excluido`
- `pendiente_revision`

### Estados editoriales

- `borrador`
- `validado`
- `publicado`
- `retirado`

## Regla de publicación pública

Un medicamento solo aparece en la API pública `/gft` si cumple simultáneamente:

- `estado_gft = incluido`
- `estado_editorial = publicado`

Cualquier otro par de estados lo deja fuera de la publicación pública.

## Regla de seguridad

No se permite dejar un medicamento con `estado_editorial = publicado` si su `estado_gft` no es `incluido`.

Esto implica que:

- Se puede publicar un medicamento ya incluido.
- Se puede incluir y publicar en una misma operación.
- No se puede publicar un medicamento excluido o pendiente de revisión.
- No se puede excluir un medicamento que queda publicado; primero debe despublicarse en la misma operación o en una operación previa.

## Ejemplos de transiciones válidas

- `pendiente_revision` / `borrador` → `incluido` / `validado`
- `incluido` / `validado` → `incluido` / `publicado`
- `incluido` / `publicado` → `incluido` / `retirado`
- `incluido` / `publicado` → `excluido` / `retirado`

## Pendiente

- Exponer este flujo mediante un endpoint admin protegido.
- Integrarlo en un futuro panel admin.
