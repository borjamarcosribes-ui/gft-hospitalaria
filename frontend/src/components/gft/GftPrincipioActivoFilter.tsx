import type { GFTPrincipioActivoIndexItem } from '../../types/gft';

interface GftPrincipioActivoFilterProps {
  items: GFTPrincipioActivoIndexItem[];
  value: string;
  loading: boolean;
  error: string | null;
  onChange: (value: string) => void;
}

export function GftPrincipioActivoFilter({ items, value, loading, error, onChange }: GftPrincipioActivoFilterProps) {
  return (
    <label className="gft-select-filter">
      <span className="gft-select-filter__label">Principio activo</span>
      <select
        className="gft-select-filter__select"
        value={value}
        disabled={loading || Boolean(error)}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Todos los principios activos</option>
        {items.map((item) => (
          <option key={item.slug} value={item.slug}>
            {item.nombre} ({item.count})
          </option>
        ))}
      </select>
      {loading ? <span className="gft-select-filter__hint">Cargando principios activos…</span> : null}
      {error ? <span className="gft-select-filter__error">{error}</span> : null}
    </label>
  );
}
