"""
A news parsing agent that monitors news articles for road disruptions,
extracts structured disruption data, and returns it in a standardized format
for potential route re-planning and re-routing.

Built with LangChain LCEL (LangChain Expression Language).
"""

import json
import logging
import os
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser

from prompts import CLASSIFY_PROMPT, EXTRACTION_PROMPT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class NewsParsingAgent:
    """
    A LangChain-based news parsing agent that reads news articles, identifies
    road disruptions, and extracts structured data.

    Uses two LCEL chains in sequence:
      1. classify_chain  — determines whether the article describes a road disruption.
      2. extraction_chain — extracts structured disruption details if classified True.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "API key must be provided as an argument or via GEMINI_API_KEY env var."
            )

        llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key)
        parser = JsonOutputParser()

        # Retry up to 2 attempts on transient failures (e.g. malformed JSON)
        self.classify_chain = (CLASSIFY_PROMPT | llm | parser).with_retry(
            stop_after_attempt=2
        )
        self.extraction_chain = (EXTRACTION_PROMPT | llm | parser).with_retry(
            stop_after_attempt=2
        )

        logger.info("Initialized NewsParsingAgent with model: %s", model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify(self, article: str) -> Optional[dict]:
        """Run the classification chain and validate its output."""
        try:
            result = self.classify_chain.invoke({"article": article})
        except Exception as e:
            logger.error("Error during classification: %s", e)
            return None

        classification = result.get("classification")
        confidence = result.get("confidence", 0)

        if classification not in ("True", "False"):
            logger.warning("Unexpected classification value: %r", classification)
            return None
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            logger.warning("Invalid confidence value: %r", confidence)
            return None

        logger.info("Article classified as %s (confidence=%.2f)", classification, confidence)
        return result

    def _extract(self, article: str, explanation: str) -> Optional[dict]:
        """Run the extraction chain and validate its output."""
        try:
            result = self.extraction_chain.invoke(
                {"article": article, "explanation": explanation}
            )
        except Exception as e:
            logger.error("Error during disruption data extraction: %s", e)
            return None

        logger.info("Extracted disruption data (confidence=%.2f)", result.get("confidence", 0))
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_article(self, article: str) -> Optional[dict]:
        """
        Parse a news article and return structured disruption data if applicable.

        Returns:
            dict with disruption fields, or None if the article is not a
            relevant disruption or confidence is too low.
        """
        if not article or not article.strip():
            logger.warning("Empty article text provided.")
            return None

        # Step 1: classify
        classify_result = self._classify(article)
        if classify_result is None:
            return None
        if classify_result.get("confidence", 0) < 0.2:
            logger.warning("Low confidence in classification (%.2f). Skipping.", classify_result["confidence"])
            return None
        if classify_result.get("classification") != "True":
            logger.info("Article is not a road disruption. No data extracted.")
            return None

        # Step 2: extract structured data
        disruption_data = self._extract(article, classify_result.get("explanation", ""))
        if disruption_data is None:
            logger.warning("Disruption data extraction failed.")
            return None
        if disruption_data.get("confidence", 0) < 0.2:
            logger.warning(
                "Low confidence in extracted disruption data (%.2f). Returning None.",
                disruption_data["confidence"],
            )
            return None

        logger.info(
            "Successfully parsed article (confidence=%.2f).",
            disruption_data.get("confidence", 0),
        )
        return disruption_data


if __name__ == "__main__":
    agent = NewsParsingAgent()

    sample_article =  """
I-70
WB
Construction work in Rostraver on I-70 WB between PA-51/ Smithton/ Exit 46 and Indian Hill Rd/ Arnold City/ Exit 44
Started 58 minutes ago at 01:39 PM on April 9, 2026
Expected to end in 1 hour on April 9, 2026 at 03:39 PM
"""

    result = agent.parse_article(sample_article)

    if result:
        print("Successfully parsed disruption event:")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Article was not classified as a relevant disruption or confidence was too low.")
