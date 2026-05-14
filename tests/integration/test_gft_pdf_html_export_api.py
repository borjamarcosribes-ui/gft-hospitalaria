from tests.integration.test_gft_pdf_export_service import (
    _add_indicaciones_cache,
    _create_view,
    _insert_medicamento,
)


FORBIDDEN_INTERNAL_FIELDS = [
    "raw_data",
    "sync_status",
    "sync_error",
    "comentario_revision",
    "revisado_por",
    "estado_gft",
    "estado_editorial",
]


def test_gft_export_html_endpoint_returns_printable_html(client, db_session):
    _insert_medicamento(db_session, "700001", nombre="Medicamento publicado")
    _add_indicaciones_cache(db_session, "700001", "Indicación pública desde ficha técnica")
    _create_view(db_session)

    response = client.get("/gft/export/html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "<!doctype html>" in html
    assert '<html lang="es">' in html
    assert "Guía Farmacoterapéutica Hospitalaria" in html
    assert "Medicamento publicado" in html
    assert "Indicación pública desde ficha técnica" in html


def test_gft_export_html_only_includes_published_medicamentos(client, db_session):
    _insert_medicamento(db_session, "710001", nombre="Publicado visible")
    _insert_medicamento(db_session, "710002", nombre="Excluido oculto", estado_gft="excluido")
    _insert_medicamento(db_session, "710003", nombre="Pendiente oculto", estado_editorial="pendiente")
    _insert_medicamento(db_session, "710004", nombre="Borrador oculto", estado_editorial="borrador")
    _create_view(db_session)

    response = client.get("/gft/export/html")

    assert response.status_code == 200
    html = response.text
    assert "Publicado visible" in html
    assert "710001" in html
    assert "Excluido oculto" not in html
    assert "710002" not in html
    assert "Pendiente oculto" not in html
    assert "710003" not in html
    assert "Borrador oculto" not in html
    assert "710004" not in html


def test_gft_export_html_does_not_expose_internal_fields(client, db_session):
    _insert_medicamento(db_session, "720001", nombre="Medicamento público")
    _create_view(db_session)

    response = client.get("/gft/export/html")

    assert response.status_code == 200
    html = response.text
    for field in FORBIDDEN_INTERNAL_FIELDS:
        assert field not in html


def test_gft_export_html_escapes_dynamic_content(client, db_session):
    _insert_medicamento(
        db_session,
        "730001",
        nombre='Nombre <script>alert("x")</script>',
        restricciones_hospitalarias='Uso <script>alert("restricción")</script>',
    )
    _add_indicaciones_cache(db_session, "730001", 'Indicación <script>alert("ft")</script>')
    _create_view(db_session)

    response = client.get("/gft/export/html")

    assert response.status_code == 200
    html = response.text
    assert '<script>alert("x")</script>' not in html
    assert '<script>alert("restricción")</script>' not in html
    assert '<script>alert("ft")</script>' not in html
    assert "&lt;script&gt;" in html
    assert "&lt;/script&gt;" in html


def test_gft_export_html_returns_valid_empty_document(client, db_session):
    _create_view(db_session)

    response = client.get("/gft/export/html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "<!doctype html>" in html
    assert '<html lang="es">' in html
    assert "Guía Farmacoterapéutica Hospitalaria" in html
    assert '<span class="total-number">0</span>' in html
    assert "No hay medicamentos publicados." in html
