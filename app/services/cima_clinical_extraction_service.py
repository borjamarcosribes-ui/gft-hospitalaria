from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Mapping


NO_INFORMADO = "No informado"
EXTRACTION_VERSION = "cima_ft_html_v1"

RENAL_KEYWORDS = (
    "renal",
    "riñón",
    "rinon",
    "insuficiencia renal",
    "función renal",
    "funcion renal",
    "aclaramiento de creatinina",
    "hemodiálisis",
    "hemodialisis",
    "diálisis",
    "dialisis",
    "nefropatía",
    "nefropatia",
)
HEPATIC_KEYWORDS = (
    "hepático",
    "hepatico",
    "hepática",
    "hepatica",
    "insuficiencia hepática",
    "insuficiencia hepatica",
    "función hepática",
    "funcion hepatica",
    "hepatopatía",
    "hepatopatia",
    "transaminasas",
    "child-pugh",
)
EMBARAZO_KEYWORDS = (
    "embarazo",
    "embarazada",
    "gestación",
    "gestacion",
    "gestante",
    "fetal",
    "feto",
    "teratogenicidad",
    "fertilidad",
)
LACTANCIA_KEYWORDS = (
    "lactancia",
    "lactante",
    "leche materna",
    "amamantamiento",
    "excreta en leche",
)
CLINICAL_FIELD_NAMES = (
    "indicaciones_ficha_tecnica",
    "ajuste_insuficiencia_renal",
    "ajuste_insuficiencia_hepatica",
    "precauciones_embarazo",
    "precauciones_lactancia",
)


@dataclass(frozen=True)
class ClinicalExtractionResult:
    indicaciones_ficha_tecnica: str = NO_INFORMADO
    ajuste_insuficiencia_renal: str = NO_INFORMADO
    ajuste_insuficiencia_hepatica: str = NO_INFORMADO
    precauciones_embarazo: str = NO_INFORMADO
    precauciones_lactancia: str = NO_INFORMADO
    source_url: str | None = None
    source_type: str = "cima_ficha_tecnica_html"
    extracted_sections: list[str] = field(default_factory=list)
    status: str = "no_data"
    extraction_version: str = EXTRACTION_VERSION
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def useful_fields(self) -> dict[str, str]:
        return {
            name: value
            for name in CLINICAL_FIELD_NAMES
            if (value := getattr(self, name)) and value != NO_INFORMADO
        }

    def to_summary_source(self) -> dict[str, Any]:
        return {
            "indicaciones_ficha_tecnica": self.indicaciones_ficha_tecnica,
            "ajuste_insuficiencia_renal": self.ajuste_insuficiencia_renal,
            "ajuste_insuficiencia_hepatica": self.ajuste_insuficiencia_hepatica,
            "precauciones_embarazo": self.precauciones_embarazo,
            "precauciones_lactancia": self.precauciones_lactancia,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "extracted_sections": self.extracted_sections,
            "status": self.status,
            "extraction_version": self.extraction_version,
            "extracted_at": self.extracted_at,
        }


class _VisibleTextParser(HTMLParser):
    _BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "fieldset", "figcaption",
        "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav",
        "ol", "p", "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def _html_to_lines(html_text: str) -> list[str]:
    parser = _VisibleTextParser()
    parser.feed(html_text)
    text = html.unescape(parser.text())
    text = text.replace("\xa0", " ")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[ \t\r\f\v]+", " ", raw).strip()
        if line:
            lines.append(line)
    return lines


def _normalise_for_match(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = text.replace("�", "")
    return re.sub(r"\s+", " ", text).strip()


_SECTION_RE = re.compile(r"^\s*(?P<section>(?:[1-9]|10)(?:\.[0-9]+){0,2})\s*\.?\s+(?P<title>\S.*)$")
_TARGET_SECTIONS = {"4.1", "4.2", "4.4", "4.6", "5.2"}


def _section_number(line: str) -> str | None:
    match = _SECTION_RE.match(line)
    if not match:
        return None
    return match.group("section")


def extract_sections_from_html(html_text: str) -> dict[str, str]:
    lines = _html_to_lines(html_text)
    starts: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        section = _section_number(line)
        if section:
            starts.append((idx, section))
    sections: dict[str, str] = {}
    for pos, (start_idx, section) in enumerate(starts):
        if section not in _TARGET_SECTIONS:
            continue
        end_idx = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        content_lines = lines[start_idx + 1 : end_idx]
        # If the heading line contains text after a dash/colon, keep that non-title tail as content.
        content = _join_paragraphs(content_lines)
        if content:
            sections[section] = content
    return sections


def _join_paragraphs(paragraphs: list[str]) -> str:
    cleaned = [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p and p.strip()]
    return "\n\n".join(cleaned)


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    norm = _normalise_for_match(text)
    return any(_normalise_for_match(keyword) in norm for keyword in keywords)


def _relevant_paragraphs(sections: Mapping[str, str], section_ids: tuple[str, ...], keywords: tuple[str, ...]) -> tuple[str, list[str]]:
    matches: list[str] = []
    used: list[str] = []
    seen: set[str] = set()
    for section in section_ids:
        for paragraph in [p.strip() for p in (sections.get(section) or "").split("\n\n") if p.strip()]:
            if not _contains_keyword(paragraph, keywords):
                continue
            key = _normalise_for_match(paragraph)
            if key in seen:
                continue
            seen.add(key)
            matches.append(paragraph)
            if section not in used:
                used.append(section)
    return _join_paragraphs(matches) if matches else NO_INFORMADO, used


def _extract_subsection(section_text: str, wanted: str) -> str | None:
    paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
    wanted_norm = _normalise_for_match(wanted)
    subheads = {"embarazo", "lactancia", "fertilidad"}
    out: list[str] = []
    in_wanted = False
    for paragraph in paragraphs:
        norm = _normalise_for_match(paragraph).strip(" .:")
        is_subhead = norm in subheads or any(norm.startswith(f"{s} ") and len(norm.split()) <= 4 for s in subheads)
        if is_subhead:
            if in_wanted and norm != wanted_norm:
                break
            in_wanted = norm.startswith(wanted_norm)
            if norm == wanted_norm:
                continue
        elif in_wanted:
            out.append(paragraph)
    return _join_paragraphs(out) if out else None


def _pregnancy_text(section_46: str) -> str:
    explicit = _extract_subsection(section_46, "embarazo")
    if explicit:
        return explicit
    matches = [p for p in [p.strip() for p in section_46.split("\n\n") if p.strip()] if _contains_keyword(p, EMBARAZO_KEYWORDS)]
    return _join_paragraphs(matches) if matches else NO_INFORMADO


def _lactation_text(section_46: str) -> str:
    explicit = _extract_subsection(section_46, "lactancia")
    if explicit:
        return explicit
    matches = [p for p in [p.strip() for p in section_46.split("\n\n") if p.strip()] if _contains_keyword(p, LACTANCIA_KEYWORDS)]
    return _join_paragraphs(matches) if matches else NO_INFORMADO


def extract_clinical_fields_from_html(html_text: str, *, source_url: str | None = None) -> ClinicalExtractionResult:
    sections = extract_sections_from_html(html_text)
    extracted_sections: list[str] = []
    indicaciones = sections.get("4.1") or NO_INFORMADO
    if indicaciones != NO_INFORMADO:
        extracted_sections.append("4.1")
    renal, renal_sections = _relevant_paragraphs(sections, ("4.2", "4.4", "5.2"), RENAL_KEYWORDS)
    hepatico, hepatic_sections = _relevant_paragraphs(sections, ("4.2", "4.4", "5.2"), HEPATIC_KEYWORDS)
    embarazo = NO_INFORMADO
    lactancia = NO_INFORMADO
    if sections.get("4.6"):
        embarazo = _pregnancy_text(sections["4.6"])
        lactancia = _lactation_text(sections["4.6"])
    for section in [*renal_sections, *hepatic_sections, "4.6" if sections.get("4.6") else None]:
        if section and section not in extracted_sections:
            extracted_sections.append(section)
    useful_count = sum(
        1
        for value in (indicaciones, renal, hepatico, embarazo, lactancia)
        if value and value != NO_INFORMADO
    )
    status = "ok" if useful_count == 5 else "partial" if useful_count else "no_data"
    return ClinicalExtractionResult(
        indicaciones_ficha_tecnica=indicaciones,
        ajuste_insuficiencia_renal=renal,
        ajuste_insuficiencia_hepatica=hepatico,
        precauciones_embarazo=embarazo,
        precauciones_lactancia=lactancia,
        source_url=source_url,
        extracted_sections=extracted_sections,
        status=status,
    )


def _coerce_doc_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):
        for key in ("descripcion", "codigo", "url", "href"):
            raw = value.get(key)
            if raw:
                return str(raw).strip() or None
    return None


def resolve_ficha_tecnica_html_url(cima_row: Any | None) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    docs = getattr(cima_row, "documentos_json", None) if cima_row is not None else None
    if isinstance(docs, str):
        try:
            import json
            docs = json.loads(docs)
        except Exception:
            docs = None
    if isinstance(docs, list):
        for doc in docs:
            if not isinstance(doc, Mapping) or doc.get("tipo") != 1:
                continue
            html_url = _coerce_doc_url(doc.get("urlHtml"))
            if html_url:
                return html_url, warnings
    url_ft = _coerce_doc_url(getattr(cima_row, "url_ficha_tecnica", None)) if cima_row is not None else None
    if url_ft and "/docpdf/ft/" in url_ft.lower():
        derived = re.sub(r"/docpdf/ft/([^/?#]+)", r"/dochtml/ft/\1", url_ft, flags=re.IGNORECASE)
        derived = re.sub(r"/([^/?#]+)\.pdf($|[?#])", r"/FT_\1.html\2", derived, flags=re.IGNORECASE)
        if derived != url_ft:
            warnings.append("html_derivado_desde_pdf_cima")
            return derived, warnings
    if url_ft and (url_ft.lower().endswith(".html") or "/dochtml/" in url_ft.lower()):
        return url_ft, warnings
    warnings.append("sin_html_ficha_tecnica")
    return None, warnings


def fetch_html(url: str, *, timeout: float = 15.0) -> str:
    import httpx

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers={"Accept": "text/html,application/xhtml+xml"})
    response.raise_for_status()
    return response.text


def extract_clinical_fields_from_cima_row(
    cima_row: Any | None,
    *,
    fetcher: Callable[[str], str] | None = None,
) -> ClinicalExtractionResult:
    url, warnings = resolve_ficha_tecnica_html_url(cima_row)
    if not url:
        return ClinicalExtractionResult(status="no_data", warnings=warnings)
    try:
        html_text = (fetcher or fetch_html)(url)
        result = extract_clinical_fields_from_html(html_text, source_url=url)
        return ClinicalExtractionResult(**{**result.__dict__, "warnings": [*warnings, *result.warnings]})
    except Exception as exc:
        return ClinicalExtractionResult(source_url=url, status="error", warnings=warnings, error=str(exc)[:500])


def clinical_extraction_hash(result: ClinicalExtractionResult) -> str:
    source = "\n".join(f"{name}:{getattr(result, name)}" for name in CLINICAL_FIELD_NAMES)
    source += f"\nsource_url:{result.source_url}\nversion:{result.extraction_version}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
