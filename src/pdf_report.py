"""Minimal PDF rendering helpers for autoresearch artifacts.

This module intentionally avoids external dependencies. It produces a simple,
text-first PDF suitable for sharing or printing research summaries.
"""

from __future__ import annotations

from textwrap import wrap


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 54
TOP_MARGIN = 54
BOTTOM_MARGIN = 54
LINE_HEIGHT = 14
FONT_SIZE = 11
MAX_CHARS_PER_LINE = 95


def render_simple_pdf(title: str, sections: list[tuple[str, str]]) -> bytes:
    """Render a basic multi-page PDF from titled text sections."""
    lines = [title, ""]
    for heading, body in sections:
        lines.append(heading.upper())
        lines.extend(_wrap_paragraphs(body))
        lines.append("")

    pages = _paginate(lines)
    objects: list[bytes] = []
    font_id = 3

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    kids = " ".join(f"{4 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>".encode("ascii"))

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, page_lines in enumerate(pages):
        content_stream = _content_stream(page_lines)
        content_obj_num = 5 + index * 2
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_obj_num} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            f"<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
            + content_stream
            + b"\nendstream"
        )

    return _build_pdf(objects)


def _wrap_paragraphs(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        stripped = raw_line.rstrip()
        if not stripped:
            lines.append("")
            continue
        wrapped = wrap(stripped, width=MAX_CHARS_PER_LINE, replace_whitespace=False, drop_whitespace=False)
        lines.extend(wrapped or [""])
    return lines


def _paginate(lines: list[str]) -> list[list[str]]:
    max_lines = int((PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN) / LINE_HEIGHT)
    pages: list[list[str]] = []
    for i in range(0, len(lines), max_lines):
        pages.append(lines[i : i + max_lines])
    return pages or [["(empty report)"]]


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(lines: list[str]) -> bytes:
    y = PAGE_HEIGHT - TOP_MARGIN
    commands = [b"BT", f"/F1 {FONT_SIZE} Tf".encode("ascii")]
    for line in lines:
        commands.append(f"1 0 0 1 {LEFT_MARGIN} {y} Tm ({_escape_pdf_text(line)}) Tj".encode("utf-8"))
        y -= LINE_HEIGHT
    commands.append(b"ET")
    return b"\n".join(commands)


def _build_pdf(objects: list[bytes]) -> bytes:
    buffer = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode("ascii"))
        buffer.extend(obj)
        buffer.extend(b"\nendobj\n")

    xref_offset = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(buffer)
