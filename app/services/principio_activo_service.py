import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.models.principio_activo_alias import PrincipioActivoAlias


_SPLIT_RE = re.compile(r"\s*[/+,]\s*")
_OBJECT_FIELDS = (
    "nombre",
    "principioActivo",
    "principio_activo",
    "descripcion",
    "sustancia",
)


def _clean_display_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_principio_activo_key(nombre_raw: str | None) -> str | None:
    cleaned = _clean_display_text(nombre_raw)
    if not cleaned:
        return None
    normalized = unicodedata.normalize("NFKD", cleaned)
    without_diacritics = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = without_diacritics.lower()
    collapsed = re.sub(r"\s+", " ", lowered).strip()
    return collapsed or None


def build_slug(nombre_normalizado: str | None) -> str | None:
    cleaned = _clean_display_text(nombre_normalizado)
    if not cleaned:
        return None
    slug = cleaned.replace(" ", "-")
    slug = re.sub(r"[^a-zA-Z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or None


def split_principio_activo_text(value: str | None) -> list[str]:
    cleaned = _clean_display_text(value)
    if not cleaned:
        return []

    parts = _SPLIT_RE.split(cleaned)
    result: list[str] = []
    seen: set[str] = set()

    for part in parts:
        display = _clean_display_text(part)
        if not display:
            continue
        key = normalize_principio_activo_key(display)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(display)

    return result


def _extract_candidate_from_object(item: dict[str, Any]) -> str | None:
    for field in _OBJECT_FIELDS:
        value = item.get(field)
        if isinstance(value, str) and _clean_display_text(value):
            return value
    return None


def _extract_source(data: Any) -> Any:
    if isinstance(data, dict) and "principios_activos_json" in data:
        return data.get("principios_activos_json")
    return data


def extract_principios_from_cima_data(data: Any) -> list[dict[str, Any]]:
    source = _extract_source(data)

    raw_items: list[str] = []

    if source is None:
        return []
    if isinstance(source, str):
        raw_items.extend(split_principio_activo_text(source))
    elif isinstance(source, list):
        for item in source:
            if isinstance(item, str):
                raw_items.extend(split_principio_activo_text(item))
            elif isinstance(item, dict):
                candidate = _extract_candidate_from_object(item)
                if candidate:
                    raw_items.extend(split_principio_activo_text(candidate))
    else:
        return []

    out: list[dict[str, Any]] = []
    seen_norm: set[str] = set()

    for raw in raw_items:
        nombre_display = _clean_display_text(raw)
        nombre_normalizado = normalize_principio_activo_key(nombre_display)
        if not nombre_display or not nombre_normalizado or nombre_normalizado in seen_norm:
            continue
        seen_norm.add(nombre_normalizado)
        out.append(
            {
                "nombre_raw": raw,
                "nombre_display": nombre_display,
                "nombre_normalizado": nombre_normalizado,
                "slug": build_slug(nombre_normalizado),
                "orden": len(out) + 1,
            }
        )

    return out



def upsert_principios_for_cn(db: Session, cn: str, principios: list[dict]) -> dict[str, Any]:
    if not cn or not str(cn).strip():
        raise ValueError("cn is required")

    cn = str(cn).strip()
    principios_input = len(principios or [])

    deleted_relations = db.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == cn).delete()

    if not principios:
        return {
            "cn": cn,
            "principios_input": principios_input,
            "principios_validos": 0,
            "principios_created": 0,
            "principios_reused": 0,
            "aliases_created": 0,
            "aliases_reused": 0,
            "relations_deleted": deleted_relations,
            "relations_created": 0,
        }

    deduped: list[dict[str, Any]] = []
    seen_norm: set[str] = set()

    for item in principios:
        if not isinstance(item, dict):
            continue
        nombre_normalizado = _clean_display_text(item.get("nombre_normalizado"))
        nombre_display = _clean_display_text(item.get("nombre_display"))
        if not nombre_normalizado or not nombre_display:
            continue
        if nombre_normalizado in seen_norm:
            continue
        seen_norm.add(nombre_normalizado)
        deduped.append(
            {
                "nombre_raw": _clean_display_text(item.get("nombre_raw")) or nombre_display,
                "nombre_display": nombre_display,
                "nombre_normalizado": nombre_normalizado,
                "slug": build_slug(item.get("slug") or nombre_normalizado) or nombre_normalizado,
            }
        )

    principios_created = 0
    principios_reused = 0
    aliases_created = 0
    aliases_reused = 0
    relations_created = 0

    for index, item in enumerate(deduped, start=1):
        pa = (
            db.query(PrincipioActivo)
            .filter(PrincipioActivo.nombre_normalizado == item["nombre_normalizado"])
            .one_or_none()
        )
        if pa is None:
            pa = PrincipioActivo(
                nombre_normalizado=item["nombre_normalizado"],
                nombre_display=item["nombre_display"],
                slug=item["slug"],
            )
            db.add(pa)
            db.flush()
            principios_created += 1
        else:
            principios_reused += 1

        alias = (
            db.query(PrincipioActivoAlias)
            .filter(
                PrincipioActivoAlias.principio_activo_id == pa.id,
                PrincipioActivoAlias.alias_normalizado == item["nombre_normalizado"],
                PrincipioActivoAlias.source == "cima",
            )
            .one_or_none()
        )
        if alias is None:
            db.add(
                PrincipioActivoAlias(
                    alias_raw=item["nombre_raw"],
                    alias_normalizado=item["nombre_normalizado"],
                    principio_activo_id=pa.id,
                    source="cima",
                    confidence="exact",
                    review_status="accepted",
                )
            )
            aliases_created += 1
        else:
            aliases_reused += 1

        db.add(
            MedicamentoPrincipioActivo(
                cn=cn,
                principio_activo_id=pa.id,
                orden=index,
            )
        )
        relations_created += 1

    db.flush()

    return {
        "cn": cn,
        "principios_input": principios_input,
        "principios_validos": len(deduped),
        "principios_created": principios_created,
        "principios_reused": principios_reused,
        "aliases_created": aliases_created,
        "aliases_reused": aliases_reused,
        "relations_deleted": deleted_relations,
        "relations_created": relations_created,
    }
