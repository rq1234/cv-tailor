"""PDF and DOCX text extraction with quality scoring."""

from __future__ import annotations

import io
import re

import pdfplumber
from docx import Document


def extract_pdf_text(file_bytes: bytes) -> tuple[str, float]:
    """Extract text from a PDF file using pdfplumber.

    Returns (text, quality_score) where quality_score is 0-1.
    """
    text_parts: list[str] = []
    total_chars = 0
    garbled_chars = 0
    has_columns = False

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""

            # Detect multi-column layout by checking word positions
            words = page.extract_words()
            if words:
                x_positions = sorted(set(round(w["x0"], -1) for w in words))
                if len(x_positions) > 1:
                    gap = max(
                        x_positions[i + 1] - x_positions[i]
                        for i in range(len(x_positions) - 1)
                    )
                    if gap > 100:
                        has_columns = True
                        # Re-extract with column-aware settings
                        page_text = page.extract_text(
                            x_tolerance=3, y_tolerance=3
                        ) or page_text

            text_parts.append(page_text)
            total_chars += len(page_text)
            # Count garbled characters (non-ASCII, non-standard)
            garbled_chars += len(re.findall(r"[^\x20-\x7E\n\r\t]", page_text))

    full_text = "\n\n".join(text_parts).strip()

    # Quality scoring
    if total_chars == 0:
        return full_text, 0.0

    garble_ratio = garbled_chars / total_chars
    quality = max(0.0, 1.0 - garble_ratio * 5)  # Penalise garbled text heavily

    # Penalise very short extractions (likely failed)
    if total_chars < 100:
        quality *= 0.5

    return full_text, round(quality, 3)


def extract_docx_text(file_bytes: bytes) -> tuple[str, float]:
    """Extract text from a DOCX file using python-docx.

    Returns (text, quality_score). DOCX extraction is generally clean.
    """
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    quality = 1.0 if len(full_text) > 50 else 0.5
    return full_text, round(quality, 3)
