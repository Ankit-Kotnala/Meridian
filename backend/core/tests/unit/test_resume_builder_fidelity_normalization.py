"""Tests for resume export fidelity text normalization."""

from __future__ import annotations

from rezumi.modules.resume_builder.domain.validation import normalize_fidelity_match_text


def test_normalize_fidelity_match_text_unifies_smart_quotes_and_control_chars() -> None:
    manifest = normalize_fidelity_match_text("Xmem is a India\u2019s First multi-modal product.")
    extracted = normalize_fidelity_match_text(
        "\x7f Xmem is a India's First multi-\nmodal product."
    )
    assert manifest == extracted
