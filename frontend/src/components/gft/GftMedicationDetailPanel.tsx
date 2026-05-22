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
  if (value === null || value === undefined) {
    return 'No informado';
  }

  const formattedValue = String(value).trim();

  return formattedValue || 'No informado';
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

function ClinicalTextBlock({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="gft-detail__text-block">
      <h4>{label}</h4>
      <p>{formatValue(value)}</p>
    </div>
  );
}

function GftClinicalUseInfo({ detail }: { detail: GFTMedicamentoDetail }) {
  return (
    <section className="gft-detail__section gft-detail__section--clinical">
      <h3>Información clínica de uso en guía</h3>
      <ClinicalTextBlock label="Indicaciones en ficha técnica" value={detail.indicaciones_ficha_tecnica} />
      <dl className="gft-detail__grid gft-detail__clinical-grid">
        <DetailRow label="Restricciones hospitalarias" value={detail.restricciones_hospitalarias} />
        <DetailRow label="Ajuste insuficiencia renal" value={detail.ajuste_insuficiencia_renal} />
        <DetailRow label="Ajuste insuficiencia hepática" value={detail.ajuste_insuficiencia_hepatica} />
        <DetailRow label="Precauciones embarazo" value={detail.precauciones_embarazo} />
        <DetailRow label="Precauciones lactancia" value={detail.precauciones_lactancia} />
      </dl>
      {detail.resumen_clinico_auto ? (
        <div className="gft-detail__text-block">
          <h4>Resumen automático basado en ficha técnica AEMPS</h4>
          <p><strong>Indicaciones:</strong> {formatValue(detail.resumen_clinico_auto.indicaciones)}</p>
          <p><strong>Posología:</strong> {formatValue(detail.resumen_clinico_auto.posologia)}</p>
          <p><strong>Ajuste renal:</strong> {formatValue(detail.resumen_clinico_auto.ajuste_renal)}</p>
          <p><strong>Ajuste hepático:</strong> {formatValue(detail.resumen_clinico_auto.ajuste_hepatico)}</p>
          <p><strong>Contraindicaciones:</strong> {formatValue(detail.resumen_clinico_auto.contraindicaciones)}</p>
          <p><strong>Advertencias:</strong> {formatValue(detail.resumen_clinico_auto.advertencias)}</p>
          <p><strong>Embarazo:</strong> {formatValue(detail.resumen_clinico_auto.embarazo)}</p>
          <p><strong>Lactancia:</strong> {formatValue(detail.resumen_clinico_auto.lactancia)}</p>
        </div>
      ) : (
        <p>Resumen clínico automático no disponible. Se muestran campos estructurados publicados.</p>
      )}
    </section>
  );
}

function GftFinanciacionDetail({ financiacion, cn }: { financiacion: GFTFinanciacionDetalle; cn: string }) {
  return (
    <section className="gft-detail__section">
      <h3>Financiación</h3>
      <dl className="gft-detail__grid gft-detail__grid--compact">
                <DetailRow label="CN" value={cn} />
        <DetailRow label="Situación BIFIMED" value={financiacion.situacion_financiacion} />
        <DetailRow label="Última sincronización" value={formatDate(financiacion.last_synced_at ?? null)} />
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
    <section
      className="gft-detail gft-detail--inline"
      aria-live="polite"
      aria-label="Detalle del medicamento seleccionado"
    >
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
              <DetailRow label="Nombre comercial" value={detail.nombre} />
              <DetailRow label="CN" value={detail.cn} />
              <DetailRow label="Presentación" value={detail.presentacion} />
              <DetailRow label="Principios activos" value={joinPrincipios(detail.principios_activos)} />
              <DetailRow label="Forma farmacéutica" value={detail.forma_farmaceutica} />
              <DetailRow label="Forma farmacéutica simplificada" value={detail.forma_farmaceutica_simplificada} />
              <DetailRow label="Vías de administración" value={joinVias(detail.vias_administracion)} />
              <DetailRow label="Código ATC" value={joinAtc(detail.atc)} />
              <DetailRow label="Nemónico" value={detail.nemonico} />
              <DetailRow label="Descripción ATC" value={detail.atc[0]?.nombre} />
            </dl>
          </section>

          <GftClinicalUseInfo detail={detail} />

          <GftFinanciacionDetail financiacion={detail.financiacion_detalle ?? { situacion_financiacion: detail.situacion_financiacion, condiciones_financiacion_restringidas: null, condiciones_especiales_financiacion: null, estado_nomenclator: null, aportacion_usuario: null, subgrupo_atc: null }} cn={detail.cn} />

          <section className="gft-detail__section">
            <h3>Trazabilidad</h3>
            <GftDocumentLinks
              fichaTecnicaUrl={detail.url_ficha_tecnica}
              prospectoUrl={detail.url_prospecto}
              fechaFichaTecnica={detail.fecha_ficha_tecnica}
              fechaProspecto={detail.fecha_prospecto}
            />
          </section>

          <GftCimaDocuments documentos={detail.documentos} />

          {detail.observaciones_publicables ? (
            <section className="gft-detail__section gft-detail__section--note">
              <h3>Observaciones</h3>
              <p>{detail.observaciones_publicables}</p>
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
