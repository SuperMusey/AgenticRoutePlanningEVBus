"""
MCP tools: generate synthetic Pittsburgh PRT transit-disruption news articles.

Adapted from news_server.py. Articles reference only streets, intersections,
neighborhoods, and landmarks — never route numbers — so the classify/extract
pipeline can infer affected routes without bias.

Workflow integration:
  1. generate_news_article(event_type, corridor_name, severity)
       → returns a `prompt` field
  2. Pass `prompt` to the LLM → LLM writes the article text
  3. Feed article text into classify_disruption / extract_disruption_data
  4. Continue with the standard ev-car route-planning workflow
"""

import datetime
import json
import logging
import random
from typing import Optional

from src.config import ROUTE_PAIRS_PATH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pittsburgh geography knowledge base
# ---------------------------------------------------------------------------

PITTSBURGH_CORRIDORS = {
    "Route 21 (Inbound)": {
        "neighborhoods": ["Carnegie", "Crafton", "Sheraden", "Elliott", "West End"],
        "key_streets": ["Chartiers Avenue", "Washington Avenue", "Main Street", "Mansfield Avenue"],
        "landmarks": ["Carnegie Library", "Crafton Borough Building", "West End Bridge"],
    },
    "Route 61C (Inbound)": {
        "neighborhoods": ["Squirrel Hill", "Greenfield", "Oakland"],
        "key_streets": ["Murray Avenue", "Forbes Avenue", "Beacon Street", "Darlington Road", "Shady Avenue"],
        "landmarks": ["Squirrel Hill Tunnel", "Magee-Womens Hospital", "Giant Eagle Murray Ave"],
    },
    "Route 64 (Inbound)": {
        "neighborhoods": ["McKeesport", "Duquesne", "Homestead", "Hazelwood"],
        "key_streets": ["Lysle Boulevard", "Fifth Avenue", "Versailles Avenue", "Eden Park Drive"],
        "landmarks": ["McKeesport YMCA", "Duquesne City Hall", "Monongahela River waterfront"],
    },
    "Route 28X (Inbound)": {
        "neighborhoods": ["Strip District", "Lawrenceville", "Oakland", "Airport Corridor"],
        "key_streets": ["Penn Avenue", "Liberty Avenue", "40th Street", "11th Street", "22nd Street"],
        "landmarks": ["Pittsburgh International Airport", "Strip District Market", "Convention Center"],
    },
    "Route 71A (Inbound)": {
        "neighborhoods": ["Shadyside", "East Liberty", "Oakland", "Negley"],
        "key_streets": ["Penn Avenue", "Negley Avenue", "Forbes Avenue", "Morewood Avenue"],
        "landmarks": ["UPMC Presbyterian", "East Liberty Presbyterian Church", "Whole Foods Market"],
    },
    "Route 71B (Inbound)": {
        "neighborhoods": ["Shadyside", "Oakland", "CMU Campus"],
        "key_streets": ["Forbes Avenue", "Morewood Avenue", "Margaret Morrison Street", "Beeler Street"],
        "landmarks": ["Carnegie Mellon University", "Shadyside Hospital", "Phipps Conservatory"],
    },
    "Route 71D (Inbound)": {
        "neighborhoods": ["Homewood", "East Liberty", "Oakland"],
        "key_streets": ["Hamilton Avenue", "Frankstown Avenue", "Tioga Street", "Lang Avenue"],
        "landmarks": ["Homewood Library", "East Liberty Transit Center", "UPMC East"],
    },
    "Route 86 (Inbound)": {
        "neighborhoods": ["South Side", "Mt. Washington", "Duquesne Heights"],
        "key_streets": ["Crosstown Boulevard", "Carson Street", "Warrington Avenue"],
        "landmarks": ["UPMC Mercy Hospital", "South Side Works", "Monongahela Incline"],
    },
    "Route 91 (Inbound)": {
        "neighborhoods": ["South Hills", "Brookline", "Beechview"],
        "key_streets": ["Becks Run Road", "Brownsville Road", "Clairton Boulevard"],
        "landmarks": ["Saw Mill Run Creek", "Brookline Memorial Park", "South Hills Junction"],
    },
    "Route 93 (Inbound)": {
        "neighborhoods": ["McKeesport", "Duquesne", "Glassport"],
        "key_streets": ["Lysle Boulevard", "Eden Park Drive", "Fifth Avenue", "Duquesne Boulevard"],
        "landmarks": ["Monongahela River", "Duquesne Steel Site", "McKeesport Transit Center"],
    },
}

EVENT_TYPES = [
    "fire",
    "traffic_accident",
    "water_main_break",
    "road_closure",
    "medical_emergency",
    "police_activity",
    "special_event",
    "weather",
    "utility_work",
    "bridge_inspection",
]

SEVERITY_LEVELS = ["minor", "moderate", "severe"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_article_data(
    event_type: str,
    corridor_name: str,
    severity: str = "moderate",
    seed: Optional[int] = None,
) -> dict:
    """Shared logic for generate_news_article and generate_news_batch."""
    if event_type not in EVENT_TYPES:
        return {"error": f"Unknown event_type '{event_type}'. Valid: {EVENT_TYPES}"}
    if severity not in SEVERITY_LEVELS:
        return {"error": f"Unknown severity '{severity}'. Valid: {SEVERITY_LEVELS}"}
    if corridor_name not in PITTSBURGH_CORRIDORS:
        return {
            "error": f"Unknown corridor '{corridor_name}'.",
            "available": list(PITTSBURGH_CORRIDORS.keys()),
        }

    if seed is not None:
        random.seed(seed)

    corridor = PITTSBURGH_CORRIDORS[corridor_name]
    streets = corridor["key_streets"]
    neighborhoods = corridor["neighborhoods"]
    landmarks = corridor["landmarks"]

    primary_street = random.choice(streets)
    cross_street = random.choice([s for s in streets if s != primary_street] or streets)
    neighborhood = random.choice(neighborhoods)
    landmark = random.choice(landmarks)

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")
    time_str = now.strftime("%I:%M %p").lstrip("0")

    prompt = _build_generation_prompt(
        event_type=event_type,
        severity=severity,
        primary_street=primary_street,
        cross_street=cross_street,
        neighborhood=neighborhood,
        landmark=landmark,
        time_str=time_str,
    )

    return {
        "prompt": prompt,
        "timestamp": timestamp,
        "event_type": event_type,
        "severity": severity,
        "affected_streets": [primary_street, cross_street],
        "affected_neighborhoods": [neighborhood],
        "landmark_reference": landmark,
        "corridor_hint": corridor_name,
        "instructions": (
            "Pass `prompt` to the LLM to produce the article text, then feed "
            "that text into classify_disruption. Do NOT pass corridor_hint to "
            "the route-planner."
        ),
    }


def _build_generation_prompt(
    event_type: str,
    severity: str,
    primary_street: str,
    cross_street: str,
    neighborhood: str,
    landmark: str,
    time_str: str,
) -> str:
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

    return f"""Write a realistic local news article about the following event in Pittsburgh, PA.

EVENT: {event_guidance[event_type]}
NEIGHBORHOOD: {neighborhood}
NEARBY LANDMARK: {landmark}
SEVERITY: {severity} — {severity_guidance[severity]}
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


def _load_route_names() -> list[str]:
    """Return route names from route_pairs.json."""
    try:
        with open(ROUTE_PAIRS_PATH) as f:
            data = json.load(f)
        names = []
        for route_dict in data["routes"]:
            names.extend(route_dict.keys())
        return names
    except Exception as e:
        logger.warning("Could not load route names: %s", e)
        return []


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp) -> None:

    @mcp.tool()
    def list_available_corridors() -> dict:
        """
        List all Pittsburgh transit corridors available for news article generation,
        with their associated neighborhoods, key streets, and landmarks.

        Use this before calling generate_news_article to pick a valid corridor_name.
        Returns a dictionary mapping corridor names to their geographic details.
        """
        return PITTSBURGH_CORRIDORS

    @mcp.tool()
    def get_corridor_details(corridor_name: str) -> dict:
        """
        Get detailed geographic information for a specific transit corridor.

        Args:
            corridor_name: The corridor name (e.g. 'Route 61C (Inbound)').
                           Use list_available_corridors() to see valid names.

        Returns:
            A dict with neighborhoods, key_streets, and landmarks, or an error
            if the corridor is not found.
        """
        if corridor_name in PITTSBURGH_CORRIDORS:
            return {"corridor": corridor_name, **PITTSBURGH_CORRIDORS[corridor_name]}
        return {
            "error": f"Corridor '{corridor_name}' not found.",
            "available": list(PITTSBURGH_CORRIDORS.keys()),
        }

    @mcp.tool()
    def get_event_types() -> dict:
        """
        Return the list of supported event types and severity levels for use with
        generate_news_article() and generate_news_batch().
        """
        return {
            "event_types": EVENT_TYPES,
            "severity_levels": SEVERITY_LEVELS,
            "descriptions": {
                "fire": "Structure or vehicle fire causing road closure or smoke obstruction",
                "traffic_accident": "Multi-vehicle collision blocking lanes or intersections",
                "water_main_break": "Ruptured water main undermining or flooding the roadway",
                "road_closure": "Planned or emergency full road closure by city or PennDOT",
                "medical_emergency": "Medical incident (cardiac, trauma) on or near transit corridor",
                "police_activity": "Active police investigation, crime scene, or bomb threat perimeter",
                "special_event": "Concert, marathon, festival, or sporting event causing lane reductions",
                "weather": "Flash flooding, ice, or storm damage affecting road access",
                "utility_work": "Gas, electric, or telecom emergency work in the roadway",
                "bridge_inspection": "Emergency structural inspection resulting in bridge closure",
            },
        }

    @mcp.tool()
    def generate_news_article(
        event_type: str,
        corridor_name: str,
        severity: str = "moderate",
        seed: Optional[int] = None,
    ) -> dict:
        """
        Generate a prompt for a single realistic Pittsburgh transit-disruption news
        article along the specified corridor. Pass the returned `prompt` field to the
        LLM; the LLM response becomes the article text. Feed that text into
        classify_disruption to continue the disruption-detection workflow.

        Articles reference only streets, intersections, neighborhoods, and landmarks
        — never PRT route numbers — so the route-planner can infer impacts unbiased.

        Args:
            event_type: One of: fire, traffic_accident, water_main_break,
                        road_closure, medical_emergency, police_activity,
                        special_event, weather, utility_work, bridge_inspection.
                        Call get_event_types() for descriptions.
            corridor_name: Target corridor. Call list_available_corridors() for
                           valid values.
            severity: 'minor', 'moderate', or 'severe'. Defaults to 'moderate'.
            seed: Optional integer seed for reproducibility.

        Returns:
            A dict with: prompt, timestamp, event_type, severity,
            affected_streets, affected_neighborhoods, landmark_reference.
            Do NOT pass corridor_hint to the route-planner.
        """
        return _generate_article_data(event_type, corridor_name, severity, seed)

    @mcp.tool()
    def generate_news_batch(
        count: int = 5,
        event_types: Optional[list[str]] = None,
        corridors: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> dict:
        """
        Generate a batch of article-generation prompts covering varied event types
        and corridors. Useful for stress-testing the full disruption pipeline.

        For each article in the returned list, pass its `prompt` to the LLM to
        produce the text, then run each through the classify/extract/route workflow.

        Args:
            count: Number of articles to generate (1–20). Defaults to 5.
            event_types: Subset of event types to draw from. Defaults to all.
            corridors: Subset of corridor names to target. Defaults to all.
            seed: Optional integer seed for reproducibility.

        Returns:
            A dict with 'articles' (list of generate_news_article outputs)
            and a 'summary' of event types, corridors, and severities used.
        """
        count = max(1, min(count, 20))

        if seed is not None:
            random.seed(seed)

        available_corridors = list(PITTSBURGH_CORRIDORS.keys())
        target_corridors = corridors if corridors else available_corridors
        target_events = event_types if event_types else EVENT_TYPES

        bad_corridors = [c for c in target_corridors if c not in available_corridors]
        if bad_corridors:
            return {"error": f"Unknown corridors: {bad_corridors}. Use list_available_corridors()."}

        bad_events = [e for e in target_events if e not in EVENT_TYPES]
        if bad_events:
            return {"error": f"Unknown event types: {bad_events}. Valid: {EVENT_TYPES}"}

        articles = []
        used_corridors: set[str] = set()

        for _ in range(count):
            unused = [c for c in target_corridors if c not in used_corridors]
            corridor = random.choice(unused if unused else target_corridors)
            event_type = random.choice(target_events)
            severity = random.choice(SEVERITY_LEVELS)

            article = _generate_article_data(event_type, corridor, severity)
            articles.append(article)
            used_corridors.add(corridor)

        return {
            "articles": articles,
            "count": len(articles),
            "summary": {
                "event_types_used": list({a["event_type"] for a in articles if "event_type" in a}),
                "corridors_targeted": list({a["corridor_hint"] for a in articles if "corridor_hint" in a}),
                "severities": list({a["severity"] for a in articles if "severity" in a}),
            },
            "instructions": (
                "For each article, pass its `prompt` to the LLM to produce the article text, "
                "then run each text through classify_disruption. Strip corridor_hint before "
                "forwarding articles to the route-planner."
            ),
        }
