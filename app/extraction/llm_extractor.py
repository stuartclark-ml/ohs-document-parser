"""
LLM-based field extraction.

Sends certificate text to the configured LLM provider and returns
structured field data as a dictionary.

The LLM is given a targeted prompt specific to the certificate type —
LOLER or pressure vessel — to maximise extraction accuracy.
"""

import json
import google.generativeai as genai
from app.config import (
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
    MODEL_PROVIDER,
)
from app.validation.schemas import DocumentType


# --- Extraction Prompts ---

LOLER_EXTRACTION_PROMPT = """You are extracting data from a LOLER thorough examination report.
Extract the following fields and return ONLY a JSON object with no other text.

Fields to extract:
- certificate_number: the certificate or report reference number
- issuing_body: the organisation that conducted the examination
- examiner_name: the name of the competent person who conducted the examination
- date_of_examination: the date the examination was conducted (format: DD-MM-YYYY)
- next_examination_due: the date the next examination is due (format: DD-MM-YYYY)
- equipment_description: description of the lifting equipment examined
- equipment_id: the equipment identification number or reference
- safe_working_load: the safe working load including units (e.g. "2000kg", "2 tonne")
- location: where the equipment is located or based
- defect_outcome: one of IMMEDIATE_PROHIBITION, REPAIR_REQUIRED, ADVISORY, or NONE
- defect_description: description of any defects found, or null if none
- repair_deadline: deadline for repairs if defect_outcome is REPAIR_REQUIRED (format: DD-MM-YYYY), or null
- equipment_installed_correctly: true if the report states the equipment was installed correctly, false if it states it was not, or null if not mentioned

Rules:
- If a field is not present in the document return null for that field
- Do not guess or infer values that are not explicitly stated
- Return dates in DD-MM-YYYY format only
- Return only the JSON object, no explanation, no markdown, no code blocks

Certificate text:
{text}"""


PRESSURE_VESSEL_EXTRACTION_PROMPT = """You are extracting data from a pressure vessel or pressure system inspection certificate.
Extract the following fields and return ONLY a JSON object with no other text.

Fields to extract:
- certificate_number: the certificate or inspection reference number
- issuing_body: the organisation that conducted the inspection
- examiner_name: the name of the inspector or competent person
- date_of_examination: the date the inspection was conducted (format: DD-MM-YYYY)
- next_examination_due: the date the next inspection is due (format: DD-MM-YYYY)
- system_description: description of the pressure system or vessel inspected
- plant_id: the plant or vessel identification number
- maximum_allowable_working_pressure: the MAWP including units (e.g. "10 bar", "150 psi")
- location: where the equipment is located
- defect_outcome: one of IMMEDIATE_PROHIBITION, REPAIR_REQUIRED, ADVISORY, or NONE
- defect_description: description of any defects found, or null if none
- repair_deadline: deadline for repairs if defect_outcome is REPAIR_REQUIRED (format: DD-MM-YYYY), or null

Rules:
- If a field is not present in the document return null for that field
- Do not guess or infer values that are not explicitly stated
- Return dates in DD-MM-YYYY format only
- Return only the JSON object, no explanation, no markdown, no code blocks

Certificate text:
{text}"""


def extract_fields(text: str, document_type: DocumentType) -> dict:
    """
    Extract structured fields from certificate text using the LLM.

    Selects the appropriate prompt for the document type and sends
    the text to the configured LLM provider. Returns a dictionary
    of extracted fields.

    Args:
        text: Extracted text from the certificate
        document_type: LOLER or PRESSURE_VESSEL

    Returns:
        Dictionary of extracted fields. Missing fields are null.

    Raises:
        ValueError: If LLM returns invalid JSON
        RuntimeError: If LLM API call fails
    """
    prompt = _build_prompt(text, document_type)

    if MODEL_PROVIDER == "google":
        return _extract_with_gemini(prompt)
    else:
        raise ValueError(
            f"Unsupported provider: {MODEL_PROVIDER}. "
            f"Currently supported: google"
        )


def _build_prompt(text: str, document_type: DocumentType) -> str:
    """
    Select and populate the correct extraction prompt.

    Args:
        text: Certificate text to insert into the prompt
        document_type: Determines which prompt template to use

    Returns:
        Complete prompt string ready to send to the LLM
    """
    if document_type == DocumentType.LOLER:
        return LOLER_EXTRACTION_PROMPT.format(text=text)
    else:
        return PRESSURE_VESSEL_EXTRACTION_PROMPT.format(text=text)


def _extract_with_gemini(prompt: str) -> dict:
    """
    Send extraction prompt to Gemini and parse the response.

    Gemini is instructed to return only JSON. This function
    parses that JSON and returns it as a dictionary.

    Args:
        prompt: Complete extraction prompt

    Returns:
        Parsed dictionary of extracted fields

    Raises:
        ValueError: If response cannot be parsed as JSON
        RuntimeError: If API call fails
    """
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GOOGLE_MODEL)
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code blocks if Gemini adds them
        # despite being told not to
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON: {e}\nRaw response: {raw}"
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")