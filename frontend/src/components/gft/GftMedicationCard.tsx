import type { GFTAtcRef, GFTMedicamentoListItem, GFTPrincipioActivoRef } from '../../types/gft';
import { GftDocumentLinks } from './GftDocumentLinks';

interface GftMedicationCardProps {
  medicamento: GFTMedicamentoListItem;
  selected?: boolean;
  onViewDetail(cn: string): void;
}

function joinPrincipios(principios: GFTPrincipioActivoRef[]): string {
  return principios.length > 0 ? principios.map((principio) => principio.nombre).join(', ') : 'No informado';
}

function joinVias(vias: string[]): string {
  return vias.length > 0 ? vias.join(', ') : 'No informado';
}

function getAtcLevelOrder(nivel: string | null): number {
  if (!nivel) {
    return 99;
  }

  const normalized = nivel.trim().toUpperCase();
  const withPrefixMatch = normalized.match(/^L([1-5])$/);

  if (withPrefixMatch) {
    return Number(withPrefixMatch[1]);
  }

  const numericMatch = normalized.match(/^([1-5])$/);

  if (numericMatch) {
    return Number(numericMatch[1]);
  }

  return 99;
}

function getAtcRoute(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return 'No disponible en la fuente actual';
  }

  const sorted = [...atc].sort((a, b) => getAtcLevelOrder(a.nivel) - getAtcLevelOrder(b.nivel));
  return sorted
    .map((item) => (item.nombre ? `${item.codigo} ${item.nombre}` : item.codigo))
    .join(' > ');
}

function getAtcResumen(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return 'No informado';
  }

  const levelFive = atc.find((item) => getAtcLevelOrder(item.nivel) === 5) ?? atc[0];
  return levelFive.nombre ? `${levelFive.codigo} · ${levelFive.nombre}` : levelFive.codigo;
}

export function GftMedicationCard({ medicamento, selected = false, onViewDetail }: GftMedicationCardProps) {
  const title = medicamento.nombre ?? 'Medicamento sin nombre informado';
  const principioActivo = joinPrincipios(medicamento.principios_activos);
  const forma = medicamento.forma_farmaceutica_simplificada ?? medicamento.forma_farmaceutica ?? 'No informada';

  return (
    <article className={`gft-card${selected ? ' gft-card--selected' : ''}`} aria-current={selected ? 'true' : undefined}>
      <header className="gft-card__header">
        <div>
          <h3>{title}</h3>
          <p className="gft-card__subtitle">{principioActivo}</p>
        </div>
      </header>

      <div className="gft-card__chips">
        <span className="gft-badge">CN {medicamento.cn}</span>
        <span className="gft-badge">Vía: {joinVias(medicamento.vias_administracion)}</span>
        <span className="gft-badge">ATC: {getAtcResumen(medicamento.atc)}</span>
        <span className="gft-badge">Nemónico: {medicamento.nemonico?.trim() || 'No informado'}</span>
      </div>

      <section className="gft-card__section">
        <h4>Datos de presentación</h4>
        <dl className="gft-card__details">
          <div><dt>Presentación</dt><dd>{medicamento.presentacion?.trim() || 'No informado'}</dd></div>
          <div><dt>Forma farmacéutica</dt><dd>{forma}</dd></div>
        </dl>
      </section>

      <section className="gft-card__section">
        <h4>Clasificación ATC</h4>
        <dl className="gft-card__details gft-card__details--single">
          <div><dt>Ruta ATC</dt><dd>{getAtcRoute(medicamento.atc)}</dd></div>
        </dl>
      </section>

      <section className="gft-card__section">
        <h4>Fuentes oficiales</h4>
        <GftDocumentLinks
          fichaTecnicaUrl={medicamento.url_ficha_tecnica}
          prospectoUrl={medicamento.url_prospecto}
          fechaFichaTecnica={medicamento.fecha_ficha_tecnica}
          fechaProspecto={medicamento.fecha_prospecto}
        />
      </section>

      <div className="gft-card__actions">
        <button className="gft-button gft-button--detail" type="button" onClick={() => onViewDetail(medicamento.cn)}>
          {selected ? 'Detalle abierto' : 'Ver detalle'}
        </button>
      </div>
    </article>
  );
}
