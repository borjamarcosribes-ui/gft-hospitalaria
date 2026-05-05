from app.services.principio_activo_service import (
    build_slug,
    extract_principios_from_cima_data,
    normalize_principio_activo_key,
    split_principio_activo_text,
)


def test_normalize_principio_activo_key_tildes():
    assert normalize_principio_activo_key("Ácido acetilsalicílico") == "acido acetilsalicilico"


def test_normalize_principio_activo_key_mayusculas_y_espacios():
    assert normalize_principio_activo_key("  PARACETAMOL   ") == "paracetamol"


def test_normalize_principio_activo_key_conserva_sales_hidratos():
    assert normalize_principio_activo_key("Amoxicilina trihidrato") == "amoxicilina trihidrato"


def test_build_slug_espacios_a_guiones():
    assert build_slug("acido acetilsalicilico") == "acido-acetilsalicilico"


def test_build_slug_elimina_caracteres_problematicos():
    assert build_slug("acido # acetilsalicilico!!!") == "acido-acetilsalicilico"


def test_build_slug_none_y_vacio():
    assert build_slug(None) is None
    assert build_slug("   ") is None


def test_split_principio_activo_text_separa_por_barra():
    assert split_principio_activo_text("Paracetamol / Codeína") == ["Paracetamol", "Codeína"]


def test_split_principio_activo_text_separa_por_mas():
    assert split_principio_activo_text("Abacavir + Lamivudina") == ["Abacavir", "Lamivudina"]


def test_split_principio_activo_text_separa_por_coma():
    assert split_principio_activo_text("Amlodipino, Valsartán") == ["Amlodipino", "Valsartán"]


def test_split_principio_activo_text_deduplica_preservando_orden():
    assert split_principio_activo_text("Paracetamol / paracetamol + Codeína") == ["Paracetamol", "Codeína"]


def test_split_principio_activo_text_no_rompe_sales_hidratos():
    assert split_principio_activo_text("Amoxicilina trihidrato") == ["Amoxicilina trihidrato"]


def test_extract_principios_from_lista_strings():
    result = extract_principios_from_cima_data(["Paracetamol", "Codeína"])
    assert [x["nombre_normalizado"] for x in result] == ["paracetamol", "codeina"]


def test_extract_principios_from_lista_objetos_nombre():
    payload = [{"nombre": "Paracetamol"}, {"nombre": "Codeína"}]
    result = extract_principios_from_cima_data(payload)
    assert [x["nombre_display"] for x in result] == ["Paracetamol", "Codeína"]


def test_extract_principios_from_lista_objetos_campos_alternativos():
    payload = [{"principioActivo": "Abacavir"}, {"descripcion": "Lamivudina"}, {"sustancia": "Zidovudina"}]
    result = extract_principios_from_cima_data(payload)
    assert [x["nombre_normalizado"] for x in result] == ["abacavir", "lamivudina", "zidovudina"]


def test_extract_principios_from_string_combinado():
    result = extract_principios_from_cima_data("Paracetamol / Codeína")
    assert [x["nombre_display"] for x in result] == ["Paracetamol", "Codeína"]


def test_extract_principios_from_data_con_clave_principios_activos_json():
    payload = {"principios_activos_json": "Paracetamol + Codeína"}
    result = extract_principios_from_cima_data(payload)
    assert [x["slug"] for x in result] == ["paracetamol", "codeina"]


def test_extract_principios_none_devuelve_lista_vacia():
    assert extract_principios_from_cima_data(None) == []


def test_extract_principios_estructura_inesperada_devuelve_lista_vacia():
    assert extract_principios_from_cima_data({"foo": "bar"}) == []
    assert extract_principios_from_cima_data(123) == []


def test_extract_principios_deduplicacion_por_clave_normalizada_y_orden():
    result = extract_principios_from_cima_data("PARACETAMOL / Paracetamol + Codeína")
    assert [x["nombre_normalizado"] for x in result] == ["paracetamol", "codeina"]
    assert [x["orden"] for x in result] == [1, 2]


def test_extract_principios_nombre_display_conservado_limpio():
    result = extract_principios_from_cima_data(["  Paracetamol   "])
    assert result[0]["nombre_display"] == "Paracetamol"
