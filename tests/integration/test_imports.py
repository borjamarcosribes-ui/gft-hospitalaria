from io import BytesIO
import uuid

import pandas as pd

from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.import_row_staging import ImportRowStaging
from app.services.excel_import_service import process_excel_upload
from app.services.import_apply_service import apply_import_batch


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


def test_import_minimal_ok_stages_without_applying(db_session):
    df = pd.DataFrame([
        {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "publicado"}
    ])
    batch = process_excel_upload(db_session, make_excel(df), "ok.xlsx")
    assert batch.status == "validated"
    assert batch.total_rows == 1
    assert batch.processed_rows == 1
    assert batch.ok_rows == 1
    assert db_session.query(ImportRowStaging).filter(ImportRowStaging.batch_id == batch.id).count() == 1
    assert db_session.get(GFTEstadoPresentacion, "123456") is None


def test_import_missing_columns(db_session):
    df = pd.DataFrame([{"CN": "123456"}])
    batch = process_excel_upload(db_session, make_excel(df), "bad.xlsx")
    assert batch.status == "failed"


def test_import_unknown_estado_editorial(db_session):
    df = pd.DataFrame([
        {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "raro"}
    ])
    batch = process_excel_upload(db_session, make_excel(df), "warn.xlsx")
    assert batch.status == "with_errors"
    assert batch.error_rows == 1


def test_import_nan_editorial_defaults_borrador(db_session):
    df = pd.DataFrame([
        {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": pd.NA}
    ])
    batch = process_excel_upload(db_session, make_excel(df), "nan.xlsx")
    assert batch.status == "validated"
    row = (
        db_session.query(ImportRowStaging)
        .filter(ImportRowStaging.batch_id == batch.id, ImportRowStaging.cn_normalized == "123456")
        .one()
    )
    assert row.estado_editorial == "borrador"
    assert db_session.get(GFTEstadoPresentacion, "123456") is None


def test_apply_import_batch_applies_valid_rows_and_skips_pending(db_session):
    df = pd.DataFrame([
        {"CN": "111111", "Observaciones revisión": "SI", "Estado editorial": "publicado"},
        {"CN": "222222", "Observaciones revisión": "NO", "Estado editorial": "publicado"},
        {"CN": "333333", "Observaciones revisión": "guía", "Estado editorial": "publicado"},
    ])
    batch = process_excel_upload(db_session, make_excel(df), "apply.xlsx")

    summary = apply_import_batch(db_session, batch.id)

    assert summary == {
        "batch_id": str(batch.id),
        "total_rows": 3,
        "applied_rows": 2,
        "skipped_errors": 0,
        "skipped_missing_cn": 0,
        "skipped_pending": 1,
        "skipped_missing_estado_editorial": 0,
    }
    row_111111 = db_session.get(GFTEstadoPresentacion, "111111")
    assert row_111111 is not None
    assert row_111111.estado_gft == "incluido"
    assert row_111111.estado_editorial == "publicado"
    row_222222 = db_session.get(GFTEstadoPresentacion, "222222")
    assert row_222222 is not None
    assert row_222222.estado_gft == "excluido"
    assert row_222222.estado_editorial == "publicado"
    assert db_session.get(GFTEstadoPresentacion, "333333") is None

    second_summary = apply_import_batch(db_session, batch.id)
    assert second_summary["applied_rows"] == 2
    assert db_session.query(GFTEstadoPresentacion).count() == 2


def test_apply_import_batch_missing_batch_returns_none(db_session):
    assert apply_import_batch(db_session, uuid.uuid4()) is None


def test_imports_excel_route_does_not_apply_to_gft_estado_presentacion(client, db_session, admin_headers):
    response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "publicado"}
            ])
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["total_rows"] == 1
    assert db_session.query(ImportRowStaging).count() == 1
    assert db_session.query(GFTEstadoPresentacion).count() == 0


def test_imports_apply_route_applies_valid_rows_and_skips_pending(client, db_session, admin_headers):
    upload_response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "111111", "Observaciones revisión": "SI", "Estado editorial": "publicado"},
                {"CN": "222222", "Observaciones revisión": "NO", "Estado editorial": "publicado"},
                {"CN": "333333", "Observaciones revisión": "guía", "Estado editorial": "publicado"},
            ])
        },
        headers=admin_headers,
    )
    assert upload_response.status_code == 200
    batch_id = upload_response.json()["batch_id"]

    apply_response = client.post(f"/imports/{batch_id}/apply", headers=admin_headers)

    assert apply_response.status_code == 200
    payload = apply_response.json()
    assert payload["applied_rows"] == 2
    assert payload["skipped_pending"] == 1
    row_111111 = db_session.get(GFTEstadoPresentacion, "111111")
    assert row_111111 is not None
    assert row_111111.estado_gft == "incluido"
    assert row_111111.estado_editorial == "publicado"
    row_222222 = db_session.get(GFTEstadoPresentacion, "222222")
    assert row_222222 is not None
    assert row_222222.estado_gft == "excluido"
    assert row_222222.estado_editorial == "publicado"
    assert db_session.get(GFTEstadoPresentacion, "333333") is None


def test_imports_apply_route_missing_batch_returns_404(client, admin_headers):
    response = client.post(f"/imports/{uuid.uuid4()}/apply", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Batch no encontrado"
