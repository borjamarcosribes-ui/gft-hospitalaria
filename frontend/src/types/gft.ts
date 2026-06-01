export interface GFTPrincipioActivoRef {
  id: string | null;
  slug: string | null;
  nombre: string;
}

export interface GFTAtcRef {
  codigo: string;
  nombre: string | null;
  nivel: string | null;
}


export interface GFTCanonicalIndicacionBifimed {
  indicacion_autorizada: string | null;
  situacion_expediente_indicacion: string | null;
  resolucion_expediente_financiacion_indicacion: string | null;
  financiada?: boolean | null;
}

export interface GFTCanonicalPayload {
  cn: string;
  nombre_comercial: string | null;
  incluido_gft?: boolean | null;
  publicado?: boolean | null;
  observaciones_revision?: string | null;
  estado_publicacion?: string | null;
  principio_activo: string | null;
  forma_farmaceutica: string | null;
  via_administracion: string | null;
  nemonico: string | null;
  codigo_atc: string | null;
  descripcion_atc: string | null;
  jerarquia_atc: GFTAtcRef[];
  indicaciones_ficha_tecnica: string | null;
  url_ficha_tecnica?: string | null;
  url_prospecto?: string | null;
  estado_cima: 'disponible' | 'no_informado' | string;
  bifimed_cache_presente: boolean;
  situacion_financiacion_bifimed: string | null;
  condiciones_financiacion_restringidas: string | null;
  condiciones_especiales_financiacion: string | null;
  detalle_financiacion_json?: unknown;
  indicaciones_bifimed: GFTCanonicalIndicacionBifimed[];
  estado_bifimed: 'disponible' | 'no_informado' | 'sin_cache' | 'sin_indicaciones' | string;
  ajuste_insuficiencia_renal: string | null;
  ajuste_insuficiencia_hepatica: string | null;
  precauciones_embarazo: string | null;
  precauciones_lactancia: string | null;
  restricciones_hospitalarias: string | null;
  resumen_clinico_auto?: GFTResumenClinicoAuto | null;
  estado_resumen_clinico?: string | null;
  fuentes_disponibles: string[];
  campos_faltantes: string[];
  warnings: string[];
  data_quality_flags: string[];
}

export interface GFTMedicamentoListItem {
  cn: string;
  nombre: string | null;
  presentacion: string | null;
  forma_farmaceutica: string | null;
  forma_farmaceutica_simplificada: string | null;
  vias_administracion: string[];
  atc: GFTAtcRef[];
  principios_activos: GFTPrincipioActivoRef[];
  nemonico: string | null;
  indicaciones_ficha_tecnica: string | null;
  restricciones_hospitalarias: string | null;
  ajuste_insuficiencia_renal: string | null;
  ajuste_insuficiencia_hepatica: string | null;
  precauciones_embarazo: string | null;
  precauciones_lactancia: string | null;
  situacion_financiacion: string | null;
  url_ficha_tecnica: string | null;
  url_prospecto: string | null;
  fecha_ficha_tecnica: string | null;
  fecha_prospecto: string | null;
}

export interface GFTDocumentoCimaRef {
  tipo: number | string | null;
  url: string | null;
  urlHtml: string | null;
  secc: string | null;
  fecha: string | null;
  titulo: string | null;
  nombre: string | null;
}

export interface GFTIndicacionAutorizadaBifimed {
  indicacion_autorizada: string | null;
  situacion_expediente_indicacion: string | null;
  resolucion_expediente_financiacion_indicacion: string | null;
  financiada: boolean | null;
}

export interface GFTFinanciacionDetalle {
  situacion_financiacion: string | null;
  condiciones_financiacion_restringidas: string | null;
  condiciones_especiales_financiacion: string | null;
  estado_nomenclator: string | null;
  aportacion_usuario: string | null;
  subgrupo_atc: string | null;
  last_synced_at?: string | null;
  indicaciones_autorizadas?: GFTIndicacionAutorizadaBifimed[] | null;
}
export interface GFTResumenClinicoAuto {
  source_status: string;
  generated_at: string | null;
  resumen_general: string | null;
  indicaciones: string | null;
  posologia: string | null;
  ajuste_renal: string | null;
  ajuste_hepatico: string | null;
  contraindicaciones: string | null;
  advertencias: string | null;
  embarazo: string | null;
  lactancia: string | null;
  fuentes: Record<string, string[]>;
  warnings: string[];
}

export interface GFTMedicamentoDetail extends GFTMedicamentoListItem {
  observaciones_publicables: string | null;
  documentos: GFTDocumentoCimaRef[];
  financiacion_detalle: GFTFinanciacionDetalle | null;
  resumen_clinico_auto?: GFTResumenClinicoAuto | null;
  canonical_payload?: GFTCanonicalPayload | null;
}

export interface GFTListResponse {
  total: number;
  limit: number;
  offset: number;
  items: GFTMedicamentoListItem[];
}

export interface GFTAtcIndexItem {
  codigo: string;
  nombre: string | null;
  nivel: string;
  count: number;
}

export interface GFTAtcIndexResponse {
  items: GFTAtcIndexItem[];
}

export interface GFTPrincipioActivoIndexItem {
  id: string;
  slug: string;
  nombre: string;
  letra: string;
  count: number;
}

export interface GFTPrincipioActivoIndexResponse {
  items: GFTPrincipioActivoIndexItem[];
}

export interface ListMedicamentosParams {
  q?: string;
  letra?: string;
  principio_activo?: string;
  atc?: string;
  limit: number;
  offset: number;
}
