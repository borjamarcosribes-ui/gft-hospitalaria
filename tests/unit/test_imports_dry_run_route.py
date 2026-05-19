from io import BytesIO

import pandas as pd

from app.models.import_batch import ImportBatch


EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_excel(rows: list[dict], add_estado_editorial: bool = True) -> bytes:
    df = pd.DataFrame(rows)
    safe_estado_aliases = {"Estado editorial", "Estado Editorial", "Estado", "Estado publicación", "Estado publicacion"}
    if add_estado_editorial and safe_estado_aliases.isdisjoint(set(df.columns)):
        df["Estado editorial"] = "publicado"

    bio = BytesIO()
    df.to_excel(bio, index=False)
    return bio.getvalue()


def post_dry_run(client, content: bytes, admin_headers, data: dict | None = None):
    return client.post(
        "/imports/excel/dry-run",
        files={"file": ("gft.xlsx", content, EXCEL_MEDIA_TYPE)},
        data=data or {},
        headers=admin_headers,
    )


def test_imports_excel_dry_run_returns_structured_result(client, admin_headers):
    response = post_dry_run(
        client,
        make_excel(
            [
                {"CN": "111111", "Observaciones revisión": "SI"},
                {"CN": "222222", "Observaciones revisión": "NO"},
                {"CN": "333333", "Observaciones revisión": "guía"},
            ]
        ),
        admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["total_rows"] == 3
    assert payload["included_count"] == 1
    assert payload["excluded_count"] == 1
    assert payload["pending_count"] == 1


def test_imports_excel_dry_run_keeps_guia_as_pending(client, admin_headers):
    response = post_dry_run(
        client,
        make_excel([{"CN": "333333", "Observaciones revisión": "guía"}]),
        admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["included_count"] == 0
    assert payload["excluded_count"] == 0
    assert payload["pending_count"] == 1
    assert payload["pending_items"][0]["observaciones_revision_raw"] == "guía"
    assert payload["rows"][0]["estado_gft"] == "pendiente_revision"


def test_imports_excel_dry_run_route_is_not_captured_by_batch_id(client, admin_headers):
    response = post_dry_run(
        client,
        make_excel([{"CN": "111111", "Observaciones revisión": "SI"}]),
        admin_headers,
    )

    assert response.status_code == 200
    assert "value is not a valid uuid" not in response.text.lower()
    assert "uuid" not in response.text.lower()


def test_imports_excel_dry_run_returns_column_diagnostics_and_does_not_create_batch(client, db_session, admin_headers):
    response = post_dry_run(
        client,
        make_excel([{"Codigo Nacional medicamento": "111111", "Notas revision": "SI"}]),
        admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["total_rows"] == 0
    assert payload["sheet_name"] == "Sheet1"
    assert payload["sheet_names"] == ["Sheet1"]
    assert payload["header_row"] == 1
    assert payload["original_columns"] == ["Codigo Nacional medicamento", "Notas revision", "Estado editorial"]
    assert payload["missing_required_columns"] == ["CN", "Observaciones revisión"]
    assert payload["column_suggestions"]["CN"] == ["Codigo Nacional medicamento"]
    assert db_session.query(ImportBatch).count() == 0


def make_multisheet_excel() -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"Título": "Resumen"}]).to_excel(writer, index=False, sheet_name="Resumen")
        pd.DataFrame([{"CN": "222222", "Observaciones revisión": "SI", "Estado editorial": "publicado"}]).to_excel(
            writer, index=False, sheet_name="Revision_GFT_ATC"
        )
    return bio.getvalue()


def test_imports_excel_dry_run_uses_form_sheet_name(client, admin_headers):
    response = client.post(
        "/imports/excel/dry-run",
        files={"file": ("gft.xlsx", make_multisheet_excel(), EXCEL_MEDIA_TYPE)},
        data={"sheet_name": "Revision_GFT_ATC"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sheet_name"] == "Revision_GFT_ATC"
    assert payload["included_count"] == 1
    assert payload["rows"][0]["cn"] == "222222"


def test_imports_excel_dry_run_returns_clear_error_for_missing_sheet(client, admin_headers):
    response = client.post(
        "/imports/excel/dry-run",
        files={"file": ("gft.xlsx", make_multisheet_excel(), EXCEL_MEDIA_TYPE)},
        data={"sheet_name": "NoExiste"},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "La hoja 'NoExiste' no existe" in response.json()["detail"]
    assert "Resumen" in response.json()["detail"]
    assert "Revision_GFT_ATC" in response.json()["detail"]


def test_imports_excel_dry_run_uses_form_header_row(client, admin_headers):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([
            ["Título", "no es encabezado", "no es encabezado"],
            ["CN", "Observaciones revisión", "Estado editorial"],
            ["555555", "SI", "publicado"],
        ]).to_excel(writer, index=False, header=False)

    response = client.post(
        "/imports/excel/dry-run",
        files={"file": ("gft.xlsx", bio.getvalue(), EXCEL_MEDIA_TYPE)},
        data={"header_row": "2"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["header_row"] == 2
    assert payload["rows"][0]["row_number"] == 3
    assert payload["rows"][0]["cn"] == "555555"


def test_imports_excel_dry_run_fails_when_estado_editorial_is_missing_and_no_default(client, admin_headers):
    response = post_dry_run(
        client,
        make_excel(
            [{"CN": "111111", "Observaciones revisión": "SI"}],
            add_estado_editorial=False,
        ),
        admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_rows"] == 0
    assert payload["missing_required_columns"] == ["Estado editorial"]
    assert payload["errors"][0]["message"] == "Columna obligatoria ausente: Estado editorial"


def test_imports_excel_dry_run_without_estado_editorial_uses_default(client, admin_headers):
    response = post_dry_run(
        client,
        make_excel([{"CN": "111111", "Observaciones revisión": "SI"}], add_estado_editorial=False),
        admin_headers,
        data={"default_estado_editorial": "borrador"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["error_count"] == 0
    assert payload["default_estado_editorial_used"] == "borrador"


def test_imports_excel_dry_run_invalid_default_estado_editorial_returns_clear_error(client, admin_headers):
    response = post_dry_run(
        client,
        make_excel([{"CN": "111111", "Observaciones revisión": "SI"}], add_estado_editorial=False),
        admin_headers,
        data={"default_estado_editorial": "raro"},
    )
    assert response.status_code == 400
    assert "default_estado_editorial inválido" in response.json()["detail"]
