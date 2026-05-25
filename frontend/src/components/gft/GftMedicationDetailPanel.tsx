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
  if (!value || !value.trim()) return null;
  return (<div className="gft-detail__text-block"><h4>{label}</h4><p>{value}</p></div>);
}

function firstNonEmpty(...values: Array<string | null | undefined>): string | null {
  for (const value of values) { if (value && value.trim()) return value.trim(); }
  return null;
}

function GftClinicalUseInfo({ detail }: { detail: GFTMedicamentoDetail }) {
  return (
    <section className="gft-detail__section gft-detail__section--clinical">
      <h3>Información clínica de uso en guía</h3>
      <ClinicalTextBlock label="Indicaciones" value={firstNonEmpty(detail.resumen_clinico_auto?.indicaciones, detail.indicaciones_ficha_tecnica, "No informado")} />
      <ClinicalTextBlock label="Posología" value={firstNonEmpty(detail.resumen_clinico_auto?.posologia, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Ajuste renal" value={firstNonEmpty(detail.resumen_clinico_auto?.ajuste_renal, detail.ajuste_insuficiencia_renal, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Ajuste hepático" value={firstNonEmpty(detail.resumen_clinico_auto?.ajuste_hepatico, detail.ajuste_insuficiencia_hepatica, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Contraindicaciones" value={firstNonEmpty(detail.resumen_clinico_auto?.contraindicaciones, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Advertencias/precauciones" value={firstNonEmpty(detail.resumen_clinico_auto?.advertencias, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Embarazo" value={firstNonEmpty(detail.resumen_clinico_auto?.embarazo, detail.precauciones_embarazo, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Lactancia" value={firstNonEmpty(detail.resumen_clinico_auto?.lactancia, detail.precauciones_lactancia, "No localizado automáticamente")} />
      <ClinicalTextBlock label="Restricciones hospitalarias" value={firstNonEmpty(detail.restricciones_hospitalarias, "No informado")} />
      <p>{detail.resumen_clinico_auto?.source_status === "ok" ? "Resumen clínico automático generado desde ficha técnica CIMA." : detail.resumen_clinico_auto?.source_status === "partial" ? "Resumen clínico automático parcial." : "Resumen clínico automático no disponible."}</p>
    </section>
  );
}

function GftFinanciacionDetail({ financiacion, cn }: { financiacion: GFTFinanciacionDetalle; cn: string }) {
  return (
    <section className="gft-detail__section">
      <h3>Financiación BIFIMED</h3>
      <dl className="gft-detail__grid gft-detail__grid--compact">
                <DetailRow label="CN" value={cn} />
        <DetailRow label="Situación" value={(financiacion.situacion_financiacion?.trim().toLowerCase() === "si" || financiacion.situacion_financiacion?.trim().toLowerCase() === "sí") ? "Financiado" : financiacion.situacion_financiacion} />
        <DetailRow label="Última sincronización" value={formatDate(financiacion.last_synced_at ?? null)} />
        <DetailRow
          label="Condiciones restringidas"
          value={firstNonEmpty(financiacion.condiciones_financiacion_restringidas, ((financiacion.situacion_financiacion?.trim().toLowerCase()==="si"||financiacion.situacion_financiacion?.trim().toLowerCase()==="sí") ? "No constan condiciones restringidas en BIFIMED." : "No informado."))}
        />
        <DetailRow label="Condiciones especiales" value={firstNonEmpty(financiacion.condiciones_especiales_financiacion, ((financiacion.situacion_financiacion?.trim().toLowerCase()==="si"||financiacion.situacion_financiacion?.trim().toLowerCase()==="sí") ? "No constan condiciones especiales en BIFIMED." : "No informado."))} />
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

          {detail.financiacion_detalle ? (<GftFinanciacionDetail financiacion={detail.financiacion_detalle} cn={detail.cn} />) : (<section className="gft-detail__section"><h3>Financiación BIFIMED</h3><p>No se dispone de detalle BIFIMED para este CN.</p></section>)}

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
