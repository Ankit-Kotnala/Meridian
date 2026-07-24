"""Deterministic ATS-friendly resume renderers for Phase 7."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from docx import Document

from careeros.modules.resume_builder.application import RenderedResume
from careeros.modules.resume_builder.application.ports import ResumeRenderer
from careeros.modules.resume_builder.domain import ResumeFormat, ResumeSection, ResumeVersion

RENDERER_VERSION = "resume-renderer-v1"


class DeterministicResumeRenderer(ResumeRenderer):
    """Render single-column searchable resume outputs without external services."""

    def render(self, version: ResumeVersion, *, fmt: str) -> RenderedResume:
        requested = ResumeFormat(fmt)
        lines = _lines(version)
        if requested == ResumeFormat.PDF:
            return RenderedResume(
                media_type="application/pdf",
                filename="resume.pdf",
                content=_pdf(lines),
                expected_lines=lines,
                renderer_version=RENDERER_VERSION,
            )
        if requested == ResumeFormat.DOCX:
            return RenderedResume(
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                filename="resume.docx",
                content=_docx(version),
                expected_lines=lines,
                renderer_version=RENDERER_VERSION,
            )
        if requested == ResumeFormat.JSON:
            content = json.dumps(
                {
                    "schemaVersion": "resume-export-json-v1",
                    "versionId": str(version.id),
                    "title": version.title,
                    "targetRole": version.target_role,
                    "template": version.template.value,
                    "sections": [
                        {
                            "id": str(section.id),
                            "title": section.title,
                            "kind": section.kind,
                            "items": [
                                {
                                    "id": str(item.id),
                                    "text": item.text,
                                    "evidenceIds": [str(value) for value in item.evidence_ids],
                                    "source": item.source,
                                }
                                for item in section.items
                            ],
                        }
                        for section in version.sections
                    ],
                },
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            return RenderedResume(
                media_type="application/json",
                filename="resume.json",
                content=content,
                expected_lines=lines,
                renderer_version=RENDERER_VERSION,
            )
        return RenderedResume(
            media_type="text/plain; charset=utf-8",
            filename="resume.txt",
            content=("\n".join(lines) + "\n").encode("utf-8"),
            expected_lines=lines,
            renderer_version=RENDERER_VERSION,
        )


def _lines(version: ResumeVersion) -> tuple[str, ...]:
    lines = [version.title]
    if version.target_role:
        lines.append(version.target_role)
    if version.template.value:
        lines.append(_template_label(version.template.value))
    for section in version.sections:
        lines.append(section.title)
        lines.extend(item.text for item in section.items)
    return tuple(line for line in lines if line.strip())


def _template_label(value: str) -> str:
    labels = {
        "standard_professional": "Standard Professional",
        "compact_technical": "Compact Technical",
        "executive": "Executive",
        "graduate": "Graduate",
        "consulting_finance": "Consulting and Finance",
    }
    return labels[value]


def _docx(version: ResumeVersion) -> bytes:
    document = Document()
    document.add_heading(version.title, level=0)
    if version.target_role:
        document.add_paragraph(version.target_role)
    document.add_paragraph(_template_label(version.template.value))
    for section in version.sections:
        document.add_heading(section.title, level=1)
        _add_section(document, section)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _add_section(document: Any, section: ResumeSection) -> None:
    for item in section.items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.add_run(item.text)


def _pdf(lines: tuple[str, ...]) -> bytes:
    pages = [lines[index : index + 42] for index in range(0, len(lines), 42)] or [()]
    objects: list[bytes] = [b""]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    font_object_id = 3 + len(pages) * 2
    for index, page_lines in enumerate(pages):
        page_id = 3 + index * 2
        content_id = page_id + 1
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        stream = _pdf_stream(page_lines)
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return _pdf_document(objects)


def _pdf_stream(lines: tuple[str, ...]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "72 740 Td", "14 TL"]
    for line in lines:
        commands.append(f"({_escape_pdf_text(line)}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _escape_pdf_text(value: str) -> str:
    table: dict[str, str | int | None] = {"\\": "\\\\", "(": "\\(", ")": "\\)"}
    return (
        value.encode("latin-1", errors="replace").decode("latin-1").translate(str.maketrans(table))
    )


def _pdf_document(objects: list[bytes]) -> bytes:
    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    for index, body in enumerate(objects[1:], start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii"))
        chunks.append(body)
        chunks.append(b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects)}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        (
            f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return b"".join(chunks)
