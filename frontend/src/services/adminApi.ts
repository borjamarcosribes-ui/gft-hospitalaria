import type {
  AdminHealthResponse,
  GFTEditorialAdminListResponse,
  GFTEditorialAdminResponse,
  GFTEditorialAdminSummaryResponse,
  ListGftEditorialMedicamentosParams,
} from '../types/admin';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

function buildUrl(path: string): URL {
  const baseUrl = API_BASE_URL.trim();

  if (baseUrl) {
    return new URL(path, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  }

  return new URL(path, window.location.origin);
}

function buildAdminHeaders(apiKey: string): HeadersInit {
  return {
    Accept: 'application/json',
    'X-Admin-API-Key': apiKey,
  };
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

async function fetchAdminJson<T>(pathOrUrl: string | URL, apiKey: string): Promise<T> {
  const response = await fetch(pathOrUrl instanceof URL ? pathOrUrl.toString() : buildUrl(pathOrUrl).toString(), {
    headers: buildAdminHeaders(apiKey),
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);

    if (response.status === 401 || response.status === 403) {
      throw new Error('Clave admin ausente o inválida.');
    }

    if (response.status === 503) {
      throw new Error('El acceso admin no está configurado en el servidor.');
    }

    throw new Error(detail ?? `No se pudo completar la operación admin (${response.status}).`);
  }

  return response.json() as Promise<T>;
}

function setQueryParam(url: URL, key: string, value?: string) {
  const cleanValue = value?.trim();

  if (cleanValue) {
    url.searchParams.set(key, cleanValue);
  }
}

export function adminHealth(apiKey: string): Promise<AdminHealthResponse> {
  return fetchAdminJson<AdminHealthResponse>('/admin/health', apiKey);
}

export function getGftEditorialSummary(apiKey: string): Promise<GFTEditorialAdminSummaryResponse> {
  return fetchAdminJson<GFTEditorialAdminSummaryResponse>('/admin/gft/medicamentos/editorial/summary', apiKey);
}

export function listGftEditorialMedicamentos(
  apiKey: string,
  params: ListGftEditorialMedicamentosParams,
): Promise<GFTEditorialAdminListResponse> {
  const url = buildUrl('/admin/gft/medicamentos/editorial');
  url.searchParams.set('limit', String(params.limit));
  url.searchParams.set('offset', String(params.offset));
  setQueryParam(url, 'q', params.q);
  setQueryParam(url, 'estado_gft', params.estado_gft);
  setQueryParam(url, 'estado_editorial', params.estado_editorial);

  return fetchAdminJson<GFTEditorialAdminListResponse>(url, apiKey);
}

export function getGftEditorialMedicamento(apiKey: string, cn: string): Promise<GFTEditorialAdminResponse> {
  return fetchAdminJson<GFTEditorialAdminResponse>(`/admin/gft/medicamentos/${encodeURIComponent(cn)}/editorial`, apiKey);
}
