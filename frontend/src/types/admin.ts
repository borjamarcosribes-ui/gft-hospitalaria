export interface AdminHealthResponse {
  status: string;
}

export type GFTPublicationGftState = 'incluido' | 'excluido' | 'pendiente_revision';
export type GFTPublicationEditorialState = 'borrador' | 'validado' | 'publicado' | 'retirado';

export interface GFTEditorialAdminSummaryResponse {
  total: number;
  by_estado_gft: Record<string, number>;
  by_estado_editorial: Record<string, number>;
  by_combination: Record<string, number>;
  publicados_en_gft: number;
  incluidos_no_publicados: number;
  pendientes_revision: number;
  excluidos: number;
}

export interface GFTEditorialAdminListItem {
  cn: string;
  estado_gft: string;
  estado_editorial: string;
  nemonico: string | null;
  nombre_comercial: string | null;
  principio_activo: string | null;
  forma_farmaceutica: string | null;
  via_administracion: string | null;
  codigo_atc: string | null;
  restricciones_hospitalarias: string | null;
  ajuste_insuficiencia_renal: string | null;
  ajuste_insuficiencia_hepatica: string | null;
  precauciones_embarazo: string | null;
  precauciones_lactancia: string | null;
  revisado_por: string | null;
  fecha_revision: string | null;
  updated_at: string | null;
  last_import_batch_id: string | null;
  last_imported_at: string | null;
}

export interface GFTEditorialAdminListResponse {
  total: number;
  limit: number;
  offset: number;
  items: GFTEditorialAdminListItem[];
}

export interface GFTEditorialAdminResponse extends GFTEditorialAdminListItem {
  observaciones_internas: string | null;
  comentario_revision: string | null;
}

export interface GFTEditorialUpdatePayload {
  restricciones_hospitalarias?: string | null;
  ajuste_insuficiencia_renal?: string | null;
  ajuste_insuficiencia_hepatica?: string | null;
  precauciones_embarazo?: string | null;
  precauciones_lactancia?: string | null;
  observaciones_internas?: string | null;
  comentario_revision?: string | null;
  revisado_por?: string | null;
}

export interface GFTEditorialUpdateResponse {
  cn: string;
  restricciones_hospitalarias: string | null;
  ajuste_insuficiencia_renal: string | null;
  ajuste_insuficiencia_hepatica: string | null;
  precauciones_embarazo: string | null;
  precauciones_lactancia: string | null;
  observaciones_internas: string | null;
  comentario_revision: string | null;
  revisado_por: string | null;
  fecha_revision: string | null;
  updated_at: string | null;
}

export interface GFTPublicationStateUpdatePayload {
  estado_gft?: GFTPublicationGftState;
  estado_editorial?: GFTPublicationEditorialState;
  comentario_revision?: string | null;
  revisado_por?: string | null;
}

export interface GFTPublicationStateUpdateResponse {
  cn: string;
  estado_gft: GFTPublicationGftState;
  estado_editorial: GFTPublicationEditorialState;
  comentario_revision: string | null;
  revisado_por: string | null;
  fecha_revision: string | null;
  updated_at: string | null;
}

export interface ListGftEditorialMedicamentosParams {
  q?: string;
  estado_gft?: string;
  estado_editorial?: string;
  limit: number;
  offset: number;
}

export interface ImportDryRunIssue {
  row_number: number | null;
  code: string;
  message: string;
  cn_raw?: string | null;
}

export interface ImportDryRunPendingItem {
  row_number: number;
  cn: string | null;
  observaciones_revision_raw: string | null;
  reason: string;
}

export interface ImportDryRunDuplicateCn {
  cn: string;
  rows: number[];
}

export type ImportDefaultEditorialState = 'borrador' | 'validado' | 'publicado';

export interface ImportExcelOptions {
  sheet_name?: string;
  header_row?: number;
  default_estado_editorial?: ImportDefaultEditorialState;
}

export interface ImportDryRunResponse {
  dry_run: boolean;
  filename: string | null;
  sheet_name: string | number | null;
  sheet_names: string[];
  header_row: number;
  original_columns: string[];
  normalized_columns: string[];
  missing_required_columns: string[];
  column_suggestions: Record<string, string[]>;
  default_estado_editorial_used: ImportDefaultEditorialState | null;
  total_rows: number;
  included_count: number;
  excluded_count: number;
  pending_count: number;
  error_count: number;
  warning_count: number;
  duplicate_cn_count: number;
  column_mapping: Record<string, string>;
  errors: ImportDryRunIssue[];
  warnings: ImportDryRunIssue[];
  pending_items: ImportDryRunPendingItem[];
  duplicate_cn: ImportDryRunDuplicateCn[];
  rows?: Array<{
    row_number: number;
    cn_raw: string | null;
    cn: string | null;
    observaciones_revision_raw: string | null;
    estado_gft: string;
    errors: ImportDryRunIssue[];
    warnings: ImportDryRunIssue[];
  }>;
}

export interface ImportBatchResponse {
  batch_id: string;
  status: string;
  total_rows: number;
  processed_rows: number;
  ok_rows: number;
  error_rows: number;
  error_summary?: Record<string, unknown> | null;
}

export interface ImportBatchSummary {
  batch_id: string;
  status: string;
  filename: string;
  batch_total_rows: number;
  staging_total_rows: number;
  included_rows: number;
  excluded_rows: number;
  pending_rows: number;
  error_rows: number;
  warning_rows: number;
  applicable_rows: number;
  not_applicable_rows: number;
  skipped_errors: number;
  skipped_missing_cn: number;
  skipped_pending: number;
  skipped_missing_estado_editorial: number;
  duplicate_cn_count: number;
  duplicate_cn: ImportDryRunDuplicateCn[];
  pending_items: Array<{
    row_number: number;
    cn: string | null;
    observaciones_revision_raw: string | null;
    estado_editorial: string | null;
  }>;
  error_items: Array<{
    row_number: number;
    cn_raw: string | null;
    cn: string | null;
    validation_errors: string[];
  }>;
}

export interface ImportRowStaging {
  id: string;
  batch_id: string;
  row_number: number;
  cn_raw: string | null;
  cn_normalized: string | null;
  observaciones_revision_raw: string | null;
  estado_editorial_raw: string | null;
  nemonico_raw: string | null;
  estado_gft: string;
  estado_editorial: string | null;
  validation_errors: string[];
  validation_warnings: string[];
  created_at: string | null;
}

export interface ApplyImportBatchResponse {
  batch_id: string;
  total_rows: number;
  applied_rows: number;
  skipped_errors: number;
  skipped_missing_cn: number;
  skipped_pending: number;
  skipped_missing_estado_editorial: number;
}
