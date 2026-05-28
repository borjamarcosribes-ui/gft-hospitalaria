import re
import unicodedata
from typing import Literal

Confidence = Literal["alta", "media", "baja"]


def _clean_text(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = unicodedata.normalize("NFKC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(lines).strip()


def _split_candidate_lines(clean_text: str) -> list[str]:
    segments: list[str] = []
    for block in clean_text.split("\n\n"):
        for line in [l.strip() for l in block.split("\n") if l.strip()]:
            segments.append(line)
    return segments


def _strip_marker(line: str) -> str:
    return re.sub(r"^(?:[-•*·]\s+|\(?\d+[\).]\s+|[a-zA-Z]\)\s+)", "", line).strip()


def _line_title_and_text(line: str) -> tuple[str, str] | None:
    line = _strip_marker(line)
    if not line:
        return None
    if ":" in line:
        title, rest = line.split(":", 1)
        title = title.strip()
        rest = rest.strip()
        if 2 <= len(title) <= 90 and rest:
            return title, rest
    return None


def normalize_cima_indicaciones(raw_text: str | None) -> list[dict[str, str]]:
    clean_text = _clean_text(raw_text)
    if not clean_text:
        return []

    lines = _split_candidate_lines(clean_text)
    items: list[dict[str, str]] = []

    # 1) Líneas con patrón "Título: texto"
    colon_items = [_line_title_and_text(line) for line in lines]
    colon_items = [item for item in colon_items if item]
    if len(colon_items) >= 2:
        for title, text in colon_items:
            items.append({"titulo": title, "texto": text, "confidence": "alta"})
        return items

    # 2) Bullets / numeración / guiones
    bullet_lines = [line for line in lines if re.match(r"^(?:[-•*·]\s+|\(?\d+[\).]\s+|[a-zA-Z]\)\s+)", line)]
    if len(bullet_lines) >= 2:
        for line in bullet_lines:
            text = _strip_marker(line)
            if text:
                items.append({"titulo": text[:110], "texto": text, "confidence": "media"})
        return items

    # 3) Bloques por línea independiente (adultos/pediátrica/patologías y similares)
    if len(lines) >= 2:
        for line in lines:
            cleaned = _strip_marker(line)
            if not cleaned:
                continue
            sentence_title = re.split(r"[.;]", cleaned, maxsplit=1)[0].strip()
            title = sentence_title if 3 <= len(sentence_title) <= 120 else cleaned[:110]
            items.append({"titulo": title, "texto": cleaned, "confidence": "media"})
        if len(items) >= 2:
            return items

    return [{"titulo": "Indicaciones terapéuticas", "texto": clean_text, "confidence": "baja"}]
