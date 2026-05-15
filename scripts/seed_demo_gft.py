"""Seed controlled local/demo GFT data without calling external services.

This script is intentionally local-only: it writes demo rows to the configured
project database, does not create endpoints, and does not contact CIMA or
BIFIMED. Run it manually only against disposable local/demo databases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models.bifimed_cache import BifimedCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.principio_activo_service import extract_principios_from_cima_data, upsert_principios_for_cn

PUBLIC_CN = "900001"
DRAFT_CN = "900002"
EXCLUDED_CN = "900003"
PENDING_CN = "900004"

_REQUIRED_TABLES = {
    "gft_estado_presentacion",
    "cima_medicamento_cache",
    "cima_ficha_tecnica_cache",
    "bifimed_cache",
    "principio_activo",
    "principio_activo_alias",
    "medicamento_principio_activo",
}
_REQUIRED_GFT_COLUMNS = {
    "ajuste_insuficiencia_renal",
    "ajuste_insuficiencia_hepatica",
    "precauciones_embarazo",
    "precauciones_lactancia",
}
_PUBLIC_VIEW = "v_gft_publicada"


@dataclass(frozen=True)
class DemoMedication:
    cn: str
    estado_gft: str
    estado_editorial: str
    nregistro: str
    nombre: str
    presentacion: str
    forma_farmaceutica: str
    principio_activo: str
    atc_codigo: str
    atc_nombre: str
    situacion_financiacion: str | None
    indicaciones: str | None = None
    nemonico: str | None = None
    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    observaciones_internas: str | None = None


DEMO_MEDICATIONS: tuple[DemoMedication, ...] = (
    DemoMedication(
        cn=PUBLIC_CN,
        estado_gft="incluido",
        estado_editorial="publicado",
        nregistro="DEMO900001",
        nombre="Democef Hospital 1 g polvo para solución inyectable",
        presentacion="1 vial de polvo para solución inyectable/perfusión",
        forma_farmaceutica="Polvo para solución inyectable y para perfusión",
        principio_activo="Ceftriaxona",
        atc_codigo="J01DD04",
        atc_nombre="Ceftriaxona",
        situacion_financiacion="Financiado en ámbito hospitalario. Uso sujeto a guía farmacoterapéutica local.",
        indicaciones=(
            "Tratamiento de infecciones bacterianas graves sensibles a ceftriaxona, "
            "incluyendo neumonía adquirida en la comunidad, infecciones intraabdominales "
            "y pielonefritis, según la sección 4.1 de la ficha técnica demo."
        ),
        nemonico="DEMOCEF-IV",
        restricciones_hospitalarias="Uso restringido a indicación validada por Enfermedades Infecciosas o PROA.",
        ajuste_insuficiencia_renal="No requiere ajuste aislado en insuficiencia renal; revisar si coexiste hepatopatía grave.",
        ajuste_insuficiencia_hepatica="Precaución en insuficiencia hepática grave; valorar monitorización clínica.",
        precauciones_embarazo="Usar durante el embarazo solo si el beneficio esperado supera el riesgo potencial.",
        precauciones_lactancia="Compatible con lactancia con vigilancia de diarrea o candidiasis en lactante.",
        observaciones_internas="Dato demo publicable: revisar duración de tratamiento a las 48-72 horas.",
    ),
    DemoMedication(
        cn=DRAFT_CN,
        estado_gft="incluido",
        estado_editorial="borrador",
        nregistro="DEMO900002",
        nombre="Demoferol 20 mg comprimidos",
        presentacion="30 comprimidos recubiertos",
        forma_farmaceutica="Comprimido recubierto",
        principio_activo="Omeprazol",
        atc_codigo="A02BC01",
        atc_nombre="Omeprazol",
        situacion_financiacion="Financiado. Pendiente de revisión editorial demo.",
        nemonico="DEMOFEROL-ORAL",
        restricciones_hospitalarias="Borrador demo: no debe aparecer en la GFT pública.",
    ),
    DemoMedication(
        cn=EXCLUDED_CN,
        estado_gft="excluido",
        estado_editorial="publicado",
        nregistro="DEMO900003",
        nombre="Demoalgin 600 mg comprimidos",
        presentacion="40 comprimidos",
        forma_farmaceutica="Comprimido",
        principio_activo="Ibuprofeno",
        atc_codigo="M01AE01",
        atc_nombre="Ibuprofeno",
        situacion_financiacion="No incluido en guía hospitalaria demo.",
        nemonico="DEMOALGIN",
        restricciones_hospitalarias="Excluido demo: no debe aparecer en la GFT pública.",
    ),
    DemoMedication(
        cn=PENDING_CN,
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
        nregistro="DEMO900004",
        nombre="Demogluc 500 mg comprimidos",
        presentacion="50 comprimidos",
        forma_farmaceutica="Comprimido",
        principio_activo="Metformina",
        atc_codigo="A10BA02",
        atc_nombre="Metformina",
        situacion_financiacion="Pendiente de revisión demo.",
        nemonico="DEMOGLUC",
        restricciones_hospitalarias="Pendiente de evaluación por la comisión demo.",
    ),
)


class DemoSeedError(RuntimeError):
    """Raised when the local database is not ready for demo seeding."""


def _assert_database_ready() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_tables = sorted(_REQUIRED_TABLES - tables)
    if missing_tables:
        raise DemoSeedError(
            "La base de datos no parece migrada. Faltan tablas requeridas: "
            f"{', '.join(missing_tables)}. Ejecuta `alembic upgrade head` antes del seed demo."
        )

    gft_columns = {column["name"] for column in inspector.get_columns("gft_estado_presentacion")}
    missing_columns = sorted(_REQUIRED_GFT_COLUMNS - gft_columns)
    if missing_columns:
        raise DemoSeedError(
            "La tabla gft_estado_presentacion no tiene columnas esperadas por la demo: "
            f"{', '.join(missing_columns)}. Ejecuta `alembic upgrade head`."
        )

    views = set(inspector.get_view_names())
    if _PUBLIC_VIEW not in views:
        raise DemoSeedError(
            "Falta la vista v_gft_publicada. Ejecuta `alembic upgrade head` y verifica las migraciones."
        )


def _upsert_by_pk(db: Session, model: type, pk: Any, values: dict[str, Any]) -> str:
    row = db.get(model, pk)
    action = "updated"
    if row is None:
        row = model(**values)
        db.add(row)
        action = "created"
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return action


def _seed_gft_row(db: Session, medication: DemoMedication) -> str:
    return _upsert_by_pk(
        db,
        GFTEstadoPresentacion,
        medication.cn,
        {
            "cn": medication.cn,
            "estado_gft": medication.estado_gft,
            "estado_editorial": medication.estado_editorial,
            "nemonico": medication.nemonico,
            "restricciones_hospitalarias": medication.restricciones_hospitalarias,
            "ajuste_insuficiencia_renal": medication.ajuste_insuficiencia_renal,
            "ajuste_insuficiencia_hepatica": medication.ajuste_insuficiencia_hepatica,
            "precauciones_embarazo": medication.precauciones_embarazo,
            "precauciones_lactancia": medication.precauciones_lactancia,
            "observaciones_internas": medication.observaciones_internas,
            "comentario_revision": "Fila demo local creada por scripts/seed_demo_gft.py",
            "revisado_por": "seed-demo-local",
            "fecha_revision": date.today(),
            "last_import_batch_id": None,
            "last_imported_at": None,
            "updated_at": datetime.utcnow(),
        },
    )


def _seed_cima_row(db: Session, medication: DemoMedication) -> str:
    ficha_url = f"https://cima.aemps.es/cima/dochtml/ft/{medication.nregistro}/FT_{medication.nregistro}.html"
    prospecto_url = f"https://cima.aemps.es/cima/dochtml/p/{medication.nregistro}/P_{medication.nregistro}.html"
    principios = [{"nombre": medication.principio_activo}]
    return _upsert_by_pk(
        db,
        CimaMedicamentoCache,
        medication.cn,
        {
            "cn": medication.cn,
            "nregistro": medication.nregistro,
            "nombre": medication.nombre,
            "presentacion": medication.presentacion,
            "forma_farmaceutica": medication.forma_farmaceutica,
            "forma_farmaceutica_simplificada": medication.forma_farmaceutica,
            "vias_administracion_json": [{"nombre": "Vía intravenosa" if medication.cn == PUBLIC_CN else "Vía oral"}],
            "atc_json": [{"codigo": medication.atc_codigo, "nombre": medication.atc_nombre, "nivel": "L5"}],
            "principios_activos_json": principios,
            "documentos_json": [
                {"tipo": 1, "url": ficha_url, "urlHtml": ficha_url, "titulo": "Ficha técnica demo"},
                {"tipo": 2, "url": prospecto_url, "urlHtml": prospecto_url, "titulo": "Prospecto demo"},
            ],
            "url_ficha_tecnica": ficha_url,
            "url_prospecto": prospecto_url,
            "fecha_ficha_tecnica": date.today(),
            "fecha_prospecto": date.today(),
            "raw_data": {"source": "local_demo_seed", "external_call": False},
            "sync_status": "ok",
            "sync_error": None,
            "last_synced_at": datetime.utcnow(),
        },
    )


def _seed_bifimed_row(db: Session, medication: DemoMedication) -> str:
    return _upsert_by_pk(
        db,
        BifimedCache,
        medication.cn,
        {
            "cn": medication.cn,
            "situacion_financiacion": medication.situacion_financiacion,
            "condiciones_financiacion_restringidas": "Demo local sin llamada a BIFIMED real.",
            "condiciones_especiales_financiacion": "Validar condiciones reales antes de uso asistencial.",
            "estado_nomenclator": "Alta demo",
            "aportacion_usuario": "No aplica en demo hospitalaria",
            "subgrupo_atc": f"{medication.atc_codigo} - {medication.atc_nombre}",
            "detalle_financiacion_json": {"source": "local_demo_seed"},
            "raw_data": {"source": "local_demo_seed", "external_call": False},
            "sync_status": "ok",
            "sync_error": None,
            "last_synced_at": datetime.utcnow(),
        },
    )


def _seed_ficha_tecnica_41(db: Session, medication: DemoMedication) -> str | None:
    if not medication.indicaciones:
        return None

    row = (
        db.query(CimaFichaTecnicaCache)
        .filter(
            CimaFichaTecnicaCache.nregistro == medication.nregistro,
            CimaFichaTecnicaCache.tipo_documento == 1,
            CimaFichaTecnicaCache.seccion == "4.1",
        )
        .one_or_none()
    )
    values = {
        "cn": medication.cn,
        "nregistro": medication.nregistro,
        "tipo_documento": 1,
        "seccion": "4.1",
        "titulo": "Indicaciones terapéuticas",
        "contenido_html": f"<p>{medication.indicaciones}</p>",
        "contenido_texto": medication.indicaciones,
        "fecha_documento": date.today(),
        "raw_data": {"source": "local_demo_seed", "external_call": False},
        "sync_status": "ok",
        "sync_error": None,
        "last_synced_at": datetime.utcnow(),
    }
    if row is None:
        db.add(CimaFichaTecnicaCache(**values))
        return "created"

    for key, value in values.items():
        setattr(row, key, value)
    return "updated"


def _seed_principios(db: Session, medication: DemoMedication) -> None:
    principios = extract_principios_from_cima_data([{"nombre": medication.principio_activo}])
    upsert_principios_for_cn(db, medication.cn, principios)


def seed_demo_data(db: Session) -> dict[str, Any]:
    """Insert or update all demo rows in the provided database session."""
    summary: dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "medicamentos": [],
        "public_cn": PUBLIC_CN,
    }

    for medication in DEMO_MEDICATIONS:
        actions = [
            _seed_gft_row(db, medication),
            _seed_cima_row(db, medication),
            _seed_bifimed_row(db, medication),
        ]
        ficha_action = _seed_ficha_tecnica_41(db, medication)
        if ficha_action:
            actions.append(ficha_action)
        _seed_principios(db, medication)

        created = actions.count("created")
        updated = actions.count("updated")
        summary["created"] += created
        summary["updated"] += updated
        summary["medicamentos"].append(
            {
                "cn": medication.cn,
                "nombre": medication.nombre,
                "estado_gft": medication.estado_gft,
                "estado_editorial": medication.estado_editorial,
                "created_rows": created,
                "updated_rows": updated,
            }
        )

    db.commit()
    visible = db.execute(text("SELECT cn FROM v_gft_publicada WHERE cn = :cn"), {"cn": PUBLIC_CN}).scalar_one_or_none()
    summary["public_visible"] = visible == PUBLIC_CN
    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    print("Seed demo GFT completado.")
    print(f"Medicamentos/filas creadas: {summary['created']}")
    print(f"Medicamentos/filas actualizadas: {summary['updated']}")
    for item in summary["medicamentos"]:
        print(
            "- CN {cn}: {nombre} [{estado_gft}/{estado_editorial}] "
            "(creadas={created_rows}, actualizadas={updated_rows})".format(**item)
        )
    print(f"CN visible públicamente: {summary['public_cn']} ({'sí' if summary['public_visible'] else 'no'})")
    print("URLs recomendadas para abrir en la demo:")
    print("- Frontend público: /")
    print("- Panel admin: /admin/gft")
    print("- Exportación HTML: /gft/export/html")
    print("- Exportación PDF: /gft/export/pdf")


def main() -> int:
    try:
        _assert_database_ready()
        with SessionLocal() as db:
            summary = seed_demo_data(db)
        _print_summary(summary)
        return 0
    except DemoSeedError as exc:
        print(f"ERROR seed demo GFT: {exc}")
        return 2
    except SQLAlchemyError as exc:
        print(f"ERROR seed demo GFT: error de base de datos: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
