"""Binary PDF rendering for the public GFT export."""

from importlib.util import find_spec


class GFTPDFRenderingError(RuntimeError):
    """Raised when the configured HTML-to-PDF renderer cannot generate a PDF."""


def render_gft_pdf_bytes(html: str) -> bytes:
    """Render complete GFT HTML into PDF bytes.

    This service is intentionally limited to binary rendering: it does not read
    from the database, know GFT publication rules, or build alternative HTML.
    """
    if find_spec("weasyprint") is None:
        raise GFTPDFRenderingError(
            "WeasyPrint is required to render the GFT PDF. Install project "
            "dependencies from requirements.txt and ensure WeasyPrint system "
            "libraries are available."
        )

    from weasyprint import HTML

    try:
        pdf_bytes = HTML(string=html).write_pdf()
    except Exception as exc:
        raise GFTPDFRenderingError("WeasyPrint failed to render the GFT PDF.") from exc

    if not isinstance(pdf_bytes, bytes):
        raise GFTPDFRenderingError("WeasyPrint did not return PDF bytes.")
    return pdf_bytes
