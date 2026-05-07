import { getPaginationRange } from '../../utils/pagination';

interface GftPaginationProps {
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  onPageChange: (offset: number) => void;
}

export function GftPagination({ total, limit, offset, loading, onPageChange }: GftPaginationProps) {
  const range = getPaginationRange(total, limit, offset);

  if (total <= 0) {
    return null;
  }

  return (
    <nav className="gft-pagination" aria-label="Paginación de medicamentos">
      <p>
        Mostrando {range.from}-{range.to} de {total}
      </p>
      <div className="gft-pagination__buttons">
        <button
          className="gft-button gft-button--secondary"
          type="button"
          disabled={!range.canPrevious || loading}
          onClick={() => onPageChange(Math.max(offset - limit, 0))}
        >
          Anterior
        </button>
        <button
          className="gft-button gft-button--secondary"
          type="button"
          disabled={!range.canNext || loading}
          onClick={() => onPageChange(offset + limit)}
        >
          Siguiente
        </button>
      </div>
    </nav>
  );
}
