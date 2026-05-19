import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import {
  adminHealth,
  applyImportBatch,
  dryRunGftExcel,
  getImportBatchRows,
  getImportBatchSummary,
  getGftEditorialMedicamento,
  getGftEditorialSummary,
  importGftExcel,
  listGftEditorialMedicamentos,
  updateGftMedicationEditorial,
  updateGftMedicationState,
} from '../services/adminApi';
import type {
  ApplyImportBatchResponse,
  GFTEditorialAdminListResponse,
  GFTEditorialAdminResponse,
  GFTEditorialAdminSummaryResponse,
  GFTEditorialUpdatePayload,
  GFTPublicationEditorialState,
  GFTPublicationGftState,
  GFTPublicationStateUpdatePayload,
  ImportBatchResponse,
  ImportBatchSummary,
  ImportDryRunResponse,
  ImportRowStaging,
} from '../types/admin';

const ADMIN_SESSION_KEY = 'gft-admin-api-key';
const DEFAULT_LIMIT = 50;
const ESTADO_GFT_OPTIONS = ['incluido', 'excluido', 'pendiente_revision'] as const;
const ESTADO_EDITORIAL_OPTIONS = ['borrador', 'validado', 'publicado', 'retirado'] as const;
const PREFERRED_GFT_SHEET_NAME = 'Revision_GFT_ATC';

type EditableClinicalField = Exclude<keyof GFTEditorialUpdatePayload, 'comentario_revision' | 'revisado_por'>;
type EditorialFormState = Record<EditableClinicalField, string>;

interface PublicationStateFormState {
  estado_gft: GFTPublicationGftState;
  estado_editorial: GFTPublicationEditorialState;
  comentario_revision: string;
  revisado_por: string;
}

const EDITABLE_CLINICAL_FIELDS: Array<{ key: EditableClinicalField; label: string; control: 'textarea' | 'input' }> = [
  { key: 'restricciones_hospitalarias', label: 'Restricciones hospitalarias', control: 'textarea' },
  { key: 'ajuste_insuficiencia_renal', label: 'Ajuste insuficiencia renal', control: 'textarea' },
  { key: 'ajuste_insuficiencia_hepatica', label: 'Ajuste insuficiencia hepática', control: 'textarea' },
  { key: 'precauciones_embarazo', label: 'Precauciones embarazo', control: 'textarea' },
  { key: 'precauciones_lactancia', label: 'Precauciones lactancia', control: 'textarea' },
  { key: 'observaciones_internas', label: 'Observaciones internas', control: 'textarea' },
];

function buildPublicationStateFormState(detail: GFTEditorialAdminResponse): PublicationStateFormState {
  return {
    estado_gft: detail.estado_gft as GFTPublicationGftState,
    estado_editorial: detail.estado_editorial as GFTPublicationEditorialState,
    comentario_revision: detail.comentario_revision ?? '',
    revisado_por: detail.revisado_por ?? '',
  };
}

function buildEditorialFormState(detail: GFTEditorialAdminResponse): EditorialFormState {
  return EDITABLE_CLINICAL_FIELDS.reduce((formState, field) => ({
    ...formState,
    [field.key]: detail[field.key] ?? '',
  }), {} as EditorialFormState);
}

function normalizeEditorialValue(value: string): string | null {
  const cleanValue = value.trim();
  return cleanValue ? cleanValue : null;
}

function buildEditorialPayload(detail: GFTEditorialAdminResponse, formState: EditorialFormState): GFTEditorialUpdatePayload {
  const payload = EDITABLE_CLINICAL_FIELDS.reduce((currentPayload, field) => {
    const normalizedValue = normalizeEditorialValue(formState[field.key]);

    if (normalizedValue !== detail[field.key]) {
      return {
        ...currentPayload,
        [field.key]: normalizedValue,
      };
    }

    return currentPayload;
  }, {} as GFTEditorialUpdatePayload);


  return payload;
}

function buildPublicationStatePayload(
  detail: GFTEditorialAdminResponse,
  formState: PublicationStateFormState,
): GFTPublicationStateUpdatePayload {
  const payload: GFTPublicationStateUpdatePayload = {};
  const normalizedComment = normalizeEditorialValue(formState.comentario_revision);
  const normalizedReviewer = normalizeEditorialValue(formState.revisado_por);

  if (formState.estado_gft !== detail.estado_gft) {
    payload.estado_gft = formState.estado_gft;
  }

  if (formState.estado_editorial !== detail.estado_editorial) {
    payload.estado_editorial = formState.estado_editorial;
  }

  if (normalizedComment !== detail.comentario_revision) {
    payload.comentario_revision = normalizedComment;
  }

  if (normalizedReviewer && normalizedReviewer !== detail.revisado_por) {
    payload.revisado_por = normalizedReviewer;
  }

  if ((payload.comentario_revision !== undefined || payload.revisado_por !== undefined) && payload.estado_gft === undefined && payload.estado_editorial === undefined) {
    payload.estado_gft = formState.estado_gft;
    payload.estado_editorial = formState.estado_editorial;
  }

  return payload;
}

function isPubliclyVisible(estadoGft: string, estadoEditorial: string): boolean {
  return estadoGft === 'incluido' && estadoEditorial === 'publicado';
}

function getMedicationDisplayName(detail: GFTEditorialAdminResponse): string {
  const commercialName = detail.nombre_comercial?.trim();

  return commercialName ? `${commercialName} (CN ${detail.cn})` : `CN ${detail.cn}`;
}

function getStateChangeConfirmationMessage(detail: GFTEditorialAdminResponse, formState: PublicationStateFormState): string {
  const wasPublic = isPubliclyVisible(detail.estado_gft, detail.estado_editorial);
  const willBePublic = isPubliclyVisible(formState.estado_gft, formState.estado_editorial);
  const medicationName = getMedicationDisplayName(detail);

  if (willBePublic && !wasPublic) {
    return `Vas a publicar ${medicationName} en la GFT pública. ¿Confirmas el cambio?`;
  }

  if (!willBePublic && wasPublic) {
    return `Vas a retirar ${medicationName} de la GFT pública. ¿Confirmas el cambio?`;
  }

  return `Vas a modificar el estado administrativo de ${medicationName}. ¿Confirmas el cambio?`;
}

function getStateSaveSuccessMessage(wasPublic: boolean, willBePublic: boolean): string {
  if (willBePublic && !wasPublic) {
    return 'Estado actualizado. El medicamento queda visible en la GFT pública.';
  }

  if (!willBePublic && wasPublic) {
    return 'Estado actualizado. El medicamento no queda visible en la GFT pública.';
  }

  return 'Estado administrativo actualizado correctamente.';
}

function formatDate(value: string | null): string {
  if (!value) {
    return '—';
  }

  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium' }).format(new Date(value));
}
function formatDateTime(value: string | null): string {
  if (!value) {
    return '—';
  }

  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ');
}

function EmptyValue({ value }: { value: string | null }) {
  return value ? <>{value}</> : <span className="admin-muted">No informado</span>;
}

function StatusBadge({ value, tone = 'neutral' }: { value: string; tone?: 'green' | 'blue' | 'amber' | 'neutral' }) {
  return <span className={`admin-status-badge admin-status-badge--${tone}`}>{formatLabel(value)}</span>;
}

function summaryValue(summary: GFTEditorialAdminSummaryResponse | null, key: string): number {
  return summary?.by_estado_editorial[key] ?? 0;
}

function formatIssueList(values: string[] | Array<{ message?: string; code?: string }>): string {
  if (values.length === 0) {
    return '—';
  }

  return values.map((value) => (typeof value === 'string' ? value : value.message ?? value.code ?? 'Incidencia')).join('; ');
}

function getDryRunValidRows(dryRun: ImportDryRunResponse): number {
  return Math.max(0, dryRun.total_rows - dryRun.error_count);
}

function formatStringList(values: string[] | undefined, emptyText = '—'): string {
  return values && values.length > 0 ? values.join(', ') : emptyText;
}

function hasDryRunColumnDiagnostics(dryRun: ImportDryRunResponse): boolean {
  return (
    dryRun.sheet_name !== null
    || dryRun.sheet_names.length > 0
    || dryRun.original_columns.length > 0
    || dryRun.normalized_columns.length > 0
    || dryRun.missing_required_columns.length > 0
    || Object.values(dryRun.column_suggestions).some((candidates) => candidates.length > 0)
  );
}

function isLikelyNonTabularSheet(dryRun: ImportDryRunResponse): boolean {
  return (
    dryRun.sheet_name === 'Resumen'
    && dryRun.sheet_names.includes(PREFERRED_GFT_SHEET_NAME)
    && dryRun.missing_required_columns.length > 0
  );
}

function normalizeSheetSelection(value: string | number | null): string {
  return value === null ? '' : String(value);
}

function AdminExcelImportSection({
  apiKey,
  onApplied,
}: {
  apiKey: string;
  onApplied: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [selectedSheetName, setSelectedSheetName] = useState('');
  const [headerRow, setHeaderRow] = useState(1);
  const [defaultEstadoEditorial, setDefaultEstadoEditorial] = useState<'borrador' | 'validado' | 'publicado'>('borrador');
  const [dryRun, setDryRun] = useState<ImportDryRunResponse | null>(null);
  const [batch, setBatch] = useState<ImportBatchResponse | null>(null);
  const [batchSummary, setBatchSummary] = useState<ImportBatchSummary | null>(null);
  const [batchRows, setBatchRows] = useState<ImportRowStaging[]>([]);
  const [applyResult, setApplyResult] = useState<ApplyImportBatchResponse | null>(null);
  const [loadingAction, setLoadingAction] = useState<'dry-run' | 'import' | 'summary' | 'apply' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const batchId = batch?.batch_id ?? batchSummary?.batch_id ?? null;
  const availableSheetNames = dryRun?.sheet_names ?? [];
  const importOptions = {
    ...(selectedSheetName.trim() ? { sheet_name: selectedSheetName.trim() } : {}),
    header_row: headerRow,
    default_estado_editorial: defaultEstadoEditorial,
  };
  const dryRunMatchesSelection = dryRun
    ? normalizeSheetSelection(dryRun.sheet_name) === (selectedSheetName.trim() || normalizeSheetSelection(dryRun.sheet_name))
      && dryRun.header_row === headerRow
      && (dryRun.default_estado_editorial_used ?? null) === (dryRun.column_mapping.estado_editorial ? null : defaultEstadoEditorial)
    : false;

  const resetBatchReview = () => {
    setBatch(null);
    setBatchSummary(null);
    setBatchRows([]);
    setApplyResult(null);
  };

  const handleFileChange = (selectedFile: File | null) => {
    setFile(selectedFile);
    setSelectedSheetName('');
    setHeaderRow(1);
    setDefaultEstadoEditorial('borrador');
    setDryRun(null);
    resetBatchReview();
    setError(null);
    setSuccess(null);
  };

  const loadBatchReview = async (activeBatchId: string) => {
    const [summaryResponse, rowsResponse] = await Promise.all([
      getImportBatchSummary(apiKey, activeBatchId),
      getImportBatchRows(apiKey, activeBatchId, 25, 0),
    ]);

    setBatchSummary(summaryResponse);
    setBatchRows(rowsResponse);
  };

  const handleDryRun = async () => {
    if (!file) {
      setError('Selecciona un archivo .xlsx antes de validar.');
      return;
    }

    setLoadingAction('dry-run');
    setError(null);
    setSuccess(null);
    resetBatchReview();

    try {
      const response = await dryRunGftExcel(apiKey, file, importOptions);
      setDryRun(response);
      if (!selectedSheetName.trim()) {
        const suggestedSheet = response.sheet_names.includes(PREFERRED_GFT_SHEET_NAME)
          ? PREFERRED_GFT_SHEET_NAME
          : normalizeSheetSelection(response.sheet_name);
        setSelectedSheetName(suggestedSheet);
      }
      setSuccess('Validación dry-run completada. No se ha aplicado ningún cambio.');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'No se pudo validar el Excel.');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleImportToStaging = async () => {
    if (!file) {
      setError('Selecciona un archivo .xlsx antes de importar a staging.');
      return;
    }

    if (!dryRun) {
      setError('Ejecuta primero la validación dry-run antes de importar a staging.');
      return;
    }

    if (!dryRunMatchesSelection) {
      setError('Ejecuta primero la validación dry-run con la hoja y fila de encabezado seleccionadas.');
      return;
    }

    setLoadingAction('import');
    setError(null);
    setSuccess(null);
    setApplyResult(null);

    try {
      const response = await importGftExcel(apiKey, file, importOptions);
      setBatch(response);
      await loadBatchReview(response.batch_id);
      setSuccess(`Excel importado a staging. Batch ${response.batch_id}. No se ha aplicado todavía.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'No se pudo importar el Excel a staging.');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRefreshBatchReview = async () => {
    if (!batchId) {
      setError('No hay ningún batch de staging cargado para consultar.');
      return;
    }

    setLoadingAction('summary');
    setError(null);

    try {
      await loadBatchReview(batchId);
      setSuccess('Resumen y primeras filas del batch actualizados.');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'No se pudo consultar el batch.');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleApplyBatch = async () => {
    if (!batchId) {
      setError('No hay ningún batch de staging cargado para aplicar.');
      return;
    }

    const confirmed = window.confirm(
      'Vas a aplicar este batch de staging. No se publicará todo automáticamente: la visibilidad pública seguirá dependiendo de estado_gft = incluido y estado_editorial = publicado. ¿Confirmas la aplicación?',
    );

    if (!confirmed) {
      return;
    }

    setLoadingAction('apply');
    setError(null);
    setSuccess(null);

    try {
      const response = await applyImportBatch(apiKey, batchId);
      setApplyResult(response);
      await loadBatchReview(batchId);
      await onApplied();
      setSuccess(`Batch aplicado: ${response.applied_rows} filas aplicadas y ${response.total_rows - response.applied_rows} omitidas.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'No se pudo aplicar el batch.');
    } finally {
      setLoadingAction(null);
    }
  };

  const isBusy = loadingAction !== null;

  return (
    <section className="admin-section admin-import-section" aria-labelledby="admin-import-title">
      <div className="admin-section__header">
        <div>
          <h2 id="admin-import-title">Importar Excel GFT</h2>
          <p>Flujo seguro: seleccionar Excel → validar dry-run → revisar → importar a staging → aplicar con confirmación.</p>
        </div>
      </div>

      <p className="admin-alert admin-alert--warning">
        Aplicar un batch no publica todo automáticamente: la visibilidad pública sigue dependiendo de <strong>estado_gft = incluido</strong> y <strong>estado_editorial = publicado</strong>.
      </p>

      <div className="admin-import-controls">
        <label>
          Archivo maestro .xlsx
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
            disabled={isBusy}
          />
        </label>
        <label>
          Hoja del Excel
          <select
            value={selectedSheetName}
            onChange={(event) => {
              setSelectedSheetName(event.target.value);
              resetBatchReview();
            }}
            disabled={isBusy || availableSheetNames.length === 0}
          >
            {availableSheetNames.length === 0 ? <option value="">Se detectará al validar</option> : null}
            {availableSheetNames.map((sheetName) => (
              <option key={sheetName} value={sheetName}>
                {sheetName}{sheetName === PREFERRED_GFT_SHEET_NAME ? ' (sugerida)' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Fila de encabezado
          <input
            type="number"
            min="1"
            step="1"
            value={headerRow}
            onChange={(event) => {
              const nextHeaderRow = Number.parseInt(event.target.value, 10);
              setHeaderRow(Number.isNaN(nextHeaderRow) ? 1 : Math.max(1, nextHeaderRow));
              resetBatchReview();
            }}
            disabled={isBusy}
          />
        </label>
        <label>
          Estado editorial por defecto si falta la columna
          <select
            value={defaultEstadoEditorial}
            onChange={(event) => {
              setDefaultEstadoEditorial(event.target.value as 'borrador' | 'validado' | 'publicado');
              resetBatchReview();
            }}
            disabled={isBusy}
          >
            <option value="borrador">borrador</option>
            <option value="validado">validado</option>
            <option value="publicado">publicado</option>
          </select>
        </label>
        <div className="admin-import-controls__actions">
          <button className="admin-button admin-button--primary" type="button" onClick={() => void handleDryRun()} disabled={!file || isBusy}>
            {loadingAction === 'dry-run' ? 'Validando…' : 'Validar Excel'}
          </button>
          <button className="admin-button admin-button--secondary" type="button" onClick={() => void handleImportToStaging()} disabled={!file || !dryRun || !dryRunMatchesSelection || isBusy}>
            {loadingAction === 'import' ? 'Importando…' : 'Importar a staging'}
          </button>
        </div>
      </div>

      {file ? <p className="admin-muted">Archivo seleccionado: <strong>{file.name}</strong></p> : null}
      {defaultEstadoEditorial === 'publicado' ? (
        <p className="admin-alert admin-alert--warning">Advertencia: usar <strong>publicado</strong> como estado editorial por defecto puede aumentar la visibilidad pública potencial. Solo se publicarán medicamentos con <strong>estado_gft = incluido</strong> y <strong>estado_editorial = publicado</strong>.</p>
      ) : null}
      {dryRun && !dryRunMatchesSelection ? (
        <p className="admin-alert admin-alert--warning">La hoja, la fila de encabezado o el estado editorial por defecto han cambiado. Vuelve a validar antes de importar a staging.</p>
      ) : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      {dryRun ? (
        <div className="admin-import-panel">
          <div className="admin-import-panel__header">
            <h3>Resumen dry-run</h3>
            <span>No se ha aplicado ningún cambio</span>
          </div>
          <div className="admin-summary-grid admin-summary-grid--compact">
            <article className="admin-summary-card"><span>Total filas</span><strong>{dryRun.total_rows}</strong><small>Leídas del Excel</small></article>
            <article className="admin-summary-card"><span>Filas válidas</span><strong>{getDryRunValidRows(dryRun)}</strong><small>Sin errores de validación</small></article>
            <article className="admin-summary-card"><span>Con error</span><strong>{dryRun.error_count}</strong><small>Revisar antes de aplicar</small></article>
            <article className="admin-summary-card"><span>Pendientes</span><strong>{dryRun.pending_count}</strong><small>No se publican automáticamente</small></article>
          </div>
          <dl className="admin-import-definition-list">
            <dt>Hoja leída</dt>
            <dd>{dryRun.sheet_name ?? '—'}</dd>
            <dt>Hojas disponibles</dt>
            <dd>{formatStringList(dryRun.sheet_names)}</dd>
            <dt>Fila de encabezado usada</dt>
            <dd>{dryRun.header_row}</dd>
            <dt>Estado editorial por defecto usado</dt>
            <dd>{dryRun.default_estado_editorial_used ?? 'No (se usó la columna del Excel)'}</dd>
            <dt>Columnas detectadas</dt>
            <dd>{Object.keys(dryRun.column_mapping).length > 0 ? Object.entries(dryRun.column_mapping).map(([key, value]) => `${formatLabel(key)} → ${value}`).join(', ') : 'No se detectaron columnas válidas'}</dd>
            <dt>Columnas originales leídas</dt>
            <dd>{formatStringList(dryRun.original_columns, 'No se leyeron encabezados')}</dd>
            <dt>Columnas normalizadas</dt>
            <dd>{formatStringList(dryRun.normalized_columns, 'No hay encabezados normalizados')}</dd>
            <dt>Obligatorias faltantes</dt>
            <dd>{formatStringList(dryRun.missing_required_columns)}</dd>
            <dt>Duplicados CN</dt>
            <dd>{dryRun.duplicate_cn_count}</dd>
            <dt>Avisos</dt>
            <dd>{dryRun.warning_count}</dd>
          </dl>
          {isLikelyNonTabularSheet(dryRun) ? (
            <p className="admin-alert admin-alert--warning">La hoja leída parece no ser tabular. Prueba con {PREFERRED_GFT_SHEET_NAME}.</p>
          ) : null}
          {dryRun.sheet_names.includes(PREFERRED_GFT_SHEET_NAME) ? (
            <p className="admin-muted">Hoja sugerida para este formato: <strong>{PREFERRED_GFT_SHEET_NAME}</strong>.</p>
          ) : null}
          {hasDryRunColumnDiagnostics(dryRun) && Object.keys(dryRun.column_suggestions).length > 0 ? (
            <div className="admin-import-issues">
              <h4>Sugerencias de columnas</h4>
              <ul>
                {Object.entries(dryRun.column_suggestions).map(([requiredColumn, candidates]) => (
                  <li key={`suggestion-${requiredColumn}`}>
                    <strong>{requiredColumn}</strong>: {formatStringList(candidates, 'sin candidatas parecidas')}
                  </li>
                ))}
              </ul>
              <p className="admin-muted">No se ha aplicado ningún cambio. Revisa si la hoja, la fila de encabezados o los nombres de columnas coinciden con el formato esperado.</p>
            </div>
          ) : null}
          {dryRun.errors.length > 0 ? (
            <div className="admin-import-issues">
              <h4>Errores principales</h4>
              <ul>
                {dryRun.errors.slice(0, 6).map((issue) => (
                  <li key={`${issue.row_number ?? 'global'}-${issue.code}-${issue.message}`}>
                    {issue.row_number ? `Fila ${issue.row_number}: ` : ''}{issue.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {dryRun.pending_items.length > 0 ? (
            <p className="admin-alert admin-alert--warning">Hay {dryRun.pending_items.length} filas pendientes de revisión. No se publican automáticamente al aplicar el batch.</p>
          ) : null}
        </div>
      ) : null}

      {batch || batchSummary ? (
        <div className="admin-import-panel">
          <div className="admin-import-panel__header">
            <div>
              <h3>Batch de staging</h3>
              <p className="admin-muted">Batch ID: <strong>{batchId}</strong></p>
            </div>
            <div className="admin-import-controls__actions">
              <button className="admin-button admin-button--secondary" type="button" onClick={() => void handleRefreshBatchReview()} disabled={isBusy}>
                {loadingAction === 'summary' ? 'Consultando…' : 'Consultar resumen/filas'}
              </button>
              <button className="admin-button admin-button--primary" type="button" onClick={() => void handleApplyBatch()} disabled={!batchId || isBusy}>
                {loadingAction === 'apply' ? 'Aplicando…' : 'Aplicar batch'}
              </button>
            </div>
          </div>

          {batchSummary ? (
            <div className="admin-summary-grid admin-summary-grid--compact">
              <article className="admin-summary-card"><span>Staging</span><strong>{batchSummary.staging_total_rows}</strong><small>Filas cargadas</small></article>
              <article className="admin-summary-card"><span>Aplicables</span><strong>{batchSummary.applicable_rows}</strong><small>Sin bloqueos</small></article>
              <article className="admin-summary-card"><span>Errores</span><strong>{batchSummary.error_rows}</strong><small>Omitidas al aplicar</small></article>
              <article className="admin-summary-card"><span>Pendientes</span><strong>{batchSummary.pending_rows}</strong><small>Revisión manual</small></article>
            </div>
          ) : null}

          {applyResult ? (
            <p className="admin-alert admin-alert--success">Aplicación completada: {applyResult.applied_rows} aplicadas, {applyResult.skipped_errors} con errores omitidas, {applyResult.skipped_pending} pendientes omitidas.</p>
          ) : null}

          {batchSummary?.error_items.length ? (
            <div className="admin-import-issues">
              <h4>Errores del batch</h4>
              <ul>
                {batchSummary.error_items.slice(0, 6).map((item) => (
                  <li key={`batch-error-${item.row_number}`}>Fila {item.row_number}: {formatIssueList(item.validation_errors)}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="admin-table-card admin-import-table-card">
            <table className="admin-table admin-import-table">
              <thead>
                <tr>
                  <th>Fila</th>
                  <th>CN</th>
                  <th>Estado GFT</th>
                  <th>Estado editorial</th>
                  <th>Nemónico</th>
                  <th>Errores</th>
                  <th>Avisos</th>
                </tr>
              </thead>
              <tbody>
                {batchRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.row_number}</td>
                    <td>{row.cn_normalized ?? row.cn_raw ?? '—'}</td>
                    <td><StatusBadge value={row.estado_gft} tone={row.estado_gft === 'incluido' ? 'green' : row.estado_gft === 'pendiente_revision' ? 'amber' : 'neutral'} /></td>
                    <td>{row.estado_editorial ? <StatusBadge value={row.estado_editorial} tone={row.estado_editorial === 'publicado' ? 'blue' : 'amber'} /> : '—'}</td>
                    <td>{row.nemonico_raw ?? '—'}</td>
                    <td>{formatIssueList(row.validation_errors)}</td>
                    <td>{formatIssueList(row.validation_warnings)}</td>
                  </tr>
                ))}
                {batchRows.length === 0 ? (
                  <tr><td colSpan={7}>No hay filas de staging cargadas para este batch.</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function AdminGftPage() {
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [authChecking, setAuthChecking] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [summary, setSummary] = useState<GFTEditorialAdminSummaryResponse | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [estadoGft, setEstadoGft] = useState('');
  const [estadoEditorial, setEstadoEditorial] = useState('');
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  const [listData, setListData] = useState<GFTEditorialAdminListResponse | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(false);

  const [selectedCn, setSelectedCn] = useState<string | null>(null);
  const [detail, setDetail] = useState<GFTEditorialAdminResponse | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [isEditingClinicalInfo, setIsEditingClinicalInfo] = useState(false);
  const [editorialForm, setEditorialForm] = useState<EditorialFormState | null>(null);
  const [isEditingPublicationState, setIsEditingPublicationState] = useState(false);
  const [publicationStateForm, setPublicationStateForm] = useState<PublicationStateFormState | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [stateSaveLoading, setStateSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [stateSaveError, setStateSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [stateSaveSuccess, setStateSaveSuccess] = useState<string | null>(null);

  const checkAccess = useCallback(async (candidateKey: string, persist: boolean) => {
    const cleanKey = candidateKey.trim();

    if (!cleanKey) {
      setAuthError('Introduce la clave API admin.');
      return;
    }

    setAuthChecking(true);
    setAuthError(null);

    try {
      await adminHealth(cleanKey);
      setApiKey(cleanKey);
      setApiKeyInput(cleanKey);

      if (persist) {
        sessionStorage.setItem(ADMIN_SESSION_KEY, cleanKey);
      }
    } catch (error) {
      setApiKey(null);
      setAuthError(error instanceof Error ? error.message : 'No se pudo comprobar el acceso admin.');
      sessionStorage.removeItem(ADMIN_SESSION_KEY);
    } finally {
      setAuthChecking(false);
    }
  }, []);

  useEffect(() => {
    const storedKey = sessionStorage.getItem(ADMIN_SESSION_KEY);

    if (storedKey) {
      void checkAccess(storedKey, true);
    }
  }, [checkAccess]);

  const loadSummary = useCallback(async (activeKey: string) => {
    setSummaryLoading(true);
    setSummaryError(null);

    try {
      setSummary(await getGftEditorialSummary(activeKey));
    } catch (error) {
      setSummaryError(error instanceof Error ? error.message : 'No se pudo cargar el resumen editorial.');
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const loadList = useCallback(
    async (activeKey: string) => {
      setListLoading(true);
      setListError(null);

      try {
        setListData(
          await listGftEditorialMedicamentos(activeKey, {
            q,
            estado_gft: estadoGft,
            estado_editorial: estadoEditorial,
            limit,
            offset,
          }),
        );
      } catch (error) {
        setListError(error instanceof Error ? error.message : 'No se pudo cargar el listado admin.');
      } finally {
        setListLoading(false);
      }
    },
    [estadoEditorial, estadoGft, limit, offset, q],
  );

  useEffect(() => {
    if (!apiKey) {
      return;
    }

    void loadSummary(apiKey);
  }, [apiKey, loadSummary]);

  useEffect(() => {
    if (!apiKey) {
      return;
    }

    void loadList(apiKey);
  }, [apiKey, loadList]);

  const handleLogin = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void checkAccess(apiKeyInput, true);
  };

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setOffset(0);
    setQ(qInput.trim());
  };

  const handleSelect = async (cn: string) => {
    if (!apiKey) {
      return;
    }

    setSelectedCn(cn);
    setDetail(null);
    setDetailLoading(true);
    setDetailError(null);
    setIsEditingClinicalInfo(false);
    setEditorialForm(null);
    setIsEditingPublicationState(false);
    setPublicationStateForm(null);
    setSaveError(null);
    setStateSaveError(null);
    setSaveSuccess(null);
    setStateSaveSuccess(null);
    setSaveLoading(false);
    setStateSaveLoading(false);

    try {
      setDetail(await getGftEditorialMedicamento(apiKey, cn));
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'No se pudo cargar el detalle editorial.');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem(ADMIN_SESSION_KEY);
    setApiKey(null);
    setApiKeyInput('');
    setAuthError(null);
    setSummary(null);
    setListData(null);
    setDetail(null);
    setSelectedCn(null);
    setIsEditingClinicalInfo(false);
    setEditorialForm(null);
    setIsEditingPublicationState(false);
    setPublicationStateForm(null);
    setSaveError(null);
    setStateSaveError(null);
    setSaveSuccess(null);
    setStateSaveSuccess(null);
    setSaveLoading(false);
    setStateSaveLoading(false);
  };

  const handleStartEditingClinicalInfo = () => {
    if (!detail) {
      return;
    }

    setEditorialForm(buildEditorialFormState(detail));
    setIsEditingClinicalInfo(true);
    setSaveError(null);
    setSaveSuccess(null);
    setStateSaveSuccess(null);
  };

  const handleCancelEditingClinicalInfo = () => {
    setEditorialForm(detail ? buildEditorialFormState(detail) : null);
    setIsEditingClinicalInfo(false);
    setSaveError(null);
  };

  const handleStartEditingPublicationState = () => {
    if (!detail) {
      return;
    }

    setPublicationStateForm(buildPublicationStateFormState(detail));
    setIsEditingPublicationState(true);
    setStateSaveError(null);
    setStateSaveSuccess(null);
    setSaveSuccess(null);
  };

  const handleCancelEditingPublicationState = () => {
    setPublicationStateForm(detail ? buildPublicationStateFormState(detail) : null);
    setIsEditingPublicationState(false);
    setStateSaveError(null);
  };

  const handlePublicationStateFormChange = <Field extends keyof PublicationStateFormState>(
    field: Field,
    value: PublicationStateFormState[Field],
  ) => {
    setPublicationStateForm((currentForm) => (currentForm ? { ...currentForm, [field]: value } : currentForm));
  };

  const handleEditorialFormChange = (field: EditableClinicalField, value: string) => {
    setEditorialForm((currentForm) => (currentForm ? { ...currentForm, [field]: value } : currentForm));
  };

  const handleSaveClinicalInfo = async () => {
    if (!apiKey || !detail || !editorialForm) {
      return;
    }

    setSaveLoading(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      const payload = buildEditorialPayload(detail, editorialForm);

      if (Object.keys(payload).length === 0) {
        setEditorialForm(buildEditorialFormState(detail));
        setIsEditingClinicalInfo(false);
        setSaveSuccess('No hay cambios clínicos/editoriales para guardar.');
        return;
      }

      await updateGftMedicationEditorial(apiKey, detail.cn, payload);
      const fullDetail = await getGftEditorialMedicamento(apiKey, detail.cn);

      setDetail(fullDetail);
      setEditorialForm(buildEditorialFormState(fullDetail));
      await loadList(apiKey);
      setIsEditingClinicalInfo(false);
      setSaveSuccess('Información clínica/editorial guardada correctamente.');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'No se pudieron guardar los cambios clínicos/editoriales.');
    } finally {
      setSaveLoading(false);
    }
  };

  const handleSavePublicationState = async () => {
    if (!apiKey || !detail || !publicationStateForm) {
      return;
    }

    setStateSaveLoading(true);
    setStateSaveError(null);
    setStateSaveSuccess(null);

    try {
      if (publicationStateForm.estado_editorial === 'publicado' && publicationStateForm.estado_gft !== 'incluido') {
        setStateSaveError('Solo se puede publicar un medicamento incluido en guía.');
        return;
      }

      const payload = buildPublicationStatePayload(detail, publicationStateForm);

      if (Object.keys(payload).length === 0) {
        setStateSaveError('No hay cambios de estado para guardar.');
        return;
      }

      const wasPublic = isPubliclyVisible(detail.estado_gft, detail.estado_editorial);
      const willBePublic = isPubliclyVisible(publicationStateForm.estado_gft, publicationStateForm.estado_editorial);

      if (!window.confirm(getStateChangeConfirmationMessage(detail, publicationStateForm))) {
        return;
      }

      await updateGftMedicationState(apiKey, detail.cn, payload);
      const fullDetail = await getGftEditorialMedicamento(apiKey, detail.cn);

      setDetail(fullDetail);
      setPublicationStateForm(buildPublicationStateFormState(fullDetail));
      await loadSummary(apiKey);
      await loadList(apiKey);
      setIsEditingPublicationState(false);
      setStateSaveSuccess(getStateSaveSuccessMessage(wasPublic, willBePublic));
    } catch (error) {
      setStateSaveError(error instanceof Error ? error.message : 'No se pudo guardar el estado de publicación.');
    } finally {
      setStateSaveLoading(false);
    }
  };

  const summaryCards = useMemo(
    () => [
      ['Total', summary?.total ?? 0, 'Registros administrativos'],
      ['Incluidos', summary?.by_estado_gft.incluido ?? 0, 'Estado GFT incluido'],
      ['Excluidos', summary?.excluidos ?? 0, 'Estado GFT excluido'],
      ['Pendientes', summary?.pendientes_revision ?? 0, 'Pendientes de revisión GFT'],
      ['Publicados', summary?.publicados_en_gft ?? 0, 'Incluidos y publicados'],
      ['Borradores', summaryValue(summary, 'borrador'), 'Estado editorial borrador'],
      ['Validados', summaryValue(summary, 'validado'), 'Estado editorial validado'],
      ['Incluidos no publicados', summary?.incluidos_no_publicados ?? 0, 'Requieren publicación editorial'],
    ],
    [summary],
  );

  const total = listData?.total ?? 0;
  const canGoBack = offset > 0;
  const canGoForward = listData ? offset + listData.limit < listData.total : false;
  const detailIsPubliclyVisible = detail ? isPubliclyVisible(detail.estado_gft, detail.estado_editorial) : false;

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div className="admin-header__content">
          <p className="admin-header__eyebrow">Panel interno</p>
          <div className="admin-header__title-row">
            <h1>Panel admin GFT</h1>
            <span className="admin-mode-badge">Modo administración</span>
          </div>
          <p>Los cambios pueden afectar a la publicación de la guía.</p>
        </div>
        <div className="admin-header__actions">
          <a className="admin-button admin-button--public-link" href="/">
            Ver GFT pública
          </a>
          {apiKey ? (
            <button className="admin-button admin-button--secondary" type="button" onClick={handleLogout}>
              Olvidar clave
            </button>
          ) : null}
        </div>
      </header>

      {!apiKey ? (
        <main className="admin-main admin-main--login">
          <form className="admin-login" onSubmit={handleLogin}>
            <div>
              <h2>Acceso restringido</h2>
              <p>Introduce la API key de administración para comprobar el acceso. La clave solo se conserva en la sesión del navegador.</p>
            </div>
            <label>
              API key admin
              <input
                autoComplete="off"
                type="password"
                value={apiKeyInput}
                onChange={(event) => setApiKeyInput(event.target.value)}
                placeholder="X-Admin-API-Key"
              />
            </label>
            {authError ? <p className="admin-alert admin-alert--error">{authError}</p> : null}
            <button className="admin-button admin-button--primary" type="submit" disabled={authChecking}>
              {authChecking ? 'Comprobando…' : 'Comprobar acceso'}
            </button>
          </form>
        </main>
      ) : (
        <main className="admin-main">
          <section className="admin-section" aria-labelledby="admin-summary-title">
            <div className="admin-section__header">
              <div>
                <h2 id="admin-summary-title">Resumen editorial</h2>
                <p>Indicadores de publicación y revisión de la guía.</p>
              </div>
              <button className="admin-button admin-button--secondary" type="button" onClick={() => void loadSummary(apiKey)}>
                Actualizar resumen
              </button>
            </div>
            {summaryError ? <p className="admin-alert admin-alert--error">{summaryError}</p> : null}
            <div className="admin-summary-grid" aria-busy={summaryLoading}>
              {summaryCards.map(([label, value, description]) => (
                <article className="admin-summary-card" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{description}</small>
                </article>
              ))}
            </div>
            {summary && Object.keys(summary.by_combination).length > 0 ? (
              <details className="admin-combinations">
                <summary>Ver combinaciones estado GFT / editorial</summary>
                <div>
                  {Object.entries(summary.by_combination).map(([key, value]) => (
                    <span key={key}>{formatLabel(key.replace('|', ' / '))}: {value}</span>
                  ))}
                </div>
              </details>
            ) : null}
          </section>

          <AdminExcelImportSection
            apiKey={apiKey}
            onApplied={async () => {
              await loadSummary(apiKey);
              await loadList(apiKey);
              if (selectedCn) {
                await handleSelect(selectedCn);
              }
            }}
          />

          <section className="admin-section" aria-labelledby="admin-list-title">
            <div className="admin-section__header">
              <div>
                <h2 id="admin-list-title">Medicamentos administrativos</h2>
                <p>{total} registros encontrados.</p>
              </div>
            </div>

            <form className="admin-toolbar" onSubmit={handleSearch}>
              <label>
                Buscar
                <input
                  value={qInput}
                  onChange={(event) => setQInput(event.target.value)}
                  placeholder="CN, nemónico o campos editoriales"
                />
              </label>
              <label>
                Estado GFT
                <select
                  value={estadoGft}
                  onChange={(event) => {
                    setOffset(0);
                    setEstadoGft(event.target.value);
                  }}
                >
                  <option value="">Todos</option>
                  {ESTADO_GFT_OPTIONS.map((estado) => <option key={estado} value={estado}>{formatLabel(estado)}</option>)}
                </select>
              </label>
              <label>
                Estado editorial
                <select
                  value={estadoEditorial}
                  onChange={(event) => {
                    setOffset(0);
                    setEstadoEditorial(event.target.value);
                  }}
                >
                  <option value="">Todos</option>
                  {ESTADO_EDITORIAL_OPTIONS.map((estado) => <option key={estado} value={estado}>{formatLabel(estado)}</option>)}
                </select>
              </label>
              <label>
                Límite
                <select
                  value={limit}
                  onChange={(event) => {
                    setOffset(0);
                    setLimit(Number(event.target.value));
                  }}
                >
                  {[25, 50, 100, 200].map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <button className="admin-button admin-button--primary" type="submit">Aplicar</button>
            </form>

            {listError ? <p className="admin-alert admin-alert--error">{listError}</p> : null}

            <div className="admin-content-grid">
              <div className="admin-table-card">
                <table className="admin-table" aria-busy={listLoading}>
                  <thead>
                    <tr>
                      <th>CN</th>
                      <th>Nombre comercial</th>
                      <th>Principio activo</th>
                      <th>Nemónico</th>
                      <th>Estado GFT</th>
                      <th>Estado editorial</th>
                      <th>Fecha revisión</th>
                    </tr>
                  </thead>
                  <tbody>
                    {listData?.items.map((item) => (
                      <tr
                        className={selectedCn === item.cn ? 'admin-table__row--selected' : ''}
                        key={item.cn}
                        onClick={() => void handleSelect(item.cn)}
                      >
                        <td><button type="button" onClick={(event) => { event.stopPropagation(); void handleSelect(item.cn); }}>{item.cn}</button></td>
                        <td><EmptyValue value={item.nombre_comercial} /></td>
                        <td><EmptyValue value={item.principio_activo} /></td>
                        <td><EmptyValue value={item.nemonico} /></td>
                        <td><StatusBadge value={item.estado_gft} tone={item.estado_gft === 'incluido' ? 'green' : 'neutral'} /></td>
                        <td><StatusBadge value={item.estado_editorial} tone={item.estado_editorial === 'publicado' ? 'blue' : 'amber'} /></td>
                        <td>{formatDate(item.fecha_revision)}</td>
                      </tr>
                    ))}
                    {!listLoading && listData?.items.length === 0 ? (
                      <tr>
                        <td colSpan={7}>No hay medicamentos con los filtros seleccionados.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
                {listLoading ? <p className="admin-muted admin-loading">Cargando listado…</p> : null}
                <div className="admin-pagination">
                  <button
                    className="admin-button admin-button--secondary"
                    type="button"
                    disabled={!canGoBack || listLoading}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                  >
                    Anterior
                  </button>
                  <span>{total === 0 ? '0' : offset + 1}–{Math.min(offset + limit, total)} de {total}</span>
                  <button
                    className="admin-button admin-button--secondary"
                    type="button"
                    disabled={!canGoForward || listLoading}
                    onClick={() => setOffset(offset + limit)}
                  >
                    Siguiente
                  </button>
                </div>
              </div>

              <aside className="admin-detail-panel" aria-live="polite">
                <div className="admin-detail-panel__header">
                  <h2>Detalle editorial</h2>
                  {selectedCn ? <span>CN {selectedCn}</span> : null}
                </div>
                {!selectedCn ? <p className="admin-muted">Selecciona un medicamento para ver el detalle editorial.</p> : null}
                {detailLoading ? <p className="admin-muted">Cargando detalle…</p> : null}
                {detailError ? <p className="admin-alert admin-alert--error">{detailError}</p> : null}
                {detail ? (
                  <div className="admin-detail-content">
                    <div className={`admin-public-visibility admin-public-visibility--${detailIsPubliclyVisible ? 'visible' : 'hidden'}`}>
                      {detailIsPubliclyVisible
                        ? 'Este medicamento es visible en la GFT pública.'
                        : 'Este medicamento no es visible actualmente en la GFT pública.'}
                    </div>
                    <section className="admin-detail-block admin-detail-block--identification">
                      <h3>Identificación</h3>
                      <dl>
                        <dt>CN</dt><dd>{detail.cn}</dd>
                        <dt>Nombre comercial</dt><dd><EmptyValue value={detail.nombre_comercial} /></dd>
                        <dt>Principio activo</dt><dd><EmptyValue value={detail.principio_activo} /></dd>
                        <dt>Forma farmacéutica</dt><dd><EmptyValue value={detail.forma_farmaceutica} /></dd>
                        <dt>Vía administración</dt><dd><EmptyValue value={detail.via_administracion} /></dd>
                        <dt>Código ATC</dt><dd><EmptyValue value={detail.codigo_atc} /></dd>
                        <dt>Nemónico</dt><dd><EmptyValue value={detail.nemonico} /></dd>
                      </dl>
                    </section>
                    <section className="admin-detail-block admin-publication-state">
                      <div className="admin-publication-state__header">
                        <div>
                          <h3>Estado de publicación</h3>
                          <p>Gestión separada de estados GFT/editoriales mediante el endpoint de estado.</p>
                        </div>
                        {!isEditingPublicationState ? (
                          <button className="admin-button admin-button--secondary" type="button" onClick={handleStartEditingPublicationState}>
                            Cambiar estado
                          </button>
                        ) : null}
                      </div>

                      {stateSaveSuccess ? <p className="admin-alert admin-alert--success">{stateSaveSuccess}</p> : null}
                      {stateSaveError ? <p className="admin-alert admin-alert--error">{stateSaveError}</p> : null}
                      {publicationStateForm?.estado_editorial === 'publicado' ? (
                        <p className="admin-alert admin-alert--warning">Publicar hace visible el medicamento en la GFT pública solo si el estado GFT es incluido.</p>
                      ) : null}
                      {publicationStateForm?.estado_editorial === 'retirado' ? (
                        <p className="admin-alert admin-alert--warning">Retirar deja el medicamento fuera de la publicación pública aunque esté incluido en guía.</p>
                      ) : null}

                      {isEditingPublicationState && publicationStateForm ? (
                        <div className="admin-publication-state-form" aria-busy={stateSaveLoading}>
                          <label className="admin-publication-state-form__field">
                            Estado GFT
                            <select
                              value={publicationStateForm.estado_gft}
                              onChange={(event) => handlePublicationStateFormChange('estado_gft', event.target.value as GFTPublicationGftState)}
                              disabled={stateSaveLoading}
                            >
                              {ESTADO_GFT_OPTIONS.map((estado) => <option key={estado} value={estado}>{formatLabel(estado)}</option>)}
                            </select>
                          </label>
                          <label className="admin-publication-state-form__field">
                            Estado editorial
                            <select
                              value={publicationStateForm.estado_editorial}
                              onChange={(event) => handlePublicationStateFormChange('estado_editorial', event.target.value as GFTPublicationEditorialState)}
                              disabled={stateSaveLoading}
                            >
                              {ESTADO_EDITORIAL_OPTIONS.map((estado) => <option key={estado} value={estado}>{formatLabel(estado)}</option>)}
                            </select>
                          </label>
                          <label className="admin-publication-state-form__field admin-publication-state-form__field--wide">
                            Comentario de revisión
                            <textarea
                              value={publicationStateForm.comentario_revision}
                              onChange={(event) => handlePublicationStateFormChange('comentario_revision', event.target.value)}
                              disabled={stateSaveLoading}
                              rows={4}
                            />
                          </label>
                          <label className="admin-publication-state-form__field admin-publication-state-form__field--wide">
                            Revisado por
                            <input
                              type="text"
                              value={publicationStateForm.revisado_por}
                              onChange={(event) => handlePublicationStateFormChange('revisado_por', event.target.value)}
                              disabled={stateSaveLoading}
                            />
                          </label>
                          <div className="admin-publication-state-form__actions">
                            <button className="admin-button admin-button--primary" type="button" onClick={() => void handleSavePublicationState()} disabled={stateSaveLoading}>
                              {stateSaveLoading ? 'Guardando…' : 'Guardar estado'}
                            </button>
                            <button className="admin-button admin-button--secondary" type="button" onClick={handleCancelEditingPublicationState} disabled={stateSaveLoading}>
                              Cancelar
                            </button>
                            {stateSaveLoading ? <span className="admin-save-status">Guardando estado de publicación…</span> : null}
                          </div>
                        </div>
                      ) : (
                        <dl>
                          <dt>Estado GFT</dt><dd><StatusBadge value={detail.estado_gft} tone={detail.estado_gft === 'incluido' ? 'green' : 'neutral'} /></dd>
                          <dt>Estado editorial</dt><dd><StatusBadge value={detail.estado_editorial} tone={detail.estado_editorial === 'publicado' ? 'blue' : 'amber'} /></dd>
                          <dt>Comentario de revisión</dt><dd><EmptyValue value={detail.comentario_revision} /></dd>
                          <dt>Revisado por</dt><dd><EmptyValue value={detail.revisado_por} /></dd>
                          <dt>Fecha revisión</dt><dd>{formatDate(detail.fecha_revision)}</dd>
                        </dl>
                      )}
                    </section>
                    <section className="admin-detail-block admin-clinical-editor">
                      <div className="admin-clinical-editor__header">
                        <div>
                          <h3>Campos clínicos/editoriales</h3>
                          <p>Edición controlada de información clínica. Los datos identificativos y los estados se mantienen fuera de este formulario.</p>
                        </div>
                        {!isEditingClinicalInfo ? (
                          <button className="admin-button admin-button--secondary" type="button" onClick={handleStartEditingClinicalInfo}>
                            Editar información clínica
                          </button>
                        ) : null}
                      </div>

                      {saveSuccess ? <p className="admin-alert admin-alert--success">{saveSuccess}</p> : null}
                      {saveError ? <p className="admin-alert admin-alert--error">{saveError}</p> : null}

                      {isEditingClinicalInfo && editorialForm ? (
                        <div className="admin-clinical-form" aria-busy={saveLoading}>
                          {EDITABLE_CLINICAL_FIELDS.map((field) => (
                            <label className="admin-clinical-form__field" key={field.key}>
                              {field.label}
                              {field.control === 'textarea' ? (
                                <textarea
                                  value={editorialForm[field.key]}
                                  onChange={(event) => handleEditorialFormChange(field.key, event.target.value)}
                                  disabled={saveLoading}
                                  rows={4}
                                />
                              ) : (
                                <input
                                  type="text"
                                  value={editorialForm[field.key]}
                                  onChange={(event) => handleEditorialFormChange(field.key, event.target.value)}
                                  disabled={saveLoading}
                                />
                              )}
                            </label>
                          ))}
                          <div className="admin-clinical-form__actions">
                            <button className="admin-button admin-button--primary" type="button" onClick={() => void handleSaveClinicalInfo()} disabled={saveLoading}>
                              {saveLoading ? 'Guardando…' : 'Guardar cambios'}
                            </button>
                            <button className="admin-button admin-button--secondary" type="button" onClick={handleCancelEditingClinicalInfo} disabled={saveLoading}>
                              Cancelar
                            </button>
                            {saveLoading ? <span className="admin-save-status">Guardando información clínica…</span> : null}
                          </div>
                        </div>
                      ) : (
                        <dl>
                          <dt>Restricciones hospitalarias</dt><dd><EmptyValue value={detail.restricciones_hospitalarias} /></dd>
                          <dt>Ajuste insuficiencia renal</dt><dd><EmptyValue value={detail.ajuste_insuficiencia_renal} /></dd>
                          <dt>Ajuste insuficiencia hepática</dt><dd><EmptyValue value={detail.ajuste_insuficiencia_hepatica} /></dd>
                          <dt>Precauciones embarazo</dt><dd><EmptyValue value={detail.precauciones_embarazo} /></dd>
                          <dt>Precauciones lactancia</dt><dd><EmptyValue value={detail.precauciones_lactancia} /></dd>
                          <dt>Observaciones internas</dt><dd><EmptyValue value={detail.observaciones_internas} /></dd>
                        </dl>
                      )}
                    </section>
                    <section className="admin-detail-block admin-detail-block--metadata">
                      <h3>Metadatos</h3>
                      <dl>
                        <dt>Actualizado</dt><dd>{formatDateTime(detail.updated_at)}</dd>
                        <dt>Lote importación</dt><dd><EmptyValue value={detail.last_import_batch_id} /></dd>
                        <dt>Importado</dt><dd>{formatDateTime(detail.last_imported_at)}</dd>
                      </dl>
                    </section>
                  </div>
                ) : null}
              </aside>
            </div>
          </section>
        </main>
      )}
    </div>
  );
}
