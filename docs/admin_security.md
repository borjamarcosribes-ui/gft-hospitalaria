# Protección mínima de endpoints admin

La protección admin actual es mínima y está basada en el header HTTP `X-Admin-API-Key`.

## Configuración

Los endpoints admin requieren definir la variable de entorno `ADMIN_API_KEY`.

No existe un valor por defecto para esta clave. Si `ADMIN_API_KEY` no está configurada, los endpoints admin responden siempre con HTTP 503 y el detalle `Admin API key is not configured`.

## Comportamiento

Para acceder a un endpoint admin protegido, la petición debe enviar:

```http
X-Admin-API-Key: <valor de ADMIN_API_KEY>
```

Si el header no se envía, la API responde HTTP 401. Si el valor no coincide con `ADMIN_API_KEY`, la API responde HTTP 403.

Actualmente usan este guard los endpoints:

- `GET /admin/health`
- `GET /admin/gft/medicamentos/editorial`
- `GET /admin/gft/medicamentos/editorial/summary`
- `GET /admin/gft/medicamentos/{cn}/editorial`
- `PATCH /admin/gft/medicamentos/{cn}/editorial`

## Alcance y limitaciones

Esta protección sirve como guard temporal para endpoints internos/admin antes de exponer rutas de escritura. No debe usarse como seguridad definitiva en producción pública.

Queda pendiente para una fase futura incorporar un modelo de seguridad más completo, por ejemplo roles, usuarios, integración institucional o autenticación corporativa mediante reverse proxy.
