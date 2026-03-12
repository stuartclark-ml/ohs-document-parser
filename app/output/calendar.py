"""
Calendar reminder generation for OHS certificate due dates.

Produces iCalendar (.ics) files that users can import into
Outlook, Google Calendar, Apple Calendar, etc.

Uses the CalendarEntry schema from validation/schemas.py and
the LEAD_ALERT_DAYS setting from config.py.
"""

from datetime import timedelta
from uuid import uuid4

from app.config import LEAD_ALERT_DAYS
from app.validation.schemas import (
    BaseExtractionResult,
    CalendarEntry,
    DocumentType,
)


def create_calendar_entry(
    extraction: BaseExtractionResult,
    document_type: DocumentType,
) -> CalendarEntry | None:
    """
    Build a CalendarEntry from an extraction result.

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

    # Build notes that give context when the user sees the reminder
    notes_parts = [
        f"Document type: {document_type.value}",
        f"Issuing body: {extraction.issuing_body or 'Unknown'}",
        f"Examiner: {extraction.examiner_name or 'Unknown'}",
    ]

    # If there was a defect, flag it in the notes so the user
    # remembers to check repair status before the next exam
    if extraction.defect_outcome and extraction.defect_outcome.value != "NONE":
        notes_parts.append(
            f"Previous defect outcome: {extraction.defect_outcome.value}"
        )
    if extraction.defect_description:
        notes_parts.append(
            f"Defect details: {extraction.defect_description}"
        )

    notes = "\n".join(notes_parts)

    return CalendarEntry(
        title=title,
        due_date=extraction.next_examination_due,
        certificate_number=extraction.certificate_number or "UNKNOWN",
        document_type=document_type.value,
        notes=notes,
    )


def generate_ics(entries: list[CalendarEntry]) -> str:
    """
    Convert a list of CalendarEntry objects into an iCalendar (.ics) string.

    Parameters
    ----------
    entries : list[CalendarEntry]
        One or more calendar entries to include in the file.

    Returns
    -------
    str
        A complete .ics file as a string. The caller can write this
        to disk or return it as an HTTP response.

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

    Why build this manually instead of using a library?
    ---------------------------------------------------
    Libraries like `icalendar` exist, but our events are simple
    (all-day, no recurrence, no attendees). Hand-building the string
    avoids an extra dependency and teaches you the format. In a more
    complex app (recurring events, timezone handling, attendees),
    you'd reach for the `icalendar` library.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OHS Document Parser//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for entry in entries:
        lines.extend(_build_vevent(entry))

    lines.append("END:VCALENDAR")

    # iCalendar spec requires CRLF line endings (\r\n)
    # — yes, the very thing we just fixed in loler.py!
    # But here it's correct: the .ics RFC mandates CRLF.
    return "\r\n".join(lines)


def _build_vevent(entry: CalendarEntry) -> list[str]:
    """
    Build the VEVENT lines for a single calendar entry.

    Parameters
    ----------
    entry : CalendarEntry
        The calendar entry to convert.

    Returns
    -------
    list[str]
        Lines to insert between VCALENDAR begin/end.

    Why is this a private function?
    -------------------------------
    The underscore prefix (_build_vevent) is a Python convention
    meaning "this is an internal helper, not part of the public API."
    Other modules should call generate_ics(), not this directly.
    It keeps the public interface clean — callers don't need to know
    how we build individual events.

    What is a VEVENT?
    -----------------
    A VEVENT is one calendar event inside a VCALENDAR file.
    Key fields:
    - DTSTART;VALUE=DATE  — the date (all-day event, no time)
    - SUMMARY             — the event title
    - DESCRIPTION         — the event notes/body
    - UID                 — a globally unique ID so calendar apps
                            can update/delete this specific event
    - VALARM              — a reminder/alert that fires before the event
    """
    # Format date as YYYYMMDD (iCalendar date format, no hyphens)
    due_date_str = entry.due_date.strftime("%Y%m%d")

    # Calculate the alert date — LEAD_ALERT_DAYS before the due date
    # This is when the VALARM reminder will trigger
    alert_date = entry.due_date - timedelta(days=LEAD_ALERT_DAYS)
    alert_date_str = alert_date.strftime("%Y%m%d")

    # uuid4() generates a random unique identifier
    # Calendar apps use this to track individual events
    uid = f"{uuid4()}@ohs-document-parser"

    # Escape special characters in description for iCalendar format
    # Newlines become literal \n, commas and semicolons get backslash-escaped
    description = _escape_ics_text(entry.notes or "")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{due_date_str}",
        f"SUMMARY:{_escape_ics_text(entry.title)}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
        # VALARM — the actual reminder notification
        "BEGIN:VALARM",
        "TRIGGER;VALUE=DATE-TIME:"
        f"{alert_date_str}T090000Z",
        "ACTION:DISPLAY",
        f"DESCRIPTION:Reminder: {_escape_ics_text(entry.title)}",
        "END:VALARM",
        "END:VEVENT",
    ]

    return lines


def _escape_ics_text(text: str) -> str:
    """
    Escape text for iCalendar format per RFC 5545.

    Parameters
    ----------
    text : str
        Raw text to escape.

    Returns
    -------
    str
        Escaped text safe for .ics fields.

    Why do we need this?
    --------------------
    iCalendar uses commas, semicolons, and backslashes as
    structural characters. If your certificate description
    contains "Defect: worn rope, frayed ends" the comma would
    break the parser. Escaping them with backslashes tells the
    calendar app "this is literal text, not structure."

    Newlines become the literal string \\n (backslash + n)
    because iCalendar doesn't allow actual line breaks inside
    a field value.
    """
    text = text.replace("\\", "\\\\")   # Backslashes first (avoid double-escaping)
    text = text.replace(";", "\\;")     # Semicolons
    text = text.replace(",", "\\,")     # Commas
    text = text.replace("\n", "\\n")    # Newlines
    return text