from io import BytesIO

import pandas as pd
import pytest

from app.services.gft_excel_dry_run_service import (
    classify_observaciones_revision_for_gft_dry_run,
    dry_run_gft_excel,
    normalize_cn_for_gft_dry_run,
)
from app.services.normalization_service import NormalizationError


def make_excel(df: pd.DataFrame, sheet_name: str = "Hoja1") -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return bio.getvalue()


@pytest.mark.parametrize("value", ["SI", "SÍ", "si", "sí"])
def test_dry_run_classifies_included_values(value):
    assert classify_observaciones_revision_for_gft_dry_run(value) == "incluido"


@pytest.mark.parametrize("value", ["NO", "no", "no guia", "no guía", "bloquear"])
def test_dry_run_classifies_excluded_values(value):
    assert classify_observaciones_revision_for_gft_dry_run(value) == "excluido"


@pytest.mark.parametrize("value", ["SI?", "SÍ?", "NO?", "???", "", None, "desconocido", "guia", "guía"])
def test_dry_run_classifies_pending_values(value):
    assert classify_observaciones_revision_for_gft_dry_run(value) == "pendiente_revision"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (123456, "123456"),
        ("123456", "123456"),
        (" 123456 ", "123456"),
        ("123456.0", "123456"),
        ("001234", "001234"),
        ("123456.CNA", "123456"),
        (" 123456.cna ", "123456"),
    ],
)
def test_dry_run_normalizes_cn_values(value, expected):
    assert normalize_cn_for_gft_dry_run(value) == expected


@pytest.mark.parametrize("value", ["", None, pd.NA])
def test_dry_run_reports_empty_cn(value):
    with pytest.raises(NormalizationError, match="CN vacío"):
        normalize_cn_for_gft_dry_run(value)


@pytest.mark.parametrize("value", ["123456.X", "123456.CNB", "CN123456"])
def test_dry_run_reports_invalid_cn_suffix(value):
    with pytest.raises(NormalizationError, match="CN inválido"):
        normalize_cn_for_gft_dry_run(value)


def test_dry_run_detects_exact_required_columns():
    result = dry_run_gft_excel(make_excel(pd.DataFrame([{"CN": "123456", "Observaciones revisión": "SI"}])))

    assert result.error_count == 0
    assert result.column_mapping == {"cn": "CN", "observaciones_revision": "Observaciones revisión"}


def test_dry_run_detects_codigo_nacional_alias():
    result = dry_run_gft_excel(make_excel(pd.DataFrame([{"Código Nacional": "123456", "Observaciones revisión": "SI"}])))

    assert result.error_count == 0
    assert result.column_mapping["cn"] == "Código Nacional"


def test_dry_run_detects_observaciones_revision_without_accent_alias():
    result = dry_run_gft_excel(make_excel(pd.DataFrame([{"CN": "123456", "Observaciones revision": "SI"}])))

    assert result.error_count == 0
    assert result.column_mapping["observaciones_revision"] == "Observaciones revision"


def test_dry_run_reports_column_diagnostics_when_required_columns_are_missing():
    result = dry_run_gft_excel(
        make_excel(
            pd.DataFrame(
                [
                    {
                        "Codigo Nacional medicamento": "123456",
                        "Observaciones revision comentario": "SI",
                        "Otra columna": "valor",
                    }
                ]
            )
        ),
        filename="diagnostico.xlsx",
    )

    assert result.dry_run is True
    assert result.filename == "diagnostico.xlsx"
    assert result.sheet_name == "Hoja1"
    assert result.sheet_names == ["Hoja1"]
    assert result.header_row == 1
    assert result.total_rows == 0
    assert result.error_count == 2
    assert result.original_columns == [
        "Codigo Nacional medicamento",
        "Observaciones revision comentario",
        "Otra columna",
    ]
    assert result.normalized_columns == [
        "codigo nacional medicamento",
        "observaciones revision comentario",
        "otra columna",
    ]
    assert result.missing_required_columns == ["CN", "Observaciones revisión"]
    assert result.column_suggestions["CN"] == ["Codigo Nacional medicamento"]
    assert result.column_suggestions["Observaciones revisión"] == ["Observaciones revision comentario"]


def test_dry_run_detects_safe_cn_and_observaciones_aliases():
    result = dry_run_gft_excel(
        make_excel(
            pd.DataFrame(
                [
                    {
                        "C.N.": "123456",
                        "Observaciones GFT": "SI",
                    }
                ]
            )
        )
    )

    assert result.error_count == 0
    assert result.column_mapping == {"cn": "C.N.", "observaciones_revision": "Observaciones GFT"}
    assert result.rows[0].cn == "123456"
    assert result.included_count == 1


def test_dry_run_returns_clear_error_when_cn_column_is_missing():
    result = dry_run_gft_excel(make_excel(pd.DataFrame([{"Observaciones revisión": "SI"}])))

    assert result.error_count == 1
    assert result.errors[0].code == "missing_required_column"
    assert result.errors[0].message == "Columna obligatoria ausente: CN"


def test_dry_run_returns_clear_error_when_observaciones_column_is_missing():
    result = dry_run_gft_excel(make_excel(pd.DataFrame([{"CN": "123456"}])))

    assert result.error_count == 1
    assert result.errors[0].code == "missing_required_column"
    assert result.errors[0].message == "Columna obligatoria ausente: Observaciones revisión"


def test_dry_run_counts_rows_and_does_not_require_estado_editorial():
    result = dry_run_gft_excel(
        make_excel(
            pd.DataFrame(
                [
                    {"CN": "111111", "Observaciones revisión": "SI"},
                    {"CN": "222222", "Observaciones revisión": "NO"},
                    {"CN": "333333", "Observaciones revisión": "SI?"},
                    {"CN": "444444", "Observaciones revisión": "guía"},
                    {"CN": "", "Observaciones revisión": "desconocido"},
                ]
            )
        ),
        filename="gft.xlsx",
    )

    assert result.dry_run is True
    assert result.filename == "gft.xlsx"
    assert result.sheet_name == "Hoja1"
    assert result.total_rows == 5
    assert result.included_count == 1
    assert result.excluded_count == 1
    assert result.pending_count == 3
    assert result.error_count == 1
    assert result.errors[0].code == "cn_empty"
    assert [item.observaciones_revision_raw for item in result.pending_items] == ["SI?", "guía", "desconocido"]
    assert result.to_dict()["dry_run"] is True


def test_dry_run_detects_duplicate_cn_and_warns_rows():
    result = dry_run_gft_excel(
        make_excel(
            pd.DataFrame(
                [
                    {"CN": "123456", "Observaciones revisión": "SI"},
                    {"CN": "654321", "Observaciones revisión": "NO"},
                    {"CN": "123456.0", "Observaciones revisión": "NO?"},
                ]
            )
        )
    )

    assert result.duplicate_cn_count == 1
    assert result.duplicate_cn[0].cn == "123456"
    assert result.duplicate_cn[0].rows == [2, 4]
    assert result.warning_count == 2
    assert [warning.code for warning in result.warnings] == ["duplicate_cn", "duplicate_cn"]
    assert result.rows[0].warnings[0].code == "duplicate_cn"
    assert result.rows[2].warnings[0].code == "duplicate_cn"


def test_dry_run_returns_unknown_observaciones_values():
    result = dry_run_gft_excel(
        make_excel(
            pd.DataFrame(
                [
                    {"CN": "111111", "Observaciones revisión": "GUÍA"},
                    {"CN": "222222", "Observaciones revisión": "GUÍA"},
                    {"CN": "333333", "Observaciones revisión": "desconocido"},
                    {"CN": "444444", "Observaciones revisión": "SI"},
                ]
            )
        )
    )

    assert len(result.unknown_observaciones_values) == 2
    assert {item.value: item.count for item in result.unknown_observaciones_values} == {"GUÍA": 2, "desconocido": 1}


def test_dry_run_uses_requested_sheet_name():
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"CN": "111111", "Observaciones revisión": "NO"}]).to_excel(
            writer, index=False, sheet_name="Primera"
        )
        pd.DataFrame([{"CN": "222222", "Observaciones revisión": "SI"}]).to_excel(
            writer, index=False, sheet_name="Segunda"
        )

    result = dry_run_gft_excel(bio.getvalue(), sheet_name="Segunda")

    assert result.sheet_name == "Segunda"
    assert result.total_rows == 1
    assert result.included_count == 1
    assert result.rows[0].cn == "222222"



def test_dry_run_without_sheet_name_keeps_first_sheet_behavior():
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"CN": "111111", "Observaciones revisión": "NO"}]).to_excel(
            writer, index=False, sheet_name="Primera"
        )
        pd.DataFrame([{"CN": "222222", "Observaciones revisión": "SI"}]).to_excel(
            writer, index=False, sheet_name="Revision_GFT_ATC"
        )

    result = dry_run_gft_excel(bio.getvalue())

    assert result.sheet_name == "Primera"
    assert result.rows[0].cn == "111111"


def test_dry_run_returns_clear_error_for_missing_sheet_name():
    content = make_excel(pd.DataFrame([{"CN": "111111", "Observaciones revisión": "SI"}]), sheet_name="HojaReal")

    with pytest.raises(ValueError, match="La hoja 'NoExiste' no existe. Hojas disponibles: HojaReal"):
        dry_run_gft_excel(content, sheet_name="NoExiste")


def test_dry_run_uses_requested_header_row():
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["Título", "no es encabezado"],
                ["CN", "Observaciones revisión"],
                ["555555", "SI"],
            ]
        ).to_excel(writer, index=False, header=False, sheet_name="Revision_GFT_ATC")

    result = dry_run_gft_excel(bio.getvalue(), sheet_name="Revision_GFT_ATC", header_row=2)

    assert result.header_row == 2
    assert result.total_rows == 1
    assert result.rows[0].row_number == 3
    assert result.rows[0].cn == "555555"


def test_dry_run_returns_clear_error_for_invalid_header_row():
    content = make_excel(pd.DataFrame([{"CN": "111111", "Observaciones revisión": "SI"}]))

    with pytest.raises(ValueError, match="fila de encabezado debe ser un entero mayor o igual que 1"):
        dry_run_gft_excel(content, header_row=0)
