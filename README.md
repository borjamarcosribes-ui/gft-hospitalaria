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

## Publicación futura

La web y el PDF futuros deberán leer desde la vista SQL `v_gft_publicada`.

## BIFIMED

BIFIMED ya está implementado para parser, cliente, sincronización individual y sincronización por batch. La estrategia técnica está documentada en [docs/bifimed_audit.md](docs/bifimed_audit.md).


## CIMA ficha técnica segmentada

La estrategia técnica y de flujo para la futura ficha técnica segmentada de CIMA está documentada en [docs/cima_ficha_tecnica_segmentada_audit.md](docs/cima_ficha_tecnica_segmentada_audit.md). La implementación queda pendiente: este módulo todavía no incorpora cliente, parser, sincronización, migraciones ni fixtures contractuales.

## API pública GFT

El contrato actual de la API pública `/gft` y el origen de sus campos están documentados en [docs/gft_public_api_contract.md](docs/gft_public_api_contract.md).

## Seguridad admin

- [docs/admin_security.md](docs/admin_security.md) — protección mínima de endpoints admin.

## Edición clínica/editorial GFT

El flujo previsto para edición clínica/editorial hospitalaria está documentado en [docs/gft_editorial_workflow.md](docs/gft_editorial_workflow.md).

## Cambio de estado GFT/editorial

- [docs/gft_publication_state_workflow.md](docs/gft_publication_state_workflow.md) — reglas para cambio de estado GFT/editorial.
