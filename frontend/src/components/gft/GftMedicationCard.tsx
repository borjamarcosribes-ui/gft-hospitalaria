import { useMemo, useState } from 'react';
import type { GFTAtcRef, GFTMedicamentoListItem, GFTPrincipioActivoRef } from '../../types/gft';
import { GftDocumentLinks } from './GftDocumentLinks';

interface GftMedicationCardProps {
  medicamento: GFTMedicamentoListItem;
  selected?: boolean;
  onViewDetail(cn: string): void;
}

const INDICACIONES_PREVIEW_LENGTH = 320;

function joinPrincipios(principios: GFTPrincipioActivoRef[]): string {
  return principios.length > 0 ? principios.map((principio) => principio.nombre).join(', ') : 'No informado';
}

function joinVias(vias: string[]): string {
  return vias.length > 0 ? vias.join(', ') : 'No informado';
}

function getAtcRoute(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return 'No disponible en la fuente actual';
  }

  const sorted = [...atc].sort((a, b) => Number(a.nivel ?? 99) - Number(b.nivel ?? 99));
  return sorted
    .map((item) => (item.nombre ? `${item.codigo} ${item.nombre}` : item.codigo))
    .join(' > ');
}

function getAtcResumen(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return 'No informado';
  }

  const levelFive = atc.find((item) => item.nivel === '5') ?? atc[0];
  return levelFive.nombre ? `${levelFive.codigo} · ${levelFive.nombre}` : levelFive.codigo;
}

function pendingHospitalFields(medicamento: GFTMedicamentoListItem): string[] {
  const pending: string[] = [];
  if (!medicamento.ajuste_insuficiencia_renal?.trim()) pending.push('Ajuste por insuficiencia renal');
  if (!medicamento.ajuste_insuficiencia_hepatica?.trim()) pending.push('Ajuste por insuficiencia hepática');
  if (!medicamento.precauciones_embarazo?.trim()) pending.push('Precauciones en embarazo');
  if (!medicamento.precauciones_lactancia?.trim()) pending.push('Precauciones en lactancia');
  return pending;
}

export function GftMedicationCard({ medicamento, selected = false, onViewDetail }: GftMedicationCardProps) {
  const [expandedIndicaciones, setExpandedIndicaciones] = useState(false);
  const title = medicamento.nombre ?? 'Medicamento sin nombre informado';
  const principioActivo = joinPrincipios(medicamento.principios_activos);
  const forma = medicamento.forma_farmaceutica_simplificada ?? medicamento.forma_farmaceutica ?? 'No informada';
  const indicaciones = medicamento.indicaciones_ficha_tecnica?.trim() ?? '';
  const showIndicacionesToggle = indicaciones.length > INDICACIONES_PREVIEW_LENGTH;
  const indicacionesPreview = showIndicacionesToggle && !expandedIndicaciones
    ? `${indicaciones.slice(0, INDICACIONES_PREVIEW_LENGTH).trimEnd()}…`
    : indicaciones;
  const pendingFields = useMemo(() => pendingHospitalFields(medicamento), [medicamento]);

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
        <h4>Indicaciones (ficha técnica 4.1)</h4>
        <p className="gft-card__text">{indicacionesPreview || 'No disponible en la fuente actual'}</p>
        {showIndicacionesToggle ? (
          <button className="gft-button gft-button--secondary" type="button" onClick={() => setExpandedIndicaciones((value) => !value)}>
            {expandedIndicaciones ? 'Ver menos' : 'Ver indicaciones completas'}
          </button>
        ) : null}
      </section>

      <section className="gft-card__section">
        <h4>Información hospitalaria</h4>
        <dl className="gft-card__details">
          <div><dt>Restricciones hospitalarias</dt><dd>{medicamento.restricciones_hospitalarias?.trim() || 'Pendiente de completar'}</dd></div>
          <div><dt>Financiación BIFIMED</dt><dd>{medicamento.situacion_financiacion?.trim() || 'No disponible en la fuente actual'}</dd></div>
          <div><dt>Ajuste insuficiencia renal</dt><dd>{medicamento.ajuste_insuficiencia_renal?.trim() || 'Pendiente de completar'}</dd></div>
          <div><dt>Ajuste insuficiencia hepática</dt><dd>{medicamento.ajuste_insuficiencia_hepatica?.trim() || 'Pendiente de completar'}</dd></div>
          <div><dt>Precauciones embarazo</dt><dd>{medicamento.precauciones_embarazo?.trim() || 'Pendiente de completar'}</dd></div>
          <div><dt>Precauciones lactancia</dt><dd>{medicamento.precauciones_lactancia?.trim() || 'Pendiente de completar'}</dd></div>
        </dl>
        {pendingFields.length > 0 ? <p className="gft-card__muted">Pendiente de completar: {pendingFields.join(' · ')}.</p> : null}
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
