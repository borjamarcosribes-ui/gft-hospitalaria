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

## Pendiente

- Exponer esta edición mediante un endpoint protegido/admin cuando se definan los roles y la seguridad.
- Crear un panel de administración para la edición clínica/editorial hospitalaria.
