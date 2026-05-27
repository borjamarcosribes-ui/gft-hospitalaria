from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_clinical_sections_auditability import build_auditable_section_scope_filters

TARGET_SECTIONS = ["4.1", "4.2", "4.3", "4.4", "4.6"]
VALID_SUMMARY_SOURCE_STATUSES = {"ok", "partial"}


def _view_columns(db: Session) -> set[str]:
    sample = db.execute(text("SELECT * FROM v_gft_publicada LIMIT 0"))
    return set(sample.keys())


def _first_present(row: dict, names: list[str]):
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _build_base_query(columns: set[str]) -> str:
    select_parts = ["cn"]
    optional = [
        "nombre",
        "nombre_comercial",
        "nombre_comercial_importado",
        "principio_activo",
        "principio_activo_importado",
        "codigo_atc",
        "atc_codigo",
        "codigo_atc_principal",
        "codigo_atc_importado",
        "atc_principal_codigo",
        "atc_json",
        "nemonico",
        "forma_farmaceutica",
        "vias_administracion_json",
        "restricciones_hospitalarias",
        "indicaciones_autorizadas_bifimed",
        "url_ficha_tecnica",
        "url_prospecto",
    ]
    select_parts.extend([col for col in optional if col in columns])

    atc_col = next((c for c in ["codigo_atc", "atc_codigo", "codigo_atc_principal", "codigo_atc_importado", "atc_principal_codigo"] if c in columns), None)
    principio_col = next((c for c in ["principio_activo", "principio_activo_importado"] if c in columns), None)
    nombre_col = next((c for c in ["nombre", "nombre_comercial", "nombre_comercial_importado"] if c in columns), None)
    order_sql = ", ".join([p for p in [atc_col, principio_col, nombre_col, "cn"] if p])
    return f"SELECT {', '.join(select_parts)} FROM v_gft_publicada ORDER BY {order_sql}"


def build_gft_export_dataset(db: Session) -> list[dict]:
    columns = _view_columns(db)
    rows = db.execute(text(_build_base_query(columns))).mappings().all()
    cns = [str(r.get("cn") or "").strip() for r in rows if str(r.get("cn") or "").strip()]

    bifis = {r.cn: r for r in db.query(BifimedCache).filter(BifimedCache.cn.in_(cns)).all()} if cns else {}
    cimas = {r.cn: r for r in db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns)).all()} if cns else {}
    sums = {r.cn: r for r in db.query(GftClinicalSummaryCache).filter(GftClinicalSummaryCache.cn.in_(cns)).all()} if cns else {}

    nregistros = [(r.nregistro or "").strip() for r in cimas.values() if (r.nregistro or "").strip()]
    sec_rows = db.query(CimaFichaTecnicaCache.cn, CimaFichaTecnicaCache.nregistro, CimaFichaTecnicaCache.seccion).filter(
        build_auditable_section_scope_filters(cns, nregistros, TARGET_SECTIONS)
    ).all() if cns else []

    nregistro_to_cns: dict[str, set[str]] = {}
    for cn, med in cimas.items():
        key = (med.nregistro or "").strip()
        if key:
            nregistro_to_cns.setdefault(key, set()).add(cn)

    cov = {s: set() for s in TARGET_SECTIONS}
    for row in sec_rows:
        row_cn = str(row.cn or "")
        if row_cn in cimas:
            cov[row.seccion].add(row_cn)
        for mapped_cn in nregistro_to_cns.get((row.nregistro or "").strip(), set()):
            cov[row.seccion].add(mapped_cn)

    out = []
    for row in rows:
        cn = str(row.get("cn") or "").strip()
        b = bifis.get(cn)
        c = cimas.get(cn)
        s = sums.get(cn)
        bifimed_ok = bool(b and b.sync_status == "ok")
        cima_ok = bool(c and c.sync_status == "ok")
        sections_complete = bool(all(cn in cov[sec] for sec in TARGET_SECTIONS))
        summary_ok = bool(s and (s.source_status or "") in VALID_SUMMARY_SOURCE_STATUSES)
        fully_ready = bool(bifimed_ok and cima_ok and sections_complete and summary_ok)

        out.append(
            {
                "cn": cn,
                "nombre_comercial": _first_present(row, ["nombre", "nombre_comercial", "nombre_comercial_importado"]),
                "principio_activo": _first_present(row, ["principio_activo", "principio_activo_importado"]),
                "codigo_atc": _first_present(row, ["codigo_atc", "atc_codigo", "codigo_atc_principal", "codigo_atc_importado", "atc_principal_codigo"]),
                "nemonico": row.get("nemonico"),
                "forma_farmaceutica": row.get("forma_farmaceutica"),
                "via_administracion": row.get("vias_administracion_json"),
                "atc_descripciones": row.get("atc_json"),
                "condiciones_especiales": row.get("restricciones_hospitalarias"),
                "indicaciones_autorizadas_bifimed": row.get("indicaciones_autorizadas_bifimed"),
                "url_ficha_tecnica": row.get("url_ficha_tecnica"),
                "url_prospecto": row.get("url_prospecto"),
                "bifimed_status": b.sync_status if b else None,
                "cima_status": c.sync_status if c else None,
                "bifimed_ok": bifimed_ok,
                "cima_ok": cima_ok,
                "sections_complete": sections_complete,
                "summary_ok": summary_ok,
                "fully_linked_public_detail_ready": fully_ready,
                "resumen_general": getattr(s, "resumen_general", None),
                "resumen_indicaciones": getattr(s, "resumen_indicaciones", None),
                "resumen_posologia": getattr(s, "resumen_posologia", None),
                "resumen_ajuste_renal": getattr(s, "resumen_ajuste_renal", None),
                "resumen_ajuste_hepatico": getattr(s, "resumen_ajuste_hepatico", None),
                "resumen_contraindicaciones": getattr(s, "resumen_contraindicaciones", None),
                "resumen_advertencias": getattr(s, "resumen_advertencias", None),
                "resumen_embarazo": getattr(s, "resumen_embarazo", None),
                "resumen_lactancia": getattr(s, "resumen_lactancia", None),
            }
        )
    return out
