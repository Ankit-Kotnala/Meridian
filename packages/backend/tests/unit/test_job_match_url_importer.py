"""SSRF and sanitization coverage for the Job Match URL importer."""

from __future__ import annotations

import pytest

from careeros.modules.job_match.domain import JobImportRejected
from careeros.modules.job_match.infrastructure.url_importer import _TextExtractor, _validate_url


def test_validate_url_rejects_non_http_and_loopback_destinations() -> None:
    with pytest.raises(JobImportRejected):
        _validate_url("file:///etc/passwd")
    with pytest.raises(JobImportRejected):
        _validate_url("http://127.0.0.1/job")
    with pytest.raises(JobImportRejected):
        _validate_url("http://[::1]/job")


def test_text_extractor_strips_scripts_and_keeps_visible_title() -> None:
    parser = _TextExtractor()
    parser.feed(
        """
        <html><head><title>Product Manager</title><script>alert(1)</script></head>
        <body><h1>Product Manager</h1><p>Must have user research experience.</p></body>
        </html>
        """
    )
    text = parser.text()

    assert parser.title() == "Product Manager"
    assert "alert" not in text
    assert "Must have user research experience." in text
