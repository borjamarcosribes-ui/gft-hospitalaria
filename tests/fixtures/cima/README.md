# Fixtures CIMA offline

Estas fixtures son **offline** y se usan para pruebas unitarias del parser de CIMA sin depender de red.

## Reglas de uso

- No deben provocar llamadas reales al API de CIMA durante los tests.
- Representan estructuras compatibles con payloads de CIMA consumidos por `CimaClient()._map_medicamento(...)`.
- En el futuro pueden sustituirse o ampliarse con payloads reales capturados manualmente.

## Fecha de creación

- Creado el **2026-05-05**.

## Propósito por fixture

- `medicamento_simple.json`: caso básico con un solo principio activo y documento tipo 1.
- `medicamento_combinacion_principios.json`: caso de combinación con múltiples principios activos y documentos tipo 1 y 2.
- `medicamento_docs_tipo_1_2.json`: caso centrado en mapeo de documentos (ficha técnica/prospecto), URLs y fechas ISO.
