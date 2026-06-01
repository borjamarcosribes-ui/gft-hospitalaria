# Backfill seguro CIMA/BIFIMED guiado por auditoría GFT

Este backfill enriquece medicamentos publicados de la GFT usando la auditoría/payload canónico como fuente de selección. No cambia UI ni PDF y no se ejecuta automáticamente al importar módulos ni durante tests.

## Runner principal

```bash
python -m scripts.backfill_gft_enrichment --source all --mode dry-run --limit 50 --audit-before
```

Argumentos soportados:

- `--source cima|bifimed|clinical|all`
- `--mode dry-run|run` (por defecto `dry-run`)
- `--limit N`, `--offset N`, `--cn CN`
- `--resume`
- `--checkpoint-path PATH`
- `--log-path PATH`
- `--sleep SECONDS` (por defecto 0.5)
- `--only-missing` / `--no-only-missing` (por defecto `--only-missing`)
- `--include-incomplete` (diagnóstico: reintenta caches existentes pero incompletas, como sin indicaciones)
- `--force` (nunca activo por defecto)
- `--stop-on-error`
- `--audit-before`, `--audit-after`

## Modos recomendados

### Ver candidatos sin tocar datos

```bash
python -m scripts.backfill_gft_enrichment --source all --mode dry-run --limit 50 --audit-before
```

### Piloto CIMA

```bash
python -m scripts.backfill_gft_enrichment --source cima --mode run --limit 20 --sleep 1 --checkpoint-path data/output/backfill_cima_pilot.json --log-path data/output/backfill_cima_pilot.jsonl --audit-before --audit-after
```

### Piloto BIFIMED

```bash
python -m scripts.backfill_gft_enrichment --source bifimed --mode run --limit 20 --sleep 1 --checkpoint-path data/output/backfill_bifimed_pilot.json --log-path data/output/backfill_bifimed_pilot.jsonl --audit-before --audit-after
```

### Ejecución masiva recomendada

Por defecto, `--only-missing` selecciona caches realmente ausentes y evita consumir el lote con filas ya cacheadas pero incompletas. En CIMA no se seleccionan filas con CIMA disponible pero sin `indicaciones_ficha_tecnica`; en BIFIMED no se seleccionan filas con `bifimed_cache` presente pero sin indicaciones extraíbles; en clinical se priorizan filas sin resumen clínico.

```bash
python -m scripts.backfill_gft_enrichment --source cima --mode run --limit 100 --sleep 1 --checkpoint-path data/output/backfill_cima_mass.json --log-path data/output/backfill_cima_mass.jsonl --audit-before --audit-after
python -m scripts.backfill_gft_enrichment --source bifimed --mode run --limit 100 --sleep 1 --checkpoint-path data/output/backfill_bifimed_mass.json --log-path data/output/backfill_bifimed_mass.jsonl --audit-before --audit-after
```

### Reintentar incompletos solo para diagnóstico

Usa `--include-incomplete` cuando quieras revisar explícitamente filas ya cacheadas pero incompletas, por ejemplo `sin_indicaciones_cima`, `bifimed_sin_indicaciones` o estados clínicos incompletos. Este modo puede producir muchos resultados `unchanged`, `no_data` o `not_found`; no es el modo recomendado para backfills masivos/nocturnos.

```bash
python -m scripts.backfill_gft_enrichment --source bifimed --mode run --include-incomplete --limit 100 --sleep 1 --checkpoint-path data/output/backfill_bifimed_incomplete.json --log-path data/output/backfill_bifimed_incomplete.jsonl
```

### Reanudar ejecución

```bash
python -m scripts.backfill_gft_enrichment --source all --mode run --resume --checkpoint-path data/output/backfill_full.json --log-path data/output/backfill_full.jsonl --sleep 1 --audit-after
```

Con `--resume`, el runner lee el checkpoint, conserva los estados previos y salta los items ya marcados como `success` o `skipped_existing`. Los items `pending`, `error`, `rate_limited`, `not_found`, `no_data` y `unchanged` pueden reevaluarse en la reanudación para permitir recuperación operativa tras errores transitorios.

## Logs y checkpoints

Si no se indican rutas, se crean rutas timestamped bajo `data/output/`:

- Checkpoint JSON: `data/output/backfill_<source>_<timestamp>.json`
- Log JSONL: `data/output/backfill_<source>_<timestamp>.jsonl`
- Auditorías: `data/output/backfill_audit_before_<timestamp>.json` y `data/output/backfill_audit_after_<timestamp>.json`

Cada línea JSONL incluye `timestamp`, `cn`, `nombre`, `source`, `action`, `status`, `message`, `duration_ms`, `changed_fields`, `reason` y `error` resumido cuando aplica. Los estados `unchanged`, `no_data` y `not_found` quedan visibles tanto en checkpoint como en log. No se guarda HTML masivo ni datos sensibles.

## Garantías anti-sobrescritura

- `dry-run` no llama a servicios de escritura.
- `--only-missing` está activo por defecto.
- Las filas ya cacheadas pero incompletas no se reintentan salvo con `--include-incomplete`.
- `--force` solo se usa si se indica explícitamente.
- Si ya existe un dato útil, el backfill no lo reemplaza por vacío.
- Incluso con `--force`, si una respuesta nueva queda vacía para campos donde había contenido útil, el runner restaura esos campos y marca el item como `unchanged`/`no_data` según corresponda.
- Los CN que fallen registran error y la ejecución continúa salvo con `--stop-on-error`.

## Fuera de alcance

- No cambia PDF.
- No cambia diseño web.
- No usa como base PR 129 ni PR 130.
- No inventa datos ni hardcodea medicamentos/CN.
- No cambia reglas de inclusión GFT.
- No hace scraping real en tests.
- No introduce normalización avanzada CIMA ni convierte el PDF en fuente de lógica.
