"""
Prompt: reusable news article generation template for PRT disruption simulation.

Exports:
  register(mcp) — registers the news_article_prompt MCP prompt.
"""


def register(mcp) -> None:
    @mcp.prompt()
    def news_article_prompt(
        event_type: str,
        primary_street: str,
        cross_street: str,
        neighborhood: str,
        landmark: str,
        severity: str = "moderate",
        time_str: str = "8:30 AM",
    ) -> str:
        """
        Reusable prompt template for generating a single PRT disruption news article.
        Call generate_news_article() to get a pre-populated version of this prompt
        with randomly selected geographic anchors for a given corridor.
        """
        severity_guidance = {
            "minor": "The disruption is localised to one block and expected to clear within the hour.",
            "moderate": "The disruption affects several blocks and will last 1–3 hours.",
            "severe": "The disruption is large-scale, affecting multiple intersections and expected to last all day.",
        }
        event_guidance = {
            "fire": f"A structure or vehicle fire near {primary_street} and {cross_street}.",
            "traffic_accident": f"A multi-vehicle collision at {primary_street} and {cross_street}.",
            "water_main_break": f"A ruptured water main beneath {primary_street} near {cross_street}.",
            "road_closure": f"An emergency road closure on {primary_street} near {cross_street}.",
            "medical_emergency": f"A medical emergency on or near {primary_street} close to {landmark}.",
            "police_activity": f"An active police investigation on {primary_street} near {cross_street}.",
            "special_event": f"A large public event near {landmark} causing lane reductions on {primary_street}.",
            "weather": f"Flash flooding or storm damage affecting {primary_street} near {cross_street}.",
            "utility_work": f"Emergency utility work in the roadway on {primary_street} near {cross_street}.",
            "bridge_inspection": f"An emergency bridge inspection closing {primary_street} at {cross_street}.",
        }

        event_desc = event_guidance.get(event_type, f"An incident on {primary_street} near {cross_street}.")
        sev_desc = severity_guidance.get(severity, "")

        return f"""Write a realistic local news article about the following event in Pittsburgh, PA.

EVENT: {event_desc}
NEIGHBORHOOD: {neighborhood}
NEARBY LANDMARK: {landmark}
SEVERITY: {severity} — {sev_desc}
TIME: {time_str} today

REQUIREMENTS:
- Write in AP style with a headline, a one-sentence lede, and 3 short paragraphs.
- Reference only street names, intersections, neighborhoods, and landmarks.
- Do NOT mention any PRT route numbers (e.g. do not say "Route 61C" or "the 71A bus").
- You MAY reference "buses", "transit", or "public transit" generically.
- Include realistic details: emergency responder units, estimated clearance times,
  impact on commuters, and any safety guidance for the public.
- Keep the total length under 300 words.
- Output plain text only — no markdown formatting.
"""
