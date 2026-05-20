interface GftActiveFiltersProps {
  q: string;
  letra: string;
  principioActivoLabel: string;
  atcLabel: string;
  total: number;
  showingFrom: number;
  showingTo: number;
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
  total,
  showingFrom,
  showingTo,
}: GftActiveFiltersProps) {
  const chips: FilterChip[] = [
    q ? { key: 'q', label: 'Búsqueda', value: q, onClear: onClearQ } : null,
    letra ? { key: 'letra', label: 'Letra', value: letra, onClear: onClearLetra } : null,
    principioActivoLabel
      ? { key: 'principio-activo', label: 'Principio activo', value: principioActivoLabel, onClear: onClearPrincipioActivo }
      : null,
    atcLabel ? { key: 'atc', label: 'ATC', value: atcLabel, onClear: onClearAtc } : null,
  ].filter((chip): chip is FilterChip => chip !== null);


  return (
    <section className="gft-active-filters" aria-label="Filtros activos">
      <div className="gft-active-filters__summary">
        <p>Se muestran {showingFrom}-{showingTo} de {total} medicamentos encontrados.</p>
      </div>
      <div className="gft-active-filters__chips">
        {chips.length > 0 ? chips.map((chip) => (
          <span className="gft-filter-chip" key={chip.key}>
            <span>
              {chip.label}: <strong>{chip.value}</strong>
            </span>
            <button type="button" onClick={chip.onClear} aria-label={`Limpiar filtro ${chip.label}`}>
              ×
            </button>
          </span>
        )) : <p className="gft-active-filters__none">Sin filtros activos.</p>}
      </div>
      <button className="gft-button gft-button--secondary" type="button" onClick={onClearAll}>
        Limpiar todos
      </button>
    </section>
  );
}
