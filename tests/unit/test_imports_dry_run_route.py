from io import BytesIO

import pandas as pd

from app.models.import_batch import ImportBatch


EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_excel(rows: list[dict]) -> bytes:
    bio = BytesIO()
    pd.DataFrame(rows).to_excel(bio, index=False)
    return bio.getvalue()


def post_dry_run(client, content: bytes, admin_headers):
    return client.post(
        "/imports/excel/dry-run",
        files={"file": ("gft.xlsx", content, EXCEL_MEDIA_TYPE)},
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
    assert payload["original_columns"] == ["Codigo Nacional medicamento", "Notas revision"]
    assert payload["missing_required_columns"] == ["CN", "Observaciones revisión"]
    assert payload["column_suggestions"]["CN"] == ["Codigo Nacional medicamento"]
    assert db_session.query(ImportBatch).count() == 0
