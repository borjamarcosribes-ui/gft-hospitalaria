import type { GFTAtcIndexItem } from '../../types/gft';

interface GftAtcFilterProps {
  items: GFTAtcIndexItem[];
  value: string;
  loading: boolean;
  error: string | null;
  onChange: (value: string) => void;
}

function formatAtcOption(item: GFTAtcIndexItem): string {
  const name = item.nombre ? ` — ${item.nombre}` : '';
  return `${item.codigo}${name} · nivel ${item.nivel} (${item.count})`;
}

export function GftAtcFilter({ items, value, loading, error, onChange }: GftAtcFilterProps) {
  return (
    <label className="gft-select-filter">
      <span className="gft-select-filter__label">Grupo ATC</span>
      <select
        className="gft-select-filter__select"
        value={value}
        disabled={loading || Boolean(error)}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Todos los grupos ATC</option>
        {items.map((item) => (
          <option key={item.codigo} value={item.codigo}>
            {formatAtcOption(item)}
          </option>
        ))}
      </select>
      {loading ? <span className="gft-select-filter__hint">Cargando grupos ATC…</span> : null}
      {error ? <span className="gft-select-filter__error">{error}</span> : null}
    </label>
  );
}
