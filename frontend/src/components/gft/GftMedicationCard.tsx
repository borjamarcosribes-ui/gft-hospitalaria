import type { GFTAtcRef, GFTMedicamentoListItem, GFTPrincipioActivoRef } from '../../types/gft';
import { GftDocumentLinks } from './GftDocumentLinks';

interface GftMedicationCardProps {
  medicamento: GFTMedicamentoListItem;
  selected?: boolean;
  onViewDetail(cn: string): void;
}

function joinPrincipios(principios: GFTPrincipioActivoRef[]): string {
  if (principios.length === 0) {
    return 'No informado';
  }

  return principios.map((principio) => principio.nombre).join(', ');
}

function joinAtc(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return 'No informado';
  }

  return atc
    .map((item) => {
      const name = item.nombre ? ` · ${item.nombre}` : '';
      return `${item.codigo}${name}`;
    })
    .join('; ');
}

function joinVias(vias: string[]): string {
  return vias.length > 0 ? vias.join(', ') : 'No informado';
}

export function GftMedicationCard({ medicamento, selected = false, onViewDetail }: GftMedicationCardProps) {
  const title = medicamento.nombre ?? 'Medicamento sin nombre informado';
  const forma = medicamento.forma_farmaceutica_simplificada ?? medicamento.forma_farmaceutica ?? 'No informada';

  return (
    <article
      className={`gft-card${selected ? ' gft-card--selected' : ''}`}
      aria-current={selected ? 'true' : undefined}
    >
      <div className="gft-card__header">
        <div>
          <h3>{title}</h3>
          <p className="gft-card__cn">CN {medicamento.cn}</p>
        </div>
        {medicamento.nemonico ? <span className="gft-badge">{medicamento.nemonico}</span> : null}
      </div>

      {medicamento.presentacion ? <p className="gft-card__presentation">{medicamento.presentacion}</p> : null}

      <dl className="gft-card__details">
        <div>
          <dt>Principios activos</dt>
          <dd>{joinPrincipios(medicamento.principios_activos)}</dd>
        </div>
        <div>
          <dt>Forma farmacéutica</dt>
          <dd>{forma}</dd>
        </div>
        <div>
          <dt>Vía administración</dt>
          <dd>{joinVias(medicamento.vias_administracion)}</dd>
        </div>
        <div>
          <dt>ATC</dt>
          <dd>{joinAtc(medicamento.atc)}</dd>
        </div>
      </dl>

      {(medicamento.restricciones_hospitalarias || medicamento.situacion_financiacion) ? (
        <div className="gft-card__notice">
          {medicamento.restricciones_hospitalarias ? (
            <p>
              <strong>Restricciones:</strong> {medicamento.restricciones_hospitalarias}
            </p>
          ) : null}
          {medicamento.situacion_financiacion ? (
            <p>
              <strong>Financiación:</strong> {medicamento.situacion_financiacion}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="gft-card__actions">
        <button
          className="gft-button gft-button--detail"
          type="button"
          onClick={() => onViewDetail(medicamento.cn)}
        >
          {selected ? 'Detalle abierto' : 'Ver detalle'}
        </button>
      </div>

      <GftDocumentLinks
        fichaTecnicaUrl={medicamento.url_ficha_tecnica}
        prospectoUrl={medicamento.url_prospecto}
        fechaFichaTecnica={medicamento.fecha_ficha_tecnica}
        fechaProspecto={medicamento.fecha_prospecto}
      />
    </article>
  );
}
