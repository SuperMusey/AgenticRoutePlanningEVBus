"""
Extraction prompt: extract structured disruption data from a classified Pittsburgh article.

Exports:
  register(mcp) — registers the extract_disruption_data MCP prompt.
"""

EXTRACTION_SYSTEM = """\
You are a news parsing agent that identifies road disruptions from news articles within Pittsburgh, PA.
You are given a news article and a classification explanation from a previous analysis.
Your task is to extract structured data about the disruption.

Extract the following if available:
- Location: Specific location down to intersection or mile marker if possible. Do not invent locations.
- Type: Type of disruption (accident, construction, road closure, heavy traffic, etc.)
- Severity: Based on expected traffic impact (high/medium/low)
- Duration: Expected duration of the disruption

If any information is unavailable, use null for numbers and empty lists for arrays.
Set confidence low (0.3-0.5) if details are vague.

Respond with ONLY a valid JSON object (no markdown, no code blocks):
{
  "event_type": "string (e.g., road closure, accident, construction, weather impact)",
  "roads_affected": ["list of specific road names/numbers affected"],
  "intersections": ["list of key intersections mentioned"],
  "neighborhoods": ["list of Pittsburgh neighborhoods affected"],
  "area_description": "brief description of the affected area",
  "severity": "high/medium/low based on impact",
  "duration_hours_estimate": null,
  "confidence": 0.0,
  "source_quote": "exact quote from article supporting the extraction",
  "additional_info": "any additional relevant information"
}
Be specific to Pittsburgh, PA geography. Use only information explicitly mentioned or strongly implied in the article.\
"""


def register(mcp) -> None:
    @mcp.prompt()
    def extract_disruption_data(article: str, explanation: str) -> str:
        """
        Prompt template for extracting structured disruption fields from a Pittsburgh
        news article. Requires the article text and a prior classification explanation.
        Returns a formatted prompt ready to send to an LLM.
        """
        return (
            f"{EXTRACTION_SYSTEM}\n\n"
            f"Article:\n{article}\n\n"
            f"Classification Explanation:\n{explanation}"
        )
