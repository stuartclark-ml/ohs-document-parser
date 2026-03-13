"""
Ingestion router — single entry point for all file uploads.

Determines the file type, routes to the correct text extractor,
and returns the extracted text along with the method used.

This keeps main.py clean — it just calls extract_text() and
gets back text regardless of whether the input was a digital PDF,
scanned PDF, or camera photo.
"""

from pathlib import Path

from app.config import OCR_TEXT_LENGTH_THRESHOLD
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.image_extractor import extract_text_from_image
from app.validation.schemas import ExtractionMethod


# File extensions we accept — lowercase, with leading dot
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def is_supported_file(file_path: str | Path) -> bool:
    """
    Check whether a file has a supported extension.

    Parameters
    ----------
    file_path : str or Path
        Path to the uploaded file.

    Returns
    -------
    bool
        True if the file extension is one we can process.

    Why use Path.suffix instead of string splitting?
    ------------------------------------------------
    Path(".../report.PDF").suffix returns ".PDF". Calling .lower()
    on it handles case insensitivity cleanly. String splitting on
    "." breaks on filenames like "my.report.v2.pdf".
    """
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS


def extract_text(file_path: str | Path) -> tuple[str, ExtractionMethod]:
    """
    Extract text from any supported file type.

    Routes to the correct extractor based on file type:
    - PDF → PyMuPDF direct extraction, with OCR fallback for scanned PDFs
    - JPG/PNG → Tesseract OCR, with Gemini Vision fallback

    Parameters
    ----------
    file_path : str or Path
        Path to the uploaded file.

    Returns
    -------
    tuple[str, ExtractionMethod]
        The extracted text and the method used to extract it.
        The method is recorded so we know how reliable the
        extraction is likely to be — direct PDF text is more
        reliable than OCR.

    Raises
    ------
    ValueError
        If the file type is not supported.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if extension == ".pdf":
        return _extract_from_pdf(path)
    else:
        # .jpg, .jpeg, .png
        return _extract_from_image(path)


def _extract_from_pdf(file_path: Path) -> tuple[str, ExtractionMethod]:
    """
    Extract text from a PDF file.

    First attempts direct text extraction (fast, accurate for
    digital PDFs). If the result is too short, the PDF is likely
    scanned — falls back to image-based OCR.

    Parameters
    ----------
    file_path : Path
        Path to the PDF file.

    Returns
    -------
    tuple[str, ExtractionMethod]
        Extracted text and the method used.
    """
    # Try direct text extraction first
    text = extract_text_from_pdf(file_path)

    if len(text) >= OCR_TEXT_LENGTH_THRESHOLD:
        return text, ExtractionMethod.PDF_DIRECT

    # Too little text — likely a scanned PDF
    # Fall back to image extraction (Tesseract → Gemini Vision)
    ocr_text, method_str = extract_text_from_image(file_path)

    # Map the string returned by image_extractor to our enum
    if method_str == "gemini_vision":
        return ocr_text, ExtractionMethod.GEMINI_VISION
    else:
        return ocr_text, ExtractionMethod.PDF_OCR_FALLBACK


def _extract_from_image(file_path: Path) -> tuple[str, ExtractionMethod]:
    """
    Extract text from an image file (JPG or PNG).

    Delegates to image_extractor which handles Tesseract → Gemini
    Vision fallback internally.

    Parameters
    ----------
    file_path : Path
        Path to the image file.

    Returns
    -------
    tuple[str, ExtractionMethod]
        Extracted text and the method used.
    """
    text, method_str = extract_text_from_image(file_path)

    if method_str == "gemini_vision":
        return text, ExtractionMethod.GEMINI_VISION
    else:
        return text, ExtractionMethod.OCR_IMAGE