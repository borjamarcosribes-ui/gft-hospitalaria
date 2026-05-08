from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from io import BytesIO
import re
import unicodedata

import pandas as pd

from app.services.normalization_service import NormalizationError, is_missing, normalize_cn, normalize_text


@dataclass
class DryRunIssue:
    row_number: int | None
    code: str
    message: str
    cn_raw: str | None = None


@dataclass
class PendingItem:
    row_number: int
    cn: str | None
    observaciones_revision_raw: str | None
    reason: str


@dataclass
class UnknownObservacionesValue:
    value: str
    count: int


@dataclass
class DuplicateCN:
    cn: str
    rows: list[int]


@dataclass
class DryRunRow:
    row_number: int
    cn_raw: str | None
    cn: str | None
    observaciones_revision_raw: str | None
    estado_gft: str
    errors: list[DryRunIssue] = field(default_factory=list)
    warnings: list[DryRunIssue] = field(default_factory=list)


@dataclass
class GFTExcelDryRunResult:
    dry_run: bool
    sheet_name: str | int | None
    total_rows: int
    included_count: int
    excluded_count: int
    pending_count: int
    error_count: int
    warning_count: int
    duplicate_cn_count: int
    column_mapping: dict[str, str]
    errors: list[DryRunIssue] = field(default_factory=list)
    warnings: list[DryRunIssue] = field(default_factory=list)
    pending_items: list[PendingItem] = field(default_factory=list)
    unknown_observaciones_values: list[UnknownObservacionesValue] = field(default_factory=list)
    duplicate_cn: list[DuplicateCN] = field(default_factory=list)
    rows: list[DryRunRow] = field(default_factory=list)
    filename: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


CN_ALIASES = {
    "cn",
    "codigo nacional",
    "cod nacional",
}

OBSERVACIONES_REVISION_ALIASES = {
    "observaciones revision",
    "observacion revision",
    "obs revision",
}

INCLUDED_OBSERVACIONES = {"si"}
EXCLUDED_OBSERVACIONES = {"no", "no guia", "bloquear"}


def _norm_column_name(value) -> str:
    text = normalize_text(value) or ""
    text = text.lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_cell(value) -> str | None:
    if is_missing(value):
        return None
    return str(value).strip()


def _find_column(columns, aliases: set[str]) -> str | None:
    for column in columns:
        if _norm_column_name(column) in aliases:
            return column
    return None


def normalize_cn_for_gft_dry_run(value) -> str:
    try:
        return normalize_cn(value)
    except NormalizationError:
        text = normalize_text(value)
        if text is None:
            raise NormalizationError("CN vacío")
        compact = re.sub(r"\s+", "", text)
        match = re.fullmatch(r"(\d+)\.CNA", compact, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        raise


def classify_observaciones_revision_for_gft_dry_run(value) -> str:
    key = _norm_column_name(value)
    if key in INCLUDED_OBSERVACIONES:
        return "incluido"
    if key in EXCLUDED_OBSERVACIONES:
        return "excluido"
    return "pendiente_revision"


def _pending_reason(value) -> str:
    key = _norm_column_name(value)
    if key == "":
        return "empty_value"
    if key in {"si?", "no?", "???"}:
        return "ambiguous_or_unknown_value"
    return "ambiguous_or_unknown_value"


def _is_unknown_observaciones_value(value) -> bool:
    key = _norm_column_name(value)
    if key == "":
        return False
    if key in INCLUDED_OBSERVACIONES or key in EXCLUDED_OBSERVACIONES:
        return False
    return True


def _empty_result(
    filename: str | None,
    sheet_name: str | int | None,
    column_mapping: dict[str, str] | None = None,
) -> GFTExcelDryRunResult:
    return GFTExcelDryRunResult(
        dry_run=True,
        sheet_name=sheet_name,
        total_rows=0,
        included_count=0,
        excluded_count=0,
        pending_count=0,
        error_count=0,
        warning_count=0,
        duplicate_cn_count=0,
        column_mapping=column_mapping or {},
        filename=filename,
    )


def dry_run_gft_excel(
    file_bytes: bytes,
    filename: str | None = None,
    sheet_name: str | int | None = None,
) -> GFTExcelDryRunResult:
    excel = pd.ExcelFile(BytesIO(file_bytes))
    selected_sheet = sheet_name if sheet_name is not None else 0
    resolved_sheet_name = (
        excel.sheet_names[selected_sheet] if isinstance(selected_sheet, int) else selected_sheet
    )
    df = pd.read_excel(excel, sheet_name=selected_sheet, dtype=str)

    cn_column = _find_column(df.columns, CN_ALIASES)
    observaciones_column = _find_column(df.columns, OBSERVACIONES_REVISION_ALIASES)
    column_mapping = {}
    errors: list[DryRunIssue] = []

    if cn_column is not None:
        column_mapping["cn"] = cn_column
    else:
        errors.append(
            DryRunIssue(
                row_number=None,
                code="missing_required_column",
                message="Columna obligatoria ausente: CN",
            )
        )

    if observaciones_column is not None:
        column_mapping["observaciones_revision"] = observaciones_column
    else:
        errors.append(
            DryRunIssue(
                row_number=None,
                code="missing_required_column",
                message="Columna obligatoria ausente: Observaciones revisión",
            )
        )

    if errors:
        result = _empty_result(filename, resolved_sheet_name, column_mapping)
        result.errors = errors
        result.error_count = len(errors)
        return result

    rows: list[DryRunRow] = []
    pending_items: list[PendingItem] = []
    unknown_values = Counter()
    cn_rows: dict[str, list[int]] = defaultdict(list)
    counts = Counter()

    for idx, row in df.iterrows():
        row_number = int(idx) + 2
        cn_raw = _safe_cell(row.get(cn_column))
        observaciones_raw = _safe_cell(row.get(observaciones_column))
        row_errors: list[DryRunIssue] = []
        row_warnings: list[DryRunIssue] = []

        try:
            cn = normalize_cn_for_gft_dry_run(cn_raw)
            cn_rows[cn].append(row_number)
        except NormalizationError as exc:
            cn = None
            code = "cn_empty" if "vac" in str(exc).lower() else "cn_invalid"
            issue = DryRunIssue(row_number=row_number, cn_raw=cn_raw, code=code, message=str(exc))
            row_errors.append(issue)
            errors.append(issue)

        estado_gft = classify_observaciones_revision_for_gft_dry_run(observaciones_raw)
        counts[estado_gft] += 1

        if estado_gft == "pendiente_revision":
            pending_items.append(
                PendingItem(
                    row_number=row_number,
                    cn=cn,
                    observaciones_revision_raw=observaciones_raw,
                    reason=_pending_reason(observaciones_raw),
                )
            )
            if _is_unknown_observaciones_value(observaciones_raw):
                unknown_values[str(observaciones_raw)] += 1

        rows.append(
            DryRunRow(
                row_number=row_number,
                cn_raw=cn_raw,
                cn=cn,
                observaciones_revision_raw=observaciones_raw,
                estado_gft=estado_gft,
                errors=row_errors,
                warnings=row_warnings,
            )
        )

    rows_by_number = {row.row_number: row for row in rows}
    warnings: list[DryRunIssue] = []
    duplicate_cn = []
    for cn, duplicate_rows in sorted(cn_rows.items()):
        if len(duplicate_rows) <= 1:
            continue
        duplicate_cn.append(DuplicateCN(cn=cn, rows=duplicate_rows))
        for row_number in duplicate_rows:
            issue = DryRunIssue(
                row_number=row_number,
                cn_raw=rows_by_number[row_number].cn_raw,
                code="duplicate_cn",
                message=f"CN duplicado: {cn}",
            )
            rows_by_number[row_number].warnings.append(issue)
            warnings.append(issue)

    unknown_observaciones_values = [
        UnknownObservacionesValue(value=value, count=count)
        for value, count in sorted(unknown_values.items(), key=lambda item: item[0])
    ]

    return GFTExcelDryRunResult(
        dry_run=True,
        sheet_name=resolved_sheet_name,
        total_rows=len(df),
        included_count=counts["incluido"],
        excluded_count=counts["excluido"],
        pending_count=counts["pendiente_revision"],
        error_count=len(errors),
        warning_count=len(warnings),
        duplicate_cn_count=len(duplicate_cn),
        column_mapping=column_mapping,
        errors=errors,
        warnings=warnings,
        pending_items=pending_items,
        unknown_observaciones_values=unknown_observaciones_values,
        duplicate_cn=duplicate_cn,
        rows=rows,
        filename=filename,
    )
