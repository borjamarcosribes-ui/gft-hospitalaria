import type {
  ApplyImportBatchResponse,
  AdminHealthResponse,
  GFTEditorialAdminListResponse,
  GFTEditorialAdminResponse,
  GFTEditorialAdminSummaryResponse,
  GFTEditorialUpdatePayload,
  GFTEditorialUpdateResponse,
  GFTPublicationStateUpdatePayload,
  GFTPublicationBulkStateUpdatePayload,
  GFTPublicationBulkStateUpdateResponse,
  GFTPublicationStateUpdateResponse,
  ImportBatchResponse,
  ImportBatchSummary,
  ImportDryRunResponse,
  ImportExcelOptions,
  ImportRowStaging,
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

function buildAdminJsonHeaders(apiKey: string): HeadersInit {
  return {
    ...buildAdminHeaders(apiKey),
    'Content-Type': 'application/json',
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

async function handleAdminResponse<T>(response: Response): Promise<T> {
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

async function fetchAdminJson<T>(pathOrUrl: string | URL, apiKey: string): Promise<T> {
  const response = await fetch(pathOrUrl instanceof URL ? pathOrUrl.toString() : buildUrl(pathOrUrl).toString(), {
    headers: buildAdminHeaders(apiKey),
  });

  return handleAdminResponse<T>(response);
}

async function patchAdminJson<T>(path: string, apiKey: string, body: unknown): Promise<T> {
  const response = await fetch(buildUrl(path).toString(), {
    method: 'PATCH',
    headers: buildAdminJsonHeaders(apiKey),
    body: JSON.stringify(body),
  });

  return handleAdminResponse<T>(response);
}

async function postAdminJson<T>(path: string, apiKey: string): Promise<T> {
  const response = await fetch(buildUrl(path).toString(), {
    method: 'POST',
    headers: buildAdminHeaders(apiKey),
  });

  return handleAdminResponse<T>(response);
}

async function postAdminForm<T>(path: string, apiKey: string, formData: FormData): Promise<T> {
  const response = await fetch(buildUrl(path).toString(), {
    method: 'POST',
    headers: buildAdminHeaders(apiKey),
    body: formData,
  });

  return handleAdminResponse<T>(response);
}

function buildExcelFormData(file: File, options: ImportExcelOptions = {}): FormData {
  const formData = new FormData();
  formData.append('file', file);

  const sheetName = options.sheet_name?.trim();
  if (sheetName) {
    formData.append('sheet_name', sheetName);
  }

  if (options.header_row !== undefined) {
    formData.append('header_row', String(options.header_row));
  }

  if (options.default_estado_editorial) {
    formData.append('default_estado_editorial', options.default_estado_editorial);
  }

  return formData;
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
  setQueryParam(url, 'quality_filter', params.quality_filter);

  return fetchAdminJson<GFTEditorialAdminListResponse>(url, apiKey);
}

export function getGftEditorialMedicamento(apiKey: string, cn: string): Promise<GFTEditorialAdminResponse> {
  return fetchAdminJson<GFTEditorialAdminResponse>(`/admin/gft/medicamentos/${encodeURIComponent(cn)}/editorial`, apiKey);
}

export function updateGftMedicationEditorial(
  apiKey: string,
  cn: string,
  payload: GFTEditorialUpdatePayload,
): Promise<GFTEditorialUpdateResponse> {
  return patchAdminJson<GFTEditorialUpdateResponse>(
    `/admin/gft/medicamentos/${encodeURIComponent(cn)}/editorial`,
    apiKey,
    payload,
  );
}

export function updateGftMedicationState(
  apiKey: string,
  cn: string,
  payload: GFTPublicationStateUpdatePayload,
): Promise<GFTPublicationStateUpdateResponse> {
  return patchAdminJson<GFTPublicationStateUpdateResponse>(
    `/admin/gft/medicamentos/${encodeURIComponent(cn)}/estado`,
    apiKey,
    payload,
  );
}

export function updateGftMedicationStateBulk(
  apiKey: string,
  payload: GFTPublicationBulkStateUpdatePayload,
): Promise<GFTPublicationBulkStateUpdateResponse> {
  return patchAdminJson<GFTPublicationBulkStateUpdateResponse>(
    '/admin/gft/medicamentos/estado/bulk',
    apiKey,
    payload,
  );
}

export function dryRunGftExcel(
  apiKey: string,
  file: File,
  options: ImportExcelOptions = {},
): Promise<ImportDryRunResponse> {
  return postAdminForm<ImportDryRunResponse>('/imports/excel/dry-run', apiKey, buildExcelFormData(file, options));
}

export function importGftExcel(
  apiKey: string,
  file: File,
  options: ImportExcelOptions = {},
): Promise<ImportBatchResponse> {
  return postAdminForm<ImportBatchResponse>('/imports/excel', apiKey, buildExcelFormData(file, options));
}

export function getImportBatchSummary(apiKey: string, batchId: string): Promise<ImportBatchSummary> {
  return fetchAdminJson<ImportBatchSummary>(`/imports/${encodeURIComponent(batchId)}/summary`, apiKey);
}

export function getImportBatchRows(
  apiKey: string,
  batchId: string,
  limit: number,
  offset: number,
): Promise<ImportRowStaging[]> {
  const url = buildUrl(`/imports/${encodeURIComponent(batchId)}/rows`);
  url.searchParams.set('limit', String(limit));
  url.searchParams.set('offset', String(offset));

  return fetchAdminJson<ImportRowStaging[]>(url, apiKey);
}

export function applyImportBatch(apiKey: string, batchId: string): Promise<ApplyImportBatchResponse> {
  return postAdminJson<ApplyImportBatchResponse>(`/imports/${encodeURIComponent(batchId)}/apply`, apiKey);
}
