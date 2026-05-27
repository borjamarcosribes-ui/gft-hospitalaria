# GFT Linkage Backfill

## Preparación

```bash
cd /workspaces/gft-hospitalaria
source .venv/bin/activate
export DATABASE_URL="postgresql+psycopg://gft:gft@localhost:5432/gft"
export ADMIN_API_KEY="demo-local-admin-key"
python -m alembic upgrade head
```

## Auditoría published/imported

```bash
PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py --scope published --json
PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py --scope imported --json
```

## Dry-run published

```bash
PYTHONPATH=. python scripts/run_gft_cache_backfill.py \
  --dry-run \
  --scope published \
  --batch-size 100 \
  --max-batches 1 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --seed-from-imported-urls \
  --repair-not-found-from-imported-url \
  --json
```

## Real published

```bash
PYTHONPATH=. python scripts/run_gft_cache_backfill.py \
  --confirm-write \
  --scope published \
  --batch-size 100 \
  --max-batches 2 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --seed-from-imported-urls \
  --repair-not-found-from-imported-url \
  --json | tee /tmp/gft_cache_backfill_published_$(date +%Y%m%d_%H%M).log
```

## Real imported

```bash
PYTHONPATH=. python scripts/run_gft_cache_backfill.py \
  --confirm-write \
  --scope imported \
  --priority-mode \
  --batch-size 100 \
  --max-batches 3 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --seed-from-imported-urls \
  --repair-not-found-from-imported-url \
  --sleep-seconds 0.2 \
  --json | tee /tmp/gft_cache_backfill_imported_$(date +%Y%m%d_%H%M).log
```

## Wrapper rápido published

```bash
PYTHONPATH=. python scripts/run_gft_fast_public_backfill.py \
  --dry-run \
  --batch-size 100 \
  --max-batches 1 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --seed-from-imported-urls \
  --repair-not-found-from-imported-url \
  --json
```

## Flujo post-importación optimizado

Preparación:

```bash
cd /workspaces/gft-hospitalaria
source .venv/bin/activate
export DATABASE_URL="postgresql+psycopg://gft:gft@localhost:5432/gft"
export ADMIN_API_KEY="demo-local-admin-key"
python -m alembic upgrade head
```

Auditoría inicial:

```bash
PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py --scope published --json
PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py --scope imported --json
```

Dry-run:

```bash
PYTHONPATH=. python scripts/run_gft_post_import_pipeline.py \
  --dry-run \
  --scope imported \
  --priority-mode \
  --batch-size 100 \
  --max-batches 1 \
  --bifimed-limit 100 \
  --cima-med-limit 100 \
  --sections-limit 50 \
  --summaries-limit 100 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --seed-from-imported-urls \
  --repair-not-found-from-imported-url \
  --workers 1 \
  --json
```

Real prudente:

```bash
PYTHONPATH=. python scripts/run_gft_post_import_pipeline.py \
  --confirm-write \
  --scope imported \
  --priority-mode \
  --batch-size 100 \
  --max-batches 3 \
  --bifimed-limit 300 \
  --cima-med-limit 300 \
  --sections-limit 150 \
  --summaries-limit 250 \
  --sections 4.1 4.2 4.3 4.4 4.6 \
  --only-missing \
  --seed-from-imported-urls \
  --repair-not-found-from-imported-url \
  --workers 3 \
  --sleep-seconds 0.2 \
  --json | tee runtime_logs/gft_post_import_$(date +%Y%m%d_%H%M).log
```

Reanudación:
- repetir el mismo comando con `--only-missing`.
- no borra ni repite lo ya cacheado.
