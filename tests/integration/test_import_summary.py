from io import BytesIO
import uuid

import pandas as pd

from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.excel_import_service import process_excel_upload


def make_excel(df):
    bio = BytesIO()
    df.to_excel(bio, index=False)
    return bio.getvalue()


def excel_file(rows):
    return (
        "test.xlsx",
        make_excel(pd.DataFrame(rows)),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def test_imports_summary_route_missing_batch_returns_404(client, admin_headers):
    response = client.get(f"/imports/{uuid.uuid4()}/summary", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch no encontrado"


def test_imports_summary_after_excel_upload_classifies_rows(client, admin_headers):
    upload_response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "111111", "Observaciones revisión": "SI", "Estado editorial": "publicado"},
                {"CN": "222222", "Observaciones revisión": "NO", "Estado editorial": "publicado"},
                {"CN": "333333", "Observaciones revisión": "guía", "Estado editorial": "publicado"},
                {"CN": "", "Observaciones revisión": "SI", "Estado editorial": "publicado"},
                {"CN": "444444", "Observaciones revisión": "SI", "Estado editorial": "valor_invalido"},
            ])
        },
        headers=admin_headers,
    )
    assert upload_response.status_code == 200
    batch_id = upload_response.json()["batch_id"]

    response = client.get(f"/imports/{batch_id}/summary", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch_id"] == batch_id
    assert payload["staging_total_rows"] == 5
    assert payload["included_rows"] == 3
    assert payload["excluded_rows"] == 1
    assert payload["pending_rows"] == 1
    assert payload["applicable_rows"] == 2
    assert payload["skipped_pending"] == 1
    assert payload["skipped_missing_cn"] == 0
    assert payload["skipped_errors"] == 2
    assert payload["not_applicable_rows"] == payload["staging_total_rows"] - payload["applicable_rows"]

    assert any(item["cn"] == "333333" for item in payload["pending_items"])
    assert any(item["cn"] is None and "CN vacío" in item["validation_errors"] for item in payload["error_items"])
    assert any(item["cn"] == "444444" for item in payload["error_items"])


def test_imports_summary_detects_duplicate_cn(client, admin_headers):
    upload_response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "publicado"},
                {"CN": "123456.0", "Observaciones revisión": "NO", "Estado editorial": "publicado"},
            ])
        },
        headers=admin_headers,
    )
    assert upload_response.status_code == 200
    batch_id = upload_response.json()["batch_id"]

    response = client.get(f"/imports/{batch_id}/summary", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["duplicate_cn_count"] == 1
    assert payload["duplicate_cn"] == [{"cn": "123456", "rows": [2, 3]}]


def test_imports_summary_does_not_apply_changes(client, db_session, admin_headers):
    upload_response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "publicado"},
            ])
        },
        headers=admin_headers,
    )
    assert upload_response.status_code == 200
    batch_id = upload_response.json()["batch_id"]

    response = client.get(f"/imports/{batch_id}/summary", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["applicable_rows"] == 1
    assert db_session.query(GFTEstadoPresentacion).count() == 0
