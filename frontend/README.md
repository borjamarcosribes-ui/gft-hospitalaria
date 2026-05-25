# Frontend GFT Hospitalaria

Frontend mínimo para consultar la Guía Farmacoterapéutica Hospitalaria publicada.

## Requisitos

- Node.js
- npm
- Backend FastAPI disponible para responder a `GET /gft/medicamentos`

## Instalación

```bash
npm install
```

## Desarrollo

```bash
npm run dev
```

El servidor de desarrollo de Vite incluye un proxy hacia `http://localhost:8000` para `/gft`, `/admin`, `/imports`, `/cima`, `/bifimed` y `/health`, evitando CORS en Codespaces y local.

## Configuración de API

Puedes configurar la URL base de la API con la variable de entorno:

```bash
VITE_API_BASE_URL=
```

En desarrollo se recomienda dejar `VITE_API_BASE_URL` vacío para que el frontend use rutas relativas y el proxy de Vite. Si defines una URL absoluta, el frontend llamará directamente a ese origen.

## Build

```bash
npm run build
```

## Typecheck

```bash
npm run typecheck
```

## Preview del build

```bash
npm run preview
```
