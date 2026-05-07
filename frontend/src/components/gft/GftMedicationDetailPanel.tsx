import type {
  GFTAtcRef,
  GFTDocumentoCimaRef,
  GFTFinanciacionDetalle,
  GFTMedicamentoDetail,
  GFTPrincipioActivoRef,
} from '../../types/gft';
import { GftDocumentLinks } from './GftDocumentLinks';

interface GftMedicationDetailPanelProps {
  cn: string | null;
  detail: GFTMedicamentoDetail | null;
  loading: boolean;
  error: string | null;
  onClose(): void;
}

function formatValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return 'No informado';
  }

  return String(value);
}

function formatDate(date: string | null): string | null {
  if (!date) {
    return null;
  }

  return new Intl.DateTimeFormat('es-ES').format(new Date(date));
}

function joinPrincipios(principios: GFTPrincipioActivoRef[]): string {
  return principios.length > 0 ? principios.map((principio) => principio.nombre).join(', ') : 'No informado';
}

function joinAtc(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return 'No informado';
  }

  return atc
    .map((item) => {
      const nombre = item.nombre ? ` · ${item.nombre}` : '';
      const nivel = item.nivel ? ` (${item.nivel})` : '';
      return `${item.codigo}${nombre}${nivel}`;
    })
    .join('; ');
}

function joinVias(vias: string[]): string {
  return vias.length > 0 ? vias.join(', ') : 'No informado';
}

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{formatValue(value)}</dd>
    </div>
  );
}

function GftFinanciacionDetail({ financiacion }: { financiacion: GFTFinanciacionDetalle }) {
  return (
    <section className="gft-detail__section">
      <h3>Financiación detalle</h3>
      <dl className="gft-detail__grid gft-detail__grid--compact">
        <DetailRow label="Situación financiación" value={financiacion.situacion_financiacion} />
        <DetailRow
          label="Condiciones restringidas"
          value={financiacion.condiciones_financiacion_restringidas}
        />
        <DetailRow label="Condiciones especiales" value={financiacion.condiciones_especiales_financiacion} />
        <DetailRow label="Estado Nomenclátor" value={financiacion.estado_nomenclator} />
        <DetailRow label="Aportación usuario" value={financiacion.aportacion_usuario} />
        <DetailRow label="Subgrupo ATC" value={financiacion.subgrupo_atc} />
      </dl>
    </section>
  );
}

function documentLabel(documento: GFTDocumentoCimaRef): string {
  return documento.titulo ?? documento.nombre ?? documento.secc ?? `Documento ${formatValue(documento.tipo)}`;
}

function GftCimaDocuments({ documentos }: { documentos: GFTDocumentoCimaRef[] }) {
  const availableDocuments = documentos.filter((documento) => documento.url || documento.urlHtml);

  if (availableDocuments.length === 0) {
    return null;
  }

  return (
    <section className="gft-detail__section">
      <h3>Documentos CIMA</h3>
      <ul className="gft-detail-documents">
        {availableDocuments.map((documento, index) => {
          const href = documento.urlHtml ?? documento.url;
          const date = formatDate(documento.fecha);

          return (
            <li key={`${href}-${index}`}>
              <a href={href ?? undefined} target="_blank" rel="noreferrer">
                {documentLabel(documento)}
              </a>
              {date ? <span>{date}</span> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function GftMedicationDetailPanel({ cn, detail, loading, error, onClose }: GftMedicationDetailPanelProps) {
  if (!cn) {
    return null;
  }

  return (
    <section className="gft-detail" aria-live="polite" aria-label="Detalle del medicamento seleccionado">
      <div className="gft-detail__header">
        <div>
          <p className="gft-detail__eyebrow">Detalle de medicamento</p>
          <h2>{detail?.nombre ?? `CN ${cn}`}</h2>
        </div>
        <button className="gft-button gft-button--secondary gft-detail__close" type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>

      {loading ? <p className="gft-detail__state">Cargando detalle del medicamento…</p> : null}

      {error ? (
        <div className="gft-detail__error" role="alert">
          <strong>No se pudo cargar el detalle.</strong>
          <span>{error}</span>
        </div>
      ) : null}

      {!loading && !error && detail ? (
        <div className="gft-detail__content">
          <section className="gft-detail__section">
            <h3>Identificación</h3>
            <dl className="gft-detail__grid">
              <DetailRow label="Nombre" value={detail.nombre} />
              <DetailRow label="CN" value={detail.cn} />
              <DetailRow label="Presentación" value={detail.presentacion} />
              <DetailRow label="Principios activos" value={joinPrincipios(detail.principios_activos)} />
              <DetailRow label="Forma farmacéutica" value={detail.forma_farmaceutica} />
              <DetailRow label="Forma farmacéutica simplificada" value={detail.forma_farmaceutica_simplificada} />
              <DetailRow label="Vías de administración" value={joinVias(detail.vias_administracion)} />
              <DetailRow label="ATC" value={joinAtc(detail.atc)} />
              <DetailRow label="Nemónico" value={detail.nemonico} />
              <DetailRow label="Restricciones hospitalarias" value={detail.restricciones_hospitalarias} />
              <DetailRow label="Situación financiación" value={detail.situacion_financiacion} />
            </dl>
          </section>

          {detail.financiacion_detalle ? <GftFinanciacionDetail financiacion={detail.financiacion_detalle} /> : null}

          <section className="gft-detail__section">
            <h3>Ficha técnica y prospecto</h3>
            <GftDocumentLinks
              fichaTecnicaUrl={detail.url_ficha_tecnica}
              prospectoUrl={detail.url_prospecto}
              fechaFichaTecnica={detail.fecha_ficha_tecnica}
              fechaProspecto={detail.fecha_prospecto}
            />
          </section>

          <GftCimaDocuments documentos={detail.documentos} />

          {detail.observaciones_internas_publicables ? (
            <section className="gft-detail__section gft-detail__section--note">
              <h3>Observaciones internas publicables</h3>
              <p>{detail.observaciones_internas_publicables}</p>
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
