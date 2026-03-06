"""
PDF text extraction using PyMuPDF.

Handles two scenarios:
1. Digital PDF — text embedded directly, extracted cleanly
2. Scanned PDF — image-based, detected by low character count
   and flagged for OCR fallback
"""

import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extract raw text from a digital PDF.

    Opens each page and extracts the embedded text content.
    Returns all pages concatenated as a single string.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as a string. Empty string if no text found.
    """
    doc = fitz.open(str(file_path))
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def is_scanned_pdf(
    file_path: str | Path,
    threshold: int = 100
) -> bool:
    """
    Detect whether a PDF is scanned (image-based) or digital.

    A digital PDF will return hundreds or thousands of characters
    when text is extracted. A scanned PDF contains no embedded text —
    PyMuPDF returns almost nothing.

    Args:
        file_path: Path to the PDF file
        threshold: Minimum character count to consider digital.
                   Default 100 — any less suggests scanned.

    Returns:
        True if scanned (needs OCR), False if digital
    """
    text = extract_text_from_pdf(file_path)
    return len(text) < threshold


def get_page_count(file_path: str | Path) -> int:
    """
    Return the number of pages in a PDF.

    Used to log document complexity and set processing
    expectations — a 10-page document takes longer than
    a single-page certificate.

    Args:
        file_path: Path to the PDF file

    Returns:
        Number of pages as integer
    """
    doc = fitz.open(str(file_path))
    count = len(doc)
    doc.close()
    return count