# Control clínico GFT (dry-run)

Este módulo resuelve la auditoría previa a cualquier escritura clínica real, usando exclusivamente el universo de `v_gft_publicada`.

Analiza cobertura CIMA por CN, disponibilidad de `nregistro`, cobertura de secciones 4.1, 4.2, 4.3, 4.4 y 4.6, plan de sync en dry-run y plan de generación de resúmenes en dry-run.

- **CIMA cache OK**: CN con `sync_status=ok` en caché de medicamento CIMA.
- **nregistro**: identificador regulatorio necesario para consultar ficha técnica segmentada.
- **only-missing**: solo considera como candidatos las secciones/resúmenes no cubiertos correctamente.

## Orden recomendado
1. Revisar panel admin `/admin/gft/clinico`.
2. Ejecutar pipeline dry-run.
3. Revisar ejemplos y bloqueos.
4. Solo después decidir lote real pequeño.

> No ejecutar `--confirm-write` sin revisión humana.

## Comandos
- Audit: `PYTHONPATH=. python scripts/gft_clinical_sections_audit.py --json`
- Sync dry-run: `PYTHONPATH=. python scripts/sync_gft_clinical_sections.py --dry-run --limit 20 --only-missing --json`
- Summaries dry-run: `PYTHONPATH=. python scripts/generate_gft_clinical_summaries.py --dry-run --limit 20 --only-missing --json`
- Pipeline dry-run: `PYTHONPATH=. python scripts/gft_clinical_pipeline_dry_run.py --limit 20 --only-missing --json`

Este PR no publica medicamentos ni modifica estado editorial y no ejecuta escrituras clínicas reales.
