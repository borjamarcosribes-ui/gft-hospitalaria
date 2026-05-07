import type { GFTListResponse, ListMedicamentosParams } from '../types/gft';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

function buildUrl(path: string): URL {
  const baseUrl = API_BASE_URL.trim();

  if (baseUrl) {
    return new URL(path, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  }

  return new URL(path, window.location.origin);
}

export async function listMedicamentos(params: ListMedicamentosParams): Promise<GFTListResponse> {
  const url = buildUrl('/gft/medicamentos');
  url.searchParams.set('limit', String(params.limit));
  url.searchParams.set('offset', String(params.offset));

  const query = params.q?.trim();
  if (query) {
    url.searchParams.set('q', query);
  }

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
