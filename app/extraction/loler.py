"""
LOLER certificate field extraction.

Takes raw text from a LOLER thorough examination report,
sends it to the LLM extractor, and returns a validated
LOLERExtractionResult Pydantic object.

Also handles post-extraction logic:
- Overdue certificate detection
- Passed repair deadline detection
- Warning generation
"""

from datetime import date
from app.extraction.llm_extractor import extract_fields
from app.extraction.regex_patterns import parse_date_string
from app.validation.schemas import (
    LOLERExtractionResult,
    DefectOutcome,
    ExtractionMethod,
    DocumentType,
)


def extract_loler(
    text: str,
    extraction_method: ExtractionMethod
) -> LOLERExtractionResult:
    """
    Extract fields from a LOLER thorough examination report.

    Sends text to LLM extractor, parses the response into a
    validated LOLERExtractionResult, then runs post-extraction
    checks to generate warnings.

    Args:
        text: Raw certificate text
        extraction_method: How the text was extracted from the document

    Returns:
        Validated LOLERExtractionResult with warnings populated
    """
    # Get raw field dictionary from LLM
    raw = extract_fields(text, DocumentType.LOLER)

    # Build validated Pydantic object from raw dictionary
    result = LOLERExtractionResult(
        extraction_method=extraction_method,
        certificate_number=raw.get("certificate_number"),
        issuing_body=raw.get("issuing_body"),
        examiner_name=raw.get("examiner_name"),
        date_of_examination=parse_date_string(raw.get("date_of_examination")),
        next_examination_due=parse_date_string(raw.get("next_examination_due")),
        equipment_description=raw.get("equipment_description"),
        equipment_id=raw.get("equipment_id"),
        safe_working_load=raw.get("safe_working_load"),
        location=raw.get("location"),
        defect_outcome=_parse_defect_outcome(
            raw.get("defect_outcome", "NONE")
        ),
        defect_description=raw.get("defect_description"),
        repair_deadline=parse_date_string(raw.get("repair_deadline")),
    )

    # Run post-extraction checks and populate warnings
    result = _add_warnings(result)

    return result


def _parse_defect_outcome(value: str | None) -> DefectOutcome:
    """
    Safely parse defect outcome string to enum value.

    The LLM may return unexpected values despite prompt instructions.
    This handles unknown values gracefully rather than crashing.

    Args:
        value: Raw string from LLM response

    Returns:
        DefectOutcome enum value. Defaults to NONE if unrecognised.
    """
    if value is None:
        return DefectOutcome.NONE
    try:
        return DefectOutcome(value.upper().strip())
    except ValueError:
        # LLM returned something unexpected
        # Default to NONE and let the warning system flag it
        return DefectOutcome.NONE


def _add_warnings(result: LOLERExtractionResult) -> LOLERExtractionResult:
    """
    Check extraction result for compliance issues and add warnings.

    Checks performed:
    1. Overdue next examination date
    2. Passed repair deadline
    3. Immediate prohibition — equipment must be out of service
    4. Missing critical fields

    Args:
        result: LOLERExtractionResult to check

    Returns:
        Same result with warnings list populated
    """
    today = date.today()
    warnings = []

    # Check for overdue examination
    if result.next_examination_due and result.next_examination_due < today:
        days_overdue = (today - result.next_examination_due).days
        warnings.append(
            f"OVERDUE: Next examination was due "
            f"{result.next_examination_due.isoformat()} "
            f"({days_overdue} days ago)"
        )

    # Check for passed repair deadline
    if result.repair_deadline and result.repair_deadline < today:
        days_overdue = (today - result.repair_deadline).days
        warnings.append(
            f"REPAIR DEADLINE PASSED: Repair was due by "
            f"{result.repair_deadline.isoformat()} "
            f"({days_overdue} days ago)"
        )

    # Flag immediate prohibition clearly
    if result.defect_outcome == DefectOutcome.IMMEDIATE_PROHIBITION:
        warnings.append(
            "IMMEDIATE PROHIBITION: Equipment must be taken out of "
            "service. Do not use until repaired and re-examined."
        )

    # Flag missing next examination date
    if result.next_examination_due is None:
        warnings.append(
            "WARNING: Next examination due date not found in document. "
            "Manual review required."
        )

    # Flag missing certificate number
    if result.certificate_number is None:
        warnings.append(
            "WARNING: Certificate number not found. "
            "Cannot uniquely identify this certificate."
        )

    result.warnings = warnings
    return result
