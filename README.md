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
