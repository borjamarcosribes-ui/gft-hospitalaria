# Verificación manual de exportación HTML/PDF de la GFT pública

## 1. Objetivo de la comprobación

Comprobar de forma manual que la exportación imprimible de la Guía Farmacoterapéutica (GFT) pública en HTML y PDF muestra exclusivamente el universo publicado, con el mismo origen funcional que la API pública, sin exponer campos internos ni estados intermedios.

Esta guía está orientada a desarrolladores y validadores funcionales que necesiten revisar visualmente la salida de `GET /gft/export/html` y `GET /gft/export/pdf` después de cargar o actualizar datos.

## 2. Precondiciones

Antes de iniciar la verificación, asegúrate de que:

- El entorno backend está arrancado.
- La base de datos está migrada a la última versión disponible.
- Los datos necesarios están importados y aplicados a la GFT.
- Existe al menos un medicamento con `estado_gft = incluido` y `estado_editorial = publicado`.

## 3. Comandos o URLs de comprobación

Sustituye `http://localhost:8000` por la URL real del backend si el entorno usa otro host o puerto.

```bash
curl -i http://localhost:8000/gft/medicamentos
curl -i http://localhost:8000/gft/export/html
curl -OJ http://localhost:8000/gft/export/pdf
```

También pueden abrirse directamente en navegador:

- `GET /gft/medicamentos`
- `GET /gft/export/html`
- `GET /gft/export/pdf`

## 4. Qué debe comprobarse visualmente

En la API pública, el HTML imprimible y el PDF descargado debe verificarse que:

- Solo aparecen medicamentos publicados.
- No aparecen medicamentos excluidos ni pendientes.
- El HTML muestra portada, índice ATC y bloques de medicamentos.
- El PDF se descarga como `gft-hospitalaria.pdf`.
- Los campos vacíos, nulos o no disponibles se muestran como **“No informado”**.
- No aparecen campos internos o de operación, especialmente:
  - `estado_gft`
  - `estado_editorial`
  - `comentario_revision`
  - `revisado_por`
  - `raw_data`
  - `sync_status`

## 5. Nota de dependencias

La generación PDF requiere WeasyPrint como motor HTML→PDF.

El fichero `requirements.txt` ya fija las versiones compatibles:

- `weasyprint==62.3`
- `pydyf==0.10.0`

No debe añadirse ninguna dependencia nueva para esta comprobación manual.

## 6. Nota funcional

- `GET /gft/export/html` es una previsualización imprimible y una herramienta de debug visual de la plantilla que alimenta el PDF.
- `GET /gft/export/pdf` es la descarga final pública de la GFT publicada.
- Ambos endpoints deben salir de la misma fuente publicada que `/gft`, sin fuentes paralelas ni consultas alternativas a datos de staging, importación o revisión interna.
