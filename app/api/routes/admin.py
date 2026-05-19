from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import String, and_, cast, exists, func, or_
from sqlalchemy.orm import Session

from app.core.admin_security import require_admin_api_key
from app.core.database import get_db
from app.core.enums import ESTADO_EDITORIAL_VALUES, ESTADO_GFT_VALUES
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.bifimed_cache import BifimedCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.gft_query_service import _parse_atc, _parse_json_value, _parse_vias
from app.services.gft_editorial_service import (
    GFTEditorialValidationError,
    update_gft_editorial_fields,
)
from app.services.gft_state_service import (
    GFTStateValidationError,
    update_gft_publication_state,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class GFTPublicationStateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado_gft: str | None = None
    estado_editorial: str | None = None
    comentario_revision: str | None = None
    revisado_por: str | None = None


class GFTPublicationStateUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cn: str
    estado_gft: str
    estado_editorial: str
    comentario_revision: str | None = None
    revisado_por: str | None = None
    fecha_revision: date | None = None
    updated_at: datetime | None = None


class GFTEditorialUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    observaciones_internas: str | None = None
    comentario_revision: str | None = None
    revisado_por: str | None = None


class GFTEditorialUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cn: str
    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    observaciones_internas: str | None = None
    comentario_revision: str | None = None
    revisado_por: str | None = None
    fecha_revision: date | None = None
    updated_at: datetime | None = None


class GFTEditorialAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cn: str
    estado_gft: str
    estado_editorial: str
    nemonico: str | None = None
    nombre_comercial: str | None = None
    principio_activo: str | None = None
    forma_farmaceutica: str | None = None
    via_administracion: str | None = None
    codigo_atc: str | None = None
    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    observaciones_internas: str | None = None
    comentario_revision: str | None = None
    revisado_por: str | None = None
    fecha_revision: date | None = None
    updated_at: datetime | None = None
    last_import_batch_id: UUID | None = None
    last_imported_at: datetime | None = None
    publication_warnings: list[str] = []


class GFTEditorialAdminListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cn: str
    estado_gft: str
    estado_editorial: str
    nemonico: str | None = None
    nombre_comercial: str | None = None
    principio_activo: str | None = None
    forma_farmaceutica: str | None = None
    via_administracion: str | None = None
    codigo_atc: str | None = None
    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    revisado_por: str | None = None
    fecha_revision: date | None = None
    updated_at: datetime | None = None
    last_import_batch_id: UUID | None = None
    last_imported_at: datetime | None = None
    publication_warnings: list[str] = []


class GFTEditorialAdminListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[GFTEditorialAdminListItem]


class GFTEditorialAdminSummaryResponse(BaseModel):
    total: int
    by_estado_gft: dict[str, int]
    by_estado_editorial: dict[str, int]
    by_combination: dict[str, int]
    publicados_en_gft: int
    incluidos_no_publicados: int
    pendientes_revision: int
    excluidos: int
    quality: dict[str, int]


def _first_non_empty(values) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def _join_non_empty(values) -> str | None:
    normalized_values = []
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized and normalized not in normalized_values:
            normalized_values.append(normalized)
    if not normalized_values:
        return None
    return ", ".join(normalized_values)


def _parse_principios_activos_json(principios_json) -> list[str]:
    parsed = _parse_json_value(principios_json)
    if not isinstance(parsed, list):
        return []

    names: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("nombre") or item.get("name") or "").strip()
        else:
            name = ""
        if name:
            names.append(name)
    return names


def _get_principio_activo_names_by_cn(
    db: Session, cns: list[str]
) -> dict[str, list[str]]:
    if not cns:
        return {}

    rows = (
        db.query(
            MedicamentoPrincipioActivo.cn,
            PrincipioActivo.nombre_display,
            PrincipioActivo.nombre_normalizado,
        )
        .join(
            PrincipioActivo,
            PrincipioActivo.id == MedicamentoPrincipioActivo.principio_activo_id,
        )
        .filter(MedicamentoPrincipioActivo.cn.in_(cns))
        .order_by(
            MedicamentoPrincipioActivo.cn,
            MedicamentoPrincipioActivo.orden,
            PrincipioActivo.nombre_display,
        )
        .all()
    )

    result: dict[str, list[str]] = {}
    for row in rows:
        name = _first_non_empty([row.nombre_display, row.nombre_normalizado])
        if name is not None:
            result.setdefault(row.cn, []).append(name)
    return result


def _via_administracion_from_cima(cima: CimaMedicamentoCache | None) -> str | None:
    if cima is None:
        return None
    return _join_non_empty(_parse_vias(cima.vias_administracion_json))


def _codigo_atc_from_cima(cima: CimaMedicamentoCache | None) -> str | None:
    if cima is None:
        return None
    return _join_non_empty(
        atc_item.get("codigo") for atc_item in _parse_atc(cima.atc_json)
    )


def _principio_activo_from_sources(
    cima: CimaMedicamentoCache | None,
    principio_names: list[str],
) -> str | None:
    from_relation = _join_non_empty(principio_names)
    if from_relation is not None:
        return from_relation
    if cima is None:
        return None
    return _join_non_empty(
        _parse_principios_activos_json(cima.principios_activos_json)
    )


def _build_admin_editorial_payload(
    db: Session,
    gft: GFTEstadoPresentacion,
    cima: CimaMedicamentoCache | None,
    principio_names: list[str],
) -> dict:
    publication_warnings = _get_publication_warnings(db, gft, cima)
    return {
        "cn": gft.cn,
        "estado_gft": gft.estado_gft,
        "estado_editorial": gft.estado_editorial,
        "nemonico": gft.nemonico,
        "nombre_comercial": cima.nombre if cima is not None else None,
        "principio_activo": _principio_activo_from_sources(cima, principio_names),
        "forma_farmaceutica": cima.forma_farmaceutica if cima is not None else None,
        "via_administracion": _via_administracion_from_cima(cima),
        "codigo_atc": _codigo_atc_from_cima(cima),
        "restricciones_hospitalarias": gft.restricciones_hospitalarias,
        "ajuste_insuficiencia_renal": gft.ajuste_insuficiencia_renal,
        "ajuste_insuficiencia_hepatica": gft.ajuste_insuficiencia_hepatica,
        "precauciones_embarazo": gft.precauciones_embarazo,
        "precauciones_lactancia": gft.precauciones_lactancia,
        "observaciones_internas": gft.observaciones_internas,
        "comentario_revision": gft.comentario_revision,
        "revisado_por": gft.revisado_por,
        "fecha_revision": gft.fecha_revision,
        "updated_at": gft.updated_at,
        "last_import_batch_id": gft.last_import_batch_id,
        "last_imported_at": gft.last_imported_at,
        "publication_warnings": publication_warnings,
    }




def _has_non_empty_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _get_publication_warnings(db: Session, gft: GFTEstadoPresentacion, cima: CimaMedicamentoCache | None) -> list[str]:
    if gft.estado_gft != "incluido":
        return []

    warnings: list[str] = []
    has_cima_name_or_presentacion = (
        cima is not None
        and cima.sync_status == "ok"
        and (_has_non_empty_text(cima.nombre) or _has_non_empty_text(cima.presentacion))
    )
    if not has_cima_name_or_presentacion:
        warnings.append("Sin datos CIMA OK")

    bifimed_ok = db.query(BifimedCache.cn).filter(
        BifimedCache.cn == gft.cn,
        BifimedCache.sync_status == "ok",
    ).first()
    if bifimed_ok is None:
        warnings.append("Sin datos BIFIMED OK")

    ficha_ok = db.query(CimaFichaTecnicaCache.cn).filter(
        CimaFichaTecnicaCache.cn == gft.cn,
        CimaFichaTecnicaCache.seccion == "4.1",
        CimaFichaTecnicaCache.sync_status == "ok",
        func.nullif(func.trim(CimaFichaTecnicaCache.contenido_texto), None).is_not(None),
    ).first()
    if ficha_ok is None:
        warnings.append("Sin ficha técnica 4.1 / indicaciones")

    if not _has_non_empty_text(gft.restricciones_hospitalarias):
        warnings.append("Sin restricciones hospitalarias")
    if not _has_non_empty_text(gft.ajuste_insuficiencia_renal):
        warnings.append("Sin ajuste renal")
    if not _has_non_empty_text(gft.ajuste_insuficiencia_hepatica):
        warnings.append("Sin ajuste hepático")
    if not _has_non_empty_text(gft.precauciones_embarazo):
        warnings.append("Sin precauciones en embarazo")
    if not _has_non_empty_text(gft.precauciones_lactancia):
        warnings.append("Sin precauciones en lactancia")

    return warnings

def _principio_activo_matches(pattern: str):
    return exists().where(
        MedicamentoPrincipioActivo.cn == GFTEstadoPresentacion.cn,
        MedicamentoPrincipioActivo.principio_activo_id == PrincipioActivo.id,
        or_(
            PrincipioActivo.nombre_display.ilike(pattern),
            PrincipioActivo.nombre_normalizado.ilike(pattern),
        ),
    )


@router.get("/health")
def admin_health(_: None = Depends(require_admin_api_key)):
    return {"status": "ok"}


@router.get(
    "/gft/medicamentos/editorial/summary",
    response_model=GFTEditorialAdminSummaryResponse,
)
def get_gft_medicamentos_editorial_summary(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    by_estado_gft = {estado: 0 for estado in ESTADO_GFT_VALUES}
    for estado_gft, count in (
        db.query(GFTEstadoPresentacion.estado_gft, func.count())
        .group_by(GFTEstadoPresentacion.estado_gft)
        .all()
    ):
        by_estado_gft[estado_gft] = count

    by_estado_editorial = {estado: 0 for estado in ESTADO_EDITORIAL_VALUES}
    for estado_editorial, count in (
        db.query(GFTEstadoPresentacion.estado_editorial, func.count())
        .group_by(GFTEstadoPresentacion.estado_editorial)
        .all()
    ):
        by_estado_editorial[estado_editorial] = count

    combination_rows = (
        db.query(
            GFTEstadoPresentacion.estado_gft,
            GFTEstadoPresentacion.estado_editorial,
            func.count(),
        )
        .group_by(
            GFTEstadoPresentacion.estado_gft,
            GFTEstadoPresentacion.estado_editorial,
        )
        .all()
    )
    by_combination = {
        f"{estado_gft}|{estado_editorial}": count
        for estado_gft, estado_editorial, count in combination_rows
    }

    total = sum(by_estado_gft.values())
    included_filter = GFTEstadoPresentacion.estado_gft == "incluido"
    non_empty = lambda field: func.nullif(func.trim(field), None)  # noqa: E731
    has_cima_name_or_presentacion = or_(
        non_empty(CimaMedicamentoCache.nombre).is_not(None),
        non_empty(CimaMedicamentoCache.presentacion).is_not(None),
    )

    quality = {
        "incluidos_no_publicados": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(
            GFTEstadoPresentacion.estado_gft == "incluido",
            GFTEstadoPresentacion.estado_editorial != "publicado",
        )
        .scalar(),
        "pendientes_revision": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(GFTEstadoPresentacion.estado_gft == "pendiente_revision")
        .scalar(),
        "sin_cima": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .outerjoin(CimaMedicamentoCache, CimaMedicamentoCache.cn == GFTEstadoPresentacion.cn)
        .filter(
            included_filter,
            or_(
                CimaMedicamentoCache.cn.is_(None),
                CimaMedicamentoCache.sync_status != "ok",
                ~has_cima_name_or_presentacion,
            ),
        )
        .scalar(),
        "sin_bifimed": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .outerjoin(BifimedCache, BifimedCache.cn == GFTEstadoPresentacion.cn)
        .filter(
            included_filter,
            or_(BifimedCache.cn.is_(None), BifimedCache.sync_status != "ok"),
        )
        .scalar(),
        "sin_ficha_tecnica_41": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(
            included_filter,
            ~exists().where(
                CimaFichaTecnicaCache.cn == GFTEstadoPresentacion.cn,
                CimaFichaTecnicaCache.seccion == "4.1",
                CimaFichaTecnicaCache.sync_status == "ok",
                non_empty(CimaFichaTecnicaCache.contenido_texto).is_not(None),
            ),
        )
        .scalar(),
        "sin_restricciones_hospitalarias": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(included_filter, non_empty(GFTEstadoPresentacion.restricciones_hospitalarias).is_(None))
        .scalar(),
        "sin_ajuste_renal": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(included_filter, non_empty(GFTEstadoPresentacion.ajuste_insuficiencia_renal).is_(None))
        .scalar(),
        "sin_ajuste_hepatico": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(included_filter, non_empty(GFTEstadoPresentacion.ajuste_insuficiencia_hepatica).is_(None))
        .scalar(),
        "sin_embarazo": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(included_filter, non_empty(GFTEstadoPresentacion.precauciones_embarazo).is_(None))
        .scalar(),
        "sin_lactancia": db.query(func.count())
        .select_from(GFTEstadoPresentacion)
        .filter(included_filter, non_empty(GFTEstadoPresentacion.precauciones_lactancia).is_(None))
        .scalar(),
    }

    return GFTEditorialAdminSummaryResponse(
        total=total,
        by_estado_gft=by_estado_gft,
        by_estado_editorial=by_estado_editorial,
        by_combination=by_combination,
        publicados_en_gft=by_combination.get("incluido|publicado", 0),
        incluidos_no_publicados=by_estado_gft.get("incluido", 0)
        - by_combination.get("incluido|publicado", 0),
        pendientes_revision=by_estado_gft.get("pendiente_revision", 0),
        excluidos=by_estado_gft.get("excluido", 0),
        quality=quality,
    )



QUALITY_FILTERS = {
    "incluidos_no_publicados",
    "pendientes_revision",
    "sin_cima",
    "sin_bifimed",
    "sin_ficha_tecnica_41",
    "sin_restricciones_hospitalarias",
    "sin_ajuste_renal",
    "sin_ajuste_hepatico",
    "sin_embarazo",
    "sin_lactancia",
}


def _apply_quality_filter(query, quality_filter: str):
    included_filter = GFTEstadoPresentacion.estado_gft == "incluido"
    non_empty = lambda field: func.nullif(func.trim(field), None)  # noqa: E731
    has_cima_name_or_presentacion = or_(
        non_empty(CimaMedicamentoCache.nombre).is_not(None),
        non_empty(CimaMedicamentoCache.presentacion).is_not(None),
    )

    if quality_filter == "incluidos_no_publicados":
        return query.filter(
            GFTEstadoPresentacion.estado_gft == "incluido",
            GFTEstadoPresentacion.estado_editorial != "publicado",
        )
    if quality_filter == "pendientes_revision":
        return query.filter(GFTEstadoPresentacion.estado_gft == "pendiente_revision")
    if quality_filter == "sin_cima":
        return query.filter(
            included_filter,
            or_(
                CimaMedicamentoCache.cn.is_(None),
                CimaMedicamentoCache.sync_status != "ok",
                ~has_cima_name_or_presentacion,
            ),
        )
    if quality_filter == "sin_bifimed":
        query = query.outerjoin(BifimedCache, BifimedCache.cn == GFTEstadoPresentacion.cn)
        return query.filter(
            included_filter,
            or_(BifimedCache.cn.is_(None), BifimedCache.sync_status != "ok"),
        )
    if quality_filter == "sin_ficha_tecnica_41":
        return query.filter(
            included_filter,
            ~exists().where(
                CimaFichaTecnicaCache.cn == GFTEstadoPresentacion.cn,
                CimaFichaTecnicaCache.seccion == "4.1",
                CimaFichaTecnicaCache.sync_status == "ok",
                non_empty(CimaFichaTecnicaCache.contenido_texto).is_not(None),
            ),
        )
    if quality_filter == "sin_restricciones_hospitalarias":
        return query.filter(included_filter, non_empty(GFTEstadoPresentacion.restricciones_hospitalarias).is_(None))
    if quality_filter == "sin_ajuste_renal":
        return query.filter(included_filter, non_empty(GFTEstadoPresentacion.ajuste_insuficiencia_renal).is_(None))
    if quality_filter == "sin_ajuste_hepatico":
        return query.filter(included_filter, non_empty(GFTEstadoPresentacion.ajuste_insuficiencia_hepatica).is_(None))
    if quality_filter == "sin_embarazo":
        return query.filter(included_filter, non_empty(GFTEstadoPresentacion.precauciones_embarazo).is_(None))
    if quality_filter == "sin_lactancia":
        return query.filter(included_filter, non_empty(GFTEstadoPresentacion.precauciones_lactancia).is_(None))
    raise HTTPException(status_code=400, detail="quality_filter inválido")
@router.get("/gft/medicamentos/editorial", response_model=GFTEditorialAdminListResponse)
def list_gft_medicamentos_editorial(
    estado_gft: str | None = None,
    estado_editorial: str | None = None,
    quality_filter: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset debe ser mayor o igual a 0")

    query = db.query(GFTEstadoPresentacion, CimaMedicamentoCache).outerjoin(
        CimaMedicamentoCache, CimaMedicamentoCache.cn == GFTEstadoPresentacion.cn
    )

    if estado_gft is not None:
        normalized_estado_gft = estado_gft.strip()
        if normalized_estado_gft:
            query = query.filter(
                GFTEstadoPresentacion.estado_gft == normalized_estado_gft
            )

    if estado_editorial is not None:
        normalized_estado_editorial = estado_editorial.strip()
        if normalized_estado_editorial:
            query = query.filter(
                GFTEstadoPresentacion.estado_editorial == normalized_estado_editorial
            )

    if quality_filter is not None and quality_filter.strip():
        normalized_quality_filter = quality_filter.strip()
        if normalized_quality_filter not in QUALITY_FILTERS:
            raise HTTPException(status_code=400, detail="quality_filter inválido")
        query = _apply_quality_filter(query, normalized_quality_filter)

    if q is not None:
        normalized_q = q.strip()
        if normalized_q:
            pattern = f"%{normalized_q}%"
            query = query.filter(
                or_(
                    GFTEstadoPresentacion.cn.ilike(pattern),
                    GFTEstadoPresentacion.nemonico.ilike(pattern),
                    GFTEstadoPresentacion.restricciones_hospitalarias.ilike(pattern),
                    GFTEstadoPresentacion.ajuste_insuficiencia_renal.ilike(pattern),
                    GFTEstadoPresentacion.ajuste_insuficiencia_hepatica.ilike(pattern),
                    GFTEstadoPresentacion.precauciones_embarazo.ilike(pattern),
                    GFTEstadoPresentacion.precauciones_lactancia.ilike(pattern),
                    CimaMedicamentoCache.nombre.ilike(pattern),
                    CimaMedicamentoCache.forma_farmaceutica.ilike(pattern),
                    CimaMedicamentoCache.presentacion.ilike(pattern),
                    cast(CimaMedicamentoCache.principios_activos_json, String).ilike(
                        pattern
                    ),
                    _principio_activo_matches(pattern),
                )
            )

    total = query.count()
    rows = (
        query.order_by(GFTEstadoPresentacion.cn.asc()).offset(offset).limit(limit).all()
    )

    cns = [gft.cn for gft, _ in rows]
    principios_by_cn = _get_principio_activo_names_by_cn(db, cns)
    items = [
        _build_admin_editorial_payload(db, gft, cima, principios_by_cn.get(gft.cn, []))
        for gft, cima in rows
    ]

    return GFTEditorialAdminListResponse(
        total=total, limit=limit, offset=offset, items=items
    )


@router.get(
    "/gft/medicamentos/{cn}/editorial", response_model=GFTEditorialAdminResponse
)
def get_gft_medicamento_editorial(
    cn: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    normalized_cn = cn.strip()
    if not normalized_cn:
        raise HTTPException(status_code=400, detail="CN obligatorio")

    row = (
        db.query(GFTEstadoPresentacion, CimaMedicamentoCache)
        .outerjoin(
            CimaMedicamentoCache, CimaMedicamentoCache.cn == GFTEstadoPresentacion.cn
        )
        .filter(GFTEstadoPresentacion.cn == normalized_cn)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Medicamento GFT no encontrado")

    gft, cima = row
    principios_by_cn = _get_principio_activo_names_by_cn(db, [normalized_cn])
    return _build_admin_editorial_payload(
        db, gft, cima, principios_by_cn.get(normalized_cn, [])
    )


@router.patch(
    "/gft/medicamentos/{cn}/estado",
    response_model=GFTPublicationStateUpdateResponse,
)
def update_gft_medicamento_publication_state(
    cn: str,
    body: GFTPublicationStateUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    payload = body.model_dump(exclude_unset=True)

    try:
        result = update_gft_publication_state(
            db=db,
            cn=cn,
            estado_gft=payload.get("estado_gft"),
            estado_editorial=payload.get("estado_editorial"),
            comentario_revision=payload.get("comentario_revision"),
            revisado_por=payload.get("revisado_por"),
        )
    except GFTStateValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Medicamento GFT no encontrado")

    return result


@router.patch(
    "/gft/medicamentos/{cn}/editorial", response_model=GFTEditorialUpdateResponse
)
def update_gft_medicamento_editorial(
    cn: str,
    body: GFTEditorialUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    payload = body.model_dump(exclude_unset=True)
    revisado_por = payload.pop("revisado_por", None)

    try:
        result = update_gft_editorial_fields(
            db,
            cn=cn,
            fields=payload,
            revisado_por=revisado_por,
        )
    except GFTEditorialValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Medicamento GFT no encontrado")

    return result
