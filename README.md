# gft-hospitalaria

## Levantar PostgreSQL

```bash
docker compose up -d db
```

## Migraciones

```bash
alembic upgrade head
```

## Tests

```bash
pytest
```

## Formato Excel esperado

Columnas mínimas:
- CN
- Observaciones revisión
- Estado editorial

Columnas opcionales:
- Nemónico
- Restricciones hospitalarias
- Observaciones internas GFT
- Comentario revisión
- Revisado por
- Fecha revisión

## Estados

- estado_gft: incluido | excluido | pendiente_revision
- estado_editorial: borrador | validado | publicado | retirado
- import_batch.status: uploaded | processing | validated | with_errors | ready_to_publish | published | rejected | failed

## Estado actual GFT

### Implementado

- Modelo de datos GFT, migraciones y vista SQL `v_gft_publicada` como frontera de publicación.
- Importación desde Excel a staging, validación/dry-run, resumen de batch y `apply` a `gft_estado_presentacion`.
- Sincronización CIMA de medicamento por CN y por batch, incluyendo `nregistro`, documentos, ATC y principios activos.
- CIMA ficha técnica segmentada por `nregistro`, con sync individual y por batch, caché persistida y publicación de la sección `4.1` como `indicaciones_ficha_tecnica` cuando está en `sync_status = ok`.
- BIFIMED: parser, cliente, sincronización individual, sincronización por batch y caché de financiación.
- API pública `/gft` con listado, detalle por CN, índice ATC, índice de principios activos y exportación pública HTML/PDF.
- Frontend público con búsqueda, filtros, navegación por índice ATC y botón de exportación PDF.
- Panel admin `/admin/gft` con resumen, listado, detalle, edición clínica/editorial y cambio de estado GFT/editorial.
- Cadena única de exportación: `build_gft_pdf_export_data(db)` → `render_gft_pdf_html(export_data)` → `render_gft_pdf_bytes(html)`.
- Runbook operativo y guía manual de verificación PDF.

### Parcial

- La protección admin e interna actual se basa en `X-Admin-API-Key`; cubre `/admin`, `/imports`, `/cima` y `/bifimed`, y es suficiente para entornos controlados o demo interna, pero no equivale a autenticación corporativa con usuarios, roles y auditoría.
- Los campos clínicos/editoriales hospitalarios son editables manualmente y se publican según contrato, pero requieren validación funcional con datos reales y revisión clínica.
- La exportación PDF está implementada, pero su estabilidad operativa depende de tener WeasyPrint/pydyf y las librerías de sistema correctamente instaladas en el despliegue.

### Pendiente para producción

- Autenticación robusta, roles, auditoría de cambios y gestión formal de sesiones.
- Validación con datos reales y checklist funcional antes de considerar una v1 productiva.
- Hardening de despliegue: variables de entorno, secretos, PostgreSQL, CORS/proxy, observabilidad y dependencias de renderizado PDF.
- Política de versionado/caché del PDF si el volumen o la trazabilidad documental lo requieren.
- Separación futura de observaciones internas no publicables si aparecen contenidos que no deban exponerse públicamente.

## BIFIMED

BIFIMED ya está implementado para parser, cliente, sincronización individual y sincronización por batch. La estrategia técnica está documentada en [docs/bifimed_audit.md](docs/bifimed_audit.md).


## CIMA ficha técnica segmentada

La estrategia técnica y el estado de implementación de CIMA ficha técnica segmentada están documentados en [docs/cima_ficha_tecnica_segmentada_audit.md](docs/cima_ficha_tecnica_segmentada_audit.md). El módulo ya incorpora cliente/parser, modelo, migración, fixtures contractuales, sync individual por `nregistro`, sync por batch y publicación de la sección `4.1` como `indicaciones_ficha_tecnica` cuando existe caché válida.

## API pública GFT

El contrato actual de la API pública `/gft` y el origen de sus campos están documentados en [docs/gft_public_api_contract.md](docs/gft_public_api_contract.md).

La GFT pública incluye navegación visual por índice ATC para filtrar por grupos terapéuticos.

La GFT pública permite exportar desde su cabecera la guía completa publicada en PDF mediante `GET /gft/export/pdf`, independientemente de los filtros activos en pantalla.

El contrato funcional y técnico de la exportación imprimible de la GFT pública está documentado en [docs/gft_pdf_export_contract.md](docs/gft_pdf_export_contract.md). La previsualización HTML imprimible está disponible en `GET /gft/export/html`; la descarga PDF pública está disponible en `GET /gft/export/pdf`. La guía breve de verificación manual está disponible en [docs/gft_pdf_export_manual_check.md](docs/gft_pdf_export_manual_check.md).


## Demo local GFT

- [docs/gft_demo_local.md](docs/gft_demo_local.md) — guía breve para preparar una demo local/visual con datos controlados, sin llamadas reales a CIMA ni BIFIMED.

## Runbook operativo GFT

- [docs/gft_operational_runbook.md](docs/gft_operational_runbook.md) — guía integral para operar el flujo funcional completo de la GFT hospitalaria digital: Excel maestro, importación/apply, sincronizaciones CIMA/BIFIMED, revisión admin, publicación y exportación HTML/PDF.

## Seguridad admin

- [docs/admin_security.md](docs/admin_security.md) — protección mínima de endpoints admin e internos (`/admin`, `/imports`, `/cima`, `/bifimed`).

## Edición clínica/editorial GFT

El flujo previsto para edición clínica/editorial hospitalaria está documentado en [docs/gft_editorial_workflow.md](docs/gft_editorial_workflow.md).

## Cambio de estado GFT/editorial

- [docs/gft_publication_state_workflow.md](docs/gft_publication_state_workflow.md) — reglas para cambio de estado GFT/editorial.
