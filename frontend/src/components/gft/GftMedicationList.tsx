import { Fragment } from 'react';
import type { GFTListResponse, GFTMedicamentoDetail } from '../../types/gft';
import { GftMedicationCard } from './GftMedicationCard';
import { GftMedicationDetailPanel } from './GftMedicationDetailPanel';

interface GftMedicationListProps {
  data: GFTListResponse | null;
  loading: boolean;
  error: string | null;
  selectedCn: string | null;
  selectedDetail: GFTMedicamentoDetail | null;
  detailLoading: boolean;
  detailError: string | null;
  onViewDetail(cn: string): void;
  onCloseDetail(): void;
}

export function GftMedicationList({
  data,
  loading,
  error,
  selectedCn,
  selectedDetail,
  detailLoading,
  detailError,
  onViewDetail,
  onCloseDetail,
}: GftMedicationListProps) {
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
    return (
      <section className="gft-state">
        <strong>No hay medicamentos que coincidan con los filtros actuales.</strong>
        <p>Prueba a limpiar filtros o revisa la búsqueda por CN, nombre comercial o principio activo.</p>
      </section>
    );
  }

  return (
    <section className="gft-results" aria-live="polite">
      <div className="gft-results__summary">
        <h2>Medicamentos incluidos</h2>
        <p>{data.total} resultado{data.total === 1 ? '' : 's'} encontrado{data.total === 1 ? '' : 's'}</p>
      </div>
      <div className="gft-results__list">
        {data.items.map((medicamento) => {
          const isSelected = selectedCn === medicamento.cn;

          return (
            <Fragment key={medicamento.cn}>
              <GftMedicationCard medicamento={medicamento} selected={isSelected} onViewDetail={onViewDetail} />
              {isSelected ? (
                <GftMedicationDetailPanel
                  cn={selectedCn}
                  detail={selectedDetail}
                  loading={detailLoading}
                  error={detailError}
                  onClose={onCloseDetail}
                />
              ) : null}
            </Fragment>
          );
        })}
      </div>
    </section>
  );
}
