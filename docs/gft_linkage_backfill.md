# GFT Linkage Backfill

Define universos CN (`published`, `included`, `state`, `imported`, `all_known`) and process linkage in safe batches.

- `published` is still the public boundary (`v_gft_publicada`).
- Wider scopes do **not** publish anything automatically.

## Audit
- `PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py --scope published --json`
- `PYTHONPATH=. python scripts/gft_linkage_coverage_audit.py --scope all_known --json`

## BIFIMED
- Dry-run: `PYTHONPATH=. python scripts/run_gft_bifimed_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --only-missing --json`
- Write: same command with `--confirm-write`.

## CIMA medicamento
- Dry-run: `PYTHONPATH=. python scripts/run_gft_cima_medicamento_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --only-missing --json`
- Write: same command with `--confirm-write`.

## Secciones + resúmenes
- `PYTHONPATH=. python scripts/run_gft_clinical_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --json`

## Orquestador global
- Dry-run: `PYTHONPATH=. python scripts/run_gft_linkage_backfill.py --dry-run --scope all_known --batch-size 50 --max-batches 1 --only-missing --json`
- Write controlado: same with `--confirm-write`.

> Siempre revisar `--dry-run` antes de `--confirm-write`.
> No ejecutar `all_known` con lotes grandes sin validar primero.
