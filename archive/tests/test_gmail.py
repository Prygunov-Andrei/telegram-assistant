"""Tests for Gmail body extraction and attachment listing."""
from __future__ import annotations

import base64

from src.integrations.google_services import GoogleServices


def _make_service() -> GoogleServices:
    """Create a GoogleServices instance without connecting (for static method tests)."""
    svc = object.__new__(GoogleServices)
    return svc


class TestExtractBody:
    def test_plain_text(self):
        svc = _make_service()
        payload = {
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(b"Hello world").decode()},
        }
        assert svc._extract_body(payload) == "Hello world"

    def test_html_stripped(self):
        svc = _make_service()
        html = "<html><body><p>Hello</p><br><b>World</b></body></html>"
        payload = {
            "mimeType": "text/html",
            "body": {"data": base64.urlsafe_b64encode(html.encode()).decode()},
        }
        result = svc._extract_body(payload)
        assert "Hello" in result
        assert "World" in result
        assert "<" not in result

    def test_multipart_prefers_plain(self):
        svc = _make_service()
        plain_data = base64.urlsafe_b64encode(b"Plain text").decode()
        html_data = base64.urlsafe_b64encode(b"<b>HTML text</b>").decode()
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": plain_data}},
                {"mimeType": "text/html", "body": {"data": html_data}},
            ],
        }
        assert svc._extract_body(payload) == "Plain text"

    def test_multipart_fallback_html(self):
        svc = _make_service()
        html_data = base64.urlsafe_b64encode(b"<p>Only HTML</p>").decode()
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": html_data}},
            ],
        }
        result = svc._extract_body(payload)
        assert "Only HTML" in result
        assert "<p>" not in result

    def test_empty_payload(self):
        svc = _make_service()
        assert svc._extract_body({}) == ""

    def test_quoted_text_trimmed(self):
        svc = _make_service()
        text = "New reply\n\nOn Mon, Jan 1 wrote:\n> old message\n> more old"
        payload = {
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(text.encode()).decode()},
        }
        result = svc._extract_body(payload)
        assert "New reply" in result
        assert "old message" not in result

    def test_charset_handling(self):
        svc = _make_service()
        # Simulate a latin-1 encoded message
        text_bytes = "Ärger mit Ü".encode("latin-1")
        payload = {
            "mimeType": "text/plain",
            "headers": [{"name": "Content-Type", "value": "text/plain; charset=iso-8859-1"}],
            "body": {"data": base64.urlsafe_b64encode(text_bytes).decode()},
        }
        result = svc._extract_body(payload)
        assert "rger" in result  # Should decode properly


class TestStripHtml:
    def test_br_to_newline(self):
        assert "\n" in GoogleServices._strip_html("line1<br>line2")

    def test_entities(self):
        result = GoogleServices._strip_html("&amp; &lt; &gt; &quot; &nbsp;")
        assert "&" in result
        assert "<" in result


class TestTrimQuoted:
    def test_preserves_original(self):
        result = GoogleServices._trim_quoted("Hello\nWorld")
        assert "Hello" in result
        assert "World" in result

    def test_trims_on_wrote(self):
        text = "Reply text\n\nOn 2024-01-01, John wrote:\n> quoted"
        result = GoogleServices._trim_quoted(text)
        assert "Reply text" in result
        assert "quoted" not in result

    def test_trims_angle_quotes(self):
        text = "Reply\n> quote1\n> quote2\nAfter"
        result = GoogleServices._trim_quoted(text)
        assert "Reply" in result
        assert "quote1" not in result


class TestListAttachments:
    def test_simple_attachment(self):
        svc = _make_service()
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": "dGVzdA=="}},
                {
                    "filename": "report.pdf",
                    "mimeType": "application/pdf",
                    "body": {"size": 12345, "attachmentId": "ATT_001"},
                },
            ],
        }
        atts = svc._list_attachments(payload)
        assert len(atts) == 1
        assert atts[0]["filename"] == "report.pdf"
        assert atts[0]["attachmentId"] == "ATT_001"

    def test_no_attachments(self):
        svc = _make_service()
        payload = {"mimeType": "text/plain", "body": {"data": "dGVzdA=="}}
        assert svc._list_attachments(payload) == []

    def test_nested_attachments(self):
        svc = _make_service()
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": "dGVzdA=="}},
                    ],
                },
                {
                    "filename": "image.jpg",
                    "mimeType": "image/jpeg",
                    "body": {"size": 5000, "attachmentId": "ATT_002"},
                },
            ],
        }
        atts = svc._list_attachments(payload)
        assert len(atts) == 1
        assert atts[0]["filename"] == "image.jpg"
