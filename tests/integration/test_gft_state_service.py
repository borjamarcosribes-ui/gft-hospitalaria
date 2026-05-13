from datetime import date

import pytest

from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.gft_state_service import (
    GFTStateValidationError,
    update_gft_publication_state,
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


def _get_gft_estado(db_session, cn: str) -> GFTEstadoPresentacion | None:
    db_session.expire_all()
    return db_session.get(GFTEstadoPresentacion, cn)


def test_update_gft_publication_state_updates_estado_gft(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_gft="incluido",
    )

    assert result is not None
    assert result.estado_gft == "incluido"
    assert result.estado_editorial == "borrador"


def test_update_gft_publication_state_updates_estado_editorial(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_editorial="validado",
    )

    assert result is not None
    assert result.estado_gft == "incluido"
    assert result.estado_editorial == "validado"


def test_update_gft_publication_state_can_publish_included(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="validado",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_editorial="publicado",
        revisado_por="Farmacia",
    )

    assert result is not None
    assert result.estado_editorial == "publicado"
    assert result.revisado_por == "Farmacia"
    assert result.fecha_revision is not None


def test_update_gft_publication_state_can_include_and_publish_same_call(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    assert result is not None
    assert result.estado_gft == "incluido"
    assert result.estado_editorial == "publicado"


def test_update_gft_publication_state_rejects_publishing_non_included(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
    )

    with pytest.raises(GFTStateValidationError) as exc_info:
        update_gft_publication_state(
            db_session,
            "111111",
            estado_editorial="publicado",
        )

    assert str(exc_info.value) == "Solo se puede publicar un medicamento incluido"


def test_update_gft_publication_state_rejects_excluding_while_remaining_published(
    db_session,
):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    with pytest.raises(GFTStateValidationError) as exc_info:
        update_gft_publication_state(
            db_session,
            "111111",
            estado_gft="excluido",
        )

    assert str(exc_info.value) == "Solo se puede publicar un medicamento incluido"
    row = _get_gft_estado(db_session, "111111")
    assert row is not None
    assert row.estado_gft == "incluido"
    assert row.estado_editorial == "publicado"


def test_update_gft_publication_state_can_unpublish_and_exclude_same_call(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_gft="excluido",
        estado_editorial="retirado",
    )

    assert result is not None
    assert result.estado_gft == "excluido"
    assert result.estado_editorial == "retirado"


def test_update_gft_publication_state_rejects_invalid_estado_gft(db_session):
    with pytest.raises(GFTStateValidationError) as exc_info:
        update_gft_publication_state(db_session, "111111", estado_gft="foo")

    assert str(exc_info.value) == "estado_gft inválido"


def test_update_gft_publication_state_rejects_invalid_estado_editorial(db_session):
    with pytest.raises(GFTStateValidationError) as exc_info:
        update_gft_publication_state(db_session, "111111", estado_editorial="foo")

    assert str(exc_info.value) == "estado_editorial inválido"


def test_update_gft_publication_state_rejects_empty_cn(db_session):
    with pytest.raises(GFTStateValidationError) as exc_info:
        update_gft_publication_state(db_session, "", estado_gft="incluido")

    assert str(exc_info.value) == "CN obligatorio"


def test_update_gft_publication_state_rejects_no_state_changes(db_session):
    with pytest.raises(GFTStateValidationError) as exc_info:
        update_gft_publication_state(
            db_session,
            "111111",
            comentario_revision="texto",
        )

    assert str(exc_info.value) == "No hay estados para actualizar"


def test_update_gft_publication_state_returns_none_for_missing_cn(db_session):
    result = update_gft_publication_state(
        db_session,
        "999999",
        estado_gft="incluido",
    )

    assert result is None
    assert db_session.query(GFTEstadoPresentacion).count() == 0


def test_update_gft_publication_state_updates_comentario_revision(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_editorial="validado",
        comentario_revision=" Revisado ",
    )

    assert result is not None
    assert result.comentario_revision == "Revisado"


def test_update_gft_publication_state_clears_blank_comentario_revision(db_session):
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
        comentario_revision="Previo",
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_editorial="validado",
        comentario_revision="   ",
    )

    assert result is not None
    assert result.comentario_revision is None


def test_update_gft_publication_state_does_not_clear_revisado_por_when_blank(
    db_session,
):
    previous_fecha_revision = date(2026, 1, 1)
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
        revisado_por="Previo",
        fecha_revision=previous_fecha_revision,
    )

    result = update_gft_publication_state(
        db_session,
        "111111",
        estado_editorial="validado",
        revisado_por="   ",
    )

    assert result is not None
    assert result.revisado_por == "Previo"
    assert result.fecha_revision == previous_fecha_revision
