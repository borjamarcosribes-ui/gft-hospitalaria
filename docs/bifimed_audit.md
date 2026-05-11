# Auditoría técnica BIFIMED

## Fuente oficial observada

- Portal BIFIMED del Ministerio de Sanidad: <https://www.sanidad.gob.es/profesionales/medicamentos.do>
- Búsqueda por "Nombre o CN del medicamento".
- Patrón de detalle observado:
  `medicamentos.do?cn=<CN>&metodo=verDetalle`
- Nota: el Nomenclátor cambia mensualmente; no se debe fijar en código un mes concreto.
- Para la v1 se asume navegación en castellano porque las etiquetas contractuales se extraerán en castellano.

## Casos revisados

| CN | Caso | Variabilidad que ilustra |
| --- | --- | --- |
| 988220 | Financiado simple | Ficha con financiación afirmativa directa, sin condiciones restringidas ni condiciones especiales relevantes para v1. Sirve como caso base `ok` con valores simples. |
| 769360 | Financiación condicionada / visado / pendiente de alta | Ficha con situación de financiación condicionada, restricción tipo visado, aportación especial y estado de Nomenclátor no equivalente a alta ordinaria. Sirve para validar que no se colapsen textos semánticos. |
| 718395 | No incluido | Ficha con situación `No incluido` y campos administrativos que pueden aparecer vacíos. Sirve para diferenciar una ficha válida no financiada de un `not_found`. |
| 685418 | Hospitalario con condiciones especiales e indicaciones largas | Ficha hospitalaria con condiciones especiales y textos extensos en indicaciones. Sirve para validar extracción por etiquetas y tolerancia a valores largos/multilínea. |
| 712570 | Ficha con múltiples indicaciones autorizadas/financiadas | Ficha con varias indicaciones autorizadas y/o financiadas. Sirve para validar que v1 conserva el bruto y no interpreta clínicamente las indicaciones. |

## Campos BIFIMED v1

| Etiqueta BIFIMED | Columna `bifimed_cache` | Notas |
| --- | --- | --- |
| Situación de financiación | `situacion_financiacion` | Mantener el texto semántico observado, por ejemplo `Si`, `Sí para determinadas indicaciones/condiciones` o `No incluido`. |
| Condiciones financiación restringidas | `condiciones_financiacion_restringidas` | Puede venir vacío o contener valores como `Visado`; no inferir reglas clínicas. |
| Condiciones especiales de financiación | `condiciones_especiales_financiacion` | Puede contener condiciones administrativas o grupos; preservar texto normalizado solo en espacios. |
| Estado de Nomenclátor | `estado_nomenclator` | Puede venir vacío o contener estados como `ALTA`, `H-ALTA` o `FINANCIADO PENDIENTE DE ALTA`. |
| Aportación usuario | `aportacion_usuario` | Preservar valores como `NORMAL`, `ESPECIAL` o `SIN APORTACION` sin reinterpretarlos. |
| Subgrupo ATC/Descripción | `subgrupo_atc` | Guardar código y descripción tal como aparezcan en la ficha, normalizando espacios. |

Además:

- `detalle_financiacion_json` almacenará un diccionario con el conjunto completo de pares etiqueta/valor extraídos.
- `raw_data` almacenará el contenido bruto que devuelva el cliente, para trazabilidad.

## Campos observados pero fuera de v1

Campos observados que no se normalizan todavía a columnas propias:

- Principio activo.
- Nombre presentación medicamento.
- Condiciones de prescripción y dispensación.
- Fechas de alta/baja.
- Indicaciones financiadas/no financiadas.
- Indicaciones autorizadas.
- Laboratorio.
- Receta.
- Tipo de envase.

Estos campos no se pierden conceptualmente: en v1 deben quedar disponibles en `detalle_financiacion_json` cuando se extraigan como pares etiqueta/valor y en `raw_data` como respuesta bruta trazable. La decisión de normalizarlos a columnas propias queda fuera de este PR.

## Contrato propuesto del futuro cliente

`BifimedClientResult`:

- `status`: `ok` | `not_found` | `error`
- `data`: `dict` normalizado con campos v1.
- `raw_payload`: contenido bruto devuelto por la fuente o por la capa de transporte.
- `error`: detalle técnico o funcional cuando `status` sea `error`; `None` en resultados `ok` y, salvo que sea útil para diagnóstico, en `not_found`.

Criterios:

- `ok`: se obtiene ficha de detalle válida y el `Código nacional` coincide con el CN solicitado.
- `not_found`: no se obtiene una ficha válida para el CN solicitado.
- `error`: fallo técnico, parseo imposible o respuesta inesperada.

## Reglas de parsing propuestas

- Extracción por etiquetas textuales, no por posición fija.
- Tolerar celdas vacías.
- Normalizar espacios y NBSP.
- Mantener texto semántico sin sobre-normalizar valores como `Si`, `Sí para determinadas indicaciones/condiciones` o `No incluido`.
- No interpretar clínicamente las indicaciones en esta primera fase.
- Diseñar el parser para no depender del idioma de navegación si la etiqueta cambia; en v1 usar páginas en castellano y documentarlo explícitamente.

## Riesgos abiertos

- No hay API pública documentada equivalente a CIMA; la primera implementación prevista será parseo HTML conservador.
- La estructura puede variar con cambios del portal.
- La detección de `not_found` debe verificarse en el PR del cliente con respuestas reales o fixtures adicionales.
- El acceso deberá ser respetuoso: timeout, reintentos limitados, caché y baja frecuencia.

## Decisiones para el siguiente PR

- Implementar `BifimedClient.get_by_cn(cn)`.
- Añadir parser HTML con tests sobre fixtures.
- Crear `sync_bifimed_cn(db, cn, force=False)`.
- Exponer `POST /bifimed/sync/{cn}` y `GET /bifimed/cache/{cn}`.
