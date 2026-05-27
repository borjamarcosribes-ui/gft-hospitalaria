from __future__ import annotations

from sqlalchemy import and_, or_, func

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache


def has_nonempty_section_content(text_value: str | None, html_value: str | None) -> bool:
    return bool((text_value or "").strip() or (html_value or "").strip())


def is_auditable_section_row(*, processed_cn: str, processed_nregistro: str | None, requested_section: str, row_cn: str | None, row_nregistro: str | None, row_section: str | None, sync_status: str | None, contenido_texto: str | None, contenido_html: str | None) -> bool:
    normalized_processed_nregistro = (processed_nregistro or "").strip()
    normalized_row_nregistro = (row_nregistro or "").strip()
    return (
        ((row_cn or "") == processed_cn or (normalized_processed_nregistro and normalized_row_nregistro == normalized_processed_nregistro))
        and (row_section or "") == requested_section
        and (sync_status or "") == "ok"
        and has_nonempty_section_content(contenido_texto, contenido_html)
    )


def build_auditable_section_filters(cn: str, nregistro: str | None, section: str):
    normalized_nregistro = (nregistro or "").strip()
    cn_or_nregistro = [CimaFichaTecnicaCache.cn == cn]
    if normalized_nregistro:
        cn_or_nregistro.append(CimaFichaTecnicaCache.nregistro == normalized_nregistro)
    return (
        or_(*cn_or_nregistro),
        CimaFichaTecnicaCache.seccion == section,
        CimaFichaTecnicaCache.sync_status == "ok",
        or_(
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_texto, "")) != "",
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_html, "")) != "",
        ),
    )


def build_auditable_section_scope_filters(cns: list[str], nregistros: list[str], sections: list[str]):
    scope_filters = [CimaFichaTecnicaCache.cn.in_(cns)]
    normalized_nregistros = [str(n).strip() for n in nregistros if str(n).strip()]
    if normalized_nregistros:
        scope_filters.append(CimaFichaTecnicaCache.nregistro.in_(normalized_nregistros))
    return and_(
        or_(*scope_filters),
        CimaFichaTecnicaCache.seccion.in_(sections),
        CimaFichaTecnicaCache.sync_status == "ok",
        or_(
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_texto, "")) != "",
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_html, "")) != "",
        ),
    )
