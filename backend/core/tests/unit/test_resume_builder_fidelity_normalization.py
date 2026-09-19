"""Tests for resume export fidelity text normalization."""

from __future__ import annotations

from collections import Counter

from rezumi.modules.resume_builder.application.export_workflow import (
    _manifest_occurrence_counts,
)
from rezumi.modules.resume_builder.domain.validation import normalize_fidelity_match_text


def test_normalize_fidelity_match_text_unifies_smart_quotes_and_control_chars() -> None:
    manifest = normalize_fidelity_match_text("Xmem is a India\u2019s First multi-modal product.")
    extracted = normalize_fidelity_match_text(
        "\x7f Xmem is a India's First multi-\nmodal product."
    )
    assert manifest == extracted


def test_normalize_fidelity_match_text_repairs_glued_pdf_section_headings() -> None:
    extracted = normalize_fidelity_match_text("Software EngineerEXPERIENCE Primary language")
    assert "software engineer experience primary language" == extracted


def test_normalize_fidelity_match_text_repairs_missing_space_after_sentence_punctuation() -> None:
    extracted = normalize_fidelity_match_text(
        "Layer for AI agents.Primary language: Python."
    )
    assert (
        "layer for ai agents. primary language: python."
        == extracted
    )
    assert "ankit.kotnala12@gmail.com" in normalize_fidelity_match_text(
        "Contact: ankit.kotnala12@gmail.com"
    )


def test_manifest_occurrence_counts_finds_glued_pdf_phrases() -> None:
    text = normalize_fidelity_match_text(
        "Software EngineerEXPERIENCE Primary language: Jupyter Notebook."
    )
    expected = Counter(
        {
            "software engineer": 1,
            "experience": 1,
            "primary language: jupyter notebook.": 1,
        }
    )
    assert _manifest_occurrence_counts(text, expected) == {
        "software engineer": 1,
        "experience": 1,
        "primary language: jupyter notebook.": 1,
    }
