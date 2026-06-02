from __future__ import annotations

import hashlib
import unicodedata
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

NO_INFORMADO = "No informado"
TARGET_SECTIONS = ("4.1", "4.2", "4.4", "4.6", "5.2")
RENAL_PATTERNS = (
    r"\brenal\b",
    r"riñ[oó]n",
    r"insuficiencia renal",
    r"aclaramiento de creatinina",
    r"\bclcr\b",
    r"filtrado glomerular",
    r"hemodi[aá]lisis",
    r"di[aá]lisis",
)
HEPATIC_PATTERNS = (
    r"hep[aá]tic[ao]",
    r"h[ií]gado",
    r"insuficiencia hep[aá]tica",
    r"hepatopat[ií]a",
    r"cirrosis",
    r"transaminasas",
)
EMBARAZO_PATTERNS = (r"embarazo", r"embarazada", r"gestaci[oó]n", r"gestante", r"feto", r"fetal")
LACTANCIA_PATTERNS = (r"lactancia", r"leche materna", r"lactante")
_HEADING_RE = re.compile(r"^(?:secci[oó]n\s*)?(4\.1|4\.2|4\.4|4\.6|5\.2)(?:\s*[.:-]?\s|$)", re.IGNORECASE)
_ANY_SECTION_RE = re.compile(r"^(?:secci[oó]n\s*)?(\d+(?:\.\d+)+)(?:\s*[.:-]?\s|$)", re.IGNORECASE)

_SECTION_TITLE_PREFIXES = {
    "4.1": ("Indicaciones terapeuticas",),
    "4.2": ("Posologia y forma de administracion",),
    "4.4": ("Advertencias y precauciones especiales de empleo",),
    "4.6": ("Fertilidad, embarazo y lactancia",),
    "5.2": ("Propiedades farmacocineticas",),
}




class _TextHTMLParser(HTMLParser):
    _BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "div", "dl", "dt", "dd",
        "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
        "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
        "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


@dataclass(frozen=True)
class CimaClinicalExtraction:
    source_status: str
    indicaciones_ficha_tecnica: str
    ajuste_insuficiencia_renal: str
    ajuste_insuficiencia_hepatica: str
    precauciones_embarazo: str
    precauciones_lactancia: str
    source_sections: dict[str, str]
    source_text: str
    source_hash: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_status": self.source_status,
            "indicaciones_ficha_tecnica": self.indicaciones_ficha_tecnica,
            "ajuste_insuficiencia_renal": self.ajuste_insuficiencia_renal,
            "ajuste_insuficiencia_hepatica": self.ajuste_insuficiencia_hepatica,
            "precauciones_embarazo": self.precauciones_embarazo,
            "precauciones_lactancia": self.precauciones_lactancia,
            "source_sections": self.source_sections,
            "source_text": self.source_text,
            "source_hash": self.source_hash,
            "warnings": self.warnings,
        }


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _html_to_lines(html: str | None) -> list[str]:
    if not html:
        return []
    parser = _TextHTMLParser()
    parser.feed(html)
    parser.close()
    text = parser.text()
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_cima_sections_from_html(html: str | None) -> dict[str, str]:
    sections: dict[str, list[str]] = {section: [] for section in TARGET_SECTIONS}
    current: str | None = None
    for line in _html_to_lines(html):
        heading = _HEADING_RE.match(line)
        any_section = _ANY_SECTION_RE.match(line)
        if heading:
            current = heading.group(1)
            heading_title = _clean(line[heading.end():])
            if current in sections and heading_title:
                sections[current].append(heading_title)
            continue
        if any_section:
            current = None
        if current in sections:
            sections[current].append(line)
    return {section: _clean(" ".join(parts)) for section, parts in sections.items() if _clean(" ".join(parts))}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;:])\s+", text) if s.strip()]


def _extract_matching_text(section_texts: list[str], patterns: tuple[str, ...]) -> str:
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    matches: list[str] = []
    for text in section_texts:
        for sentence in _sentences(text):
            if any(regex.search(sentence) for regex in regexes):
                matches.append(sentence)
    return _clean(" ".join(dict.fromkeys(matches)))


def _source_hash(source_sections: dict[str, str], source_text: str) -> str:
    canonical = "\n".join(f"{section}:{source_sections.get(section, '')}" for section in TARGET_SECTIONS)
    return hashlib.sha256(f"{canonical}\n{source_text}".encode("utf-8")).hexdigest()



def _fold_title(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _section_body_without_title(section: str, text: str) -> str:
    body = _clean(text)
    folded_body = _fold_title(body)
    for prefix in _SECTION_TITLE_PREFIXES.get(section, ()):
        if folded_body.startswith(_fold_title(prefix)):
            return _clean(body[len(prefix):])
    return body

def extract_cima_clinical_from_html(html: str | None) -> CimaClinicalExtraction:
    source_sections = extract_cima_sections_from_html(html)
    source_text = _clean(" ".join(_html_to_lines(html)))
    extract_sections = {
        section: _section_body_without_title(section, text)
        for section, text in source_sections.items()
    }
    warnings: list[str] = []

    indicaciones = extract_sections.get("4.1", "")
    renal = _extract_matching_text([extract_sections.get(s, "") for s in ("4.2", "4.4", "5.2")], RENAL_PATTERNS)
    hepatica = _extract_matching_text([extract_sections.get(s, "") for s in ("4.2", "4.4", "5.2")], HEPATIC_PATTERNS)
    embarazo = _extract_matching_text([extract_sections.get("4.6", "")], EMBARAZO_PATTERNS)
    lactancia = _extract_matching_text([extract_sections.get("4.6", "")], LACTANCIA_PATTERNS)

    values = {
        "indicaciones_ficha_tecnica": indicaciones,
        "ajuste_insuficiencia_renal": renal,
        "ajuste_insuficiencia_hepatica": hepatica,
        "precauciones_embarazo": embarazo,
        "precauciones_lactancia": lactancia,
    }
    for field, value in values.items():
        if not value:
            warnings.append(f"{field}: no informado en secciones HTML analizadas")

    useful_count = sum(1 for value in values.values() if value)
    if useful_count == 0:
        source_status = "no_data"
    elif useful_count == len(values):
        source_status = "ok"
    else:
        source_status = "partial"

    return CimaClinicalExtraction(
        source_status=source_status,
        indicaciones_ficha_tecnica=indicaciones or NO_INFORMADO,
        ajuste_insuficiencia_renal=renal or NO_INFORMADO,
        ajuste_insuficiencia_hepatica=hepatica or NO_INFORMADO,
        precauciones_embarazo=embarazo or NO_INFORMADO,
        precauciones_lactancia=lactancia or NO_INFORMADO,
        source_sections=source_sections,
        source_text=source_text,
        source_hash=_source_hash(source_sections, source_text),
        warnings=warnings,
    )


# Backwards-compatible alias for tests/callers that prefer a shorter name.
def extract_clinical_fields_from_cima_html(html: str | None) -> dict[str, Any]:
    return extract_cima_clinical_from_html(html).to_dict()
