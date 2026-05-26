# GFT Linkage Backfill

Define universos CN (`published`, `included`, `state`, `imported`, `all_known`) y procesa linkage en lotes seguros y reanudables.

- `published` sigue siendo el perímetro público (`v_gft_publicada`).
- Alcances más amplios **no publican** nada automáticamente.
- **Codex solo prepara scripts/documentación**; la ejecución real se hace en terminal local porque escribe caché y puede hacer llamadas externas.

## Recomendación operativa para backfill masivo (~5000 CN)

Orden recomendado:

1. Auditar `published`.
2. Ejecutar backfill `published` por tandas pequeñas.
3. Re-auditar `published`.
4. Ejecutar backfill `all_known` por tandas pequeñas.
5. Auditar `all_known`.

Esta secuencia prioriza primero el universo publicado y evita gastar lotes masivos sin visibilidad previa.

## Preparación de entorno

```bash
cd /workspaces/gft-hospitalaria
source .venv/bin/activate
export DATABASE_URL="postgresql+psycopg://gft:gft@localhost:5432/gft"
export ADMIN_API_KEY="demo-local-admin-key"
alembic upgrade head
```

Comprobar conexión antes de ejecutar auditorías/backfills:

```bash
python - <<'PY'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    print("dialect =", conn.dialect.name)
    print("database =", conn.execute(text("SELECT current_database()")).scalar())
PY
```

Esperado:
- `dialect = postgresql`
- `database = gft`

No lances backfill si `dialect != postgresql`. `--allow-default-db` solo debe usarse en tests/desarrollo controlado.

## Auditoría inicial

```bash
PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py \
  --scope published \
  --json

PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py \
  --scope all_known \
  --json
```

## Backfill published (seguro por tandas)

Dry-run:

```bash
PYTHONPATH=. python scripts/run_gft_linkage_backfill.py \
  --dry-run \
  --scope published \
  --batch-size 100 \
  --max-batches 1 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --json
```

Ejecución real:

```bash
PYTHONPATH=. python scripts/run_gft_linkage_backfill.py \
  --confirm-write \
  --scope published \
  --batch-size 100 \
  --max-batches 1 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --sleep-seconds 0.2 \
  --json
```

## Backfill all_known (seguro por tandas)

Dry-run:

```bash
PYTHONPATH=. python scripts/run_gft_linkage_backfill.py \
  --dry-run \
  --scope all_known \
  --batch-size 100 \
  --max-batches 1 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --json
```

Ejecución real:

```bash
PYTHONPATH=. python scripts/run_gft_linkage_backfill.py \
  --confirm-write \
  --scope all_known \
  --batch-size 100 \
  --max-batches 1 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --sleep-seconds 0.2 \
  --json
```

## Regenerar resúmenes generales con `force`

```bash
PYTHONPATH=. python scripts/generate_gft_clinical_summaries.py \
  --confirm-write \
  --candidate-mode summary_ready \
  --scope all_known \
  --limit 200 \
  --force \
  --json
```

## Qué métricas revisar

- `bifimed.sin_cache`
- `cima.sin_cache`
- `cima.ok`
- `sections.complete_all_requested_sections`
- `summaries.con_resumen`
- `summaries.con_resumen_general`
- `linked_status_counts.full_public_ready`
- `not_found` no es necesariamente error

## Cuándo parar una tanda

- muchos `not_found` consecutivos
- errores externos repetidos
- rate limit
- tiempos excesivos
- caída de backend/DB

## Advertencias de seguridad

- No lanzar `all_known` con `max-batches` grande sin revisar antes `--dry-run`.
- Evitar ejecuciones ilimitadas: usar siempre `--batch-size` y `--max-batches`.
- En CI no debe ejecutarse backfill con llamadas externas ni escritura de caché.

## Scripts específicos (si se necesita granularidad)

- BIFIMED dry-run: `PYTHONPATH=. python scripts/run_gft_bifimed_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --only-missing --json`
- CIMA medicamento dry-run: `PYTHONPATH=. python scripts/run_gft_cima_medicamento_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --only-missing --json`
- Clínico dry-run: `PYTHONPATH=. python scripts/run_gft_clinical_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --json`

## Reglas de `source_status`

- `ok` / `partial`: resumen clínico útil para métricas de cobertura.
- `missing_source`: no cuenta como resumen útil y no debe incrementar `con_resumen` ni campos clínicos derivados.
- Por defecto, el backfill **no escribe** filas `missing_source` en `gft_clinical_summary_cache`.
- Si se necesita persistir intentos sin fuente, usar `scripts/generate_gft_clinical_summaries.py --write-missing-source` explícitamente.

Si existen filas históricas `missing_source`, se pueden limpiar con:

```sql
DELETE FROM gft_clinical_summary_cache
WHERE source_status = 'missing_source';
```

## Backfill rápido recomendado tras importar Excel

Usar `scripts/run_gft_fast_public_backfill.py` en modo `--dry-run` y luego `--confirm-write` por tandas, con `--seed-from-imported-urls` y `--repair-not-found-from-imported-url` para priorizar CIMA desde URLs AEMPS importadas.
