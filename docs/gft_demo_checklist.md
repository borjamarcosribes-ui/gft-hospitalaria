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
