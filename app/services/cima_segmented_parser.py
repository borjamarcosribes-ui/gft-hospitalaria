from typing import Any


def normalize_segmented_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.replace("\xa0", " ").split()).strip()
    return normalized or None


def _coerce_order(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_sections_payload(payload: Any) -> list[dict] | None:
    if isinstance(payload, dict) and "error" in payload:
        return None
    if not isinstance(payload, list):
        return None

    sections = []
    for item in payload:
        if not isinstance(item, dict) or item.get("seccion") is None:
            continue
        title = item.get("titulo")
        sections.append({
            "seccion": str(item["seccion"]),
            "titulo": str(title) if title is not None else None,
            "orden": _coerce_order(item.get("orden")),
        })
    return sections


def parse_section_content_json(payload: Any, requested_section: str) -> dict | None:
    if isinstance(payload, dict) and "error" in payload:
        return None
    if not isinstance(payload, list):
        return None

    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("seccion") != requested_section:
            continue
        title = item.get("titulo")
        return {
            "seccion": item.get("seccion"),
            "titulo": str(title) if title is not None else None,
            "contenido_html": item.get("contenido"),
            "orden": _coerce_order(item.get("orden")),
        }
    return None


def parse_section_text(text: str | None) -> str | None:
    return normalize_segmented_text(text)
