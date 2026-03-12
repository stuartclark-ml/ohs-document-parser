"""
Image text extraction using Tesseract OCR and Gemini Vision.

Handles two scenarios:
1. Good quality image — Tesseract extracts text reliably
2. Poor quality image — falls back to Gemini Vision which
   understands document layout and handles poor lighting,
   skew, and low resolution better than rule-based OCR
"""

import pytesseract
from PIL import Image
from pathlib import Path
import google.generativeai as genai
from app.config import GOOGLE_API_KEY, GOOGLE_MODEL, OCR_TEXT_LENGTH_THRESHOLD


def extract_text_from_image(file_path: str | Path) -> tuple[str, str]:
    """
    Extract text from a JPG or PNG image.

    Attempts Tesseract OCR first. If the result is below the
    quality threshold, falls back to Gemini Vision which handles
    poor quality photos significantly better.

    Args:
        file_path: Path to the image file

    Returns:
        Tuple of (extracted_text, method_used)
        method_used is either "ocr_image" or "gemini_vision"
    """
    # Attempt Tesseract first
    tesseract_text = _tesseract_extract(file_path)

    if len(tesseract_text) >= OCR_TEXT_LENGTH_THRESHOLD:
        return tesseract_text, "ocr_image"

    # Tesseract returned too little text — fall back to Gemini Vision
    gemini_text = _gemini_vision_extract(file_path)
    return gemini_text, "gemini_vision"


def _tesseract_extract(file_path: str | Path) -> str:
    """
    Extract text using Tesseract OCR.

    Converts image to RGB first — Tesseract requires RGB format.
    CMYK images (common in professional print PDFs) and RGBA images
    (PNG with transparency) will fail without this conversion.

    Args:
        file_path: Path to the image file

    Returns:
        Extracted text string. Empty string if extraction fails.
    """
    try:
        image = Image.open(str(file_path))
        if image.mode != "RGB":
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image, lang="eng")
        return text.strip()
    except Exception as e:
        # Do not crash the pipeline on OCR failure
        # Return empty string and let the fallback handle it
        print(f"Tesseract extraction failed: {e}")
        return ""


def _gemini_vision_extract(file_path: str | Path) -> str:
    """
    Extract text from image using Gemini Vision.

    Used as fallback when Tesseract returns poor results.
    Gemini Vision understands document layout and handles:
    - Poor lighting from phone photos
    - Slight rotation or skew
    - Low resolution images
    - Mixed layouts with tables and text

    Args:
        file_path: Path to the image file

    Returns:
        Extracted text string
    """
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GOOGLE_MODEL)

    image = Image.open(str(file_path))

    prompt = """Extract all text from this certificate image.
Return the raw text exactly as it appears on the document.
Preserve the structure — keep labels and values on the same line.
Do not summarise or interpret — just extract the text."""

    response = model.generate_content([prompt, image])
    return response.text.strip()