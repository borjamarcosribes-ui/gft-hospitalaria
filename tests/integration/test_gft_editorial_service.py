import pytest

from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.gft_editorial_service import (
    GFTEditorialValidationError,
    update_gft_editorial_fields,
)


def _insert_gft_estado(
    db_session,
    cn: str = "111111",
    estado_gft: str = "incluido",
    estado_editorial: str = "publicado",
    **kwargs,
):
    row = GFTEstadoPresentacion(
        cn=cn,
        estado_gft=estado_gft,
        estado_editorial=estado_editorial,
        **kwargs,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_update_gft_editorial_fields_updates_allowed_fields(db_session):
    _insert_gft_estado(db_session, cn="111111")

    result = update_gft_editorial_fields(
        db_session,
        "111111",
        {
            "ajuste_insuficiencia_renal": " Ajustar si FG < 30 ",
            "precauciones_embarazo": " Evitar salvo criterio clínico ",
        },
        revisado_por=" Farmacia ",
    )

    assert result is not None
    assert result.ajuste_insuficiencia_renal == "Ajustar si FG < 30"
    assert result.precauciones_embarazo == "Evitar salvo criterio clínico"
    assert result.revisado_por == "Farmacia"
    assert result.fecha_revision is not None
    assert result.updated_at is not None


def test_update_gft_editorial_fields_preserves_omitted_fields(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        ajuste_insuficiencia_hepatica="Texto previo",
    )

    result = update_gft_editorial_fields(
        db_session,
        "111111",
        {"precauciones_lactancia": "Precaución en lactancia"},
    )

    assert result is not None
    assert result.precauciones_lactancia == "Precaución en lactancia"
    assert result.ajuste_insuficiencia_hepatica == "Texto previo"


def test_update_gft_editorial_fields_clears_blank_values(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        ajuste_insuficiencia_renal="Texto previo",
    )

    result = update_gft_editorial_fields(
        db_session,
        "111111",
        {"ajuste_insuficiencia_renal": "   "},
    )

    assert result is not None
    assert result.ajuste_insuficiencia_renal is None


def test_update_gft_editorial_fields_returns_none_for_missing_cn(db_session):
    result = update_gft_editorial_fields(
        db_session,
        "999999",
        {"precauciones_lactancia": "Precaución en lactancia"},
    )

    assert result is None


def test_update_gft_editorial_fields_rejects_empty_cn(db_session):
    with pytest.raises(GFTEditorialValidationError) as exc_info:
        update_gft_editorial_fields(
            db_session,
            "",
            {"precauciones_lactancia": "Precaución en lactancia"},
        )

    assert str(exc_info.value) == "CN obligatorio"


def test_update_gft_editorial_fields_rejects_empty_fields(db_session):
    with pytest.raises(GFTEditorialValidationError) as exc_info:
        update_gft_editorial_fields(db_session, "111111", {})

    assert str(exc_info.value) == "No hay campos para actualizar"


def test_update_gft_editorial_fields_rejects_forbidden_fields(db_session):
    with pytest.raises(GFTEditorialValidationError) as exc_info:
        update_gft_editorial_fields(
            db_session,
            "111111",
            {"estado_gft": "excluido", "cn": "222222"},
        )

    assert str(exc_info.value) == "Campos editoriales no permitidos: cn, estado_gft"


def test_update_gft_editorial_fields_does_not_change_publication_state(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    result = update_gft_editorial_fields(
        db_session,
        "111111",
        {"comentario_revision": "Revisión clínica"},
    )

    assert result is not None
    assert result.estado_gft == "incluido"
    assert result.estado_editorial == "publicado"


def test_update_gft_editorial_fields_does_not_create_new_rows(db_session):
    result = update_gft_editorial_fields(
        db_session,
        "999999",
        {"comentario_revision": "Revisión clínica"},
    )

    assert result is None
    assert db_session.query(GFTEstadoPresentacion).count() == 0
