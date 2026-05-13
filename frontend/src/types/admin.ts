export interface AdminHealthResponse {
  status: string;
}

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

export type GFTEditorialAdminDetail = GFTEditorialAdminResponse;

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

export interface ListGftEditorialMedicamentosParams {
  q?: string;
  estado_gft?: string;
  estado_editorial?: string;
  limit: number;
  offset: number;
}
