# Pipeline clínico GFT

- Universo: `v_gft_publicada`.
- Secciones CIMA: 4.1 indicaciones, 4.2 posología, 4.3 contraindicaciones, 4.4 advertencias, 4.6 embarazo/lactancia.
- `CIMA cache OK`: registro disponible y sincronizado correctamente.
- `nregistro`: identificador CIMA necesario para sincronizar secciones.
- `summary_ready`: CN con al menos una sección clínica disponible para resumen.

## Auditorías
- Clínica: `PYTHONPATH=. python scripts/gft_clinical_coverage_audit.py --json`
- BIFIMED: `PYTHONPATH=. python scripts/gft_bifimed_coverage_audit.py --json`

## Backfill
- Dry-run (recomendado):
  `PYTHONPATH=. python scripts/run_gft_clinical_backfill.py --dry-run --batch-size 20 --max-batches 1 --sections 4.2 4.3 4.4 4.6 --only-missing --json`
- Real controlado:
  `PYTHONPATH=. python scripts/run_gft_clinical_backfill.py --confirm-write --batch-size 20 --max-batches 1 --sections 4.2 4.3 4.4 4.6 --only-missing --json`

> No ejecutar `--confirm-write` sin revisar antes el dry-run.

## Revisar después
- Ficha pública (IR/IH/embarazo/lactancia desde resumen automático).
- Cobertura por secciones y resumen.
- Cobertura BIFIMED y condiciones.

## Fuera de alcance
- Restricciones hospitalarias editoriales.
- CN sin CIMA cache OK.
- Condiciones BIFIMED no presentes en fuente local.
