const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

interface GftAZFilterProps {
  activeLetter: string;
  onChange: (letter: string) => void;
  disabled?: boolean;
}

export function GftAZFilter({ activeLetter, onChange, disabled = false }: GftAZFilterProps) {
  return (
    <div className="gft-az-filter" aria-label="Filtro A-Z por principio activo">
      <button
        className={`gft-az-filter__button${activeLetter === '' ? ' gft-az-filter__button--active' : ''}`}
        type="button"
        disabled={disabled}
        aria-pressed={activeLetter === ''}
        onClick={() => onChange('')}
      >
        Todas
      </button>
      {LETTERS.map((letter) => (
        <button
          key={letter}
          className={`gft-az-filter__button${activeLetter === letter ? ' gft-az-filter__button--active' : ''}`}
          type="button"
          disabled={disabled}
          aria-pressed={activeLetter === letter}
          onClick={() => onChange(letter)}
        >
          {letter}
        </button>
      ))}
    </div>
  );
}
