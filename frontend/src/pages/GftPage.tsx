import { useEffect, useState } from 'react';
import { GftInstitutionalHeader } from '../components/gft/GftInstitutionalHeader';
import { GftMedicationList } from '../components/gft/GftMedicationList';
import { GftPagination } from '../components/gft/GftPagination';
import { GftSearchBar } from '../components/gft/GftSearchBar';
import { listMedicamentos } from '../services/gftApi';
import type { GFTListResponse } from '../types/gft';

const PAGE_SIZE = 20;

export function GftPage() {
  const [q, setQ] = useState('');
  const [submittedQ, setSubmittedQ] = useState('');
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<GFTListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function loadMedicamentos() {
      setLoading(true);
      setError(null);

      try {
        const response = await listMedicamentos({
          q: submittedQ,
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
  }, [submittedQ, offset]);

  function handleSearch(value: string) {
    setQ(value);
    setSubmittedQ(value);
    setOffset(0);
  }

  function handleClear() {
    setQ('');
    setSubmittedQ('');
    setOffset(0);
  }

  return (
    <div className="gft-page">
      <GftInstitutionalHeader />

      <main className="gft-main">
        <section className="gft-panel" aria-label="Búsqueda de medicamentos">
          <GftSearchBar value={q} loading={loading} onSearch={handleSearch} onClear={handleClear} />
        </section>

        {submittedQ ? (
          <p className="gft-active-query">
            Búsqueda activa: <strong>{submittedQ}</strong>
          </p>
        ) : null}

        <GftMedicationList data={data} loading={loading} error={error} />

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
