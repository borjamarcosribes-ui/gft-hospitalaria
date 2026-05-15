# Demo local visual de la GFT hospitalaria

## Objetivo

Preparar una demo local controlada para enseñar la GFT pública, el panel admin y las exportaciones HTML/PDF sin depender de llamadas reales a CIMA ni BIFIMED.

El seed demo se ejecuta manualmente con `scripts/seed_demo_gft.py`, usa las tablas/modelos existentes y respeta la frontera de publicación actual: solo aparece públicamente lo que esté en `v_gft_publicada` (`estado_gft = incluido` y `estado_editorial = publicado`). No crea endpoints nuevos.

> **Importante:** esta guía está pensada para entornos locales o bases demo desechables. No ejecutes el seed sobre datos reales salvo que quieras sobrescribir los CN demo `900001`, `900002`, `900003` y `900004`.

## Precondiciones

- Python 3.12 o superior.
- Node.js y npm para el frontend.
- Docker si quieres levantar PostgreSQL con `docker compose`.
- Repositorio con dependencias instalables desde `requirements.txt` y `frontend/package-lock.json`.
- Base de datos migrada hasta `head`, incluyendo la vista `v_gft_publicada`.

## Variables de entorno necesarias

```bash
# Si usas PostgreSQL del docker-compose local:
export DATABASE_URL="postgresql+psycopg://gft:gft@localhost:5432/gft"

# Clave que usarás para entrar al panel admin y llamar rutas protegidas:
export ADMIN_API_KEY="demo-local-admin-key"
```

Si no defines `DATABASE_URL`, el backend usa por defecto `sqlite:///./gft.db`. En ese caso aplica igualmente las migraciones antes de ejecutar el seed.

## Comandos de preparación

### 1. Levantar base de datos local (PostgreSQL opcional)

```bash
docker compose up -d db
```

### 2. Instalar dependencias backend

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. Aplicar migraciones

```bash
PYTHONPATH=. alembic upgrade head
```

### 4. Ejecutar seed demo

```bash
PYTHONPATH=. python scripts/seed_demo_gft.py
```

El script es idempotente: puedes ejecutarlo varias veces y actualizará las mismas filas demo sin duplicarlas. Si falta alguna tabla o la vista `v_gft_publicada`, falla con un mensaje explícito pidiendo ejecutar migraciones.

### 5. Arrancar backend

```bash
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Instalar y arrancar frontend

En otra terminal:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Normalmente Vite mostrará la URL local del frontend, por ejemplo `http://localhost:5173`.

## URLs a abrir

Con backend en `http://localhost:8000` y frontend en `http://localhost:5173`:

- GFT pública visual: `http://localhost:5173/`
- Panel admin: `http://localhost:5173/admin/gft`
- Exportación HTML pública: `http://localhost:8000/gft/export/html`
- Exportación PDF pública: `http://localhost:8000/gft/export/pdf`
- Healthcheck público: `http://localhost:8000/health`

## Cómo entrar al panel admin

El panel admin está protegido por `X-Admin-API-Key`. Define la misma clave en `ADMIN_API_KEY` antes de arrancar el backend.

En la pantalla `/admin/gft`, introduce el valor de `ADMIN_API_KEY` cuando el frontend solicite la clave admin. El frontend enviará esa clave en la cabecera `X-Admin-API-Key` para las rutas `/admin`.

## Qué se debe ver

El seed crea cuatro medicamentos demo:

| CN | Estado GFT | Estado editorial | Visibilidad esperada |
| --- | --- | --- | --- |
| `900001` | `incluido` | `publicado` | Visible en `/`, `/gft/medicamentos`, `/gft/export/html` y `/gft/export/pdf` |
| `900002` | `incluido` | `borrador` | Visible en admin, no visible públicamente |
| `900003` | `excluido` | `publicado` | Visible en admin, no visible públicamente |
| `900004` | `pendiente_revision` | `borrador` | Visible en admin, no visible públicamente |

Para el CN público `900001` deberías poder validar visualmente:

- CN, nombre comercial, presentación y forma farmacéutica.
- Principio activo `Ceftriaxona`.
- Vía de administración.
- Código ATC `J01DD04` y descripción ATC.
- Número de registro demo `DEMO900001` en caché CIMA/admin.
- Enlaces demo de ficha técnica y prospecto.
- Indicaciones de ficha técnica desde la sección `4.1`.
- Situación de financiación desde caché BIFIMED demo.
- Campos clínicos/editoriales: restricciones hospitalarias, ajuste renal, ajuste hepático, embarazo y lactancia.
- PDF descargable desde `/gft/export/pdf`.

## Checklist rápido de demo

1. Abrir `/health` y confirmar respuesta correcta.
2. Abrir `/` y buscar `Democef` o `900001`.
3. Confirmar que `Demoferol`, `Demoalgin` y `Demogluc` no aparecen en la GFT pública.
4. Abrir el detalle público de `900001` y revisar indicaciones 4.1, financiación y campos clínicos.
5. Abrir `/admin/gft`, introducir `ADMIN_API_KEY` y comprobar que aparecen los cuatro CN demo.
6. En admin, confirmar los estados: publicado, borrador, excluido y pendiente de revisión.
7. Abrir `/gft/export/html` y comprobar que solo aparece el medicamento publicado.
8. Descargar `/gft/export/pdf` y comprobar que el PDF contiene el medicamento publicado.

## Limpieza de datos demo

El script actual **no implementa limpieza automática**. Si necesitas limpiar la demo, elimina manualmente los CN `900001`, `900002`, `900003` y `900004` de las tablas afectadas en una base local/desechable:

- `gft_estado_presentacion`
- `cima_medicamento_cache`
- `cima_ficha_tecnica_cache`
- `bifimed_cache`
- `medicamento_principio_activo`

No borres datos manualmente en entornos con datos reales sin una copia de seguridad y una revisión previa.

## Seguridad mantenida

Esta preparación no cambia rutas ni dependencias de seguridad:

- `/gft` continúa siendo público.
- `/gft/export/html` continúa siendo público.
- `/gft/export/pdf` continúa siendo público.
- `/health` continúa siendo público.
- `/admin` continúa protegido por `X-Admin-API-Key`.
- `/imports` continúa protegido por `X-Admin-API-Key`.
- `/cima` continúa protegido por `X-Admin-API-Key`.
- `/bifimed` continúa protegido por `X-Admin-API-Key`.

No existe endpoint público ni endpoint admin para ejecutar el seed. El seed solo se ejecuta por consola en entorno local/demo.
