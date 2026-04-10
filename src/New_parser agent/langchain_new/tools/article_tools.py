"""
LangChain tools for news article processing.
These can be used standalone or wired into a LangChain agent with tool-calling.
"""

import os
from typing import Optional
from langchain_core.tools import tool


@tool
def read_article_from_file(file_path: str) -> str:
    """Read a news article from a text file and return its contents as a string."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Article file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def validate_classification_result(classification: str, confidence: float) -> bool:
    """
    Validate that a classification result is well-formed.
    Returns True if valid, raises ValueError otherwise.
    """
    if classification not in ("True", "False"):
        raise ValueError(f"Invalid classification value: {classification!r}. Must be 'True' or 'False'.")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Invalid confidence value: {confidence}. Must be a float between 0 and 1.")
    return True


@tool
def validate_disruption_result(disruption_data: dict) -> bool:
    """
    Validate that extracted disruption data contains required fields.
    Returns True if valid, raises ValueError otherwise.
    """
    required_fields = [
        "event_type", "roads_affected", "intersections",
        "neighborhoods", "area_description", "severity",
        "duration_hours_estimate", "confidence", "source_quote",
    ]
    missing = [f for f in required_fields if f not in disruption_data]
    if missing:
        raise ValueError(f"Disruption data missing required fields: {missing}")
    confidence = disruption_data.get("confidence", 0)
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Invalid confidence value in disruption data: {confidence}")
    return True
