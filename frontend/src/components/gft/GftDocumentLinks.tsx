interface GftDocumentLinksProps {
  fichaTecnicaUrl: string | null;
  prospectoUrl: string | null;
  fechaFichaTecnica: string | null;
  fechaProspecto: string | null;
}

function formatDate(date: string | null): string | null {
  if (!date) {
    return null;
  }

  return new Intl.DateTimeFormat('es-ES').format(new Date(date));
}

export function GftDocumentLinks({
  fichaTecnicaUrl,
  prospectoUrl,
  fechaFichaTecnica,
  fechaProspecto,
}: GftDocumentLinksProps) {
  if (!fichaTecnicaUrl && !prospectoUrl) {
    return <p className="gft-card__muted">Documentación CIMA no disponible.</p>;
  }

  const fichaDate = formatDate(fechaFichaTecnica);
  const prospectoDate = formatDate(fechaProspecto);

  return (
    <div className="gft-documents" aria-label="Documentación del medicamento">
      {fichaTecnicaUrl ? (
        <a className="gft-document-link" href={fichaTecnicaUrl} target="_blank" rel="noreferrer">
          Ficha técnica AEMPS{fichaDate ? <span>{fichaDate}</span> : null}
        </a>
      ) : null}
      {prospectoUrl ? (
        <a className="gft-document-link" href={prospectoUrl} target="_blank" rel="noreferrer">
          Prospecto AEMPS{prospectoDate ? <span>{prospectoDate}</span> : null}
        </a>
      ) : null}
    </div>
  );
}
