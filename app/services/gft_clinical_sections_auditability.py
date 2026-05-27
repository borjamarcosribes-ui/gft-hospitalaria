from __future__ import annotations

from sqlalchemy import and_, or_, func

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache


def has_nonempty_section_content(text_value: str | None, html_value: str | None) -> bool:
    return bool((text_value or "").strip() or (html_value or "").strip())


def is_auditable_section_row(*, processed_cn: str, requested_section: str, row_cn: str | None, row_section: str | None, sync_status: str | None, contenido_texto: str | None, contenido_html: str | None) -> bool:
    return (
        (row_cn or "") == processed_cn
        and (row_section or "") == requested_section
        and (sync_status or "") == "ok"
        and has_nonempty_section_content(contenido_texto, contenido_html)
    )


def build_auditable_section_filters(cn: str, section: str):
    return (
        CimaFichaTecnicaCache.cn == cn,
        CimaFichaTecnicaCache.seccion == section,
        CimaFichaTecnicaCache.sync_status == "ok",
        or_(
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_texto, "")) != "",
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_html, "")) != "",
        ),
    )


def build_auditable_section_scope_filters(cns: list[str], sections: list[str]):
    return and_(
        CimaFichaTecnicaCache.cn.in_(cns),
        CimaFichaTecnicaCache.seccion.in_(sections),
        CimaFichaTecnicaCache.sync_status == "ok",
        or_(
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_texto, "")) != "",
            func.trim(func.coalesce(CimaFichaTecnicaCache.contenido_html, "")) != "",
        ),
    )
