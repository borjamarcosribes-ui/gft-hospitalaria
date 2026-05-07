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
  restricciones_hospitalarias: string | null;
  situacion_financiacion: string | null;
  url_ficha_tecnica: string | null;
  url_prospecto: string | null;
  fecha_ficha_tecnica: string | null;
  fecha_prospecto: string | null;
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
