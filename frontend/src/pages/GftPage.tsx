import { useEffect, useMemo, useRef, useState } from 'react';
import { GftActiveFilters } from '../components/gft/GftActiveFilters';
import { GftAtcFilter } from '../components/gft/GftAtcFilter';
import { GftAtcIndex } from '../components/gft/GftAtcIndex';
import { GftAZFilter } from '../components/gft/GftAZFilter';
import { GftInstitutionalHeader } from '../components/gft/GftInstitutionalHeader';
import { GftMedicationList } from '../components/gft/GftMedicationList';
import { GftPagination } from '../components/gft/GftPagination';
import { GftPrincipioActivoFilter } from '../components/gft/GftPrincipioActivoFilter';
import { GftSearchBar } from '../components/gft/GftSearchBar';
import { getGftPdfExportUrl, getMedicamentoByCn, listAtcIndex, listMedicamentos, listPrincipiosActivos } from '../services/gftApi';
import type {
  GFTAtcIndexResponse,
  GFTListResponse,
  GFTMedicamentoDetail,
  GFTPrincipioActivoIndexResponse,
} from '../types/gft';

const PAGE_SIZE = 20;


function shouldAutoApplySearch(value: string): boolean {
  const cleanValue = value.trim();

  if (cleanValue.length === 0) {
    return true;
  }

  if (/^\d{3,}$/.test(cleanValue)) {
    return true;
  }

  return cleanValue.length >= 3;
}


export function GftPage() {
  const [q, setQ] = useState('');
  const [submittedQ, setSubmittedQ] = useState('');
  const [letra, setLetra] = useState('');
  const [principioActivo, setPrincipioActivo] = useState('');
  const [atc, setAtc] = useState('');
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<GFTListResponse | null>(null);
  const [principiosActivosData, setPrincipiosActivosData] = useState<GFTPrincipioActivoIndexResponse | null>(null);
  const [atcData, setAtcData] = useState<GFTAtcIndexResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filtersLoading, setFiltersLoading] = useState(false);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const [selectedCn, setSelectedCn] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<GFTMedicamentoDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRequestId = useRef(0);
  const pdfExportUrl = getGftPdfExportUrl();

  useEffect(() => {
    let ignore = false;

    async function loadFilters() {
      setFiltersLoading(true);
      setFiltersError(null);

      try {
        const [principiosActivosResponse, atcResponse] = await Promise.all([listPrincipiosActivos(), listAtcIndex()]);

        if (!ignore) {
          setPrincipiosActivosData(principiosActivosResponse);
          setAtcData(atcResponse);
        }
      } catch (caughtError) {
        if (!ignore) {
          setFiltersError(caughtError instanceof Error ? caughtError.message : 'Error inesperado al cargar filtros.');
        }
      } finally {
        if (!ignore) {
          setFiltersLoading(false);
        }
      }
    }

    loadFilters();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadMedicamentos() {
      setLoading(true);
      setError(null);

      try {
        const response = await listMedicamentos({
          q: submittedQ,
          letra,
          principio_activo: principioActivo,
          atc,
          limit: PAGE_SIZE,
          offset,
        });

        if (!ignore) {
          setData(response);
        }
      } catch (caughtError) {
        if (!ignore) {
          setError(caughtError instanceof Error ? caughtError.message : 'Error inesperado al cargar medicamentos.');
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadMedicamentos();

    return () => {
      ignore = true;
    };
  }, [submittedQ, letra, principioActivo, atc, offset]);

  const principioActivoLabel = useMemo(() => {
    return principiosActivosData?.items.find((item) => item.slug === principioActivo)?.nombre ?? '';
  }, [principiosActivosData, principioActivo]);

  const atcLabel = useMemo(() => {
    const selectedAtc = atcData?.items.find((item) => item.codigo === atc);

    if (!selectedAtc) {
      return '';
    }

    return selectedAtc.nombre ? `${selectedAtc.codigo} — ${selectedAtc.nombre}` : selectedAtc.codigo;
  }, [atcData, atc]);

  function handleSearch(value: string) {
    const cleanValue = value.trim();
    setQ(value);
    setSubmittedQ(cleanValue);
    setOffset(0);
  }

  useEffect(() => {
    const cleanValue = q.trim();

    if (!shouldAutoApplySearch(q)) {
      return;
    }

    if (cleanValue === submittedQ) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setSubmittedQ(cleanValue);
      setOffset(0);
    }, 400);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [q, submittedQ]);

  function handleClearQ() {
    setQ('');
    setSubmittedQ('');
    setOffset(0);
  }

  function handleLetraChange(value: string) {
    setLetra(value);
    setOffset(0);
  }

  function handlePrincipioActivoChange(value: string) {
    setPrincipioActivo(value);
    setOffset(0);
  }

  function handleAtcChange(value: string) {
    setAtc(value);
    setOffset(0);
  }

  function handleClearAllFilters() {
    setQ('');
    setSubmittedQ('');
    setLetra('');
    setPrincipioActivo('');
    setAtc('');
    setOffset(0);
  }

  async function handleViewDetail(cn: string) {
    const requestId = detailRequestId.current + 1;
    detailRequestId.current = requestId;
    setSelectedCn(cn);
    setSelectedDetail(null);
    setDetailError(null);
    setDetailLoading(true);

    try {
      const response = await getMedicamentoByCn(cn);
      if (detailRequestId.current === requestId) {
        setSelectedDetail(response);
      }
    } catch (caughtError) {
      if (detailRequestId.current === requestId) {
        setDetailError(caughtError instanceof Error ? caughtError.message : 'Error inesperado al cargar el detalle.');
      }
    } finally {
      if (detailRequestId.current === requestId) {
        setDetailLoading(false);
      }
    }
  }

  function handleCloseDetail() {
    detailRequestId.current += 1;
    setSelectedCn(null);
    setSelectedDetail(null);
    setDetailError(null);
    setDetailLoading(false);
  }

  return (
    <div className="gft-page">
      <GftInstitutionalHeader />

      <main className="gft-main">
        <section className="gft-panel gft-search-panel" aria-label="Búsqueda y exportación de medicamentos">
          <div className="gft-search-panel__content">
            <GftSearchBar value={q} loading={loading} onSearch={handleSearch} onClear={handleClearQ} />
            <p className="gft-search-panel__hint">La búsqueda se aplica automáticamente al escribir 3 o más caracteres. También puedes pulsar Buscar/Aplicar.</p>
            <aside className="gft-export" aria-label="Exportación de la GFT publicada">
              <a className="gft-button gft-button--export" href={pdfExportUrl}>
                Exportar PDF
              </a>
              <p>Descarga la guía completa publicada.</p>
            </aside>
          </div>
        </section>

        <section className="gft-panel gft-filters-panel" aria-label="Filtros de medicamentos">
          <div className="gft-filters-panel__header">
            <div>
              <h2>Filtros de la guía</h2>
              <p>Acota el listado por inicial del principio activo, principio activo concreto o grupo ATC.</p>
            </div>
          </div>
          <GftAZFilter activeLetter={letra} onChange={handleLetraChange} disabled={loading} />
          <div className="gft-filters-panel__selectors">
            <GftPrincipioActivoFilter
              items={principiosActivosData?.items ?? []}
              value={principioActivo}
              loading={filtersLoading}
              error={filtersError}
              onChange={handlePrincipioActivoChange}
            />
            <GftAtcFilter
              items={atcData?.items ?? []}
              value={atc}
              loading={filtersLoading}
              error={filtersError}
              onChange={handleAtcChange}
            />
          </div>
          <GftAtcIndex items={atcData?.items ?? []} selectedAtc={atc} onSelectAtc={handleAtcChange} />
        </section>

        <GftActiveFilters
          q={submittedQ}
          letra={letra}
          principioActivoLabel={principioActivoLabel}
          atcLabel={atcLabel}
          onClearQ={handleClearQ}
          onClearLetra={() => handleLetraChange('')}
          onClearPrincipioActivo={() => handlePrincipioActivoChange('')}
          onClearAtc={() => handleAtcChange('')}
          onClearAll={handleClearAllFilters}
        />

        <GftMedicationList
          data={data}
          loading={loading}
          error={error}
          selectedCn={selectedCn}
          selectedDetail={selectedDetail}
          detailLoading={detailLoading}
          detailError={detailError}
          onViewDetail={handleViewDetail}
          onCloseDetail={handleCloseDetail}
        />

        {data ? (
          <GftPagination
            total={data.total}
            limit={data.limit}
            offset={data.offset}
            loading={loading}
            onPageChange={setOffset}
          />
        ) : null}
      </main>
    </div>
  );
}
