# GFT demo: smoke check y checklist operativa

## 1) Arrancar backend

```bash
cd /workspaces/gft-hospitalaria
source .venv/bin/activate
export DATABASE_URL="postgresql+psycopg://gft:gft@localhost:5432/gft"
export ADMIN_API_KEY="demo-local-admin-key"
docker compose up -d db
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2) Arrancar frontend

```bash
cd /workspaces/gft-hospitalaria
npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173
```

## 3) Nota sobre `frontend/.env.local`

Puedes usar `frontend/.env.local` en Codespaces con este valor:

```bash
VITE_API_BASE_URL=https://<codespace>-8000.app.github.dev
```

Este archivo **no debe commitearse**.

## 4) Comando de smoke test (local)

```bash
PYTHONPATH=. python scripts/gft_demo_smoke_check.py
```

## 5) Comando de smoke test (Codespaces)

```bash
PYTHONPATH=. python scripts/gft_demo_smoke_check.py \
  --backend-url https://verbose-space-cod-r4vx56r7wqx72x5jv-8000.app.github.dev \
  --frontend-url https://verbose-space-cod-r4vx56r7wqx72x5jv-5173.app.github.dev \
  --admin-api-key demo-local-admin-key
```

## 6) Checklist antes de subir Excel

- Backend health OK.
- Frontend OK.
- Admin summary OK.
- Medicamentos administrativos OK.
- No hay “Failed to fetch”.
- La pública carga.
- `git status` no incluye `frontend/.env.local` para commit.

## 7) Checklist de subida Excel

- Seleccionar Excel maestro.
- Hoja correcta.
- Fila encabezado correcta.
- Estado editorial por defecto: borrador.
- Validar Excel.
- Revisar total, errores, pendientes, se aplicarán.
- Crear staging.
- Aplicar lote solo si errores = 0.
- Comprobar summary.
- No publicar automáticamente.

## 8) Checklist post-carga

- Comprobar incluidos/excluidos/pendientes.
- Comprobar calidad sin CIMA/BIFIMED/FT 4.1.
- Sincronizar enriquecimientos si procede.
- Publicar solo medicamentos seleccionados.

## 9) Auditoría de calidad pública visible

Ejecutar este script después de publicar o actualizar una carga GFT para verificar si la calidad visible de la API pública es enseñable.

Comando local:

```bash
PYTHONPATH=. python scripts/gft_public_quality_audit.py --backend-url http://localhost:8000
```

Comando con salidas a fichero:

```bash
PYTHONPATH=. python scripts/gft_public_quality_audit.py \
  --backend-url http://localhost:8000 \
  --output-json reports/gft_public_quality_audit.json \
  --output-csv reports/gft_public_quality_issues.csv
```

Interpretación rápida:

- Si `sin_nombre` es alto, revisar fallback Excel/CIMA.
- Si `sin_atc` es alto, revisar mapeo ATC.
- Si `sin_indicaciones_ficha_tecnica` es alto, revisar sync ficha técnica 4.1.

## 10) Readiness check integral de demo

Usar este check cuando quieras validar en un único paso si la demo GFT está lista para enseñar sin ejecutar acciones destructivas (solo llamadas GET).
Nota: si quieres que cualquier campo de calidad faltante (además de `sin_nombre`) eleve el resultado a `WARNING`, usa `--strict-quality`.

Comando local básico:

```bash
PYTHONPATH=. python scripts/gft_demo_readiness_check.py
```

Comando recomendado para nuestra demo:

```bash
PYTHONPATH=. python scripts/gft_demo_readiness_check.py \
  --backend-url http://localhost:8000 \
  --frontend-url http://localhost:5173 \
  --admin-api-key demo-local-admin-key \
  --expected-public-total 1780 \
  --expected-no-missing-name
```

Comando con PDF cuando esté mergeado:

```bash
PYTHONPATH=. python scripts/gft_demo_readiness_check.py \
  --backend-url http://localhost:8000 \
  --frontend-url http://localhost:5173 \
  --admin-api-key demo-local-admin-key \
  --expected-public-total 1780 \
  --expected-no-missing-name \
  --check-pdf
```
