"""
Pydantic schemas for certificate extraction results.

These models define exactly what fields are extracted from each
certificate type, their data types, and validation rules.
All other modules produce or consume these models.
"""

from pydantic import BaseModel, field_validator
from datetime import date
from enum import Enum
from typing import Optional


class DefectOutcome(str, Enum):
    """
    Possible outcomes when a defect is noted on a certificate.
    Based on real-world OHS practice — three distinct action levels.
    """
    IMMEDIATE_PROHIBITION = "IMMEDIATE_PROHIBITION"
    # Equipment must be taken out of service immediately.
    # No further use until repaired and re-examined.

    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    # Repair needed before next use or within a specified deadline.
    # Equipment may continue in use until deadline if safe to do so.

    ADVISORY = "ADVISORY"
    # Monitor only. No immediate action required.
    # Record and review at next examination.

    NONE = "NONE"
    # No defects noted. Certificate is clear.


class DocumentType(str, Enum):
    """Supported certificate types."""
    LOLER = "LOLER"
    PRESSURE_VESSEL = "PRESSURE_VESSEL"


class ExtractionMethod(str, Enum):
    """How the text was extracted from the document."""
    PDF_DIRECT = "pdf_direct"
    # Digital PDF — text extracted directly by PyMuPDF
    OCR_IMAGE = "ocr_image"
    # JPG or PNG — text extracted by Tesseract OCR
    PDF_OCR_FALLBACK = "pdf_ocr_fallback"
    # Scanned PDF — converted to image then OCR'd
    GEMINI_VISION = "gemini_vision"
    # Poor quality image — sent directly to Gemini Vision


class BaseExtractionResult(BaseModel):
    """
    Fields common to all certificate types.
    LOLER and pressure vessel schemas inherit from this.
    """
    document_type: DocumentType
    certificate_number: Optional[str] = None
    issuing_body: Optional[str] = None
    date_of_examination: Optional[date] = None
    next_examination_due: Optional[date] = None
    examiner_name: Optional[str] = None
    defect_outcome: DefectOutcome = DefectOutcome.NONE
    defect_description: Optional[str] = None
    repair_deadline: Optional[date] = None
    extraction_method: ExtractionMethod
    warnings: list[str] = []

    @field_validator("next_examination_due")
    @classmethod
    def flag_overdue_certificate(
        cls, v: Optional[date]
    ) -> Optional[date]:
        """
        Do not reject overdue certificates — an overdue certificate
        is itself critical compliance information.
        Flag it as a warning instead.
        The warning is added in the extraction pipeline.
        """
        return v

    @field_validator("repair_deadline")
    @classmethod
    def flag_passed_repair_deadline(
        cls, v: Optional[date]
    ) -> Optional[date]:
        """
        A passed repair deadline is a serious compliance failure.
        Flag it — do not reject.
        """
        return v


class LOLERExtractionResult(BaseExtractionResult):
    """
    Extraction schema for LOLER thorough examination reports.

    LOLER = Lifting Operations and Lifting Equipment Regulations 1998.
    Applies to all lifting equipment — cranes, hoists, fork lifts,
    patient hoists, MEWPs, lifting accessories.

    Statutory examination frequency:
    - 6 months: equipment used to lift people
    - 12 months: all other lifting equipment
    - Or as specified in a written scheme of examination
    """
    document_type: DocumentType = DocumentType.LOLER
    equipment_description: Optional[str] = None
    equipment_id: Optional[str] = None
    safe_working_load: Optional[str] = None
    location: Optional[str] = None


class PressureVesselExtractionResult(BaseExtractionResult):
    """
    Extraction schema for pressure vessel / pressure system
    inspection certificates.

    PSSR = Pressure Systems Safety Regulations 2000.
    Applies to steam boilers, compressed air systems, autoclaves,
    pressurised pipework, and associated protective devices.

    Examination interval defined by Written Scheme of Examination —
    varies by system type and risk level.
    """
    document_type: DocumentType = DocumentType.PRESSURE_VESSEL
    system_description: Optional[str] = None
    plant_id: Optional[str] = None
    maximum_allowable_working_pressure: Optional[str] = None
    location: Optional[str] = None


class ClassificationResult(BaseModel):
    """Result from the document classifier."""
    document_type: DocumentType
    confidence: float
    requires_user_confirmation: bool
    scores: dict[str, float]


class CalendarEntry(BaseModel):
    """A single calendar entry generated from extraction results."""
    title: str
    due_date: date
    lead_alert_date: date
    entry_type: str
    # "examination_due", "repair_deadline"
    urgency: str
    # "overdue", "upcoming", "high"
    ical_data: Optional[bytes] = None


class Alert(BaseModel):
    """An urgent alert generated from extraction results."""
    level: str
    # "critical", "warning", "info"
    message: str


class ExtractionResponse(BaseModel):
    """
    Top-level response returned to the user from the API.
    Contains everything needed to display results and
    generate calendar entries.
    """
    result: LOLERExtractionResult | PressureVesselExtractionResult
    calendar_entries: list[CalendarEntry] = []
    alerts: list[Alert] = []
    summary: str = ""
    processing_time_seconds: Optional[float] = None