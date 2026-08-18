import io
import logging

import markdown
from bs4 import BeautifulSoup
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

# Every tag capable of making xhtml2pdf resolve an external URI or read a
# local file (img/link/object/iframe/embed), plus style/script, which have no
# legitimate place in generated proposal content. See SecurityIssues.md H-1.
_DISALLOWED_TAGS = ("img", "link", "object", "iframe", "embed", "script", "style")


class PdfGenerationError(Exception):
    pass


def _sanitize_html(html: str) -> str:
    """Strips every tag that could trigger a resource fetch or a script
    execution before the markup ever reaches xhtml2pdf. Defense in depth
    alongside `_reject_external_uris` below — either one closes H-1 on its
    own, but a sanitizer that only runs at the renderer boundary is one
    refactor away from being silently bypassed.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_DISALLOWED_TAGS):
        tag.decompose()
    return str(soup)


def _reject_external_uris(uri: str, rel: str) -> None:
    """xhtml2pdf's `link_callback` — invoked for every resource URI it would
    otherwise fetch itself. Its default resolver makes real outbound HTTP
    requests for http(s) URIs and opens local files for anything else,
    which is exactly the SSRF / local-file-read primitive documented as H-1
    in SecurityIssues.md. Returning None tells xhtml2pdf the resource is
    unavailable instead of falling through to that resolver. Proposals need
    no external resources today, so nothing is allowlisted.
    """
    return None


def render_proposal_pdf(content: str) -> bytes:
    """Renders proposal `content` (markdown, or HTML already) to a PDF.

    markdown.markdown() passes through content that's already HTML largely
    unchanged, so a single code path handles both cases per the "content
    (markdown or html)" contract on the Proposal model.
    """
    body_html = markdown.markdown(content, extensions=["tables", "fenced_code"])
    body_html = _sanitize_html(body_html)
    document = f"<html><head>{_PDF_STYLE}</head><body>{body_html}</body></html>"

    buffer = io.BytesIO()
    result = pisa.CreatePDF(document, dest=buffer, encoding="utf-8", link_callback=_reject_external_uris)
    if result.err:
        logger.error("PDF generation failed: %s error(s) reported by xhtml2pdf", result.err)
        raise PdfGenerationError("Failed to render proposal content to PDF")

    return buffer.getvalue()
