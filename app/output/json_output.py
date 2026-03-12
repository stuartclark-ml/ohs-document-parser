"""
JSON output assembly for OHS certificate extraction results.

Takes the outputs from classification, extraction, and calendar modules
and assembles them into the final ExtractionResponse that FastAPI returns.

Also generates domain-specific alerts based on certificate data:
- Overdue examination warnings
- Immediate prohibition notices
- Repair deadline warnings
- Approaching due date reminders
"""

from datetime import date

from app.config import LEAD_ALERT_DAYS
from app.validation.schemas import (
    Alert,
    BaseExtractionResult,
    CalendarEntry,
    ClassificationResult,
    DefectOutcome,
    ExtractionResponse,
)


def generate_alerts(extraction: BaseExtractionResult) -> list[Alert]:
    """
    Generate domain-specific alerts from certificate extraction data.

    Parameters
    ----------
    extraction : BaseExtractionResult
        The parsed certificate data.

    Returns
    -------
    list[Alert]
        A list of alerts, possibly empty if nothing needs flagging.

    Why generate alerts here instead of in the extraction layer?
    -----------------------------------------------------------
    loler.py and pressure.py already add warning *strings* to
    extraction.warnings. Those are human-readable messages baked
    into the extraction result.

    This function creates structured Alert objects with a severity
    level (CRITICAL, WARNING, INFO). Structured alerts let the
    frontend display them differently — red banners for critical,
    yellow for warnings, blue for info. The raw warning strings
    are useful for the plain-English summary; the Alert objects
    are useful for the API and UI.

    This separation follows the Single Responsibility Principle:
    the extraction layer extracts data, the output layer decides
    how to present it.
    """
    alerts: list[Alert] = []
    today = date.today()
    cert_number = extraction.certificate_number or "UNKNOWN"

    # --- CRITICAL: Immediate prohibition ---
    # If the examiner issued an immediate prohibition, the equipment
    # MUST NOT be used. This is the most serious outcome under both
    # LOLER Reg 10 and PSSR Reg 6.
    if extraction.defect_outcome == DefectOutcome.IMMEDIATE_PROHIBITION:
        alerts.append(
            Alert(
                level="CRITICAL",
                message=(
                    "IMMEDIATE PROHIBITION — Equipment must not be used. "
                    "Examiner has identified a defect involving danger."
                ),
                certificate_number=cert_number,
            )
        )

    # --- CRITICAL: Examination overdue ---
    # If next_examination_due is in the past, the equipment is being
    # used without a valid examination certificate. This is a breach
    # of LOLER Reg 9 or PSSR Reg 8.
    if extraction.next_examination_due is not None:
        days_until_due = (extraction.next_examination_due - today).days

        if days_until_due < 0:
            alerts.append(
                Alert(
                    level="CRITICAL",
                    message=(
                        f"OVERDUE — Next examination was due "
                        f"{abs(days_until_due)} days ago on "
                        f"{extraction.next_examination_due.isoformat()}. "
                        f"Arrange re-examination immediately."
                    ),
                    certificate_number=cert_number,
                )
            )

        # --- WARNING: Due date approaching ---
        # Fires when the due date is within LEAD_ALERT_DAYS (30 days).
        # Gives the duty holder time to book the next examination.
        elif days_until_due <= LEAD_ALERT_DAYS:
            alerts.append(
                Alert(
                    level="WARNING",
                    message=(
                        f"Examination due in {days_until_due} days on "
                        f"{extraction.next_examination_due.isoformat()}. "
                        f"Book re-examination now."
                    ),
                    certificate_number=cert_number,
                )
            )

    # --- WARNING: Repair deadline set ---
    # If the examiner found a defect requiring repair within a
    # specified timeframe, flag it. Missing a repair deadline can
    # escalate to a prohibition notice from the enforcing authority.
    if extraction.defect_outcome == DefectOutcome.REPAIR_REQUIRED:
        if extraction.repair_deadline is not None:
            days_to_repair = (extraction.repair_deadline - today).days

            if days_to_repair < 0:
                alerts.append(
                    Alert(
                        level="CRITICAL",
                        message=(
                            f"REPAIR DEADLINE PASSED — Repair was due "
                            f"{abs(days_to_repair)} days ago on "
                            f"{extraction.repair_deadline.isoformat()}. "
                            f"Equipment may need to be taken out of service."
                        ),
                        certificate_number=cert_number,
                    )
                )
            else:
                alerts.append(
                    Alert(
                        level="WARNING",
                        message=(
                            f"Repair required within {days_to_repair} days "
                            f"(deadline: {extraction.repair_deadline.isoformat()}). "
                            f"Defect: {extraction.defect_description or 'See certificate'}."
                        ),
                        certificate_number=cert_number,
                    )
                )
        else:
            # Repair required but no deadline specified — still flag it
            alerts.append(
                Alert(
                    level="WARNING",
                    message=(
                        "Repair required — no deadline specified on certificate. "
                        f"Defect: {extraction.defect_description or 'See certificate'}."
                    ),
                    certificate_number=cert_number,
                )
            )

    # --- INFO: Advisory defect noted ---
    # Not as urgent as a repair, but worth recording. The examiner
    # has flagged something that should be monitored.
    if extraction.defect_outcome == DefectOutcome.ADVISORY:
        alerts.append(
            Alert(
                level="INFO",
                message=(
                    f"Advisory: {extraction.defect_description or 'See certificate'}. "
                    f"Monitor condition before next examination."
                ),
                certificate_number=cert_number,
            )
        )

    return alerts


def build_response(
    extraction: BaseExtractionResult,
    classification: ClassificationResult,
    calendar_entries: list[CalendarEntry],
    alerts: list[Alert] | None = None,
) -> ExtractionResponse:
    """
    Assemble the final API response from all pipeline outputs.

    Parameters
    ----------
    extraction : BaseExtractionResult
        The parsed certificate data (either LOLER or PressureVessel subclass).
    classification : ClassificationResult
        The document type classification with confidence score.
    calendar_entries : list[CalendarEntry]
        Calendar reminders generated for due dates.
    alerts : list[Alert] or None
        Pre-generated alerts. If None, this function will generate
        them from the extraction data.

    Returns
    -------
    ExtractionResponse
        The complete response object ready for FastAPI to serialise.

    Why accept alerts as an optional parameter?
    -------------------------------------------
    This gives the calling code flexibility. In the normal pipeline,
    main.py will call generate_alerts() then pass the result here.
    But for testing, you might want to inject specific alerts without
    going through the generation logic. Making it optional with a
    sensible default (generate if not provided) supports both cases.

    This pattern is called "dependency injection" — the function
    accepts its dependencies as parameters rather than creating
    them internally. It makes code easier to test and more flexible.
    """
    if alerts is None:
        alerts = generate_alerts(extraction)

    return ExtractionResponse(
        extraction=extraction,
        classification=classification,
        calendar_entries=calendar_entries,
        alerts=alerts,
    )


def response_to_json(response: ExtractionResponse) -> dict:
    """
    Convert an ExtractionResponse to a JSON-serialisable dictionary.

    Parameters
    ----------
    response : ExtractionResponse
        The complete response object.

    Returns
    -------
    dict
        A dictionary safe to pass to json.dumps() or return from
        a FastAPI endpoint.

    Why do we need this if FastAPI auto-serialises Pydantic models?
    ---------------------------------------------------------------
    FastAPI does handle Pydantic serialisation automatically when you
    return a model from an endpoint. But there are cases where you
    need the dict directly:
    - Writing results to a JSON file
    - Logging the response
    - Passing data to the Streamlit UI (which doesn't use FastAPI)
    - Unit testing where you want to inspect the raw dict

    model_dump() is Pydantic v2's method for converting a model to a
    dict. The mode="json" argument tells Pydantic to convert Python
    types into JSON-compatible types — date objects become ISO strings
    ("2025-06-15"), enums become their string values, etc.

    In Pydantic v1 this was called .dict() — if you see that in
    tutorials, it's the old API. Always use model_dump() in v2.
    """
    return response.model_dump(mode="json")