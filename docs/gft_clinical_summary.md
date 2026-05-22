# Resumen clínico automático y financiación visible

Flujo recomendado:
1. Verificar readiness.
2. `PYTHONPATH=. python scripts/gft_clinical_sections_audit.py --json`
3. `PYTHONPATH=. python scripts/sync_gft_clinical_sections.py --dry-run --limit 20 --json`
4. `PYTHONPATH=. python scripts/sync_gft_clinical_sections.py --limit 20 --confirm-write --json`
5. `PYTHONPATH=. python scripts/generate_gft_clinical_summaries.py --dry-run --limit 20 --json`
6. `PYTHONPATH=. python scripts/generate_gft_clinical_summaries.py --limit 20 --confirm-write --json`
7. Revisar pública.

Los resúmenes son automáticos, trazables y no sustituyen la ficha técnica oficial AEMPS/CIMA.
No se modifican estados GFT/editoriales.
