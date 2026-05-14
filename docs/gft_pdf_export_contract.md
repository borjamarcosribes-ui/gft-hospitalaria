# Contrato de exportación PDF de la GFT pública

## 1. Finalidad

La exportación PDF de la Guía Farmacoterapéutica (GFT) debe generar una versión imprimible y archivable de la GFT pública hospitalaria.

El PDF no será una fuente alternativa ni un canal de publicación independiente: debe representar exactamente el mismo universo publicado que consulta la web pública a través de `/gft`. Su finalidad es facilitar la impresión, archivo, revisión documental y distribución controlada de una fotografía de la GFT digital publicada en un momento concreto.

## 2. Fuente de datos

La fuente funcional del PDF será la vista SQL `v_gft_publicada` o, alternativamente, el mismo servicio público que alimenta `/gft`, siempre que dicho servicio aplique las mismas reglas contractuales de publicación.

El PDF debe generarse desde la misma base de datos publicada que alimenta la GFT digital. No debe existir una fuente paralela, una consulta directa a staging, una exportación desde ficheros importados ni una composición manual que pueda divergir de `/gft`.

Reglas obligatorias de inclusión:

- Se incluyen únicamente medicamentos con `estado_gft = 'incluido'` y `estado_editorial = 'publicado'`.
- No se incluyen medicamentos excluidos.
- No se incluyen medicamentos pendientes de revisión.
- No se incluyen borradores.
- No se incluyen medicamentos retirados o despublicados.
- No se incluyen registros importados pero no aplicados a la GFT publicada.
- No se incluyen campos técnicos internos, payloads crudos, errores de sincronización ni metadatos operativos que no formen parte de la consulta pública.

## 3. Alcance inicial del PDF

El primer alcance del PDF será una exportación completa de la guía publicada.

No se implementarán inicialmente exportaciones parciales filtradas por grupo ATC, letra, principio activo, texto libre u otros criterios. Estos filtros podrán valorarse como evolución futura, siempre manteniendo la misma frontera de publicación que `/gft`.

## 4. Estructura propuesta del PDF

### Portada

La portada debe incluir, como mínimo:

- Título: **“Guía Farmacoterapéutica Hospitalaria”**.
- Fecha y hora de generación.
- Nota: **“Documento generado desde la base de datos publicada de la GFT digital”**.
- Versión, identificador documental o identificador de generación, si existe en el futuro.

### Índice ATC

El índice debe facilitar la navegación por grupos terapéuticos:

- Agrupación por niveles ATC L1-L5 cuando existan datos suficientes.
- Al menos niveles L1/L2 como estructura visible.
- Recuento de medicamentos por grupo si es técnicamente viable y no penaliza la legibilidad.

### Cuerpo

El cuerpo debe contener los medicamentos publicados organizados de forma clínica y legible:

- Agrupación principal por ATC.
- Dentro de cada grupo, orden por principio activo, nombre comercial y CN.
- Cada medicamento debe representarse en un bloque compacto, claramente separado del siguiente y apto para lectura en pantalla o papel.

### Pie o nota final

El documento debe finalizar, o incluir en pie de página cuando sea viable, una nota con:

- Advertencia de que la ficha técnica y el prospecto oficiales prevalecen sobre cualquier resumen o campo editorial de la GFT.
- Fecha de generación del PDF.
- Origen de información: GFT digital hospitalaria.

## 5. Campos públicos mínimos en cada medicamento

Cada bloque de medicamento debe incluir, como mínimo, los siguientes campos públicos cuando estén disponibles:

- Nombre comercial.
- Principio activo.
- Forma farmacéutica.
- Vía de administración.
- Nemónico.
- CN.
- Código ATC.
- Descripción ATC por niveles.
- Indicaciones en ficha técnica.
- Ajuste por insuficiencia renal.
- Ajuste por insuficiencia hepática.
- Precauciones en embarazo.
- Precauciones en lactancia.
- Restricciones de uso hospitalarias.
- Situación de financiación BIFIMED.
- URL de ficha técnica.
- URL de prospecto.

Los campos vacíos, nulos o no disponibles se representarán como **“No informado”** para evitar ambigüedad entre ausencia de dato y omisión accidental en la generación del PDF.

## 6. Campos excluidos del PDF

El PDF no debe mostrar campos técnicos internos, datos de auditoría, payloads crudos ni información operativa de sincronización o revisión interna.

En particular, no deben aparecer:

- `raw_data`.
- `contenido_html`.
- `sync_status`.
- `sync_error`.
- Observaciones internas de importación.
- `comentario_revision`.
- `revisado_por`.
- `fecha_revision`.
- Estados internos si no son necesarios para el lector público.
- Claves API.
- Metadatos técnicos de sincronización.

## 7. Diseño visual

El diseño visual debe ser:

- Institucional y sanitario.
- Sobrio, sin elementos decorativos innecesarios.
- Basado en una paleta blanco/azul/gris suave.
- De alta legibilidad, con tipografías y tamaños adecuados para consulta clínica.
- Apto para impresión en papel y revisión digital.
- Estructurado con separadores, encabezados y espaciado suficiente para evitar bloques excesivamente largos sin separación.
- Completo en contenido: no debe esconder información relevante para ganar compacidad visual.

## 8. Estrategia técnica futura

Cuando se implemente la exportación, se propone crear el endpoint público:

```http
GET /gft/export/pdf
```

Requisitos técnicos esperados:

- El endpoint debe consultar `v_gft_publicada` o el mismo servicio público que alimenta `/gft`.
- La generación síncrona será aceptable inicialmente si el volumen de medicamentos permite tiempos de respuesta razonables.
- Si el volumen crece o el coste de generación es elevado, deberá valorarse una generación asíncrona, cacheada o precomputada por versión de publicación.
- La respuesta HTTP debe usar `Content-Type: application/pdf`.
- El nombre de archivo sugerido es `gft_hospitalaria_YYYYMMDD.pdf`.

Esta estrategia no implica implementación en este documento. No se añaden dependencias, endpoints ni cambios de modelo como parte de este contrato.

## 9. Criterios de aceptación futuros

Cuando se implemente la generación PDF, deberán cumplirse al menos estos criterios:

- El PDF y `/gft` deben tener el mismo universo de medicamentos publicados.
- Un medicamento retirado o despublicado no debe aparecer en el PDF.
- Un medicamento incluido y publicado sí debe aparecer en el PDF.
- Los campos técnicos internos no deben aparecer en el PDF.
- Las `indicaciones_ficha_tecnica` deben proceder de la sección 4.1 cacheada si está disponible y sincronizada correctamente.
- Los campos clínicos/editoriales deben coincidir con lo visible en `/gft`.
- Los campos vacíos deben aparecer como **“No informado”**.
- La fecha/hora de generación debe quedar visible en el documento.

## 10. Pendientes

Quedan pendientes para una implementación futura:

- Elegir la librería de generación PDF.
- Definir si el PDF se genera desde HTML/CSS o mediante un motor PDF directo.
- Crear el endpoint `GET /gft/export/pdf`.
- Añadir tests de equivalencia entre `/gft` y el PDF.
- Validar manualmente la legibilidad con datos reales.
- Decidir si se añade índice clicable o marcadores internos.
- Definir política de cacheado o versionado si el volumen de generación lo requiere.
