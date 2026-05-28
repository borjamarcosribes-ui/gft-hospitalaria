import type { GFTCimaIndicacionNormalizada } from '../../types/gft';

function toParagraphs(texto: string): string[] {
  return texto
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export function GftCimaIndicacionesList({ indicaciones }: { indicaciones: GFTCimaIndicacionNormalizada[] | null | undefined }) {
  if (!indicaciones || indicaciones.length === 0) {
    return <p>No hay indicaciones CIMA disponibles.</p>;
  }

  return (
    <div className="gft-bifimed-indicaciones" role="list" aria-label="Indicaciones CIMA normalizadas">
      {indicaciones.map((item, idx) => (
        <details key={`${item.titulo}-${idx}`} className="gft-bifimed-indicaciones__item" role="listitem" open={idx === 0}>
          <summary>
            <span>{item.titulo || 'Indicaciones terapéuticas'}</span>
          </summary>
          <div className="gft-bifimed-indicaciones__content">
            {toParagraphs(item.texto).map((parrafo, i) => (
              <p key={i}>{parrafo}</p>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}
