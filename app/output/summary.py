"""
Plain-English summary generation for OHS certificate extractions.

Produces a human-readable summary of what was extracted from
a certificate. This is displayed in the Streamlit UI and
included in the API response.

The summary is intentionally non-technical — it's written for
a site manager or duty holder who needs to know:
1. What was examined
2. When it was examined and when it's next due
3. Whether there are any problems
4. What action they need to take
"""

from datetime import date

from app.validation.schemas import (
    BaseExtractionResult,
    ClassificationResult,
    DefectOutcome,
    DocumentType,
    LOLERExtractionResult,
    PressureVesselExtractionResult,
)


def generate_summary(
    extraction: BaseExtractionResult,
    classification: ClassificationResult,
) -> str:
    """
    Generate a plain-English summary of a certificate extraction.

    Parameters
    ----------
    extraction : BaseExtractionResult
        The parsed certificate data. Will be either a
        LOLERExtractionResult or PressureVesselExtractionResult.
    classification : ClassificationResult
        The document type classification result.

    Returns
    -------
    str
        A multi-line plain-English summary.

    Why a separate function instead of a __str__ method on the model?
    ----------------------------------------------------------------
    Pydantic models should represent data, not presentation. The
    same extraction result might be presented as JSON (API), HTML
    (Streamlit), or plain text (this summary). Keeping presentation
    logic in separate modules follows the Single Responsibility
    Principle — the model holds data, the output modules format it.

    This is the same reason we have json_output.py and calendar.py
    as separate modules rather than methods on the Pydantic models.
    """
    # Build the summary in sections, then join them at the end
    sections = []

    # --- Header section ---
    sections.append(_build_header(extraction, classification))

    # --- Equipment/system details ---
    sections.append(_build_details(extraction, classification))

    # --- Dates section ---
    sections.append(_build_dates(extraction))

    # --- Defect section (only if there's something to report) ---
    defect_section = _build_defect_section(extraction)
    if defect_section:
        sections.append(defect_section)

    # --- Warnings section (only if there are warnings) ---
    if extraction.warnings:
        sections.append(_build_warnings(extraction))

    # --- Action required section ---
    action_section = _build_actions(extraction)
    if action_section:
        sections.append(action_section)

    # Join sections with blank lines between them
    # filter(None, sections) removes any None values — a safety
    # net in case a section builder returns None unexpectedly
    return "\n\n".join(filter(None, sections))


def _build_header(
    extraction: BaseExtractionResult,
    classification: ClassificationResult,
) -> str:
    """
    Build the summary header with document type and confidence.

    Returns something like:
        LOLER Thorough Examination Report
        Certificate: CERT-2024-001
        Classification confidence: 95%
    """
    # Map the DocumentType enum to a human-friendly label
    # Using a dict for this is cleaner than if/elif chains
    # and easier to extend when new document types are added
    type_labels = {
        DocumentType.LOLER: "LOLER Thorough Examination Report",
        DocumentType.PRESSURE_VESSEL: "Pressure Systems Examination Certificate",
    }

    doc_label = type_labels.get(
        classification.document_type,
        "Unknown Document Type",
    )

    cert = extraction.certificate_number or "Not found"
    confidence = f"{classification.confidence:.0%}"

    lines = [
        doc_label,
        f"Certificate: {cert}",
        f"Classification confidence: {confidence}",
    ]

    return "\n".join(lines)


def _build_details(
    extraction: BaseExtractionResult,
    classification: ClassificationResult,
) -> str:
    """
    Build the equipment or system details section.

    Uses isinstance() to check which subclass we're dealing with,
    then pulls the specific fields for that document type.

    What is isinstance()?
    ---------------------
    isinstance(obj, ClassName) returns True if obj is an instance
    of ClassName or any of its subclasses. We use it here because
    extraction could be either LOLERExtractionResult or
    PressureVesselExtractionResult — both inherit from
    BaseExtractionResult. isinstance() lets us safely access
    subclass-specific fields like equipment_description or
    system_description.

    This is called "polymorphism" — one function handles multiple
    types by checking what it received and adapting its behaviour.
    """
    lines = ["Equipment / System Details:"]

    if isinstance(extraction, LOLERExtractionResult):
        lines.append(
            f"  Description: "
            f"{extraction.equipment_description or 'Not found'}"
        )
        lines.append(
            f"  Equipment ID: "
            f"{extraction.equipment_id or 'Not found'}"
        )
        lines.append(
            f"  Safe Working Load: "
            f"{extraction.safe_working_load or 'Not found'}"
        )

    elif isinstance(extraction, PressureVesselExtractionResult):
        lines.append(
            f"  Description: "
            f"{extraction.system_description or 'Not found'}"
        )
        lines.append(
            f"  Plant ID: "
            f"{extraction.plant_id or 'Not found'}"
        )
        lines.append(
            f"  Max Working Pressure: "
            f"{extraction.maximum_allowable_working_pressure or 'Not found'}"
        )

    # Fields common to both document types
    lines.append(
        f"  Location: {extraction.location or 'Not found'}"
        if hasattr(extraction, 'location')
        else ""
    )
    lines.append(
        f"  Issuing body: {extraction.issuing_body or 'Not found'}"
    )
    lines.append(
        f"  Examiner: {extraction.examiner_name or 'Not found'}"
    )

    return "\n".join(lines)


def _build_dates(extraction: BaseExtractionResult) -> str:
    """
    Build the dates section showing examination and due dates.

    Uses isoformat() to display dates as YYYY-MM-DD. This is
    unambiguous — unlike "01/02/2025" which could be January 2nd
    or February 1st depending on locale. For a UK OHS tool we
    could use strftime("%d %B %Y") for "15 March 2025" format,
    but ISO is safer for a v1 that might be used internationally.
    """
    exam_date = (
        extraction.date_of_examination.isoformat()
        if extraction.date_of_examination
        else "Not found"
    )
    next_due = (
        extraction.next_examination_due.isoformat()
        if extraction.next_examination_due
        else "Not found"
    )

    lines = [
        "Examination Dates:",
        f"  Date of examination: {exam_date}",
        f"  Next examination due: {next_due}",
    ]

    # Add days-until-due calculation if we have a date
    if extraction.next_examination_due:
        days = (extraction.next_examination_due - date.today()).days
        if days < 0:
            lines.append(f"  *** OVERDUE by {abs(days)} days ***")
        elif days == 0:
            lines.append("  *** DUE TODAY ***")
        else:
            lines.append(f"  ({days} days from today)")

    return "\n".join(lines)


def _build_defect_section(extraction: BaseExtractionResult) -> str | None:
    """
    Build the defect outcome section. Returns None if no defect.

    Why return None instead of an empty string?
    -------------------------------------------
    The calling function checks `if defect_section:` before adding
    it. None is falsy in Python, so the section gets skipped
    entirely — no blank gap in the summary. An empty string ""
    is also falsy, but returning None makes the intent explicit:
    "there is no section to show" vs "there is a section but it's
    empty."
    """
    if (
        extraction.defect_outcome is None
        or extraction.defect_outcome == DefectOutcome.NONE
    ):
        return None

    # Map enum values to plain-English descriptions
    outcome_labels = {
        DefectOutcome.IMMEDIATE_PROHIBITION: (
            "IMMEDIATE PROHIBITION — Equipment must not be used"
        ),
        DefectOutcome.REPAIR_REQUIRED: (
            "Repair required before next use or within specified deadline"
        ),
        DefectOutcome.ADVISORY: (
            "Advisory — Monitor condition"
        ),
    }

    outcome_text = outcome_labels.get(
        extraction.defect_outcome,
        str(extraction.defect_outcome.value),
    )

    lines = [
        "Defect Outcome:",
        f"  Status: {outcome_text}",
    ]

    if extraction.defect_description:
        lines.append(f"  Details: {extraction.defect_description}")

    if extraction.repair_deadline:
        lines.append(
            f"  Repair deadline: "
            f"{extraction.repair_deadline.isoformat()}"
        )

    return "\n".join(lines)


def _build_warnings(extraction: BaseExtractionResult) -> str:
    """
    Build the warnings section from extraction.warnings list.

    These are the warning strings generated by loler.py and
    pressure.py during extraction — things like overdue dates,
    missing fields, prohibition notices.

    The enumerate() function is used here to number each warning.
    enumerate(iterable, start=1) yields pairs of (index, item),
    so we get (1, first_warning), (2, second_warning), etc.
    The start=1 makes it human-friendly (1-based) instead of
    the Python default of 0-based.
    """
    lines = ["Warnings:"]
    for i, warning in enumerate(extraction.warnings, start=1):
        lines.append(f"  {i}. {warning}")
    return "\n".join(lines)


def _build_actions(extraction: BaseExtractionResult) -> str | None:
    """
    Build an action-required section based on the certificate state.

    This is the most important part of the summary for the end user.
    A site manager reading this wants to know: "What do I need to do?"

    Returns None if no actions are needed.
    """
    actions = []

    # Prohibition — most urgent
    if extraction.defect_outcome == DefectOutcome.IMMEDIATE_PROHIBITION:
        actions.append(
            "IMMEDIATELY take equipment out of service"
        )
        actions.append(
            "Arrange repair by competent person"
        )
        actions.append(
            "Do not return to service until re-examined "
            "and new certificate issued"
        )

    # Overdue examination
    if extraction.next_examination_due:
        days = (extraction.next_examination_due - date.today()).days
        if days < 0:
            actions.append(
                "Arrange thorough examination IMMEDIATELY — "
                "certificate has expired"
            )

    # Repair required
    if extraction.defect_outcome == DefectOutcome.REPAIR_REQUIRED:
        if extraction.repair_deadline:
            days_left = (extraction.repair_deadline - date.today()).days
            if days_left < 0:
                actions.append(
                    "Repair deadline has PASSED — assess whether "
                    "equipment should be taken out of service"
                )
            else:
                actions.append(
                    f"Complete repair by "
                    f"{extraction.repair_deadline.isoformat()} "
                    f"({days_left} days remaining)"
                )
        else:
            actions.append(
                "Arrange repair — no deadline specified, "
                "treat as priority"
            )

    # Advisory
    if extraction.defect_outcome == DefectOutcome.ADVISORY:
        actions.append(
            "Note advisory finding and monitor condition"
        )

    if not actions:
        return None

    lines = ["Action Required:"]
    for i, action in enumerate(actions, start=1):
        lines.append(f"  {i}. {action}")

    return "\n".join(lines)