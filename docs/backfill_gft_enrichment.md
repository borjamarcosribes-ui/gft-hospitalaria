# Backfill seguro CIMA/BIFIMED guiado por auditoría GFT

Este backfill enriquece caches CIMA/BIFIMED/clinical con protección anti-sobrescritura, dry-run, logs, checkpoints y auditoría. No cambia UI ni PDF, no se ejecuta automáticamente al importar módulos ni durante tests, y **cachear medicamentos no publicados no implica publicarlos en la web**.

## Alcances (`--scope`)

El runner soporta:

- `--scope gft-publicada` (por defecto): modo seguro para la web actual. Selecciona solo medicamentos incluidos y publicados en la GFT mediante la auditoría/payload canónico.
- `--scope all-imported`: modo para enriquecer PostgreSQL con todos los artículos procedentes del Excel/import maestro aplicado, incluidos los no publicados o excluidos, siempre que tengan CN válido.
- `--scope excel-master`: alias operativo de `all-imported` para el Excel maestro/import Orion/AEMPS.

`all-imported`/`excel-master` deduplican por CN normalizado, preservan ceros a la izquierda y omiten CN inválidos en el universo (`total_skipped_invalid_cn`). Para `--source all` en estos alcances se planifican CIMA y BIFIMED; clinical se mantiene ligado al flujo de GFT publicada.

## Runner principal

```bash
python -m scripts.backfill_gft_enrichment --source all --scope gft-publicada --mode dry-run --limit 50 --audit-before
```

Argumentos soportados:

- `--source cima|bifimed|clinical|all`
- `--scope gft-publicada|excel-master|all-imported` (por defecto `gft-publicada`)
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

### Ver candidatos de la GFT publicada sin tocar datos

```bash
python -m scripts.backfill_gft_enrichment --source all --scope gft-publicada --mode dry-run --limit 20
```

### Ver candidatos de todo el Excel/import maestro sin tocar datos

```bash
python -m scripts.backfill_gft_enrichment --source cima --scope all-imported --mode dry-run --limit 20
python -m scripts.backfill_gft_enrichment --source bifimed --scope all-imported --mode dry-run --limit 20
```

### Piloto CIMA/BIFIMED sobre GFT publicada

```bash
python -m scripts.backfill_gft_enrichment --source cima --scope gft-publicada --mode run --limit 20 --sleep 1 --checkpoint-path data/output/backfill_cima_pilot.json --log-path data/output/backfill_cima_pilot.jsonl --audit-before --audit-after
python -m scripts.backfill_gft_enrichment --source bifimed --scope gft-publicada --mode run --limit 20 --sleep 1 --checkpoint-path data/output/backfill_bifimed_pilot.json --log-path data/output/backfill_bifimed_pilot.jsonl --audit-before --audit-after
```

### Backfill completo por lotes del Excel/import maestro

Por defecto, `--only-missing` selecciona caches realmente ausentes y evita consumir el lote con filas ya cacheadas pero incompletas. En `all-imported`, CIMA no reintenta CN con cache CIMA existente salvo `--include-incomplete`; BIFIMED no reintenta CN con cache BIFIMED existente aunque no tenga indicaciones salvo `--include-incomplete`.

```bash
python -m scripts.backfill_gft_enrichment --source cima --scope all-imported --mode run --limit 100 --sleep 1 --checkpoint-path data/output/backfill_cima_all_imported_100.json --log-path data/output/backfill_cima_all_imported_100.jsonl --audit-before --audit-after
python -m scripts.backfill_gft_enrichment --source bifimed --scope all-imported --mode run --limit 100 --sleep 1 --checkpoint-path data/output/backfill_bifimed_all_imported_100.json --log-path data/output/backfill_bifimed_all_imported_100.jsonl --audit-before --audit-after
```

Repite aumentando `--offset` o usando checkpoints dedicados por lote según la operación. Cachear `all-imported` solo precalienta/enriquece PostgreSQL; las reglas de inclusión/publicación de `v_gft_publicada` no cambian.

### Reintentar incompletos solo para diagnóstico

Usa `--include-incomplete` cuando quieras revisar explícitamente filas ya cacheadas pero incompletas, por ejemplo `sin_indicaciones_cima`, `bifimed_sin_indicaciones` o estados clínicos incompletos. Este modo puede producir muchos resultados `unchanged`, `no_data` o `not_found`; no es el modo recomendado para backfills masivos/nocturnos.

```bash
python -m scripts.backfill_gft_enrichment --source bifimed --scope all-imported --mode run --include-incomplete --limit 100 --sleep 1 --checkpoint-path data/output/backfill_bifimed_incomplete.json --log-path data/output/backfill_bifimed_incomplete.jsonl
```

### Reanudar ejecución

```bash
python -m scripts.backfill_gft_enrichment --source all --scope gft-publicada --mode run --resume --checkpoint-path data/output/backfill_full.json --log-path data/output/backfill_full.jsonl --sleep 1 --audit-after
```

Con `--resume`, el runner lee el checkpoint, conserva los estados previos y salta los items ya marcados como `success` o `skipped_existing`. Los items `pending`, `error`, `rate_limited`, `not_found`, `no_data` y `unchanged` pueden reevaluarse en la reanudación para permitir recuperación operativa tras errores transitorios.

## Salida, logs y checkpoints

Si no se indican rutas, se crean rutas timestamped bajo `data/output/`:

- Checkpoint JSON: `data/output/backfill_<source>_<scope>_<timestamp>.json`
- Log JSONL: `data/output/backfill_<source>_<scope>_<timestamp>.jsonl`
- Auditorías GFT: `data/output/backfill_audit_before_<timestamp>.json` y `data/output/backfill_audit_after_<timestamp>.json`

El JSON resumen incluye `source`, `scope`, `mode`, `only_missing`, `include_incomplete`, `total_candidates`, `total_universe`, contadores de cache CIMA/BIFIMED, indicaciones BIFIMED, CN inválidos omitidos, publicados/no publicados si puede calcularse, y `processed`/`succeeded`/`failed`/`skipped` desde checkpoint.

Cada línea JSONL incluye `timestamp`, `cn`, `nombre`, `source`, `scope`, `action`, `status`, `message`, `duration_ms`, `changed_fields`, `reason` y `error` resumido cuando aplica. Los estados `unchanged`, `no_data` y `not_found` quedan visibles tanto en checkpoint como en log. No se guarda HTML masivo ni datos sensibles.

## Garantías anti-sobrescritura

- `dry-run` no llama a servicios de escritura.
- `--only-missing` está activo por defecto.
- Las filas ya cacheadas pero incompletas no se reintentan salvo con `--include-incomplete`.
- `--force` solo se usa si se indica explícitamente.
- Si ya existe un dato útil, el backfill no lo reemplaza por vacío.
- Incluso con `--force`, si una respuesta nueva queda vacía para campos donde había contenido útil, el runner restaura esos campos y marca el item como `unchanged`/`no_data` según corresponda.
- Los CN que fallen registran error y la ejecución continúa salvo con `--stop-on-error`.
- Los medicamentos no incluidos o no publicados pueden cachearse en `all-imported`, pero no aparecen publicados en la web por este backfill.

## Fuera de alcance

- No cambia PDF.
- No cambia diseño web.
- No usa como base PR 129 ni PR 130.
- No inventa datos ni hardcodea medicamentos/CN.
- No cambia reglas de inclusión GFT.
- No hace scraping real en tests.
- No introduce normalización avanzada CIMA ni convierte el PDF en fuente de lógica.
