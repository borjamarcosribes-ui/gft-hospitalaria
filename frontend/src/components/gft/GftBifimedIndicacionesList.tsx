import type { GFTIndicacionAutorizadaBifimed } from '../../types/gft';

function formatValue(value: string | null | undefined): string {
  if (!value) return 'No informado';
  const normalized = value.trim();
  return normalized || 'No informado';
}

function financiacionBadge(financiada: boolean | null | undefined): { label: string; className: string } {
  if (financiada === true) return { label: 'Financiada', className: 'gft-bifimed-indicaciones__badge gft-bifimed-indicaciones__badge--yes' };
  if (financiada === false) return { label: 'No financiada', className: 'gft-bifimed-indicaciones__badge gft-bifimed-indicaciones__badge--no' };
  return { label: 'No informado', className: 'gft-bifimed-indicaciones__badge gft-bifimed-indicaciones__badge--unknown' };
}

function buildSummary(indicacion: string | null | undefined): string {
  const raw = (indicacion ?? '').replace(/\s+/g, ' ').trim();
  if (!raw) return 'Indicación autorizada no informada';
  const firstSentence = raw.split(/(?<=[.!?])\s+/)[0]?.trim();
  if (firstSentence && firstSentence.length >= 12 && firstSentence.length <= 120) return firstSentence;
  if (raw.length <= 120) return raw;
  return `${raw.slice(0, 117).trimEnd()}...`;
}

export function GftBifimedIndicacionesList({ indicaciones }: { indicaciones: GFTIndicacionAutorizadaBifimed[] | null | undefined }) {
  if (!indicaciones || indicaciones.length === 0) {
    return <p className="gft-bifimed-indicaciones__empty">No hay indicaciones autorizadas BIFIMED disponibles.</p>;
  }

  return (
    <div className="gft-bifimed-indicaciones" role="list" aria-label="Indicaciones autorizadas BIFIMED">
      {indicaciones.map((item, idx) => {
        const badge = financiacionBadge(item.financiada);
        return (
          <details key={idx} className="gft-bifimed-indicaciones__item" role="listitem">
            <summary>
              <span>{buildSummary(item.indicacion_autorizada)}</span>
              <span className={badge.className}>{badge.label}</span>
            </summary>
            <div className="gft-bifimed-indicaciones__content">
              <p><strong>Indicación autorizada:</strong> {formatValue(item.indicacion_autorizada)}</p>
              <p><strong>Situación:</strong> {formatValue(item.situacion_expediente_indicacion)}</p>
              <p><strong>Resolución:</strong> {formatValue(item.resolucion_expediente_financiacion_indicacion)}</p>
            </div>
          </details>
        );
      })}
    </div>
  );
}
