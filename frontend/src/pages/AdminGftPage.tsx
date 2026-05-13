import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import {
  adminHealth,
  getGftEditorialMedicamento,
  getGftEditorialSummary,
  listGftEditorialMedicamentos,
} from '../services/adminApi';
import type {
  GFTEditorialAdminListResponse,
  GFTEditorialAdminResponse,
  GFTEditorialAdminSummaryResponse,
} from '../types/admin';

const ADMIN_SESSION_KEY = 'gft-admin-api-key';
const DEFAULT_LIMIT = 50;
const ESTADO_GFT_OPTIONS = ['incluido', 'excluido', 'pendiente_revision'];
const ESTADO_EDITORIAL_OPTIONS = ['borrador', 'validado', 'publicado', 'retirado'];

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

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div>
          <p className="admin-header__eyebrow">Panel interno</p>
          <h1>Administración GFT</h1>
          <p>Panel interno de revisión editorial y publicación</p>
        </div>
        {apiKey ? (
          <button className="admin-button admin-button--secondary" type="button" onClick={handleLogout}>
            Olvidar clave
          </button>
        ) : null}
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
                        <td><span className="admin-muted">No disponible en endpoint admin</span></td>
                        <td><span className="admin-muted">No disponible en endpoint admin</span></td>
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
                    <section>
                      <h3>Datos identificativos</h3>
                      <dl>
                        <dt>CN</dt><dd>{detail.cn}</dd>
                        <dt>Nemónico</dt><dd><EmptyValue value={detail.nemonico} /></dd>
                      </dl>
                    </section>
                    <section>
                      <h3>Estados</h3>
                      <dl>
                        <dt>Estado GFT</dt><dd><StatusBadge value={detail.estado_gft} tone={detail.estado_gft === 'incluido' ? 'green' : 'neutral'} /></dd>
                        <dt>Estado editorial</dt><dd><StatusBadge value={detail.estado_editorial} tone={detail.estado_editorial === 'publicado' ? 'blue' : 'amber'} /></dd>
                      </dl>
                    </section>
                    <section>
                      <h3>Campos clínicos/editoriales</h3>
                      <dl>
                        <dt>Restricciones hospitalarias</dt><dd><EmptyValue value={detail.restricciones_hospitalarias} /></dd>
                        <dt>Ajuste insuficiencia renal</dt><dd><EmptyValue value={detail.ajuste_insuficiencia_renal} /></dd>
                        <dt>Ajuste insuficiencia hepática</dt><dd><EmptyValue value={detail.ajuste_insuficiencia_hepatica} /></dd>
                        <dt>Precauciones embarazo</dt><dd><EmptyValue value={detail.precauciones_embarazo} /></dd>
                        <dt>Precauciones lactancia</dt><dd><EmptyValue value={detail.precauciones_lactancia} /></dd>
                        <dt>Observaciones internas</dt><dd><EmptyValue value={detail.observaciones_internas} /></dd>
                      </dl>
                    </section>
                    <section>
                      <h3>Metadatos de revisión</h3>
                      <dl>
                        <dt>Revisado por</dt><dd><EmptyValue value={detail.revisado_por} /></dd>
                        <dt>Fecha revisión</dt><dd>{formatDate(detail.fecha_revision)}</dd>
                        <dt>Actualizado</dt><dd>{formatDateTime(detail.updated_at)}</dd>
                        <dt>Lote importación</dt><dd><EmptyValue value={detail.last_import_batch_id} /></dd>
                        <dt>Importado</dt><dd>{formatDateTime(detail.last_imported_at)}</dd>
                      </dl>
                    </section>
                    {detail.comentario_revision ? (
                      <section className="admin-comment">
                        <h3>Comentario de revisión</h3>
                        <p>{detail.comentario_revision}</p>
                      </section>
                    ) : null}
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
