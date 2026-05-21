from app.services.import_apply_service import _pick_imported


def test_pick_imported_aemps_nombre_medicamento_alias():
    raw_payload = {"AEMPS nombre medicamento": "Medicamento Demo"}
    assert _pick_imported(raw_payload, "AEMPS nombre medicamento", "Nombre comercial") == "Medicamento Demo"


def test_pick_imported_principio_activo_aemps_alias():
    raw_payload = {"Principio activo AEMPS": "Amoxicilina"}
    assert _pick_imported(raw_payload, "Principio activo AEMPS", "Principio activo") == "Amoxicilina"


def test_pick_imported_aemps_presentacion_alias():
    raw_payload = {"AEMPS presentación": "500 mg comprimidos"}
    assert _pick_imported(raw_payload, "AEMPS presentación", "Presentación") == "500 mg comprimidos"


def test_pick_imported_atc_descripcion_alias():
    raw_payload = {"ATC descripción": "Antibacterianos de uso sistémico"}
    assert _pick_imported(raw_payload, "ATC descripción", "Descripción ATC") == "Antibacterianos de uso sistémico"
