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


def test_process_excel_upload_uses_requested_sheet_and_header_row(db_session):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"CN": "111111", "Observaciones revisión": "NO", "Estado editorial": "publicado"}]).to_excel(
            writer, index=False, sheet_name="Resumen"
        )
        pd.DataFrame(
            [
                ["Título", "no es encabezado", "no es encabezado"],
                ["CN", "Observaciones revisión", "Estado editorial"],
                ["222222", "SI", "publicado"],
            ]
        ).to_excel(writer, index=False, header=False, sheet_name="Revision_GFT_ATC")

    batch = process_excel_upload(
        db_session,
        bio.getvalue(),
        "multisheet.xlsx",
        sheet_name="Revision_GFT_ATC",
        header_row=2,
    )

    assert batch.status == "validated"
    assert batch.total_rows == 1
    row = db_session.query(ImportRowStaging).filter(ImportRowStaging.batch_id == batch.id).one()
    assert row.row_number == 3
    assert row.cn_normalized == "222222"
    assert row.estado_gft == "incluido"


def test_imports_excel_route_uses_form_sheet_and_header_row(client, db_session, admin_headers):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"CN": "111111", "Observaciones revisión": "NO", "Estado editorial": "publicado"}]).to_excel(
            writer, index=False, sheet_name="Resumen"
        )
        pd.DataFrame(
            [
                ["Título", "no es encabezado", "no es encabezado"],
                ["CN", "Observaciones revisión", "Estado editorial"],
                ["222222", "SI", "publicado"],
            ]
        ).to_excel(writer, index=False, header=False, sheet_name="Revision_GFT_ATC")

    response = client.post(
        "/imports/excel",
        files={"file": ("gft.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"sheet_name": "Revision_GFT_ATC", "header_row": "2"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "validated"
    row = db_session.query(ImportRowStaging).one()
    assert row.row_number == 3
    assert row.cn_normalized == "222222"


def test_dry_run_and_import_accept_same_aliases_with_same_sheet_and_header(db_session):
    from app.services.gft_excel_dry_run_service import dry_run_gft_excel

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"Título": "Resumen"}]).to_excel(writer, index=False, sheet_name="Resumen")
        pd.DataFrame(
            [
                ["Título", "no es encabezado", "no es encabezado"],
                ["Código Nacional", "Observaciones revision", "Estado publicación"],
                ["222222", "SI", "publicado"],
            ]
        ).to_excel(writer, index=False, header=False, sheet_name="Revision_GFT_ATC")
    content = bio.getvalue()

    dry_run = dry_run_gft_excel(content, sheet_name="Revision_GFT_ATC", header_row=2)

    assert dry_run.error_count == 0
    assert dry_run.sheet_name == "Revision_GFT_ATC"
    assert dry_run.header_row == 2
    assert dry_run.column_mapping == {
        "cn": "Código Nacional",
        "observaciones_revision": "Observaciones revision",
        "estado_editorial": "Estado publicación",
    }

    batch = process_excel_upload(
        db_session,
        content,
        "aliases.xlsx",
        sheet_name="Revision_GFT_ATC",
        header_row=2,
    )

    assert batch.status == "validated"
    assert batch.total_rows == 1
    row = db_session.query(ImportRowStaging).filter(ImportRowStaging.batch_id == batch.id).one()
    assert row.row_number == 3
    assert row.cn_normalized == "222222"
    assert row.observaciones_revision_raw == "SI"
    assert row.estado_editorial_raw == "publicado"
    assert row.estado_gft == "incluido"
    assert row.estado_editorial == "publicado"


def test_excel_validated_by_dry_run_imports_to_staging_with_alias_columns(client, db_session, admin_headers):
    bio = BytesIO()
    pd.DataFrame(
        [{"Código Nacional": "333333", "Observaciones GFT": "NO", "Estado": "validado"}]
    ).to_excel(bio, index=False)
    content = bio.getvalue()

    dry_run_response = client.post(
        "/imports/excel/dry-run",
        files={"file": ("aliases.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )

    assert dry_run_response.status_code == 200
    dry_run_payload = dry_run_response.json()
    assert dry_run_payload["error_count"] == 0
    assert dry_run_payload["column_mapping"] == {
        "cn": "Código Nacional",
        "observaciones_revision": "Observaciones GFT",
        "estado_editorial": "Estado",
    }

    import_response = client.post(
        "/imports/excel",
        files={"file": ("aliases.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )

    assert import_response.status_code == 200
    assert import_response.json()["status"] == "validated"
    row = db_session.query(ImportRowStaging).one()
    assert row.cn_normalized == "333333"
    assert row.estado_gft == "excluido"
    assert row.estado_editorial == "validado"


def test_import_excel_without_estado_editorial_uses_default_borrador(client, db_session, admin_headers):
    response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "777777", "Observaciones revisión": "SI"}
            ])
        },
        data={"default_estado_editorial": "borrador"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validated"
    row = db_session.query(ImportRowStaging).filter(ImportRowStaging.cn_normalized == "777777").one()
    assert row.estado_editorial == "borrador"


def test_import_excel_estado_editorial_column_prevails_over_default(client, db_session, admin_headers):
    response = client.post(
        "/imports/excel",
        files={
            "file": excel_file([
                {"CN": "888888", "Observaciones revisión": "SI", "Estado editorial": "validado"}
            ])
        },
        data={"default_estado_editorial": "borrador"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    row = db_session.query(ImportRowStaging).filter(ImportRowStaging.cn_normalized == "888888").one()
    assert row.estado_editorial == "validado"


def test_import_excel_invalid_default_estado_editorial_fails_cleanly(client, admin_headers):
    response = client.post(
        "/imports/excel",
        files={"file": excel_file([{"CN": "999999", "Observaciones revisión": "SI"}])},
        data={"default_estado_editorial": "raro"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "Estado editorial inválido" in response.json()["error_summary"]["error"]
