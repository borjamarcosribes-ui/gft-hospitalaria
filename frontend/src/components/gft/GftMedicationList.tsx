import type { GFTListResponse } from '../../types/gft';
import { GftMedicationCard } from './GftMedicationCard';

interface GftMedicationListProps {
  data: GFTListResponse | null;
  loading: boolean;
  error: string | null;
  onViewDetail(cn: string): void;
}

export function GftMedicationList({ data, loading, error, onViewDetail }: GftMedicationListProps) {
  if (loading && !data) {
    return <section className="gft-state">Cargando medicamentos de la guía…</section>;
  }

  if (error) {
    return (
      <section className="gft-state gft-state--error">
        <strong>No se pudo cargar la GFT.</strong>
        <span>{error}</span>
      </section>
    );
  }

  if (!data || data.items.length === 0) {
    return <section className="gft-state">Sin resultados para la búsqueda actual.</section>;
  }

  return (
    <section className="gft-results" aria-live="polite">
      <div className="gft-results__summary">
        <h2>Medicamentos incluidos</h2>
        <p>{data.total} resultado{data.total === 1 ? '' : 's'} encontrado{data.total === 1 ? '' : 's'}</p>
      </div>
      <div className="gft-results__list">
        {data.items.map((medicamento) => (
          <GftMedicationCard key={medicamento.cn} medicamento={medicamento} onViewDetail={onViewDetail} />
        ))}
      </div>
    </section>
  );
}
