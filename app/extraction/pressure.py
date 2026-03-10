"""
Extraction pipeline for pressure vessel and pressure system certificates.
Orchestrates regex extraction, LLM field extraction, date parsing,
and domain logic (overdue warnings, prohibition alerts).
"""

from datetime import date

from app.extraction.regex_patterns import (
    extract_certificate_number,
    extract_pressure,
    extract_plant_id,
    parse_date_string,
)
from app.extraction.llm_extractor import extract_fields
from app.validation.schemas import (
    PressureVesselExtractionResult,
    DefectOutcome,
    ExtractionMethod,
)


def extract_pressure_vessel(
    text: str,
    extraction_method: ExtractionMethod,
) -> PressureVesselExtractionResult:
    """
    Full extraction pipeline for pressure vessel / pressure system certificates.

    Args:
        text: Raw certificate text
        extraction_method: How the text was obtained (pdf_direct, ocr_image, etc.)

    Returns:
        Validated PressureVesselExtractionResult
    """
    # --- Step 1: Regex extraction ---
    # Fast, deterministic. Handles structured fields that follow
    # consistent patterns across issuing bodies.
    cert_number = extract_certificate_number(text)
    mawp = extract_pressure(text)
    plant_id = extract_plant_id(text)

    # --- Step 2: LLM extraction ---
    # For fields requiring contextual understanding:
    # free-text descriptions, locations, defect outcomes, dates.
    llm_result = extract_fields(text, "PRESSURE_VESSEL")

    # --- Step 3: Parse dates from LLM output ---
    # LLM is instructed to return dates as YYYY-MM-DD strings.
    # parse_date_string handles malformed output gracefully.
    exam_date = parse_date_string(llm_result.get("date_of_examination"))
    next_due = parse_date_string(llm_result.get("next_examination_due"))
    repair_deadline = parse_date_string(llm_result.get("repair_deadline"))

    # --- Step 4: Map defect outcome string to enum ---
    defect_outcome = _parse_defect_outcome(
        llm_result.get("defect_outcome", "NONE")
    )

    # --- Step 5: Domain logic ---
    # Apply OHS-specific warnings based on extracted data.
    # This is where 14 years of consulting knowledge goes into the pipeline.
    warnings = _generate_warnings(next_due, repair_deadline, defect_outcome)

    return PressureVesselExtractionResult(
        certificate_number=cert_number,
        issuing_body=llm_result.get("issuing_body"),
        date_of_examination=exam_date,
        next_examination_due=next_due,
        examiner_name=llm_result.get("examiner_name"),
        system_description=llm_result.get("system_description"),
        plant_id=plant_id,
        maximum_allowable_working_pressure=mawp,
        location=llm_result.get("location"),
        defect_outcome=defect_outcome,
        defect_description=llm_result.get("defect_description"),
        repair_deadline=repair_deadline,
        extraction_method=extraction_method,
        warnings=warnings,
    )


def _parse_defect_outcome(value: str) -> DefectOutcome:
    """
    Map LLM-returned string to DefectOutcome enum.
    Defaults to NONE if the value is unrecognised.
    """
    mapping = {
        "immediate_prohibition": DefectOutcome.IMMEDIATE_PROHIBITION,
        "repair_required": DefectOutcome.REPAIR_REQUIRED,
        "advisory": DefectOutcome.ADVISORY,
        "none": DefectOutcome.NONE,
    }
    return mapping.get(str(value).lower(), DefectOutcome.NONE)


def _generate_warnings(
    next_due: date | None,
    repair_deadline: date | None,
    defect_outcome: DefectOutcome,
) -> list[str]:
    """
    Generate domain-specific warnings based on extracted certificate data.

    These warnings surface compliance issues that require immediate
    attention from the user — overdue examinations, active prohibitions,
    and missed repair deadlines.
    """
    warnings = []
    today = date.today()

    if next_due and next_due < today:
        warnings.append(
            f"OVERDUE: Next examination was due {next_due}. "
            f"Equipment may not legally be operated under PSSR 2000 "
            f"until re-examined by a competent person."
        )

    if defect_outcome == DefectOutcome.IMMEDIATE_PROHIBITION:
        warnings.append(
            "PROHIBITION: Equipment must be taken out of service immediately. "
            "Do not operate until defect is rectified and re-examination confirms safety."
        )

    if defect_outcome == DefectOutcome.REPAIR_REQUIRED:
        if repair_deadline and repair_deadline < today:
            warnings.append(
                f"REPAIR OVERDUE: Repair deadline of {repair_deadline} has passed. "
                f"Equipment should not be operated until repair is completed."
            )
        elif repair_deadline:
            warnings.append(
                f"REPAIR REQUIRED: Defect repair due by {repair_deadline}."
            )
        else:
            warnings.append(
                "REPAIR REQUIRED: Defect noted. Repair deadline not specified — "
                "confirm timeline with competent person."
            )

    return warnings