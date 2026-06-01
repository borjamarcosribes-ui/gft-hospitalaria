import type { ReactNode } from 'react';
import type {
  GFTAtcRef,
  GFTCanonicalIndicacionBifimed,
  GFTCanonicalPayload,
  GFTDocumentoCimaRef,
  GFTMedicamentoDetail,
} from '../../types/gft';
import { normalizeDisplayText, normalizeDisplayValue } from '../../utils/displayText';
import { GftDocumentLinks } from './GftDocumentLinks';

interface GftMedicationDetailPanelProps {
  cn: string | null;
  detail: GFTMedicamentoDetail | null;
  loading: boolean;
  error: string | null;
  onClose(): void;
}

type BadgeTone = 'success' | 'neutral' | 'warning' | 'info';

const NO_INFORMADO = 'No informado';

function firstNonEmpty(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    const normalized = normalizeDisplayText(value)?.trim();
    if (normalized) return normalized;
  }
  return null;
}

function isInformative(value: string | null | undefined): boolean {
  const normalized = normalizeDisplayText(value)?.trim().toLowerCase();
  return Boolean(normalized && normalized !== NO_INFORMADO.toLowerCase());
}

function formatDate(date: string | null): string | null {
  if (!date) {
    return null;
  }

  return new Intl.DateTimeFormat('es-ES').format(new Date(date));
}

function joinAtcHierarchy(atc: GFTAtcRef[]): string {
  if (atc.length === 0) {
    return NO_INFORMADO;
  }

  return atc
    .map((item) => {
      const nombre = item.nombre ? ` · ${normalizeDisplayText(item.nombre)}` : '';
      const nivel = item.nivel ? ` (${normalizeDisplayText(item.nivel)})` : '';
      return `${normalizeDisplayValue(item.codigo)}${nombre}${nivel}`;
    })
    .join(' › ');
}

function canonicalFallback(detail: GFTMedicamentoDetail): GFTCanonicalPayload {
  const atc = detail.atc ?? [];
  return {
    cn: detail.cn,
    nombre_comercial: detail.nombre ?? NO_INFORMADO,
    incluido_gft: true,
    publicado: true,
    principio_activo: detail.principios_activos?.map((item) => item.nombre).filter(Boolean).join(', ') || NO_INFORMADO,
    forma_farmaceutica: detail.forma_farmaceutica ?? NO_INFORMADO,
    via_administracion: detail.vias_administracion?.join(', ') || NO_INFORMADO,
    nemonico: detail.nemonico ?? NO_INFORMADO,
    codigo_atc: atc[atc.length - 1]?.codigo ?? NO_INFORMADO,
    descripcion_atc: atc[atc.length - 1]?.nombre ?? NO_INFORMADO,
    jerarquia_atc: atc,
    indicaciones_ficha_tecnica: detail.indicaciones_ficha_tecnica ?? NO_INFORMADO,
    url_ficha_tecnica: detail.url_ficha_tecnica,
    url_prospecto: detail.url_prospecto,
    estado_cima: isInformative(detail.indicaciones_ficha_tecnica) || detail.url_ficha_tecnica || detail.url_prospecto ? 'disponible' : 'no_informado',
    bifimed_cache_presente: Boolean(detail.financiacion_detalle),
    situacion_financiacion_bifimed: detail.financiacion_detalle?.situacion_financiacion ?? detail.situacion_financiacion ?? NO_INFORMADO,
    condiciones_financiacion_restringidas: detail.financiacion_detalle?.condiciones_financiacion_restringidas ?? NO_INFORMADO,
    condiciones_especiales_financiacion: detail.financiacion_detalle?.condiciones_especiales_financiacion ?? NO_INFORMADO,
    indicaciones_bifimed: detail.financiacion_detalle?.indicaciones_autorizadas ?? [],
    estado_bifimed: detail.financiacion_detalle?.indicaciones_autorizadas?.length ? 'disponible' : detail.financiacion_detalle ? 'sin_indicaciones' : 'sin_cache',
    ajuste_insuficiencia_renal: detail.ajuste_insuficiencia_renal ?? NO_INFORMADO,
    ajuste_insuficiencia_hepatica: detail.ajuste_insuficiencia_hepatica ?? NO_INFORMADO,
    precauciones_embarazo: detail.precauciones_embarazo ?? NO_INFORMADO,
    precauciones_lactancia: detail.precauciones_lactancia ?? NO_INFORMADO,
    restricciones_hospitalarias: detail.restricciones_hospitalarias ?? NO_INFORMADO,
    resumen_clinico_auto: detail.resumen_clinico_auto ?? null,
    fuentes_disponibles: ['detalle_legacy'],
    campos_faltantes: detail.canonical_payload ? [] : ['canonical_payload'],
    warnings: detail.canonical_payload ? [] : ['Detalle renderizado con campos legacy porque canonical_payload no está disponible'],
    data_quality_flags: detail.canonical_payload ? [] : ['canonical_payload_no_disponible'],
  };
}

function getCanonical(detail: GFTMedicamentoDetail): GFTCanonicalPayload {
  return detail.canonical_payload ?? canonicalFallback(detail);
}

function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'disponible':
      return 'Disponible';
    case 'no_informado':
      return 'No informado';
    case 'sin_cache':
      return 'Sin caché';
    case 'sin_indicaciones':
      return 'Sin indicaciones';
    default:
      return normalizeDisplayValue(status);
  }
}

function StatusBadge({ label, tone = 'neutral' }: { label: string; tone?: BadgeTone }) {
  return <span className={`gft-status-badge gft-status-badge--${tone}`}>{label}</span>;
}

function FieldRow({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{normalizeDisplayValue(value)}</dd>
    </div>
  );
}

function ClinicalField({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="gft-clinical-field">
      <h4>{label}</h4>
      <p className={!isInformative(value) ? 'gft-clinical-field__missing' : undefined}>{normalizeDisplayValue(value)}</p>
    </div>
  );
}

function MissingDataNotice({ children }: { children: ReactNode }) {
  return <p className="gft-missing-data-notice">{children}</p>;
}

export function splitLongClinicalText(value: string | null | undefined): string[] {
  const normalized = normalizeDisplayText(value)?.trim();
  if (!normalized) {
    return [NO_INFORMADO];
  }

  const lineParts = normalized
    .split(/\n{1,}/)
    .map((part) => part.trim())
    .filter(Boolean);
  const parts = lineParts.length > 1 ? lineParts : normalized.split(/(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9])/).map((part) => part.trim()).filter(Boolean);

  const paragraphs: string[] = [];
  let current = '';
  for (const part of parts) {
    if (!current) {
      current = part;
      continue;
    }
    if (current.length + part.length < 360) {
      current = `${current} ${part}`;
    } else {
      paragraphs.push(current);
      current = part;
    }
  }
  if (current) paragraphs.push(current);
  return paragraphs.length > 0 ? paragraphs : [NO_INFORMADO];
}

function CimaIndicacionesCanonicalBlock({ canonical }: { canonical: GFTCanonicalPayload }) {
  const paragraphs = splitLongClinicalText(canonical.indicaciones_ficha_tecnica);
  return (
    <details className="gft-detail__section gft-detail__section--cima gft-collapsible-section">
      <summary className="gft-collapsible-section__summary">
        <span className="gft-collapsible-section__heading">
          <span className="gft-collapsible-section__title">Indicaciones ficha técnica / CIMA</span>
          <StatusBadge label={statusLabel(canonical.estado_cima)} tone={canonical.estado_cima === 'disponible' ? 'success' : 'neutral'} />
        </span>
        <span className="gft-collapsible-section__action">Ver indicaciones</span>
      </summary>
      <div className="gft-long-text" aria-label="Indicaciones completas de ficha técnica CIMA">
        {paragraphs.map((paragraph, index) => (
          <p key={index} className={!isInformative(paragraph) ? 'gft-long-text__missing' : undefined}>
            {paragraph}
          </p>
        ))}
      </div>
    </details>
  );
}

function stripBifimedTitleClauses(value: string): string {
  return value
    .replace(/^.*?\best[áa] indicado(?:a)?\s+(?:para|en)\s+(?:el\s+)?tratamiento\s+(?:de|del|de la|de las|de los)\s+/i, '')
    .replace(/^.*?\best[áa] indicado(?:a)?\s+(?:para|en)\s+/i, '')
    .replace(/\s+(?:en pacientes|en adultos|en niños|en adolescentes|que han presentado|cuando|con una respuesta|ver secci[óo]n)\b.*$/i, '')
    .replace(/\s+(?:activa|activo|moderada|moderado|grave|severa|severo)\b.*$/i, '')
    .replace(/^[,;:.\s]+/, '')
    .replace(/^(?:el|la|los|las)\s+/i, '')
    .replace(/\s*[,;:]\s*$/, '')
    .trim();
}

export function deriveBifimedIndicacionTitle(item: GFTCanonicalIndicacionBifimed): string {
  const text = normalizeDisplayText(item.indicacion_autorizada)?.replace(/\s+/g, ' ').trim();
  if (!text) {
    return 'Indicación BIFIMED sin texto extraíble';
  }

  const firstSentence = text.split(/(?<=[.!?])\s+/)[0] ?? text;
  const candidate = stripBifimedTitleClauses(firstSentence) || firstSentence;
  const title = candidate.length <= 72 ? candidate : `${candidate.slice(0, 69).trim()}…`;
  return title || text.slice(0, 72);
}

function BifimedIndicacionesCanonicalList({ indicaciones }: { indicaciones: GFTCanonicalIndicacionBifimed[] }) {
  if (indicaciones.length === 0) {
    return <p className="gft-bifimed-indicaciones__empty">No hay indicaciones BIFIMED extraíbles en la caché local.</p>;
  }

  return (
    <div className="gft-bifimed-indicaciones" role="list" aria-label="Indicaciones BIFIMED">
      {indicaciones.map((item, index) => (
        <article key={`${item.indicacion_autorizada ?? 'indicacion'}-${index}`} className="gft-bifimed-indicaciones__entry" role="listitem">
          <h5>{deriveBifimedIndicacionTitle(item)}</h5>
          <details className="gft-bifimed-indicaciones__item">
            <summary>Ver texto completo de la indicación</summary>
            <div className="gft-bifimed-indicaciones__content">
              <p>{normalizeDisplayValue(item.indicacion_autorizada)}</p>
              {isInformative(item.situacion_expediente_indicacion) ? (
                <p>
                  <strong>Situación expediente indicación:</strong> {normalizeDisplayValue(item.situacion_expediente_indicacion)}
                </p>
              ) : null}
              {isInformative(item.resolucion_expediente_financiacion_indicacion) ? (
                <p>
                  <strong>Resolución expediente financiación indicación:</strong>{' '}
                  {normalizeDisplayValue(item.resolucion_expediente_financiacion_indicacion)}
                </p>
              ) : null}
            </div>
          </details>
        </article>
      ))}
    </div>
  );
}

function SourceCoveragePanel({ canonical }: { canonical: GFTCanonicalPayload }) {
  return (
    <details className="gft-source-coverage">
      <summary>
        <span>Cobertura y calidad de datos</span>
        <span>Ver detalles técnicos</span>
      </summary>
      <dl className="gft-detail__grid gft-detail__grid--compact">
        <FieldRow label="Fuentes disponibles" value={canonical.fuentes_disponibles.join(', ')} />
        <FieldRow label="Campos faltantes" value={canonical.campos_faltantes.join(', ')} />
        <FieldRow label="Warnings" value={canonical.warnings.join(', ')} />
        <FieldRow label="data_quality_flags" value={canonical.data_quality_flags.join(', ')} />
      </dl>
    </details>
  );
}

function documentLabel(documento: GFTDocumentoCimaRef): string {
  for (const value of [documento.titulo, documento.nombre, documento.secc]) {
    if (typeof value !== 'string') continue;
    const normalized = normalizeDisplayText(value)?.trim();
    if (normalized && !/^(?:true|false|null|undefined)$/i.test(normalized)) {
      return normalized;
    }
  }
  return 'Documento CIMA';
}

function usableUrl(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = normalizeDisplayText(value)?.trim();
  if (!normalized || /^(?:true|false|null|undefined)$/i.test(normalized)) {
    return null;
  }
  return normalized;
}

function GftCimaDocuments({ documentos }: { documentos: GFTDocumentoCimaRef[] }) {
  const availableDocuments = documentos
    .map((documento) => ({ ...documento, href: usableUrl(documento.urlHtml) ?? usableUrl(documento.url) }))
    .filter((documento) => documento.href);

  if (availableDocuments.length === 0) {
    return <p className="gft-card__muted">No hay documentos CIMA enlazados.</p>;
  }

  return (
    <ul className="gft-detail-documents">
      {availableDocuments.map((documento, index) => {
        const date = formatDate(documento.fecha);

        return (
          <li key={`${documento.href}-${index}`}>
            <a href={documento.href ?? undefined} target="_blank" rel="noreferrer">
              {documentLabel(documento)}
            </a>
            {date ? <span>{date}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

function Header({ canonical, requestedCn }: { canonical: GFTCanonicalPayload | null; requestedCn: string }) {
  const bifimedTone: BadgeTone = canonical?.estado_bifimed === 'disponible' ? 'success' : canonical?.estado_bifimed === 'sin_cache' ? 'warning' : 'neutral';
  return (
    <div>
      <p className="gft-detail__eyebrow">Detalle de medicamento</p>
      <h2>{normalizeDisplayValue(canonical?.nombre_comercial ?? `CN ${requestedCn}`)}</h2>
      {canonical ? (
        <>
          <p className="gft-detail__subtitle">{normalizeDisplayValue(canonical.principio_activo)}</p>
          <p className="gft-detail__meta">
            CN {normalizeDisplayValue(canonical.cn)} · ATC {normalizeDisplayValue(canonical.codigo_atc)} ·{' '}
            {normalizeDisplayValue(canonical.descripcion_atc)}
          </p>
          <div className="gft-detail__badges" aria-label="Estados del medicamento">
            <StatusBadge label="GFT publicado" tone="success" />
            <StatusBadge label={`CIMA ${statusLabel(canonical.estado_cima).toLowerCase()}`} tone={canonical.estado_cima === 'disponible' ? 'success' : 'neutral'} />
            <StatusBadge label={`BIFIMED ${statusLabel(canonical.estado_bifimed).toLowerCase()}`} tone={bifimedTone} />
          </div>
        </>
      ) : null}
    </div>
  );
}

export function GftMedicationDetailPanel({ cn, detail, loading, error, onClose }: GftMedicationDetailPanelProps) {
  if (!cn) {
    return null;
  }

  const canonical = detail ? getCanonical(detail) : null;

  return (
    <section className="gft-detail gft-detail--inline" aria-live="polite" aria-label="Detalle del medicamento seleccionado">
      <div className="gft-detail__header">
        <Header canonical={canonical} requestedCn={cn} />
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

      {!loading && !error && detail && canonical ? (
        <div className="gft-detail__content">
          <section className="gft-detail__section">
            <h3>Datos básicos</h3>
            <dl className="gft-detail__grid">
              <FieldRow label="Principio activo" value={canonical.principio_activo} />
              <FieldRow label="Forma farmacéutica" value={canonical.forma_farmaceutica} />
              <FieldRow label="Vía" value={canonical.via_administracion} />
              <FieldRow label="Nemónico" value={canonical.nemonico} />
              <FieldRow label="CN" value={canonical.cn} />
              <FieldRow label="Código ATC" value={canonical.codigo_atc} />
              <FieldRow label="Descripción ATC" value={canonical.descripcion_atc} />
              <FieldRow label="Jerarquía ATC" value={joinAtcHierarchy(canonical.jerarquia_atc)} />
            </dl>
          </section>

          <CimaIndicacionesCanonicalBlock canonical={canonical} />

          <details className="gft-detail__section gft-detail__section--bifimed gft-collapsible-section">
            <summary className="gft-collapsible-section__summary">
              <span className="gft-collapsible-section__heading">
                <span className="gft-collapsible-section__title">BIFIMED</span>
                <StatusBadge label={statusLabel(canonical.estado_bifimed)} tone={canonical.estado_bifimed === 'disponible' ? 'success' : canonical.estado_bifimed === 'sin_cache' ? 'warning' : 'neutral'} />
                <span className="gft-collapsible-section__meta">
                  Financiación: {normalizeDisplayValue(canonical.situacion_financiacion_bifimed)}
                </span>
              </span>
              <span className="gft-collapsible-section__action">Ver financiación e indicaciones</span>
            </summary>
            <dl className="gft-detail__grid">
              <FieldRow label="Situación de financiación BIFIMED" value={canonical.situacion_financiacion_bifimed} />
              <FieldRow label="Condiciones financiación restringidas" value={canonical.condiciones_financiacion_restringidas} />
              <FieldRow label="Condiciones especiales financiación" value={canonical.condiciones_especiales_financiacion} />
            </dl>
            {!canonical.bifimed_cache_presente ? <MissingDataNotice>Sin caché BIFIMED local para este CN.</MissingDataNotice> : null}
            {canonical.estado_bifimed === 'sin_indicaciones' ? (
              <MissingDataNotice>BIFIMED disponible, pero sin indicaciones autorizadas extraíbles en la caché local.</MissingDataNotice>
            ) : null}
            {canonical.indicaciones_bifimed.length > 0 ? (
              <div className="gft-detail__subsection">
                <h4>Indicaciones BIFIMED</h4>
                <BifimedIndicacionesCanonicalList indicaciones={canonical.indicaciones_bifimed} />
              </div>
            ) : null}
          </details>

          <section className="gft-detail__section gft-detail__section--clinical">
            <h3>Clínica</h3>
            <div className="gft-clinical-grid">
              <ClinicalField label="Ajuste insuficiencia renal" value={canonical.ajuste_insuficiencia_renal} />
              <ClinicalField label="Ajuste insuficiencia hepática" value={canonical.ajuste_insuficiencia_hepatica} />
              <ClinicalField label="Precauciones embarazo" value={canonical.precauciones_embarazo} />
              <ClinicalField label="Precauciones lactancia" value={canonical.precauciones_lactancia} />
              <ClinicalField label="Restricciones hospitalarias" value={canonical.restricciones_hospitalarias} />
            </div>
          </section>

          <SourceCoveragePanel canonical={canonical} />

          <details className="gft-detail__section gft-collapsible-section gft-detail__section--traceability">
            <summary className="gft-collapsible-section__summary">
              <span className="gft-collapsible-section__heading">
                <span className="gft-collapsible-section__title">Documentos y trazabilidad CIMA</span>
                <span className="gft-collapsible-section__meta">
                  Ficha técnica: {usableUrl(detail.url_ficha_tecnica ?? canonical.url_ficha_tecnica) ? 'disponible' : 'no informada'} · Prospecto:{' '}
                  {usableUrl(detail.url_prospecto ?? canonical.url_prospecto) ? 'disponible' : 'no informado'}
                </span>
              </span>
              <span className="gft-collapsible-section__action">Ver documentos</span>
            </summary>
            <GftDocumentLinks
              fichaTecnicaUrl={usableUrl(detail.url_ficha_tecnica ?? canonical.url_ficha_tecnica)}
              prospectoUrl={usableUrl(detail.url_prospecto ?? canonical.url_prospecto)}
              fechaFichaTecnica={detail.fecha_ficha_tecnica}
              fechaProspecto={detail.fecha_prospecto}
            />
            <GftCimaDocuments documentos={detail.documentos} />
          </details>

          {detail.observaciones_publicables ? (
            <section className="gft-detail__section gft-detail__section--note">
              <h3>Observaciones</h3>
              <p>{normalizeDisplayText(detail.observaciones_publicables)}</p>
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
