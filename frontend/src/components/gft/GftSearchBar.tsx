import { FormEvent, useEffect, useState } from 'react';

interface GftSearchBarProps {
  value: string;
  loading: boolean;
  onSearch: (value: string) => void;
  onClear: () => void;
}

export function GftSearchBar({ value, loading, onSearch, onClear }: GftSearchBarProps) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch(draft.trim());
  }

  function handleClear() {
    setDraft('');
    onClear();
  }

  return (
    <form className="gft-search" onSubmit={handleSubmit}>
      <label className="gft-search__label" htmlFor="gft-search-input">
        Buscador general
      </label>
      <div className="gft-search__controls">
        <input
          id="gft-search-input"
          className="gft-search__input"
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Buscar por CN, medicamento, principio activo o nemónico"
        />
        <button className="gft-button gft-button--primary" type="submit" disabled={loading}>
          Buscar
        </button>
        <button className="gft-button gft-button--secondary" type="button" onClick={handleClear} disabled={loading && !draft}>
          Limpiar
        </button>
      </div>
    </form>
  );
}
