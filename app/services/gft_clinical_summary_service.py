from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

MISSING_AUTO = "No localizado automáticamente en las secciones analizadas."
GENERAL_SUMMARY_MAX_LEN = 1200

RENAL_PATTERNS = [
    r"\brenal\b", r"riñ[oó]n", r"insuficiencia renal", r"aclaramiento de creatinina", r"\bclcr\b", r"filtrado glomerular", r"hemodi[aá]lisis", r"di[aá]lisis",
]
HEPATIC_PATTERNS = [
    r"hep[aá]tica", r"hep[aá]tico", r"h[ií]gado", r"insuficiencia hep[aá]tica", r"hepatopat[ií]a", r"cirrosis", r"transaminasas",
]
EMBARAZO_PATTERNS = [r"embarazo", r"embarazada", r"gestaci[oó]n", r"gestante", r"feto", r"fetal"]
LACTANCIA_PATTERNS = [r"lactancia", r"leche materna", r"lactante"]


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, limit: int, warnings: list[str], code: str) -> str:
    if len(text) <= limit:
        return text
    warnings.append(f"{code}: truncado a {limit} caracteres")
    return text[:limit].rstrip() + "…"


def _split_sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"(?<=[\.!?;])\s+", text) if chunk.strip()]


def _extract_by_patterns(texts: list[str], patterns: list[str], fallback: str | None = None) -> tuple[str, bool]:
    regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
    matches: list[str] = []
    for text in texts:
        for sentence in _split_sentences(text):
            if any(r.search(sentence) for r in regexes):
                matches.append(sentence)
    if matches:
        return " ".join(dict.fromkeys(matches)), True
    return (fallback or "", False)


def compute_source_hash(source_sections: dict[str, str]) -> str:
    canonical = "\n".join(f"{k}:{_clean(source_sections.get(k, ''))}" for k in sorted(source_sections))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_general_summary(source_sections: dict[str, str], warnings: list[str]) -> tuple[str | None, list[str]]:
    s41 = _clean(source_sections.get("4.1"))
    s42 = _clean(source_sections.get("4.2"))
    s43 = _clean(source_sections.get("4.3"))
    s44 = _clean(source_sections.get("4.4"))
    s46 = _clean(source_sections.get("4.6"))
    used: list[str] = []
    parts: list[str] = []

    if s41:
        parts.append(f"Indicaciones: {s41[:250].strip()}")
        used.append("4.1")
    if s42:
        parts.append(f"Posología/administración: {s42[:250].strip()}")
        used.append("4.2")
    safety = " ".join(p for p in [s43[:220].strip() if s43 else "", s44[:300].strip() if s44 else ""] if p)
    if safety:
        parts.append(f"Seguridad: {safety}")
        if s43:
            used.append("4.3")
        if s44:
            used.append("4.4")
    if s46:
        parts.append(f"Embarazo/lactancia: {s46[:220].strip()}")
        used.append("4.6")

    if not parts:
        return None, []

    summary = " ".join(parts)
    if MISSING_AUTO.lower() in summary.lower():
        summary = summary.replace(MISSING_AUTO, "").strip()
    if len(summary) > GENERAL_SUMMARY_MAX_LEN:
        summary = summary[:GENERAL_SUMMARY_MAX_LEN].rstrip() + "…"
        warnings.append("resumen_general: truncado a 1200 caracteres")
    return summary, list(dict.fromkeys(used))


def build_clinical_summary(source_sections: dict[str, str], has_nregistro: bool, has_cima_ok: bool) -> dict:
    warnings: list[str] = []
    fuentes: dict[str, list[str]] = {}

    s41 = _clean(source_sections.get("4.1"))
    s42 = _clean(source_sections.get("4.2"))
    s43 = _clean(source_sections.get("4.3"))
    s44 = _clean(source_sections.get("4.4"))
    s46 = _clean(source_sections.get("4.6"))

    if not has_nregistro:
        warnings.append("sin nregistro")
    if not has_cima_ok:
        warnings.append("sin cache CIMA ok")
    for section in ("4.1", "4.2", "4.3", "4.4", "4.6"):
        if not _clean(source_sections.get(section)):
            warnings.append(f"sin sección {section}")

    resumen_general, used_general_sections = build_general_summary(source_sections, warnings)
    fuentes["resumen_general"] = used_general_sections
    indicaciones = _truncate(s41, 900, warnings, "resumen_indicaciones") if s41 else None
    fuentes["resumen_indicaciones"] = ["4.1"] if s41 else []
    posologia = _truncate(s42, 900, warnings, "resumen_posologia") if s42 else None
    fuentes["resumen_posologia"] = ["4.2"] if s42 else []
    renal, found_renal = _extract_by_patterns([s42, s44], RENAL_PATTERNS, fallback=MISSING_AUTO)
    if not found_renal:
        warnings.append("sin coincidencias renal")
    fuentes["resumen_ajuste_renal"] = [s for s in ["4.2", "4.4"] if _clean(source_sections.get(s))]
    hepatico, found_hep = _extract_by_patterns([s42, s44], HEPATIC_PATTERNS, fallback=MISSING_AUTO)
    if not found_hep:
        warnings.append("sin coincidencias hepática")
    fuentes["resumen_ajuste_hepatico"] = [s for s in ["4.2", "4.4"] if _clean(source_sections.get(s))]
    contra = _truncate(s43, 900, warnings, "resumen_contraindicaciones") if s43 else None
    fuentes["resumen_contraindicaciones"] = ["4.3"] if s43 else []
    adv = _truncate(s44, 1200, warnings, "resumen_advertencias") if s44 else None
    fuentes["resumen_advertencias"] = ["4.4"] if s44 else []
    emb, found_emb = _extract_by_patterns([s46], EMBARAZO_PATTERNS)
    if not emb and s46:
        emb = _truncate(s46, 900, warnings, "resumen_embarazo")
    fuentes["resumen_embarazo"] = ["4.6"] if s46 else []
    lact, found_lac = _extract_by_patterns([s46], LACTANCIA_PATTERNS)
    if not lact and s46:
        lact = _truncate(s46, 900, warnings, "resumen_lactancia")
    fuentes["resumen_lactancia"] = ["4.6"] if s46 else []

    available_sections = [s for s in ("4.1", "4.2", "4.3", "4.4", "4.6") if _clean(source_sections.get(s))]
    source_status = "ok" if len(available_sections) == 5 else "partial" if available_sections else "missing_source"
    return {"source_status": source_status, "generated_at": datetime.now(timezone.utc), "source_sections_json": available_sections, "source_hash": compute_source_hash(source_sections), "resumen_general": resumen_general, "resumen_indicaciones": indicaciones, "resumen_posologia": posologia, "resumen_ajuste_renal": renal, "resumen_ajuste_hepatico": hepatico, "resumen_contraindicaciones": contra, "resumen_advertencias": adv, "resumen_embarazo": emb or None, "resumen_lactancia": lact or None, "resumen_fuente_json": fuentes, "warnings_json": warnings, "error_message": None, "_flags": {"found_renal": found_renal, "found_hep": found_hep, "found_emb": found_emb, "found_lac": found_lac}}
