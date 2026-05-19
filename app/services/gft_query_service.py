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


def _infer_atc_level(codigo: str) -> str | None:
    length = len(codigo)
    if length == 1:
        return "L1"
    if length == 3:
        return "L2"
    if length == 4:
        return "L3"
    if length == 5:
        return "L4"
    if length >= 7:
        return "L5"
    return None


def _expand_atc_code(codigo: str) -> list[tuple[str, str]]:
    code = codigo.strip().upper()
    if not code:
        return []

    expanded: list[tuple[str, str]] = []
    for length in (1, 3, 4, 5):
        if len(code) >= length:
            prefix = code[:length]
            level = _infer_atc_level(prefix)
            if level is not None:
                expanded.append((prefix, level))

    if len(code) >= 7:
        level = _infer_atc_level(code)
        if level is not None and all(prefix != code for prefix, _ in expanded):
            expanded.append((code, level))

    return expanded


def _merge_atc_index_entry(
    index: dict[str, dict],
    codigo: str,
    nivel: str,
    cn: str,
    nombre: str | None = None,
) -> None:
    entry = index.setdefault(codigo, {"codigo": codigo, "nombre": None, "nivel": nivel, "cns": set()})
    entry["cns"].add(cn)
    if nombre and entry["nombre"] is None:
        entry["nombre"] = nombre


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

    documentos: list[dict] = []
    for item in parsed:
        if not isinstance(item, Mapping):
            continue
        documentos.append(
            {
                "tipo": item.get("tipo"),
                "url": item.get("url"),
                "urlHtml": item.get("urlHtml"),
                "secc": item.get("secc"),
                "fecha": item.get("fecha"),
                "titulo": item.get("titulo"),
                "nombre": item.get("nombre"),
            }
        )
    return documentos


def _row_get(row, key: str, default=None):
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


def _build_financiacion_detalle(row) -> dict | None:
    detalle = {
        "situacion_financiacion": _row_get(row, "situacion_financiacion"),
        "condiciones_financiacion_restringidas": _row_get(row, "condiciones_financiacion_restringidas"),
        "condiciones_especiales_financiacion": _row_get(row, "condiciones_especiales_financiacion"),
        "estado_nomenclator": _row_get(row, "estado_nomenclator"),
        "aportacion_usuario": _row_get(row, "aportacion_usuario"),
        "subgrupo_atc": _row_get(row, "subgrupo_atc"),
    }
    if not any(value is not None for value in detalle.values()):
        return None
    return detalle


def _row_to_list_item(row, principios: list[dict]) -> dict:
    return {
        "cn": row["cn"],
        "nombre": row["nombre"],
        "presentacion": row["presentacion"],
        "forma_farmaceutica": row["forma_farmaceutica"],
        "forma_farmaceutica_simplificada": _row_get(row, "forma_farmaceutica_simplificada"),
        "vias_administracion": _parse_vias(row["vias_administracion_json"]),
        "atc": _parse_atc(row["atc_json"]),
        "principios_activos": principios,
        "nemonico": row["nemonico"],
        "restricciones_hospitalarias": row["restricciones_hospitalarias"],
        "ajuste_insuficiencia_renal": _row_get(row, "ajuste_insuficiencia_renal"),
        "ajuste_insuficiencia_hepatica": _row_get(row, "ajuste_insuficiencia_hepatica"),
        "precauciones_embarazo": _row_get(row, "precauciones_embarazo"),
        "precauciones_lactancia": _row_get(row, "precauciones_lactancia"),
        "situacion_financiacion": _row_get(row, "situacion_financiacion"),
        "url_ficha_tecnica": row["url_ficha_tecnica"],
        "url_prospecto": row["url_prospecto"],
        "fecha_ficha_tecnica": _row_get(row, "fecha_ficha_tecnica"),
        "fecha_prospecto": _row_get(row, "fecha_prospecto"),
        "indicaciones_ficha_tecnica": _row_get(row, "indicaciones_ficha_tecnica"),
    }


def _row_to_detail(row, principios: list[dict]) -> dict:
    item = _row_to_list_item(row, principios)
    item["observaciones_publicables"] = _row_get(row, "observaciones_publicables")
    item["documentos"] = _parse_documentos(row["documentos_json"])
    item["financiacion_detalle"] = _build_financiacion_detalle(row)
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


def _usable_principio_name(row) -> str | None:
    nombre = str(row.nombre_display or "").strip()
    if nombre:
        return nombre

    nombre = str(row.nombre_normalizado or "").strip()
    if nombre:
        return nombre

    return None


def list_principios_activos_index(db: Session) -> dict:
    rows = db.execute(text("SELECT cn FROM v_gft_publicada")).mappings().all()
    cns = [str(row["cn"] or "").strip() for row in rows if str(row["cn"] or "").strip()]
    if not cns:
        return {"items": []}

    rows = (
        db.query(
            MedicamentoPrincipioActivo.cn,
            PrincipioActivo.id,
            PrincipioActivo.slug,
            PrincipioActivo.nombre_display,
            PrincipioActivo.nombre_normalizado,
        )
        .join(PrincipioActivo, PrincipioActivo.id == MedicamentoPrincipioActivo.principio_activo_id)
        .filter(MedicamentoPrincipioActivo.cn.in_(cns))
        .all()
    )

    index: dict[str, dict] = {}
    for row in rows:
        slug = str(row.slug or "").strip()
        if not slug:
            continue

        nombre = _usable_principio_name(row)
        if nombre is None:
            continue

        key = str(row.id)
        entry = index.setdefault(
            key,
            {
                "id": row.id,
                "slug": slug,
                "nombre": nombre,
                "sort_name": str(row.nombre_normalizado or nombre).strip().casefold(),
                "cns": set(),
            },
        )
        entry["cns"].add(str(row.cn or "").strip())

    items = []
    for entry in sorted(index.values(), key=lambda item: (item["sort_name"], item["slug"])):
        nombre = entry["nombre"]
        items.append(
            {
                "id": entry["id"],
                "slug": entry["slug"],
                "nombre": nombre,
                "letra": nombre[0].upper(),
                "count": len(entry["cns"]),
            }
        )

    return {"items": items}


def list_atc_index(db: Session) -> dict:
    rows = db.execute(
        text(
            """
            SELECT cn, atc_json
            FROM v_gft_publicada
            """
        )
    ).mappings().all()

    index: dict[str, dict] = {}
    for row in rows:
        cn = str(row["cn"] or "").strip()
        if not cn:
            continue

        seen_for_cn: set[str] = set()
        for atc_item in _parse_atc(row["atc_json"]):
            raw_code = str(atc_item.get("codigo") or "").strip().upper()
            if not raw_code:
                continue

            exact_name = atc_item.get("nombre")
            exact_name = str(exact_name).strip() if exact_name is not None else None
            if exact_name == "":
                exact_name = None

            for codigo, nivel in _expand_atc_code(raw_code):
                if codigo in seen_for_cn:
                    continue
                seen_for_cn.add(codigo)
                nombre = exact_name if codigo == raw_code else None
                _merge_atc_index_entry(index, codigo, nivel, cn, nombre=nombre)

    items = []
    for codigo in sorted(index):
        entry = index[codigo]
        items.append(
            {
                "codigo": entry["codigo"],
                "nombre": entry["nombre"],
                "nivel": entry["nivel"],
                "count": len(entry["cns"]),
            }
        )

    return {"items": items}


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
