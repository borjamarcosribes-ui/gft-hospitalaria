interface GftActiveFiltersProps {
  q: string;
  letra: string;
  principioActivoLabel: string;
  atcLabel: string;
  onClearQ: () => void;
  onClearLetra: () => void;
  onClearPrincipioActivo: () => void;
  onClearAtc: () => void;
  onClearAll: () => void;
}

interface FilterChip {
  key: string;
  label: string;
  value: string;
  onClear: () => void;
}

export function GftActiveFilters({
  q,
  letra,
  principioActivoLabel,
  atcLabel,
  onClearQ,
  onClearLetra,
  onClearPrincipioActivo,
  onClearAtc,
  onClearAll,
}: GftActiveFiltersProps) {
  const chips: FilterChip[] = [
    q ? { key: 'q', label: 'Búsqueda', value: q, onClear: onClearQ } : null,
    letra ? { key: 'letra', label: 'Letra', value: letra, onClear: onClearLetra } : null,
    principioActivoLabel
      ? { key: 'principio-activo', label: 'Principio activo', value: principioActivoLabel, onClear: onClearPrincipioActivo }
      : null,
    atcLabel ? { key: 'atc', label: 'ATC', value: atcLabel, onClear: onClearAtc } : null,
  ].filter((chip): chip is FilterChip => chip !== null);

  if (chips.length === 0) {
    return null;
  }

  return (
    <section className="gft-active-filters" aria-label="Filtros activos">
      <div className="gft-active-filters__chips">
        {chips.map((chip) => (
          <span className="gft-filter-chip" key={chip.key}>
            <span>
              {chip.label}: <strong>{chip.value}</strong>
            </span>
            <button type="button" onClick={chip.onClear} aria-label={`Limpiar filtro ${chip.label}`}>
              ×
            </button>
          </span>
        ))}
      </div>
      <button className="gft-button gft-button--secondary" type="button" onClick={onClearAll}>
        Limpiar todos
      </button>
    </section>
  );
}
