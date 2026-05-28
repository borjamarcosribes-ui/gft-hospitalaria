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


def _line_heading(line: str) -> str | None:
    cleaned = _strip_marker(line)
    if not cleaned.endswith(":"):
        return None
    heading = cleaned[:-1].strip()
    if 2 <= len(heading) <= 90:
        return heading
    return None


def _extract_multiline_heading_blocks(lines: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    idx = 0
    while idx < len(lines):
        heading = _line_heading(lines[idx])
        if not heading:
            return []
        idx += 1
        body_lines: list[str] = []
        while idx < len(lines) and _line_heading(lines[idx]) is None:
            body = _strip_marker(lines[idx])
            if body:
                body_lines.append(body)
            idx += 1
        body_text = "\n".join(body_lines).strip()
        if not body_text:
            return []
        items.append({"titulo": heading, "texto": body_text, "confidence": "alta"})
    return items if len(items) >= 2 else []


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


def _extract_by_commercial_name(clean_text: str, commercial_name: str | None) -> list[dict[str, str]]:
    if not commercial_name:
        return []

    name = re.sub(r"\s+", " ", commercial_name).strip()
    if len(name) < 3:
        return []

    pattern = re.compile(re.escape(name), re.IGNORECASE)
    matches = list(pattern.finditer(clean_text))
    if len(matches) < 2:
        return []

    anchors: list[tuple[int, str]] = []

    for match in matches:
        prefix = clean_text[:match.start()]
        boundary = max(prefix.rfind("."), prefix.rfind(";"), prefix.rfind("\n"))
        title_start = 0 if boundary < 0 else boundary + 1

        title = clean_text[title_start:match.start()]
        title = _strip_marker(title)
        title = re.sub(r"\s+", " ", title).strip(" .;:-\n\t")

        if not title:
            continue
        if len(title) < 3 or len(title) > 120:
            continue
        if re.search(re.escape(name), title, flags=re.IGNORECASE):
            continue
        if re.search(r"\b(est[aá]\s+indicado|se\s+utiliza|indicado\s+para)\b", title, flags=re.IGNORECASE):
            continue

        anchors.append((title_start, title))

    deduped: list[tuple[int, str]] = []
    seen_starts: set[int] = set()
    for start, title in anchors:
        if start in seen_starts:
            continue
        seen_starts.add(start)
        deduped.append((start, title))

    if len(deduped) < 2:
        return []

    items: list[dict[str, str]] = []
    for idx, (start, title) in enumerate(deduped):
        end = deduped[idx + 1][0] if idx + 1 < len(deduped) else len(clean_text)
        block = clean_text[start:end].strip(" ;\n\t")
        if len(block) < 20:
            continue
        items.append({"titulo": title, "texto": block, "confidence": "media"})

    return items if len(items) >= 2 else []


def normalize_cima_indicaciones(raw_text: str | None, commercial_name: str | None = None) -> list[dict[str, str]]:
    clean_text = _clean_text(raw_text)
    if not clean_text:
        return []

    lines = _split_candidate_lines(clean_text)
    items: list[dict[str, str]] = []

    multiline_heading_items = _extract_multiline_heading_blocks(lines)
    if multiline_heading_items:
        return multiline_heading_items

    colon_items = [_line_title_and_text(line) for line in lines]
    colon_items = [item for item in colon_items if item]
    if len(colon_items) >= 2:
        for title, text in colon_items:
            items.append({"titulo": title, "texto": text, "confidence": "alta"})
        return items

    bullet_lines = [line for line in lines if re.match(r"^(?:[-•*·]\s+|\(?\d+[\).]\s+|[a-zA-Z]\)\s+)", line)]
    if len(bullet_lines) >= 2:
        for line in bullet_lines:
            text = _strip_marker(line)
            if text:
                items.append({"titulo": text[:110], "texto": text, "confidence": "media"})
        return items

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

    name_based_items = _extract_by_commercial_name(clean_text, commercial_name)
    if name_based_items:
        return name_based_items

    return [{"titulo": "Indicaciones terapéuticas", "texto": clean_text, "confidence": "baja"}]
