import type {
  GFTAtcIndexResponse,
  GFTListResponse,
  GFTMedicamentoDetail,
  GFTPrincipioActivoIndexResponse,
  ListMedicamentosParams,
} from '../types/gft';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

function buildUrl(path: string): URL {
  const baseUrl = API_BASE_URL.trim();

  if (baseUrl) {
    return new URL(path, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  }

  return new URL(path, window.location.origin);
}

export function getGftPdfExportUrl(): string {
  const exportPath = '/gft/export/pdf';
  const baseUrl = API_BASE_URL.trim();

  return baseUrl ? buildUrl(exportPath).toString() : exportPath;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(buildUrl(path).toString(), {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`No se pudo cargar la GFT (${response.status})`);
  }

  return response.json() as Promise<T>;
}

function setQueryParam(url: URL, key: string, value?: string) {
  const cleanValue = value?.trim();

  if (cleanValue) {
    url.searchParams.set(key, cleanValue);
  }
}

export async function listMedicamentos(params: ListMedicamentosParams): Promise<GFTListResponse> {
  const url = buildUrl('/gft/medicamentos');
  url.searchParams.set('limit', String(params.limit));
  url.searchParams.set('offset', String(params.offset));
  setQueryParam(url, 'q', params.q);
  setQueryParam(url, 'letra', params.letra);
  setQueryParam(url, 'principio_activo', params.principio_activo);
  setQueryParam(url, 'atc', params.atc);

  const response = await fetch(url.toString(), {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`No se pudo cargar la GFT (${response.status})`);
  }

  return response.json() as Promise<GFTListResponse>;
}

export function getMedicamentoByCn(cn: string): Promise<GFTMedicamentoDetail> {
  return fetchJson<GFTMedicamentoDetail>(`/gft/medicamentos/${encodeURIComponent(cn)}`);
}

export function listPrincipiosActivos(): Promise<GFTPrincipioActivoIndexResponse> {
  return fetchJson<GFTPrincipioActivoIndexResponse>('/gft/principios-activos');
}

export function listAtcIndex(): Promise<GFTAtcIndexResponse> {
  return fetchJson<GFTAtcIndexResponse>('/gft/atc');
}
