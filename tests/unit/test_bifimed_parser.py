from pathlib import Path

from app.services.bifimed_parser import extract_label_value_pairs, parse_bifimed_detail_html


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "bifimed"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_parse_detail_ok_simple_fixture():
    data = parse_bifimed_detail_html(_load_fixture("detail_ok_simple.html"), requested_cn="988220")

    assert data is not None
    assert data["situacion_financiacion"] == "Si"
    assert data["estado_nomenclator"] == "ALTA"
    assert data["aportacion_usuario"] == "NORMAL"
    assert data["subgrupo_atc"] == "A01AA01 - Medicamento de ejemplo"
    assert data["detalle_financiacion_json"]["Código nacional"] == "988220"


def test_parse_detail_ok_restricted_fixture():
    data = parse_bifimed_detail_html(_load_fixture("detail_ok_restricted.html"), requested_cn="769360")

    assert data is not None
    assert data["situacion_financiacion"] == "Sí para determinadas indicaciones/condiciones"
    assert data["condiciones_financiacion_restringidas"] == "Visado"
    assert data["estado_nomenclator"] == "FINANCIADO PENDIENTE DE ALTA"
    assert data["aportacion_usuario"] == "ESPECIAL"


def test_extract_label_value_pairs_ignores_nested_table_rows():
    html = _load_fixture("detail_ok_nested_indications.html")

    pairs = extract_label_value_pairs(html)

    assert "Indicaciones autorizadas" in pairs
    assert "Indicación autorizada" not in pairs
    assert "Texto de indicación de ejemplo" not in pairs

    data = parse_bifimed_detail_html(html, requested_cn="767418")

    assert data is not None
    assert data["situacion_financiacion"] == "Sí para determinadas indicaciones/condiciones"
    assert data["estado_nomenclator"] == "H-ALTA"
    assert data["aportacion_usuario"] == "SIN APORTACION"
    assert data["subgrupo_atc"] == "B06AC07 - Garadacimab"


def test_parse_detail_ok_not_included_fixture():
    data = parse_bifimed_detail_html(_load_fixture("detail_ok_not_included.html"), requested_cn="718395")

    assert data is not None
    assert data["situacion_financiacion"] == "No incluido"
    assert data["estado_nomenclator"] is None
    assert data["aportacion_usuario"] is None


def test_parse_detail_returns_none_when_requested_cn_differs():
    data = parse_bifimed_detail_html(_load_fixture("detail_ok_simple.html"), requested_cn="000000")

    assert data is None


def test_parse_detail_returns_none_without_codigo_nacional():
    html = """
    <table>
      <tr><th>Situación de financiación</th><td>Si</td></tr>
    </table>
    """

    assert parse_bifimed_detail_html(html, requested_cn="988220") is None


def test_extract_label_value_pairs_normalizes_nbsp_and_spaces():
    html = """
    <table>
      <tr><td> Código&nbsp; nacional </td><td>  988&nbsp;220  </td></tr>
      <tr><th>Subgrupo ATC/Descripción</th><td>A01AA01\n-\tMedicamento&nbsp;de ejemplo</td></tr>
    </table>
    """

    pairs = extract_label_value_pairs(html)

    assert pairs["Código nacional"] == "988 220"
    assert pairs["Subgrupo ATC/Descripción"] == "A01AA01 - Medicamento de ejemplo"
