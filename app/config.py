"""
Application configuration.

Loads all settings from environment variables via .env file.
This is the single source of truth for configuration — nothing
else in the project hardcodes model names, API keys, or thresholds.
"""

import os
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()

# --- Model Configuration ---

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "google")
# Which LLM provider to use: "google", "anthropic", or "ollama"
# Change this one value to switch the entire pipeline between providers

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- Application Settings ---

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
# Classification confidence below this value triggers user confirmation

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
# Maximum uploaded file size in megabytes

OCR_TEXT_LENGTH_THRESHOLD = int(os.getenv("OCR_TEXT_LENGTH_THRESHOLD", "200"))
# If extracted PDF text is below this character count, treat as scanned
# and fall back to OCR

LEAD_ALERT_DAYS = int(os.getenv("LEAD_ALERT_DAYS", "30"))
# How many days before a deadline to generate a lead alert calendar entry