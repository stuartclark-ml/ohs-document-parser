"""
Calendar reminder generation for OHS certificate due dates.

Produces iCalendar (.ics) files that users can import into
Outlook, Google Calendar, Apple Calendar, etc.

Uses the CalendarEntry schema from validation/schemas.py and
the LEAD_ALERT_DAYS setting from config.py.
"""

from datetime import date, timedelta
from uuid import uuid4

from app.config import LEAD_ALERT_DAYS
from app.validation.schemas import (
    BaseExtractionResult,
    CalendarEntry,
    DefectOutcome,
    DocumentType,
)


def create_calendar_entry(
    extraction: BaseExtractionResult,
    document_type: DocumentType,
) -> CalendarEntry | None:
    """
    Build a CalendarEntry for the next examination due date.

    Parameters
    ----------
    extraction : BaseExtractionResult
        The parsed certificate data. We need certificate_number
        and next_examination_due from this.
    document_type : DocumentType
        Either DocumentType.LOLER or DocumentType.PRESSURE_VESSEL.
        Used to label the calendar event clearly.

    Returns
    -------
    CalendarEntry or None
        Returns None if next_examination_due is missing — we can't
        create a reminder without a date.

    Why return None instead of raising an error?
    --------------------------------------------
    Not every certificate will have a next examination date.
    Some are final inspections or the field might not be extractable.
    Returning None lets the calling code simply skip calendar generation
    rather than crashing the whole pipeline. This is a common Python
    pattern called "optional return" — the caller checks:
        entry = create_calendar_entry(...)
        if entry is not None:
            # do something with it
    """
    if extraction.next_examination_due is None:
        return None

    # Build a human-readable title for the calendar event
    # e.g. "LOLER Examination Due — CERT-2024-001"
    title = (
        f"{document_type.value} Examination Due"
        f" — {extraction.certificate_number or 'Unknown Certificate'}"
    )

    # Calculate the lead alert date — LEAD_ALERT_DAYS before the due date
    # This is when the reminder notification should fire
    lead_alert_date = (
        extraction.next_examination_due - timedelta(days=LEAD_ALERT_DAYS)
    )

    # Determine urgency based on how far away the due date is
    today = date.today()
    days_until_due = (extraction.next_examination_due - today).days

    if days_until_due < 0:
        urgency = "overdue"
    elif days_until_due <= LEAD_ALERT_DAYS:
        urgency = "upcoming"
    else:
        urgency = "scheduled"

    # Generate the .ics data for this single entry
    ics_string = _generate_ics_single(
        title=title,
        due_date=extraction.next_examination_due,
        lead_alert_date=lead_alert_date,
    )
    # Convert string to bytes — the schema expects Optional[bytes]
    # because .ics files are typically served as binary downloads
    ical_data = ics_string.encode("utf-8")

    return CalendarEntry(
        title=title,
        due_date=extraction.next_examination_due,
        lead_alert_date=lead_alert_date,
        entry_type="examination_due",
        urgency=urgency,
        ical_data=ical_data,
    )


def create_repair_calendar_entry(
    extraction: BaseExtractionResult,
    document_type: DocumentType,
) -> CalendarEntry | None:
    """
    Build a CalendarEntry for a repair deadline.

    Only creates an entry if there's a repair deadline set AND
    the defect outcome is REPAIR_REQUIRED.

    Parameters
    ----------
    extraction : BaseExtractionResult
        The parsed certificate data.
    document_type : DocumentType
        The document type for labelling.

    Returns
    -------
    CalendarEntry or None
        Returns None if no repair deadline exists.
    """
    if extraction.repair_deadline is None:
        return None
    if extraction.defect_outcome != DefectOutcome.REPAIR_REQUIRED:
        return None

    title = (
        f"{document_type.value} Repair Deadline"
        f" — {extraction.certificate_number or 'Unknown Certificate'}"
    )

    # For repairs, alert earlier — half the lead time or 7 days,
    # whichever is larger
    repair_lead_days = max(LEAD_ALERT_DAYS // 2, 7)
    lead_alert_date = (
        extraction.repair_deadline - timedelta(days=repair_lead_days)
    )

    today = date.today()
    days_until_deadline = (extraction.repair_deadline - today).days

    if days_until_deadline < 0:
        urgency = "overdue"
    else:
        urgency = "high"

    ics_string = _generate_ics_single(
        title=title,
        due_date=extraction.repair_deadline,
        lead_alert_date=lead_alert_date,
    )
    ical_data = ics_string.encode("utf-8")

    return CalendarEntry(
        title=title,
        due_date=extraction.repair_deadline,
        lead_alert_date=lead_alert_date,
        entry_type="repair_deadline",
        urgency=urgency,
        ical_data=ical_data,
    )


def collect_calendar_entries(
    extraction: BaseExtractionResult,
    document_type: DocumentType,
) -> list[CalendarEntry]:
    """
    Generate all relevant calendar entries for an extraction result.

    Collects both examination due dates and repair deadlines
    into a single list. Returns an empty list if neither applies.

    Parameters
    ----------
    extraction : BaseExtractionResult
        The parsed certificate data.
    document_type : DocumentType
        The document type for labelling.

    Returns
    -------
    list[CalendarEntry]
        Zero, one, or two entries depending on the certificate.
    """
    entries: list[CalendarEntry] = []

    exam_entry = create_calendar_entry(extraction, document_type)
    if exam_entry is not None:
        entries.append(exam_entry)

    repair_entry = create_repair_calendar_entry(extraction, document_type)
    if repair_entry is not None:
        entries.append(repair_entry)

    return entries


def generate_ics(entries: list[CalendarEntry]) -> str:
    """
    Generate a combined .ics file from multiple CalendarEntry objects.

    Parameters
    ----------
    entries : list[CalendarEntry]
        One or more calendar entries to combine into a single file.

    Returns
    -------
    str
        A complete .ics file containing all events.

    What is .ics?
    -------------
    iCalendar is an open standard (RFC 5545) for calendar data exchange.
    Every major calendar app supports it. The file is plain text with a
    specific structure:
        BEGIN:VCALENDAR  — start of the file
        BEGIN:VEVENT     — start of one event
        ...fields...
        END:VEVENT       — end of one event
        END:VCALENDAR    — end of the file
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OHS Document Parser//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for entry in entries:
        due_date_str = entry.due_date.strftime("%Y%m%d")
        alert_date_str = entry.lead_alert_date.strftime("%Y%m%d")
        uid = f"{uuid4()}@ohs-document-parser"
        escaped_title = _escape_ics_text(entry.title)

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;VALUE=DATE:{due_date_str}",
            f"SUMMARY:{escaped_title}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            f"TRIGGER;VALUE=DATE-TIME:{alert_date_str}T090000Z",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Reminder: {escaped_title}",
            "END:VALARM",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    # iCalendar spec requires CRLF line endings (\r\n)
    # — yes, the very thing we fixed in loler.py!
    # But here it's correct: the .ics RFC mandates CRLF.
    return "\r\n".join(lines)


def _generate_ics_single(
    title: str,
    due_date: date,
    lead_alert_date: date,
) -> str:
    """
    Generate a complete .ics file string for a single event.

    This is a private helper used by create_calendar_entry() and
    create_repair_calendar_entry() to embed .ics data directly
    into the CalendarEntry model.

    Parameters
    ----------
    title : str
        The event title / summary.
    due_date : date
        The date of the event (all-day).
    lead_alert_date : date
        When the reminder alert should fire.

    Returns
    -------
    str
        A complete .ics file as a string.
    """
    due_date_str = due_date.strftime("%Y%m%d")
    alert_date_str = lead_alert_date.strftime("%Y%m%d")
    uid = f"{uuid4()}@ohs-document-parser"
    escaped_title = _escape_ics_text(title)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OHS Document Parser//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{due_date_str}",
        f"SUMMARY:{escaped_title}",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        f"TRIGGER;VALUE=DATE-TIME:{alert_date_str}T090000Z",
        "ACTION:DISPLAY",
        f"DESCRIPTION:Reminder: {escaped_title}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    return "\r\n".join(lines)


def _escape_ics_text(text: str) -> str:
    """
    Escape text for iCalendar format per RFC 5545.

    iCalendar uses commas, semicolons, and backslashes as
    structural characters. If your certificate description
    contains "Defect: worn rope, frayed ends" the comma would
    break the parser. Escaping them with backslashes tells the
    calendar app "this is literal text, not structure."
    """
    text = text.replace("\\", "\\\\")   # Backslashes first (avoid double-escaping)
    text = text.replace(";", "\\;")     # Semicolons
    text = text.replace(",", "\\,")     # Commas
    text = text.replace("\n", "\\n")    # Newlines
    return text