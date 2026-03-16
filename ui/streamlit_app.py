"""
Streamlit UI for the OHS Document Parser.

Provides a web interface where users can upload a certificate,
see the extraction results, download calendar reminders, and
read the plain-English summary.

This communicates with the FastAPI backend — it doesn't run
the extraction pipeline directly. This separation means the
UI and API can be deployed independently if needed.

Run with:
    streamlit run ui/streamlit_app.py
"""

import requests
import streamlit as st


# --- Configuration ---

# The FastAPI backend URL. In development this is localhost.
# In production on Railway, both services run on the same host
# or you'd set this via environment variable.
API_BASE_URL = "http://127.0.0.1:8000"


# --- Page config ---
# Must be the first Streamlit command in the script.
# set_page_config controls the browser tab title, icon, and layout.

st.set_page_config(
    page_title="OHS Document Parser",
    page_icon="🔍",
    layout="wide",
)


# --- Header ---

st.title("Demo OHS Document Parser")
st.markdown(
    "THIS IS A DEMO APPLICATION. The extraction results are not guaranteed to be accurate. "
    "Always verify against the original certificate and consult a qualified health and safety professional for critical decisions. "
    "Upload a LOLER thorough examination report or pressure vessel "
    "certificate to extract structured data, generate alerts, and "
    "create calendar reminders."
)


# --- Sidebar ---

with st.sidebar:
    st.header("About")
    st.markdown(
        "AI-powered document intelligence for UK occupational "
        "health and safety certificates."
    )
    st.markdown("---")
    st.markdown("**Supported documents:**")
    st.markdown("- LOLER thorough examination reports")
    st.markdown("- PSSR pressure vessel certificates")
    st.markdown("---")
    st.markdown("**Supported formats:**")
    st.markdown("- PDF (digital or scanned)")
    st.markdown("- JPG / PNG images")
    st.markdown("---")
    st.markdown("**How it works:**")
    st.markdown(
        "1. Upload a certificate\n"
        "2. Text is extracted via PyMuPDF or Tesseract OCR\n"
        "3. Document type is classified automatically\n"
        "4. Fields are extracted using regex + LLM\n"
        "5. Alerts and calendar reminders are generated"
    )


# --- Display function ---

def _display_results(data: dict, file_bytes: bytes, file_name: str) -> None:
    """
    Display the extraction results in a structured layout.

    Parameters
    ----------
    data : dict
        The JSON response from the /extract endpoint.
    file_bytes : bytes
        The raw uploaded file content, kept so we can send it
        to /extract/calendar if the user wants a download.
    file_name : str
        The original filename, needed for the calendar endpoint.
    """
    result = data.get("result", {})
    alerts = data.get("alerts", [])
    calendar_entries = data.get("calendar_entries", [])
    summary = data.get("summary", "")
    processing_time = data.get("processing_time_seconds")

    # --- Alerts banner ---
    for alert in alerts:
        level = alert.get("level", "info")
        message = alert.get("message", "")
        if level == "critical":
            st.error(f"🚨 {message}")
        elif level == "warning":
            st.warning(f"⚠️ {message}")
        else:
            st.info(f"ℹ️ {message}")

    # --- Summary section ---
    st.header("Summary")
    st.text(summary)

    # --- Extracted fields ---
    st.header("Extracted Fields")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Certificate Details")
        st.markdown(f"**Document type:** {result.get('document_type', 'Unknown')}")
        st.markdown(f"**Certificate number:** {result.get('certificate_number', 'Not found')}")
        st.markdown(f"**Issuing body:** {result.get('issuing_body', 'Not found')}")
        st.markdown(f"**Examiner:** {result.get('examiner_name', 'Not found')}")
        st.markdown(f"**Extraction method:** {result.get('extraction_method', 'Unknown')}")

    with col2:
        st.subheader("Dates")
        st.markdown(f"**Date of examination:** {result.get('date_of_examination', 'Not found')}")
        st.markdown(f"**Next examination due:** {result.get('next_examination_due', 'Not found')}")
        if result.get("repair_deadline"):
            st.markdown(f"**Repair deadline:** {result.get('repair_deadline')}")

    # --- Equipment / system details ---
    st.subheader("Equipment / System Details")

    doc_type = result.get("document_type", "")

    if doc_type == "LOLER":
        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f"**Equipment description:** {result.get('equipment_description', 'Not found')}")
            st.markdown(f"**Equipment ID:** {result.get('equipment_id', 'Not found')}")
        with col4:
            st.markdown(f"**Safe Working Load:** {result.get('safe_working_load', 'Not found')}")
            st.markdown(f"**Location:** {result.get('location', 'Not found')}")

    elif doc_type == "PRESSURE_VESSEL":
        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f"**System description:** {result.get('system_description', 'Not found')}")
            st.markdown(f"**Plant ID:** {result.get('plant_id', 'Not found')}")
        with col4:
            st.markdown(f"**Max working pressure:** {result.get('maximum_allowable_working_pressure', 'Not found')}")
            st.markdown(f"**Location:** {result.get('location', 'Not found')}")

    # --- Defect details ---
    if result.get("defect_outcome") and result["defect_outcome"] != "NONE":
        st.subheader("Defect Details")
        st.markdown(f"**Outcome:** {result.get('defect_outcome')}")
        if result.get("defect_description"):
            st.markdown(f"**Description:** {result.get('defect_description')}")
        if result.get("repair_deadline"):
            st.markdown(f"**Repair deadline:** {result.get('repair_deadline')}")

    # --- Warnings ---
    if result.get("warnings"):
        with st.expander("Warnings", expanded=True):
            for warning in result["warnings"]:
                st.markdown(f"- {warning}")

    # --- Calendar download ---
    # Instead of extracting .ics data from the JSON response
    # (which loses formatting during serialisation), we call the
    # dedicated /extract/calendar endpoint. This returns a proper
    # .ics file with correct CRLF line endings.
    if calendar_entries:
        st.header("Calendar Reminders")
        st.markdown(
            "Download an .ics file to import examination due dates "
            "into your calendar."
        )

        # Show what reminders are available
        for entry in calendar_entries:
            title = entry.get("title", "Reminder")
            due = entry.get("due_date", "Unknown")
            urgency = entry.get("urgency", "")
            st.markdown(f"- **{title}** — Due: {due} ({urgency})")

        # Use session_state to track whether the user has requested
        # a calendar download. This avoids re-calling the API on
        # every Streamlit rerun.
        if "ics_data" not in st.session_state:
            st.session_state.ics_data = None

        if st.button("Generate calendar file"):
            with st.spinner("Generating .ics file..."):
                try:
                    cal_response = requests.post(
                        f"{API_BASE_URL}/extract/calendar",
                        files={"file": (file_name, file_bytes)},
                        timeout=60,
                    )
                    if cal_response.status_code == 200:
                        st.session_state.ics_data = cal_response.content
                    else:
                        error = cal_response.json().get("detail", "Unknown error")
                        st.error(f"Calendar generation failed: {error}")
                except Exception as e:
                    st.error(f"Calendar generation failed: {str(e)}")

        if st.session_state.ics_data is not None:
            st.download_button(
                label="📅 Download examination_reminder.ics",
                data=st.session_state.ics_data,
                file_name="examination_reminder.ics",
                mime="text/calendar",
            )

    # --- Raw JSON ---
    with st.expander("Raw JSON response"):
        st.json(data)

    # --- Processing time ---
    if processing_time:
        st.caption(f"Processed in {processing_time:.1f} seconds")


# --- File upload ---

uploaded_file = st.file_uploader(
    "Upload a certificate",
    type=["pdf", "jpg", "jpeg", "png"],
    help="Maximum file size: 10MB",
)


# --- Process the upload ---

if uploaded_file is not None:
    # Read file bytes once — we need them for both the /extract
    # and potentially the /extract/calendar call
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name

    # Use session_state to cache the extraction result.
    # Without this, Streamlit would re-call the API every time
    # the user interacts with anything on the page (clicks a
    # button, expands a section, etc). session_state persists
    # data across reruns within the same browser session.
    if "last_file_name" not in st.session_state:
        st.session_state.last_file_name = None
    if "extraction_data" not in st.session_state:
        st.session_state.extraction_data = None

    # Only call the API if this is a new file upload
    needs_extraction = (
        st.session_state.last_file_name != file_name
        or st.session_state.extraction_data is None
    )

    if needs_extraction:
        # Reset calendar data for new uploads
        st.session_state.ics_data = None

        with st.spinner("Extracting data from certificate..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/extract",
                    files={"file": (file_name, file_bytes)},
                    timeout=60,
                )

                if response.status_code != 200:
                    error_detail = response.json().get("detail", "Unknown error")
                    st.error(f"Extraction failed: {error_detail}")
                    st.session_state.extraction_data = None
                else:
                    st.session_state.extraction_data = response.json()
                    st.session_state.last_file_name = file_name

            except requests.exceptions.ConnectionError:
                st.error(
                    "Cannot connect to the API. "
                    "Make sure the FastAPI server is running: "
                    "`uvicorn app.main:app --reload`"
                )
            except requests.exceptions.Timeout:
                st.error(
                    "The API took too long to respond. "
                    "The file may be too large or the LLM service "
                    "may be experiencing issues."
                )
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    # Display results if we have them
    if st.session_state.extraction_data is not None:
        _display_results(
            st.session_state.extraction_data,
            file_bytes,
            file_name,
        )