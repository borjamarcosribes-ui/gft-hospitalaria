# Runbook operativo de la GFT hospitalaria digital

## 1. Objetivo

Esta guía describe el flujo funcional completo para operar la GFT hospitalaria digital desde la carga del Excel maestro hasta la publicación pública y la exportación HTML/PDF.

Está orientada a desarrolladores y validadores funcionales. No define cambios de lógica, modelos, migraciones ni frontend: únicamente documenta el uso operativo de las capacidades existentes y los puntos de verificación recomendados.

## 2. Flujo completo recomendado

### 2.1 Preparar el Excel maestro

1. Confirmar que cada fila tenga un `CN` válido y estable. El CN es la clave principal funcional para identificar la presentación GFT.
2. Completar las columnas clínicas/editoriales disponibles en el Excel cuando aplique:
   - `Estado editorial`.
   - `Observaciones revisión`.
   - `Nemónico`.
   - `Restricciones hospitalarias`.
   - `Observaciones internas GFT`.
   - `Comentario revisión`.
   - `Revisado por`.
   - `Fecha revisión`.
3. Revisar manualmente valores ambiguos antes de importarlos. Valores como `SI?`, `SÍ?`, `NO?`, `???` o vacío deben tratarse como pendientes de revisión funcional y no como decisiones publicables automáticas.
4. Verificar que los CN coinciden con los usados por CIMA/BIFIMED y por el catálogo hospitalario.

### 2.2 Validar/importar Excel

1. Ejecutar primero una validación sin persistencia si se quiere revisar estructura y errores de columnas/filas:
   - `POST /imports/excel/dry-run`
   - multipart con campo `file`.
   - Query opcional: `sheet_name`.
2. Importar el Excel maestro confirmado:
   - `POST /imports/excel`
   - multipart con campo `file`.
3. Guardar el `batch_id` devuelto. Se reutiliza para resumen, apply y sincronizaciones por lote.
4. Revisar el lote importado si es necesario:
   - `GET /imports/{batch_id}`.
   - `GET /imports/{batch_id}/summary`.
   - `GET /imports/{batch_id}/rows?limit=100&offset=0`.

### 2.3 Aplicar importación a GFT

1. Aplicar el lote validado:
   - `POST /imports/{batch_id}/apply`.
2. Revisar el resumen devuelto:
   - `applied_rows`: filas aplicadas a GFT.
   - `skipped_errors`: filas no aplicadas por errores de validación.
   - `skipped_missing_cn`: filas sin CN normalizado.
   - `skipped_pending`: filas con estado GFT no aplicable automáticamente.
   - `skipped_missing_estado_editorial`: filas sin estado editorial.
3. Tratar cualquier fila saltada como revisión funcional/manual antes de publicarla.

### 2.4 Sincronizar datos CIMA de medicamento

1. Sincronizar por lote tras aplicar/importar:
   - `POST /cima/sync/import-batch/{batch_id}`.
   - Query opcional: `force=true` para refrescar caché existente.
2. Para un CN concreto:
   - `POST /cima/sync/{cn}`.
   - `GET /cima/cache/{cn}` para inspeccionar caché.
3. Confirmar que el caché de medicamento contiene, cuando proceda, `nregistro`, nombre, presentación, forma farmacéutica, vías, ATC y enlaces de ficha técnica/prospecto.

### 2.5 Sincronizar ficha técnica segmentada, especialmente sección 4.1

1. La sección funcional crítica para indicaciones es `4.1` de la ficha técnica (`tipo_documento=1`).
2. Sincronizar por lote:
   - `POST /cima/segmented/sync/import-batch/{batch_id}?tipo_documento=1&seccion=4.1`.
   - Query opcional: `force=true`.
3. Sincronizar un `nregistro` concreto:
   - `POST /cima/segmented/sync/{nregistro}?tipo_documento=1&seccion=4.1&cn={cn}`.
   - `cn` es opcional en la ruta actual, pero es útil para asociar trazabilidad del caché.
4. Inspeccionar caché segmentada:
   - `GET /cima/segmented/cache/{nregistro}?tipo_documento=1&seccion=4.1`.
5. Solo se considera publicable automáticamente en la GFT pública la sección 4.1 que esté en caché con `sync_status = ok`.

### 2.6 Sincronizar BIFIMED

1. Sincronizar por lote:
   - `POST /bifimed/sync/import-batch/{batch_id}`.
   - Query opcional: `force=true`.
2. Sincronizar un CN concreto:
   - `POST /bifimed/sync/{cn}`.
3. Inspeccionar caché:
   - `GET /bifimed/cache/{cn}`.
4. Revisar especialmente situación de financiación, condiciones restringidas, condiciones especiales, estado en nomenclátor, aportación y subgrupo ATC.

### 2.7 Revisar medicamentos en panel admin

1. Abrir el panel frontend de administración en `/admin/gft`.
2. Configurar/introducir la clave admin requerida por el backend. Los endpoints admin usan cabecera `X-Admin-API-Key`.
3. Comprobar conectividad:
   - `GET /admin/health`.
4. Revisar resumen editorial:
   - `GET /admin/gft/medicamentos/editorial/summary`.
5. Listar medicamentos para revisión:
   - `GET /admin/gft/medicamentos/editorial?limit=50&offset=0`.
   - Filtros disponibles confirmados: `estado_gft`, `estado_editorial`, `q`, `limit`, `offset`.
6. Abrir un medicamento concreto:
   - `GET /admin/gft/medicamentos/{cn}/editorial`.

### 2.8 Completar campos clínicos/editoriales

1. Editar campos clínicos/editoriales confirmados por la API admin:
   - `restricciones_hospitalarias`.
   - `ajuste_insuficiencia_renal`.
   - `ajuste_insuficiencia_hepatica`.
   - `precauciones_embarazo`.
   - `precauciones_lactancia`.
   - `observaciones_internas`.
   - `comentario_revision`.
   - `revisado_por`.
2. Guardar cambios con:
   - `PATCH /admin/gft/medicamentos/{cn}/editorial`.
3. Validar que los campos publicables aparecen en la respuesta admin y, tras publicación, en la GFT pública/exportación. No asumir que campos internos deben exponerse si no forman parte del contrato público.

### 2.9 Cambiar estados GFT/editorial

1. Cambiar estados con:
   - `PATCH /admin/gft/medicamentos/{cn}/estado`.
2. Estados GFT permitidos:
   - `incluido`.
   - `excluido`.
   - `pendiente_revision`.
3. Estados editoriales permitidos:
   - `borrador`.
   - `validado`.
   - `publicado`.
   - `retirado`.
4. Para que un medicamento aparezca en la GFT pública debe quedar como:
   - `estado_gft = incluido`.
   - `estado_editorial = publicado`.
5. Cualquier combinación distinta debe considerarse no publicada.

### 2.10 Verificar publicación pública

1. Frontend público: acceder a la ruta pública configurada para la GFT. En despliegues habituales puede exponerse como `/gft`; confirmar el routing del entorno.
2. API pública confirmada por código:
   - `GET /gft/medicamentos?limit=20&offset=0`.
   - `GET /gft/medicamentos/{cn}`.
   - `GET /gft/atc`.
   - `GET /gft/principios-activos`.
3. Verificar búsqueda, filtros por letra, principio activo e índice ATC desde el frontend o la API.
4. Confirmar que medicamentos excluidos, pendientes o no publicados editorialmente no aparecen ni en listado ni en detalle.

### 2.11 Exportar HTML/PDF

1. Previsualización HTML imprimible:
   - `GET /gft/export/html`.
2. Descarga PDF:
   - `GET /gft/export/pdf`.
3. El HTML/PDF deben salir de la misma fuente publicada que la GFT pública. Si un medicamento no aparece en `/gft/medicamentos`, tampoco debe aparecer en la exportación.
4. Si falla el PDF pero el HTML funciona, revisar dependencias de renderizado PDF, especialmente WeasyPrint/pydyf y sus dependencias del sistema.

## 3. Reglas funcionales clave

- Solo se publica `estado_gft = incluido` y `estado_editorial = publicado`.
- Los valores dudosos como `SI?`, `SÍ?`, `NO?`, `???` o vacío no deben publicarse automáticamente. Deben quedar como revisión funcional/editorial antes de marcarse como publicados.
- `CN` es la clave principal funcional de la presentación GFT.
- `nregistro` se usa para CIMA y para localizar la ficha técnica segmentada.
- La sección `4.1` de ficha técnica alimenta `indicaciones_ficha_tecnica` cuando existe caché segmentada con `sync_status = ok`.
- La exportación PDF sale de la misma fuente publicada que la GFT pública.
- Los endpoints públicos deben exponer información funcional/publicable, no trazas técnicas internas, errores de sincronización ni campos auxiliares de caché.

## 4. Endpoints relevantes confirmados

> Nota: esta sección enumera rutas confirmadas en el código actual. Si se añaden rutas nuevas, revisar `app/api/routes/*.py` antes de actualizar el runbook.

### Públicos GFT

- `GET /gft/medicamentos` — listado público paginado. Query confirmada: `limit`, `offset`, `q`, `letra`, `principio_activo`, `atc`.
- `GET /gft/medicamentos/{cn}` — detalle público por CN.
- `GET /gft/atc` — índice ATC público.
- `GET /gft/principios-activos` — índice de principios activos.
- `GET /gft/export/html` — HTML imprimible de la guía publicada.
- `GET /gft/export/pdf` — PDF de la guía publicada.

### Frontend

- `/admin/gft` — panel admin GFT confirmado en el frontend.
- Ruta pública GFT: confirmar en el despliegue. El frontend renderiza la GFT pública para rutas no admin; si el entorno publica específicamente `/gft`, validar el rewrite/router del servidor web.

### Admin

Todos requieren `X-Admin-API-Key` válido.

- `GET /admin/health`.
- `GET /admin/gft/medicamentos/editorial/summary`.
- `GET /admin/gft/medicamentos/editorial`.
- `GET /admin/gft/medicamentos/{cn}/editorial`.
- `PATCH /admin/gft/medicamentos/{cn}/editorial`.
- `PATCH /admin/gft/medicamentos/{cn}/estado`.

### Importación

- `POST /imports/excel/dry-run`.
- `POST /imports/excel`.
- `POST /imports/{batch_id}/apply`.
- `GET /imports/{batch_id}/summary`.
- `GET /imports/{batch_id}`.
- `GET /imports/{batch_id}/rows`.

### CIMA medicamento y ficha técnica segmentada

- `POST /cima/sync/{cn}`.
- `GET /cima/cache/{cn}`.
- `POST /cima/sync/import-batch/{batch_id}`.
- `POST /cima/segmented/sync/import-batch/{batch_id}`.
- `POST /cima/segmented/sync/{nregistro}`.
- `GET /cima/segmented/cache/{nregistro}`.

### BIFIMED

- `POST /bifimed/sync/import-batch/{batch_id}`.
- `POST /bifimed/sync/{cn}`.
- `GET /bifimed/cache/{cn}`.

## 5. Validaciones manuales recomendadas

1. **Incluido/publicado visible**: un medicamento con `estado_gft = incluido` y `estado_editorial = publicado` aparece en listado público, detalle público, índice correspondiente y exportación.
2. **Excluido no visible**: un medicamento con `estado_gft = excluido` no aparece en GFT pública ni exportaciones aunque tenga datos CIMA/BIFIMED.
3. **Pendiente no visible**: un medicamento con `estado_gft = pendiente_revision` no aparece en GFT pública ni exportaciones.
4. **Editorial no publicado no visible**: un medicamento incluido pero con `estado_editorial` distinto de `publicado` no aparece.
5. **Indicaciones 4.1**: si existe caché segmentada de CIMA para `nregistro`, `tipo_documento = 1`, `seccion = 4.1` y `sync_status = ok`, el contenido se muestra como `indicaciones_ficha_tecnica`.
6. **Campos clínicos/editoriales**: tras editar desde admin, los campos publicables aparecen en la GFT pública y en exportación cuando el medicamento está publicado.
7. **PDF consistente**: el PDF contiene el mismo universo de medicamentos publicados que la API pública y el HTML imprimible.
8. **Sin campos técnicos**: la API pública, el frontend público y el PDF no deben mostrar `sync_status`, `sync_error`, IDs de batch, trazas, estados internos no publicables ni datos de auditoría técnica.

## 6. Errores frecuentes y cómo diagnosticarlos

- **CN no coincide**: el medicamento no se cruza con CIMA/BIFIMED o no se actualiza el registro esperado. Revisar normalización de CN, Excel maestro y rutas por CN.
- **`nregistro` ausente o incorrecto**: la ficha técnica segmentada no puede cruzarse con el medicamento. Revisar `GET /cima/cache/{cn}` y confirmar `nregistro`.
- **Ficha técnica 4.1 sin `sync_status = ok`**: `indicaciones_ficha_tecnica` no se publica. Revisar `GET /cima/segmented/cache/{nregistro}?tipo_documento=1&seccion=4.1` y repetir sync si procede.
- **Medicamento incluido pero no visible**: comprobar que también tenga `estado_editorial = publicado`.
- **Valores dudosos importados**: valores como `SI?`, `SÍ?`, `NO?`, `???` o vacío requieren validación manual y no deben traducirse a publicado automáticamente.
- **PDF falla y HTML no**: probable problema de WeasyPrint/pydyf o dependencias del sistema para renderizado PDF.
- **Panel admin devuelve 401/403/503**: revisar que `ADMIN_API_KEY` esté configurada en backend y que el frontend/petición envíe `X-Admin-API-Key`.
- **Batch aplicado con filas saltadas**: revisar `skipped_errors`, `skipped_missing_cn`, `skipped_pending` y `skipped_missing_estado_editorial` en la respuesta de apply.

## 7. Comandos de verificación

### Verificaciones mínimas para cambios documentales

```bash
PYTHONPATH=. python -m compileall -f -q app alembic tests
git diff --check
```

### Tests backend recomendados para ciclo GFT

```bash
PYTHONPATH=. pytest tests/integration/test_gft_api.py
PYTHONPATH=. pytest tests/integration/test_gft_public_export_workflow.py
PYTHONPATH=. pytest tests/integration/test_admin_gft_editorial_api.py tests/integration/test_admin_gft_state_api.py
PYTHONPATH=. pytest tests/integration/test_gft_pdf_html_export_api.py tests/integration/test_gft_pdf_export_api.py
PYTHONPATH=. pytest tests/integration/test_imports.py tests/integration/test_gft_import_workflow.py
PYTHONPATH=. pytest tests/integration/test_cima_sync.py tests/integration/test_cima_segmented_sync.py tests/integration/test_cima_segmented_batch_sync.py
PYTHONPATH=. pytest tests/integration/test_bifimed_sync.py
```

### Frontend recomendado

```bash
cd frontend && npm run typecheck
cd frontend && npm run build
```

Si el proyecto no define alguno de esos scripts npm en el entorno actual, documentar la limitación y ejecutar el build/check disponible en `frontend/package.json`.

## 8. Checklist operativo resumido

1. Excel maestro preparado y revisado.
2. Dry-run de Excel sin errores bloqueantes.
3. Importación con `batch_id` registrado.
4. Apply revisado sin filas saltadas inesperadas.
5. CIMA medicamento sincronizado.
6. CIMA ficha técnica segmentada 4.1 sincronizada con `sync_status = ok` donde aplique.
7. BIFIMED sincronizado.
8. Revisión clínica/editorial completada en `/admin/gft`.
9. Estados finales definidos: solo incluido + publicado para publicar.
10. GFT pública validada por API/frontend.
11. HTML y PDF exportados y comparados contra la fuente publicada.
12. No se exponen campos técnicos en vistas públicas.
