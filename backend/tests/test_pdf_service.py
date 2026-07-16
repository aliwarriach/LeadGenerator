from unittest.mock import MagicMock, patch

import pytest

from app.services.pdf_service import PdfGenerationError, render_proposal_pdf


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
