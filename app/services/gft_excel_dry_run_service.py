from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
from dataclasses import asdict, dataclass, field
from io import BytesIO
import re
import unicodedata

import pandas as pd

from app.services.normalization_service import NormalizationError, is_missing, normalize_cn, normalize_estado_editorial, normalize_text


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
    sheet_names: list[str] = field(default_factory=list)
    header_row: int = 1
    original_columns: list[str] = field(default_factory=list)
    normalized_columns: list[str] = field(default_factory=list)
    missing_required_columns: list[str] = field(default_factory=list)
    column_suggestions: dict[str, list[str]] = field(default_factory=dict)
    default_estado_editorial_used: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


CN_ALIASES = {
    "cn",
    "codigo nacional",
    "c n",
    "cod nacional",
}

OBSERVACIONES_REVISION_ALIASES = {
    "observaciones revision",
    "observacion revision",
    "observaciones",
    "observaciones gft",
    "observaciones revision gft",
    "obs revision",
}

ESTADO_EDITORIAL_ALIASES = {
    "estado editorial",
    "estado",
    "estado publicacion",
}

REQUIRED_COLUMN_ALIASES = {
    "CN": CN_ALIASES,
    "Observaciones revisión": OBSERVACIONES_REVISION_ALIASES,
}

OPTIONAL_COLUMN_ALIASES = {
    "Estado editorial": ESTADO_EDITORIAL_ALIASES,
}

REQUIRED_COLUMN_MAPPING_KEYS = {
    "CN": "cn",
    "Observaciones revisión": "observaciones_revision",
    "Estado editorial": "estado_editorial",
}

INCLUDED_OBSERVACIONES = {"si"}
EXCLUDED_OBSERVACIONES = {"no", "no guia", "bloquear"}


def _norm_column_name(value) -> str:
    text = normalize_text(value) or ""
    text = text.lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = re.sub(r"[._-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_cell(value) -> str | None:
    if is_missing(value):
        return None
    return str(value).strip()


def _original_column_name(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _find_column(columns, aliases: set[str]) -> str | None:
    for column in columns:
        if _norm_column_name(column) in aliases:
            return column
    return None


def build_gft_excel_column_mapping(columns) -> tuple[dict[str, str], list[str], list[DryRunIssue]]:
    column_mapping: dict[str, str] = {}
    missing_required_columns: list[str] = []
    errors: list[DryRunIssue] = []

    for required_column, aliases in REQUIRED_COLUMN_ALIASES.items():
        matched_column = _find_column(columns, aliases)
        if matched_column is not None:
            column_mapping[REQUIRED_COLUMN_MAPPING_KEYS[required_column]] = matched_column
            continue

        missing_required_columns.append(required_column)
        errors.append(
            DryRunIssue(
                row_number=None,
                code="missing_required_column",
                message=f"Columna obligatoria ausente: {required_column}",
            )
        )


    for optional_column, aliases in OPTIONAL_COLUMN_ALIASES.items():
        matched_column = _find_column(columns, aliases)
        if matched_column is not None:
            column_mapping[REQUIRED_COLUMN_MAPPING_KEYS[optional_column]] = matched_column

    return column_mapping, missing_required_columns, errors


def _column_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return max(SequenceMatcher(a=left, b=right).ratio(), overlap)


def _suggest_columns(columns, aliases: set[str], limit: int = 3) -> list[str]:
    scored: list[tuple[float, str]] = []
    seen: set[str] = set()

    for column in columns:
        original = _original_column_name(column)
        if not original or original in seen:
            continue
        normalized = _norm_column_name(column)
        score = max((_column_similarity(normalized, alias) for alias in aliases), default=0.0)
        if score >= 0.62:
            scored.append((score, original))
            seen.add(original)

    scored.sort(key=lambda item: (-item[0], item[1].lower()))
    return [column for _, column in scored[:limit]]


def _build_column_diagnostics(
    columns,
    missing_required_columns: list[str],
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    original_columns = [_original_column_name(column) for column in columns]
    normalized_columns = [_norm_column_name(column) for column in columns]
    suggestions = {
        required_column: _suggest_columns(columns, aliases)
        for required_column, aliases in REQUIRED_COLUMN_ALIASES.items()
        if required_column in missing_required_columns
    }
    return original_columns, normalized_columns, suggestions


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
    sheet_names: list[str] | None = None,
    header_row: int = 1,
    original_columns: list[str] | None = None,
    normalized_columns: list[str] | None = None,
    missing_required_columns: list[str] | None = None,
    column_suggestions: dict[str, list[str]] | None = None,
) -> GFTExcelDryRunResult:
    return GFTExcelDryRunResult(
        dry_run=True,
        sheet_name=sheet_name,
        sheet_names=sheet_names or [],
        header_row=header_row,
        original_columns=original_columns or [],
        normalized_columns=normalized_columns or [],
        missing_required_columns=missing_required_columns or [],
        column_suggestions=column_suggestions or {},
        total_rows=0,
        included_count=0,
        excluded_count=0,
        pending_count=0,
        error_count=0,
        warning_count=0,
        duplicate_cn_count=0,
        column_mapping=column_mapping or {},
        filename=filename,
        default_estado_editorial_used=(normalized_default_estado_editorial if estado_editorial_column is None else None),
    )


def _validate_header_row(header_row: int | None) -> int:
    selected_header_row = 1 if header_row is None else header_row
    if selected_header_row < 1:
        raise ValueError("La fila de encabezado debe ser un entero mayor o igual que 1")
    return selected_header_row


def _validate_sheet_name(excel: pd.ExcelFile, sheet_name: str | int | None) -> str | int:
    if sheet_name is None:
        return 0

    if isinstance(sheet_name, int):
        if sheet_name < 0 or sheet_name >= len(excel.sheet_names):
            raise ValueError(
                f"La hoja {sheet_name} no existe. Hojas disponibles: {', '.join(excel.sheet_names)}"
            )
        return sheet_name

    if sheet_name not in excel.sheet_names:
        raise ValueError(
            f"La hoja '{sheet_name}' no existe. Hojas disponibles: {', '.join(excel.sheet_names)}"
        )
    return sheet_name


def _resolve_sheet_name(excel: pd.ExcelFile, selected_sheet: str | int) -> str:
    return excel.sheet_names[selected_sheet] if isinstance(selected_sheet, int) else selected_sheet


def dry_run_gft_excel(
    file_bytes: bytes,
    filename: str | None = None,
    sheet_name: str | int | None = None,
    header_row: int | None = None,
    default_estado_editorial: str | None = None,
) -> GFTExcelDryRunResult:
    excel = pd.ExcelFile(BytesIO(file_bytes))
    selected_sheet = _validate_sheet_name(excel, sheet_name)
    resolved_sheet_name = _resolve_sheet_name(excel, selected_sheet)
    selected_header_row = _validate_header_row(header_row)
    try:
        df = pd.read_excel(excel, sheet_name=selected_sheet, dtype=str, header=selected_header_row - 1)
    except ValueError as exc:
        raise ValueError(f"Fila de encabezado inválida ({selected_header_row}): {exc}") from exc

    column_mapping, missing_required_columns, errors = build_gft_excel_column_mapping(df.columns)
    cn_column = column_mapping.get("cn")
    observaciones_column = column_mapping.get("observaciones_revision")
    estado_editorial_column = column_mapping.get("estado_editorial")

    normalized_default_estado_editorial = None
    if default_estado_editorial is not None:
        try:
            normalized_default_estado_editorial = normalize_estado_editorial(default_estado_editorial)
        except NormalizationError as exc:
            raise ValueError(f"default_estado_editorial inválido: {exc}") from exc

    if estado_editorial_column is None and normalized_default_estado_editorial is None:
        issue = DryRunIssue(
            row_number=None,
            code="missing_required_column",
            message="Columna obligatoria ausente: Estado editorial",
        )
        errors.append(issue)
        missing_required_columns.append("Estado editorial")

    original_columns, normalized_columns, column_suggestions = _build_column_diagnostics(
        df.columns,
        missing_required_columns,
    )

    if errors:
        result = _empty_result(
            filename,
            resolved_sheet_name,
            column_mapping,
            sheet_names=excel.sheet_names,
            header_row=selected_header_row,
            original_columns=original_columns,
            normalized_columns=normalized_columns,
            missing_required_columns=missing_required_columns,
            column_suggestions=column_suggestions,
        )
        result.errors = errors
        result.error_count = len(errors)
        return result

    rows: list[DryRunRow] = []
    pending_items: list[PendingItem] = []
    unknown_values = Counter()
    cn_rows: dict[str, list[int]] = defaultdict(list)
    counts = Counter()

    for idx, row in df.iterrows():
        row_number = int(idx) + selected_header_row + 1
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
        sheet_names=excel.sheet_names,
        header_row=selected_header_row,
        original_columns=original_columns,
        normalized_columns=normalized_columns,
        missing_required_columns=missing_required_columns,
        column_suggestions=column_suggestions,
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
        default_estado_editorial_used=(normalized_default_estado_editorial if estado_editorial_column is None else None),
    )
