# CIMA fixtures offline

Estas fixtures se usan para validar el parser de `app/services/cima_client.py` en modo **offline**.

- No deben realizar llamadas reales a CIMA durante los tests.
- Deben representar estructuras compatibles con payloads de CIMA.
- En el futuro pueden sustituirse o ampliarse con payloads reales capturados manualmente.

## Fixtures incluidas

- `medicamento_simple.json`
  - **Fecha de creación:** 2026-05-05
  - **Propósito:** validar mapeo base (identidad, forma farmacéutica, ATC, principios y documentos).
- `medicamento_combinacion_principios.json`
  - **Fecha de creación:** 2026-05-05
  - **Propósito:** validar medicamentos con combinación de varios principios activos.
- `medicamento_docs_tipo_1_2.json`
  - **Fecha de creación:** 2026-05-05
  - **Propósito:** validar selección de documentos tipo 1 (ficha técnica) y tipo 2 (prospecto), URLs y fechas ISO.
