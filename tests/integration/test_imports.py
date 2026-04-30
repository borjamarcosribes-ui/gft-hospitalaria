from io import BytesIO
import pandas as pd
from app.services.excel_import_service import process_excel_upload
from app.models.gft_estado_presentacion import GFTEstadoPresentacion


def make_excel(df):
    bio = BytesIO()
    df.to_excel(bio, index=False)
    return bio.getvalue()


def test_import_minimal_ok(db_session):
    df = pd.DataFrame([
        {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "publicado"}
    ])
    batch = process_excel_upload(db_session, make_excel(df), "ok.xlsx")
    assert batch.status == "validated"
    assert db_session.get(GFTEstadoPresentacion, "123456") is not None


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
    row = db_session.get(GFTEstadoPresentacion, "123456")
    assert row is not None
    assert row.estado_editorial == "borrador"
