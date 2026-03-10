"""
Document type classifier.

Scores extracted text against LOLER and pressure vessel keyword lists
to determine document type before extraction begins.

Returns a ClassificationResult with:
- document_type: the predicted type
- confidence: score between 0 and 1
- requires_user_confirmation: True if confidence is below threshold
- scores: raw scores for transparency
"""

from app.classification.keywords import (
    LOLER_KEYWORDS,
    PRESSURE_VESSEL_KEYWORDS,
    NEGATIVE_KEYWORDS,
)
from app.validation.schemas import ClassificationResult, DocumentType
from app.config import CONFIDENCE_THRESHOLD


def classify_document(text: str) -> ClassificationResult:
    """
    Classify a document as LOLER or pressure vessel.

    Scores the text against keyword lists, normalises the scores
    to produce a confidence value, and flags low confidence results
    for human confirmation.

    Args:
        text: Extracted text from the document

    Returns:
        ClassificationResult with type, confidence, and raw scores
    """
    text_lower = text.lower()

    # Calculate raw keyword scores
    loler_score = _calculate_score(text_lower, LOLER_KEYWORDS)
    pressure_score = _calculate_score(text_lower, PRESSURE_VESSEL_KEYWORDS)
    negative_score = _calculate_score(text_lower, NEGATIVE_KEYWORDS)

    # Apply negative keyword penalty
    loler_score = max(0.0, loler_score - negative_score * 0.5)
    pressure_score = max(0.0, pressure_score - negative_score * 0.5)

    # Calculate confidence
    total = loler_score + pressure_score

    if total == 0:
        # No keywords matched at all
        # Cannot classify — return low confidence LOLER as default
        return ClassificationResult(
            document_type=DocumentType.LOLER,
            confidence=0.0,
            requires_user_confirmation=True,
            scores={"loler": 0.0, "pressure_vessel": 0.0}
        )

    # Normalise scores to get confidence
    loler_confidence = loler_score / total
    pressure_confidence = pressure_score / total

    # Pick the higher scoring type
    if loler_confidence >= pressure_confidence:
        document_type = DocumentType.LOLER
        confidence = loler_confidence
    else:
        document_type = DocumentType.PRESSURE_VESSEL
        confidence = pressure_confidence

    return ClassificationResult(
        document_type=document_type,
        confidence=round(confidence, 3),
        requires_user_confirmation=confidence < CONFIDENCE_THRESHOLD,
        scores={
            "loler": round(loler_confidence, 3),
            "pressure_vessel": round(pressure_confidence, 3),
        }
    )


def _calculate_score(text: str, keywords: list[str]) -> float:
    """
    Score text against a keyword list.

    Counts how many keywords from the list appear in the text.
    Each keyword match adds 1.0 to the score.

    Multi-word keywords (e.g. "thorough examination") count as
    a single match — they are more specific and therefore more
    informative than single word matches.

    Args:
        text: Lowercased document text
        keywords: List of keywords to match against

    Returns:
        Raw score as float
    """
    score = 0.0
    for keyword in keywords:
        if keyword.lower() in text:
            score += 1.0
    return score