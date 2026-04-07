"""
A news parsing agent that monitors news articles for road disruptions,
extracts structured disruption data, and returns it in a standardized format
for potential route re-planning and re-routing .
"""

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

from matplotlib import text

import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NewsParsingAgent:
    """
    A news parsing agent that reads news articles, identifies road disruptions, and extracts structured data.
    1. Reads news articles in as a string from a specified directory. --> currently assuming string input, can be extended to read from files or APIs.
    2. Uses a language model to analyze the content and identify potential road disruptions.
    3. Extracts structured data about the disruption, including location, type, severity, and expected duration.
    4. Returns the extracted data in a standardized format for use in route re-planning and re-routing.
    """
    
    def __init__(self, api_key: Optional[str]=None, model: str = "gemini-1.5-flash"):
        """
        Initializes the NewsParsingAgent.

        Args:
            api_key (str): The API key for accessing the language model.    
            model (str): The name of the language model to use for parsing news articles.
        """
        self.api_key = api_key or os.getenv("GENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided either as an argument or through the GENAI_API_KEY environment variable.")
        genai.configure(api_key=self.api_key)
        self.model=genai.GenerativeModel(model)
        logger.info(f"Initialized NewsParsingAgent with model: {model}")
    
    def parse_json(self, text: str) -> dict:
    # strip markdown code blocks if present
        text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
        return json.loads(text)
    
    def call_with_retry(self, prompt: str) -> dict:
        for attempt in range(2):
            try:
                response = self.model.generate_content(prompt)
                return self.parse_json(response.text)  # strip backticks then parse
            except json.JSONDecodeError:
                if attempt == 0:
                    logger.warning("Malformed JSON, retrying with explicit instruction...")
                    prompt = "Return ONLY valid JSON, no markdown, no explanation.\n\n" + prompt
                else:
                    logger.error("Failed to parse JSON after retry")
                    raise

    def classify_subagent(self, article: str) -> dict:
        """
        This sub-agent classifies whether a given news article describes a road disruption that could impact traffic.
        It uses the content of the article to determine if it meets the criteria for a road disruption

        Args:
            article (str): The news article text.
        Returns:    
            dict: A dictionary containing the classification and explanation.
        """
        prompt = f"""
You are a news parsing agent that identifies road disruptions from news articles within Pittsburgh, PA.
You are given a news article or piece of text. 
Your task is to determine if the article describes a road disruption that could impact traffic.
A road disruption is defined as any event or condition that significantly impedes the normal flow of traffic on a roadway, potentially causing delays or requiring detours.
A road disruption could include high congestion traffic, accidents, road closures, major event, or construction work.
Please analyze the article and classify it as either "road disruption" or "not road disruption" based on the content.

Article:
{article}

Please provide your classification as a single word: "True" for a road disruptionor "False" for not a road disruption.
If the article is classified as "True", please also provide a thorough explanation of the reasoning behind the classification, including specific details from the article that led to the conclusion.
Provide this inforomation in a JSON format with the following structure:
{{
    "classification": "True" or "False",
    "explanation": "A detailed explanation of the reasoning behind the classification, including specific details from the article that led to the conclusion.",
    "confidence": "A number between 0 and 1 indicating the confidence level of the classification, with 1 being completely confident and 0 being not confident at all."
}}
"""         
        try:
            response_json = self.call_with_retry(prompt)
            classification = response_json.get("classification")
            #explanation = response_json.get("explanation")
            logger.info(f"Article classified as: {classification}")
            return response_json
        except Exception as e:
            logger.error(f"Error during classification: {e}")
            return {"classification": "False", "explanation": f"Error during classification: {e}", "confidence": 0}
            


    def disruption_data_subagent(self, article: str, classify_json: dict) -> dict:
        """
        This sub-agent extracts structured data about the disruption, including location, type, severity, and expected duration.
        It uses the original article and the classification explanation to inform its extraction.

        Args:
            article (str): The news article text.   
            classify_json (dict): The JSON output from the classification sub-agent, containing the classification and explanation.
        Returns:
            dict: A dictionary containing the extracted disruption data in a standardized format.
        """
        prompt = f"""
You are a news parsing agent that identifies road disruptions from news articles within Pittsburgh, PA.
You are given a news article or piece of text, along with a classification result and explanation from a previous analysis.
Your task is to extract structured data about the disruption, including location, type, severity, and expected duration.
Please analyze the article and the classification explanation, and extract the following information if available:
- Location: The specific location of the disruption (e.g., "I-95 near downtown", "Main Street between 1st and 2nd Ave").
    - The more specific the location, the better, down to the intersection or mile marker that are closed or disrupted if possible,
    but do not invent locations if they are not mentioned in the article. 
    You can also include the city or region if that is the only location information provided, such as "downtown" or "the city center".
- Type: The type of disruption (e.g., "accident", "construction", "road closure", "heavy traffic").
- Severity: The severity of the disruption (e.g., "minor", "moderate", "severe") based on the expected impact on traffic.
- Expected Duration: The expected duration of the disruption (e.g., "30 minutes", "2 hours", "until further notice").
If any of the above information is not available in the article, please indicate it as "unknown". 
If you have any additiona relevant or historical data about such disruptions in the area that could help inform the expected duration or severity, you can include that as well.
Article:
{article}

Classification Explanation:
{classify_json.get("explanation")}

Respond with ONLY a JSON object (no markdown, no code blocks) in this exact format:
{{
  "event_type": "string (e.g., 'road closure', 'accident', 'construction', 'weather impact')",
  "roads_affected": ["list of specific road names/numbers affected"],
  "intersections": ["list of key intersections mentioned"],
  "neighborhoods": ["list of Pittsburgh neighborhoods affected"],
  "area_description": "brief description of the affected area",
  "severity": "high/medium/low based on impact",
  "duration_hours_estimate": number or null if unknown,
  "confidence": number between 0 and 1 indicating confidence in the extraction,
  "source_quote": "exact quote from article supporting the extraction",
  "additional_info": "any additional relevant information or context that could be useful for understanding the disruption"
}}

Be specific to Pittsburgh, PA geography. Use only information explicitly mentioned or strongly implied 
in the article. Set confidence low (0.3-0.5) if details are vague. Empty lists are acceptable."""
        try:
            response_json = self.call_with_retry(prompt)
            logger.info(f"Extracted disruption data")
            return response_json
        except Exception as e:
            logger.error(f"Error during disruption data extraction: {e}")
            return None
    
    def parse_article(self, article: str) -> dict:
        """
        Main method to parse a news article and extract disruption data if applicable.
        It first classifies the article to determine if it describes a road disruption, and if so
        it extracts structured data about the disruption.
        Args:
            article (str): The news article text.
        Returns:        
            dict: A dictionary containing the extracted disruption data in a standardized format, or None if the article does not describe a road disruption or if there was an error during parsing.
        """
        if not article or not article.strip():
            logger.warning("Empty article text provided")
            return None
        classify_result = self.classify_subagent(article)
        if classify_result.get("classification") not in ["True", "False"] or not isinstance(classify_result.get("confidence"), (int, float)) or not (0 <= classify_result.get("confidence") <= 1):
            return None
            # raise ValueError(f"Invalid classification or confidence in response: {classify_result}")
        if classify_result.get("confidence") < 0.2:
            logger.warning(f"Low confidence {classify_result.get('confidence')} in classification. Article: {article}")
            return None 
        if classify_result.get("classification") == "True":
            disruption_data = self.disruption_data_subagent(article, classify_result)
                 
        else:
            logger.info("Article classified as not a road disruption. No further data extracted.")
            return None
           
        if disruption_data is None:
            logger.warning("Disruption data extraction failed.")
            return None
        if disruption_data.get("confidence", 0) < 0.2:
            logger.warning(f"Low confidence {disruption_data.get('confidence', 0)} in extracted disruption data. Returning None.")
            return None
        logger.info(f"Successfully parsed article with confidence {disruption_data.get('confidence', 0)}. Returning extracted data.")
        return disruption_data
    

if __name__ == "__main__":
    # Initialize the agent
    agent = NewsParsingAgent()

    # Example article text
    sample_article = """
    Pittsburgh Traffic Alert: Major accident reported on Route 28 near the 16th Street Bridge.
    Multiple vehicles involved in collision this morning around 8:30 AM. The northbound lanes 
    are completely blocked, causing major delays for commuters heading downtown. Emergency 
    responders are on scene. The Pennsylvania Department of Transportation estimates the closure 
    will last at least 2 hours. Drivers are advised to use alternate routes such as the 
    Pittsburgh Bridge or local streets through the Strip District and Downtown.
    """

    result = agent.parse_article(sample_article)

    if result:
        print("Successfully parsed disruption event:")
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print("Article was not classified as a relevant disruption or confidence was too low")

