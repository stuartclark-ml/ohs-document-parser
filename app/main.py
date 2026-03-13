"""
FastAPI application — the API layer for the OHS Document Parser.

This is the entry point for the application. It defines the HTTP
endpoints that accept certificate uploads and return structured
extraction results.

Run locally with:
    uvicorn app.main:app --reload

The --reload flag watches for file changes and restarts the server
automatically during development. Never use --reload in production.
"""

import time
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import Response

from app.config import MAX_FILE_SIZE_MB
from app.ingestion.router import extract_text, is_supported_file
from app.classification.classifier import classify_document
from app.extraction.loler import extract_loler
from app.extraction.pressure import extract_pressure_vessel
from app.output.calendar import collect_calendar_entries, generate_ics
from app.output.json_output import generate_alerts, build_response
from app.output.summary import generate_summary
from app.validation.schemas import (
    DocumentType,
    ExtractionResponse,
)


# --- Create the FastAPI app ---

app = FastAPI(
    title="OHS Document Parser",
    description=(
        "AI-powered document intelligence for UK occupational health "
        "and safety certificates. Extracts structured data from LOLER "
        "thorough examination reports and PSSR pressure vessel certificates."
    ),
    version="0.1.0",
)


# --- Health check endpoint ---

@app.get("/health")
def health_check() -> dict:
    """
    Health check endpoint.

    Returns a simple JSON response confirming the API is running.
    Used by Railway (and any monitoring tool) to check the service
    is alive. This is the first thing deployment platforms hit to
    verify your app started correctly.

    Why a dedicated health endpoint?
    --------------------------------
    Railway, AWS, and most cloud platforms periodically ping a URL
    to check your app is responsive. If it stops responding, they
    restart it. Without this, they'd hit your main endpoint which
    might be slow or require auth — a lightweight /health is standard
    practice.
    """
    return {"status": "healthy", "service": "ohs-document-parser"}


# --- Main extraction endpoint ---

@app.post("/extract", response_model=ExtractionResponse)
async def extract_certificate(file: UploadFile) -> ExtractionResponse:
    """
    Upload a certificate and extract structured data.

    Accepts a PDF, JPG, or PNG file. Runs the full pipeline:
    1. Text extraction (PDF direct or OCR)
    2. Document classification (LOLER vs pressure vessel)
    3. Field extraction (regex + LLM)
    4. Alert generation
    5. Calendar entry generation
    6. Plain-English summary generation

    Parameters
    ----------
    file : UploadFile
        The uploaded certificate file. FastAPI handles multipart
        form data parsing automatically — the client sends the file
        as a multipart/form-data POST request and FastAPI gives us
        this UploadFile object.

    Returns
    -------
    ExtractionResponse
        The complete extraction result including fields, alerts,
        calendar entries, and summary.

    Raises
    ------
    HTTPException 400
        If the file type is unsupported or file is too large.
    HTTPException 500
        If extraction fails for any reason.

    Why async def?
    --------------
    FastAPI supports both sync (def) and async (async def) endpoints.
    We use async here because file I/O (reading the upload, writing
    to temp file) benefits from non-blocking execution. When one
    request is waiting for file I/O, the server can handle other
    requests. For a single-user demo this doesn't matter much, but
    it's the correct pattern for production APIs.

    Why a temp file?
    ----------------
    UploadFile gives us a file-like object in memory. But PyMuPDF
    and Tesseract need a real file path on disk. We write the upload
    to a temporary file, process it, then clean up. The tempfile
    module handles this safely — it creates files in the OS temp
    directory and we delete them in the finally block.
    """
    start_time = time.time()

    # --- Validate file type ---
    filename = file.filename or "unknown"
    if not is_supported_file(filename):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {Path(filename).suffix}. "
                f"Accepted formats: PDF, JPG, PNG."
            ),
        )

    # --- Validate file size ---
    # Read the file content into memory to check size
    # For very large files you'd stream this, but our 10MB limit
    # means reading into memory is fine
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large: {size_mb:.1f}MB. "
                f"Maximum allowed: {MAX_FILE_SIZE_MB}MB."
            ),
        )

    # --- Write to temp file for processing ---
    # suffix preserves the file extension so our router knows
    # how to handle it
    tmp_path = None
    try:
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        # --- Step 1: Text extraction ---
        text, extraction_method = extract_text(tmp_path)

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not extract any text from this file. "
                    "The document may be blank, corrupted, or in "
                    "an unsupported format."
                ),
            )

        # --- Step 2: Classification ---
        classification = classify_document(text)

        # --- Step 3: Field extraction ---
        if classification.document_type == DocumentType.LOLER:
            result = extract_loler(text, extraction_method)
        else:
            result = extract_pressure_vessel(text, extraction_method)

        # --- Step 4: Alerts ---
        alerts = generate_alerts(result)

        # --- Step 5: Calendar entries ---
        calendar_entries = collect_calendar_entries(
            result, classification.document_type
        )

        # --- Step 6: Summary ---
        summary = generate_summary(result)

        # --- Assemble response ---
        processing_time = time.time() - start_time

        response = build_response(
            result=result,
            calendar_entries=calendar_entries,
            alerts=alerts,
            summary=summary,
            processing_time_seconds=round(processing_time, 3),
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is (don't wrap them)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}",
        )
    finally:
        # Always clean up the temp file, even if an error occurred
        # This prevents temp files accumulating on disk
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


# --- Calendar download endpoint ---

@app.post("/extract/calendar")
async def extract_and_download_calendar(file: UploadFile) -> Response:
    """
    Upload a certificate and download an .ics calendar file.

    Runs the same pipeline as /extract but returns an .ics file
    instead of JSON. The user can import this directly into
    Outlook, Google Calendar, or Apple Calendar.

    Parameters
    ----------
    file : UploadFile
        The uploaded certificate file.

    Returns
    -------
    Response
        An .ics file as a downloadable attachment.

    Why a separate endpoint instead of including .ics in /extract?
    -------------------------------------------------------------
    The /extract endpoint returns JSON — it's for the API and
    Streamlit UI. This endpoint returns a binary file download —
    it's for users who just want the calendar reminder without
    the full extraction result. Different consumers, different
    response formats, different endpoints. This follows REST
    conventions where each endpoint returns one type of response.

    What is Response?
    -----------------
    FastAPI's Response class lets you return any content type,
    not just JSON. We set the media_type to "text/calendar" (the
    official MIME type for .ics files) and add a Content-Disposition
    header that tells the browser "download this as a file called
    reminders.ics" rather than displaying it inline.
    """
    # Run the extraction pipeline via the main endpoint logic
    # to avoid duplicating code
    extraction_response = await extract_certificate(file)

    if not extraction_response.calendar_entries:
        raise HTTPException(
            status_code=404,
            detail=(
                "No calendar entries could be generated. "
                "The certificate may not contain a next examination "
                "due date or repair deadline."
            ),
        )

    # Generate combined .ics file from all calendar entries
    ics_content = generate_ics(extraction_response.calendar_entries)

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=reminders.ics"
        },
    )