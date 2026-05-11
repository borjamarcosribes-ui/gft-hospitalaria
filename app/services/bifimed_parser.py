import re

from bs4 import BeautifulSoup


# La v1 del parser BIFIMED depende explícitamente de etiquetas en castellano.
BIFIMED_LABELS_ES_V1 = {
    "situacion_financiacion": "Situación de financiación",
    "condiciones_financiacion_restringidas": "Condiciones financiación restringidas",
    "condiciones_especiales_financiacion": "Condiciones especiales de financiación",
    "estado_nomenclator": "Estado de Nomenclátor",
    "aportacion_usuario": "Aportación usuario",
    "subgrupo_atc": "Subgrupo ATC/Descripción",
    "codigo_nacional": "Código nacional",
}


def normalize_bifimed_text(value: str) -> str:
    """Normaliza espacios preservando el texto semántico original de BIFIMED."""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def extract_label_value_pairs(html: str) -> dict[str, str]:
    """Extrae pares etiqueta/valor desde filas HTML de detalle BIFIMED."""
    soup = BeautifulSoup(html, "html.parser")
    pairs: dict[str, str] = {}

    for row in soup.find_all("tr"):
        # Las fichas BIFIMED pueden contener tablas internas de indicaciones;
        # sus filas no forman parte de los pares principales de la ficha.
        if row.find_parent("tr") is not None:
            continue

        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue

        label_index = None
        for index, cell in enumerate(cells[:-1]):
            if cell.name == "th":
                label_index = index
                break
        if label_index is None and cells[0].name == "td":
            label_index = 0
        if label_index is None or label_index + 1 >= len(cells):
            continue

        label = normalize_bifimed_text(cells[label_index].get_text(" ", strip=False))
        if not label:
            continue
        value = normalize_bifimed_text(cells[label_index + 1].get_text(" ", strip=False))
        pairs[label] = value

    return pairs


def _normalized_field(pairs: dict[str, str], field: str) -> str | None:
    value = pairs.get(BIFIMED_LABELS_ES_V1[field])
    return value if value else None


def parse_bifimed_detail_html(html: str, requested_cn: str) -> dict | None:
    """Parsea una ficha BIFIMED v1 basada explícitamente en etiquetas en castellano."""
    pairs = extract_label_value_pairs(html)
    codigo_nacional = pairs.get(BIFIMED_LABELS_ES_V1["codigo_nacional"])
    if codigo_nacional is None:
        return None
    if codigo_nacional != normalize_bifimed_text(requested_cn):
        return None

    return {
        "situacion_financiacion": _normalized_field(pairs, "situacion_financiacion"),
        "condiciones_financiacion_restringidas": _normalized_field(pairs, "condiciones_financiacion_restringidas"),
        "condiciones_especiales_financiacion": _normalized_field(pairs, "condiciones_especiales_financiacion"),
        "estado_nomenclator": _normalized_field(pairs, "estado_nomenclator"),
        "aportacion_usuario": _normalized_field(pairs, "aportacion_usuario"),
        "subgrupo_atc": _normalized_field(pairs, "subgrupo_atc"),
        "detalle_financiacion_json": pairs,
    }
