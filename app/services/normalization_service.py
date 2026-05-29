import math
import re
import unicodedata


class NormalizationError(ValueError):
    pass


def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "<na>", "none", "null", "nulo"}


def normalize_text(value):
    if is_missing(value):
        return None
    text = str(value).strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _norm_key(value):
    text = normalize_text(value)
    if text is None:
        return ""
    text = text.lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text


def normalize_cn(value) -> str:
    """Normalize CN values for safe internal joins without coercing to int.

    The canonical GFT flow must tolerate missing, numeric and textual CN
    representations.  Missing values return an empty string; significant
    leading zeros are preserved.
    """
    if is_missing(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.endswith(".0") and text.replace(".", "", 1).isdigit():
        text = text[:-2]
    return text


def normalize_cn_or_raise(value) -> str:
    text = normalize_cn(value)
    if not text:
        raise NormalizationError("CN vacío")
    if not text.isdigit():
        raise NormalizationError("CN inválido")
    return text


def classify_observaciones_revision(value):
    key = _norm_key(value)
    included = {"si"}
    excluded = {"no", "no guia", "bloquear", "no aparece en clinic", "sin planificador o consumo"}
    pending = {"guia", "si?", "no?", "???", "", "nulo", "none", "vacio", "nan"}
    if key in included:
        return "incluido"
    if key in excluded:
        return "excluido"
    if key in pending:
        return "pendiente_revision"
    return "pendiente_revision"


def normalize_estado_editorial(value):
    key = _norm_key(value)
    if key in {"", "none", "null", "nan"}:
        return "borrador"
    mapping = {
        "borrador": "borrador",
        "draft": "borrador",
        "validado": "validado",
        "publicado": "publicado",
        "publish": "publicado",
        "retirado": "retirado",
    }
    if key in mapping:
        return mapping[key]
    raise NormalizationError(f"Estado editorial desconocido: {value}")


def normalize_principio_activo(value):
    text = normalize_text(value)
    if not text:
        return None
    key = _norm_key(text)
    key = key.replace("/", " + ").replace("|", " + ").replace("+", " + ")
    key = re.sub(r"\s+", " ", key).strip()
    return key
