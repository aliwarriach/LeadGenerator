from unittest.mock import MagicMock, patch

import pytest

from app.services.pdf_service import PdfGenerationError, _reject_external_uris, _sanitize_html, render_proposal_pdf


def test_render_proposal_pdf_returns_pdf_bytes_for_markdown_content():
    pdf_bytes = render_proposal_pdf("# Proposal\n\nWe propose a full website redesign.")

    assert pdf_bytes.startswith(b"%PDF")


def test_render_proposal_pdf_returns_pdf_bytes_for_html_content():
    pdf_bytes = render_proposal_pdf("<h1>Proposal</h1><p>Full website redesign.</p>")

    assert pdf_bytes.startswith(b"%PDF")


def test_render_proposal_pdf_raises_on_render_failure():
    fake_result = MagicMock(err=1)

    with patch("app.services.pdf_service.pisa.CreatePDF", return_value=fake_result):
        with pytest.raises(PdfGenerationError):
            render_proposal_pdf("some content")


# ---- H-1 regression: SSRF / local-file access via resource resolution -----


def test_reject_external_uris_resolves_nothing():
    """The link_callback must never hand xhtml2pdf's default resolver a URI
    to fetch or open — that resolver is what makes real outbound HTTP
    requests and local filesystem reads (SecurityIssues.md H-1)."""
    assert _reject_external_uris("http://169.254.169.254/latest/meta-data/", "href") is None
    assert _reject_external_uris("/etc/passwd", "href") is None
    assert _reject_external_uris("file:///etc/passwd", "href") is None


def test_sanitize_html_strips_img_and_link_and_object_and_iframe_and_script_tags():
    html = (
        '<p>hello</p>'
        '<img src="http://169.254.169.254/latest/meta-data/">'
        '<link rel="stylesheet" href="/etc/passwd">'
        '<object data="http://internal-host:8080/"></object>'
        '<iframe src="http://internal-host:8080/"></iframe>'
        '<script>alert(1)</script>'
    )
    sanitized = _sanitize_html(html)

    assert "<img" not in sanitized
    assert "<link" not in sanitized
    assert "<object" not in sanitized
    assert "<iframe" not in sanitized
    assert "<script" not in sanitized
    assert "<p>hello</p>" in sanitized


def test_render_proposal_pdf_does_not_call_xhtml2pdfs_default_resolver_for_a_malicious_image():
    """End-to-end regression for H-1: content containing an SSRF/local-file
    payload must render without xhtml2pdf ever attempting to resolve it."""
    from xhtml2pdf.files import getFile

    resolved_uris: list[str] = []
    original_get_file = getFile

    def _spying_get_file(url, *args, **kwargs):
        resolved_uris.append(url)
        return original_get_file(url, *args, **kwargs)

    malicious_content = (
        "# Proposal\n\n"
        '<img src="http://169.254.169.254/latest/meta-data/">\n'
        '<link rel="stylesheet" href="/etc/passwd">\n'
    )

    with patch("xhtml2pdf.files.getFile", new=_spying_get_file):
        pdf_bytes = render_proposal_pdf(malicious_content)

    assert pdf_bytes.startswith(b"%PDF")
    assert resolved_uris == []
