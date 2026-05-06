import json
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.normalization_service import normalize_cn


def _parse_json_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def _parse_vias(vias_json) -> list[str]:
    parsed = _parse_json_value(vias_json)
    if not isinstance(parsed, list):
        return []

    out: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, Mapping):
            name = str(item.get("nombre") or item.get("name") or "").strip()
        else:
            name = ""
        if name:
            out.append(name)
    return out


def _parse_atc(atc_json) -> list[dict]:
    parsed = _parse_json_value(atc_json)
    if not isinstance(parsed, list):
        return []

    out: list[dict] = []
    for item in parsed:
        if isinstance(item, str):
            code = item.strip()
            if code:
                out.append({"codigo": code, "nombre": None, "nivel": None})
            continue

        if not isinstance(item, Mapping):
            continue

        code = str(item.get("codigo") or item.get("code") or "").strip()
        if not code:
            continue
        name = item.get("nombre") or item.get("name")
        level = item.get("nivel") or item.get("level")
        out.append(
            {
                "codigo": code,
                "nombre": str(name).strip() if name is not None else None,
                "nivel": str(level).strip() if level is not None else None,
            }
        )
    return out


def _get_principios_for_cns(db: Session, cns: list[str]) -> dict[str, list[dict]]:
    if not cns:
        return {}

    rows = (
        db.query(
            MedicamentoPrincipioActivo.cn,
            PrincipioActivo.id,
            PrincipioActivo.slug,
            PrincipioActivo.nombre_display,
            MedicamentoPrincipioActivo.orden,
        )
        .join(PrincipioActivo, PrincipioActivo.id == MedicamentoPrincipioActivo.principio_activo_id)
        .filter(MedicamentoPrincipioActivo.cn.in_(cns))
        .order_by(MedicamentoPrincipioActivo.cn, MedicamentoPrincipioActivo.orden, PrincipioActivo.nombre_display)
        .all()
    )

    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row.cn, []).append(
            {
                "id": row.id,
                "slug": row.slug,
                "nombre": row.nombre_display,
            }
        )
    return result


def _parse_documentos(documentos_json) -> list[dict]:
    parsed = _parse_json_value(documentos_json)
    if not isinstance(parsed, list):
        return []
    return [dict(item) for item in parsed if isinstance(item, Mapping)]


def _row_to_list_item(row, principios: list[dict]) -> dict:
    return {
        "cn": row["cn"],
        "nombre": row["nombre"],
        "presentacion": row["presentacion"],
        "forma_farmaceutica": row["forma_farmaceutica"],
        "vias_administracion": _parse_vias(row["vias_administracion_json"]),
        "atc": _parse_atc(row["atc_json"]),
        "principios_activos": principios,
        "nemonico": row["nemonico"],
        "restricciones_hospitalarias": row["restricciones_hospitalarias"],
        "situacion_financiacion": row["situacion_financiacion"],
        "url_ficha_tecnica": row["url_ficha_tecnica"],
        "url_prospecto": row["url_prospecto"],
    }


def _row_to_detail(row, principios: list[dict]) -> dict:
    item = _row_to_list_item(row, principios)
    item["observaciones_internas_publicables"] = row["observaciones_internas"]
    item["documentos"] = _parse_documentos(row["documentos_json"])
    return item


def list_medicamentos(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
    letra: str | None = None,
    principio_activo: str | None = None,
    atc: str | None = None,
) -> dict:
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0

    rows = db.execute(
        text(
            """
            SELECT *
            FROM v_gft_publicada
            """
        )
    ).mappings().all()

    cns = [row["cn"] for row in rows]
    principios_by_cn = _get_principios_for_cns(db, cns)

    enriched = []
    for row in rows:
        principios = principios_by_cn.get(row["cn"], [])
        enriched.append((principios[0]["nombre"].lower() if principios else "", _row_to_list_item(row, principios)))

    enriched.sort(key=lambda x: (x[0], (x[1].get("nombre") or "").lower(), x[1]["cn"]))
    ordered_items = [item for _, item in enriched]
    q_norm = (q or "").strip().lower()
    letra_norm = (letra or "").strip().lower()[:1]
    principio_raw = (principio_activo or "").strip()
    principio_slug_norm = principio_raw.lower()
    atc_norm = (atc or "").strip().upper()

    filtered_items = ordered_items
    if q_norm:
        def _matches_q(item: dict) -> bool:
            principles = item.get("principios_activos", [])
            fields = [
                item.get("cn"),
                item.get("nombre"),
                item.get("presentacion"),
                item.get("forma_farmaceutica"),
                item.get("nemonico"),
                item.get("restricciones_hospitalarias"),
                *[p.get("nombre") for p in principles if isinstance(p, Mapping)],
            ]
            haystack = " ".join(str(value).lower() for value in fields if value)
            return q_norm in haystack

        filtered_items = [item for item in filtered_items if _matches_q(item)]

    if letra_norm:
        filtered_items = [
            item
            for item in filtered_items
            if item.get("principios_activos")
            and str(item["principios_activos"][0].get("nombre") or "").strip().lower().startswith(letra_norm)
        ]

    if principio_raw:
        filtered_items = [
            item
            for item in filtered_items
            if any(
                str(principio.get("id")) == principio_raw
                or str(principio.get("slug") or "").lower() == principio_slug_norm
                for principio in item.get("principios_activos", [])
                if isinstance(principio, Mapping)
            )
        ]

    if atc_norm:
        filtered_items = [
            item
            for item in filtered_items
            if any(
                str(atc_item.get("codigo") or "").strip().upper().startswith(atc_norm)
                for atc_item in item.get("atc", [])
                if isinstance(atc_item, Mapping)
            )
        ]

    total = len(filtered_items)
    items = filtered_items[offset : offset + limit]

    return {"total": int(total), "limit": limit, "offset": offset, "items": items}


def get_medicamento_by_cn(db: Session, cn: str) -> dict | None:
    cn_norm = normalize_cn(cn)

    row = db.execute(
        text("SELECT * FROM v_gft_publicada WHERE cn = :cn LIMIT 1"),
        {"cn": cn_norm},
    ).mappings().first()

    if row is None:
        return None

    principios = _get_principios_for_cns(db, [cn_norm]).get(cn_norm, [])
    return _row_to_detail(row, principios)
