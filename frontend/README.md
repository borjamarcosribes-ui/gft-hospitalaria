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

El servidor de desarrollo de Vite incluye un proxy para `/gft` hacia `http://localhost:8000`.

## Configuración de API

Puedes configurar la URL base de la API con la variable de entorno:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Si `VITE_API_BASE_URL` no está definida, el frontend usa una cadena vacía (`""`) para permitir proxy de desarrollo o despliegue en el mismo origen.

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
