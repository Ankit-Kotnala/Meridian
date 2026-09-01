"""Reconstruct PDF reading order from glyph positions.

pypdf's default ``extract_text`` follows content-stream order. Word and
Google Docs two-column resumes often emit left-cell then right-cell of each
row, which interleaves Experience with Skills. Resume review needs column
order: left column top-to-bottom, then right.

Visitor text is only reordered. Layout-mode reconstruction splits on the
wide gaps pypdf already inserted; cell strings stay exact PDF text. Nothing
is invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from pypdf import PageObject

_MIN_COLUMN_GAP_POINTS = 60.0
_MIN_COLUMN_LINES = 2
_HEADER_BAND = 0.90
_FOOTER_BAND = 0.12
_LINE_Y_TOLERANCE_RATIO = 0.4
_MIN_LINE_Y_TOLERANCE = 3.0
_LAYOUT_COLUMN_GAP = re.compile(r"[ \t]{8,}")


@dataclass(frozen=True, slots=True)
class _Run:
    x: float
    y: float
    font_size: float
    text: str
    rotated: bool


@dataclass(frozen=True, slots=True)
class _Line:
    x0: float
    y: float
    text: str


def extract_pdf_pages(pages: list[PageObject]) -> tuple[list[str], tuple[str, ...]]:
    """Return per-page text in resume reading order plus layout signals."""
    collected: list[tuple[list[_Line], bool, float, str]] = []
    for page in pages:
        height = _page_height(page)
        lines, rotated = _lines_from_visitor(page)
        fallback = (page.extract_text() or "").replace("\x00", "")
        try:
            layout_text = page.extract_text(extraction_mode="layout") or ""
        except (TypeError, ValueError):
            layout_text = ""
        if _visitor_too_sparse(lines, fallback) or rotated:
            collected.append((_fallback_lines(fallback), False, height, layout_text))
            continue
        collected.append((lines, True, height, layout_text))

    repeating = _repeating_band_text(collected)
    page_texts: list[str] = []
    signals: list[str] = []
    for lines, positioned, _height, layout_text in collected:
        kept = [line for line in lines if _normalize_line(line.text) not in repeating]
        if repeating and len(kept) < len(lines):
            signals.append("header_footer_present")
        columns = _split_columns(kept) if positioned else None
        if columns is not None:
            ordered_lines = [
                line for column in columns for line in sorted(column, key=lambda item: -item.y)
            ]
            page_texts.append("\n".join(line.text for line in ordered_lines))
            signals.append("multi_column_candidate")
            signals.append("multi_column_reconstructed")
            continue
        layout_columns = _reconstruct_from_layout(layout_text)
        if layout_columns is not None:
            page_texts.append("\n".join(layout_columns))
            signals.append("multi_column_candidate")
            signals.append("multi_column_reconstructed")
            continue
        ordered = sorted(kept, key=lambda line: -line.y) if positioned else kept
        page_texts.append("\n".join(line.text for line in ordered))
        if (positioned and _looks_multicolumn(kept)) or _LAYOUT_COLUMN_GAP.search(layout_text):
            signals.append("multi_column_candidate")
    return page_texts, tuple(dict.fromkeys(signals))


def _page_height(page: PageObject) -> float:
    try:
        return float(page.mediabox.height)
    except (AttributeError, TypeError, ValueError):
        return 792.0


def _lines_from_visitor(page: PageObject) -> tuple[list[_Line], bool]:
    runs: list[_Run] = []
    rotated = False

    def visitor(text: object, cm: object, tm: object, font_dict: object, font_size: object) -> None:
        del cm, font_dict
        if not isinstance(text, str) or not isinstance(tm, (list, tuple)) or len(tm) < 6:
            return
        cleaned = text.replace("\r", "").replace("\n", "").replace("\x00", "")
        if not cleaned.strip():
            return
        try:
            x = float(tm[4])
            y = float(tm[5])
            a = float(tm[0])
            b = float(tm[1])
            c = float(tm[2])
            d = float(tm[3])
        except (TypeError, ValueError, IndexError):
            return
        size = (
            float(font_size)
            if isinstance(font_size, int | float) and not isinstance(font_size, bool)
            else 10.0
        )
        if x == 0.0 and y == 0.0 and abs(a - 1.0) < 0.01 and abs(d - 1.0) < 0.01:
            return
        is_rotated = abs(b) > 0.15 or abs(c) > 0.15 or a * d < 0
        nonlocal rotated
        rotated = rotated or is_rotated
        runs.append(_Run(x=x, y=y, font_size=max(size, 1.0), text=cleaned, rotated=is_rotated))

    try:
        page.extract_text(visitor_text=visitor)
    except (TypeError, ValueError):
        return [], True
    return _cluster_lines(runs), rotated


def _cluster_lines(runs: list[_Run]) -> list[_Line]:
    if not runs:
        return []
    remaining = sorted(runs, key=lambda run: (-round(run.y, 1), run.x))
    lines: list[_Line] = []
    while remaining:
        seed = remaining.pop(0)
        tolerance = max(_MIN_LINE_Y_TOLERANCE, seed.font_size * _LINE_Y_TOLERANCE_RATIO)
        same_line = [seed]
        kept: list[_Run] = []
        for run in remaining:
            if abs(run.y - seed.y) <= tolerance:
                same_line.append(run)
            else:
                kept.append(run)
        remaining = kept
        same_line.sort(key=lambda run: run.x)
        fragments: list[list[_Run]] = [[same_line[0]]]
        for run in same_line[1:]:
            previous = fragments[-1][-1]
            estimated_end = previous.x + (len(previous.text) * previous.font_size * 0.5)
            if run.x - estimated_end >= _MIN_COLUMN_GAP_POINTS:
                fragments.append([run])
            else:
                fragments[-1].append(run)
        for fragment in fragments:
            parts: list[str] = []
            previous_end = None
            for run in fragment:
                if (
                    previous_end is not None
                    and run.x - previous_end > max(1.0, run.font_size * 0.15)
                    and parts
                    and not parts[-1].endswith(" ")
                    and not run.text.startswith(" ")
                ):
                    parts.append(" ")
                parts.append(run.text)
                previous_end = run.x + (len(run.text) * run.font_size * 0.5)
            text = "".join(parts).strip()
            if text:
                lines.append(_Line(x0=fragment[0].x, y=seed.y, text=text))
    return lines


def _fallback_lines(text: str) -> list[_Line]:
    return [
        _Line(x0=0.0, y=float(-index), text=line.strip())
        for index, line in enumerate(text.splitlines())
        if line.strip()
    ]


def _visitor_too_sparse(lines: list[_Line], fallback: str) -> bool:
    visitor_len = sum(len(_alnum(line.text)) for line in lines)
    fallback_len = len(_alnum(fallback))
    if fallback_len == 0:
        return False
    return visitor_len < fallback_len * 0.85


def _alnum(value: str) -> str:
    return "".join(character for character in value if character.isalnum())


def _normalize_line(value: str) -> str:
    return " ".join(value.split()).casefold()


def _repeating_band_text(
    collected: list[tuple[list[_Line], bool, float, str]],
) -> frozenset[str]:
    if len(collected) < 2:
        return frozenset()
    seen: dict[str, set[int]] = {}
    for page_index, (lines, positioned, height, _layout_text) in enumerate(collected):
        if not positioned or height <= 0:
            continue
        for line in lines:
            in_header = line.y >= height * _HEADER_BAND
            in_footer = 0.0 <= line.y <= height * _FOOTER_BAND
            if not in_header and not in_footer:
                continue
            normalized = _normalize_line(line.text)
            if not normalized:
                continue
            seen.setdefault(normalized, set()).add(page_index)
    return frozenset(text for text, pages in seen.items() if len(pages) >= 2)


def _reconstruct_from_layout(layout_text: str) -> list[str] | None:
    """Stack left then right cells from layout-mode lines with wide column gaps."""
    if not _LAYOUT_COLUMN_GAP.search(layout_text):
        return None
    left: list[str] = []
    right: list[str] = []
    saw_split = False
    for raw_line in layout_text.splitlines():
        if not raw_line.strip():
            continue
        parts = [part.strip() for part in _LAYOUT_COLUMN_GAP.split(raw_line) if part.strip()]
        if len(parts) >= 2:
            saw_split = True
            left.append(parts[0])
            right.extend(parts[1:])
            continue
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent >= 40:
            right.append(stripped)
        else:
            left.append(stripped)
    if not saw_split or not left or not right:
        return None
    return left + right


def _looks_multicolumn(lines: list[_Line]) -> bool:
    return _split_columns(lines) is not None or _widest_x_gap(lines) >= _MIN_COLUMN_GAP_POINTS


def _widest_x_gap(lines: list[_Line]) -> float:
    unique = sorted({round(line.x0, 1) for line in lines})
    if len(unique) < 2:
        return 0.0
    return max(right - left for left, right in pairwise(unique))


def _split_columns(lines: list[_Line]) -> list[list[_Line]] | None:
    """Return left then right when the page is a confident two-column layout."""
    if len(lines) < _MIN_COLUMN_LINES * 2:
        return None
    unique = sorted({round(line.x0, 1) for line in lines})
    if len(unique) < 2:
        return None
    gap, split_at = max(
        ((unique[index + 1] - unique[index], index) for index in range(len(unique) - 1)),
        key=lambda item: item[0],
    )
    if gap < _MIN_COLUMN_GAP_POINTS:
        return None
    mid = (unique[split_at] + unique[split_at + 1]) / 2
    left = [line for line in lines if line.x0 < mid]
    right = [line for line in lines if line.x0 >= mid]
    if len(left) < _MIN_COLUMN_LINES or len(right) < _MIN_COLUMN_LINES:
        return None
    if _widest_x_gap(left) >= _MIN_COLUMN_GAP_POINTS and _column_pair(left) is not None:
        return None
    if _widest_x_gap(right) >= _MIN_COLUMN_GAP_POINTS and _column_pair(right) is not None:
        return None
    return [left, right]


def _column_pair(lines: list[_Line]) -> list[list[_Line]] | None:
    unique = sorted({round(line.x0, 1) for line in lines})
    if len(unique) < 2:
        return None
    gap, split_at = max(
        ((unique[index + 1] - unique[index], index) for index in range(len(unique) - 1)),
        key=lambda item: item[0],
    )
    if gap < _MIN_COLUMN_GAP_POINTS:
        return None
    mid = (unique[split_at] + unique[split_at + 1]) / 2
    left = [line for line in lines if line.x0 < mid]
    right = [line for line in lines if line.x0 >= mid]
    if len(left) < _MIN_COLUMN_LINES or len(right) < _MIN_COLUMN_LINES:
        return None
    return [left, right]
