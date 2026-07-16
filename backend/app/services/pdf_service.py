import io
import logging

import markdown
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

_PDF_STYLE = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a1a; }
  h1, h2, h3 { color: #111; }
  table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #ccc; padding: 6px; }
</style>
"""


class PdfGenerationError(Exception):
    pass


def render_proposal_pdf(content: str) -> bytes:
    """Renders proposal `content` (markdown, or HTML already) to a PDF.

    markdown.markdown() passes through content that's already HTML largely
    unchanged, so a single code path handles both cases per the "content
    (markdown or html)" contract on the Proposal model.
    """
    body_html = markdown.markdown(content, extensions=["tables", "fenced_code"])
    document = f"<html><head>{_PDF_STYLE}</head><body>{body_html}</body></html>"

    buffer = io.BytesIO()
    result = pisa.CreatePDF(document, dest=buffer, encoding="utf-8")
    if result.err:
        logger.error("PDF generation failed: %s error(s) reported by xhtml2pdf", result.err)
        raise PdfGenerationError("Failed to render proposal content to PDF")

    return buffer.getvalue()
