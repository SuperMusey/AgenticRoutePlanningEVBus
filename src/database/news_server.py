"""
PRT News MCP Server
-------------------
Exposes tools for generating realistic transit-disruption news articles
about Pittsburgh Regional Transit corridors. Articles describe events
(fires, crashes, road closures, etc.) using only street names,
intersections, and landmarks — never route numbers — so a downstream
route-planner LLM can infer which routes are affected.

Run with:
    python server/news_server.py
or via the MCP CLI:
    mcp dev server/news_server.py
"""

import json
import random
import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="prt-news-generator",
    instructions=(
        "You are a news generation service for Pittsburgh Regional Transit. "
        "You produce realistic local news articles describing events that may "
        "affect bus service. Articles reference only streets, intersections, "
        "neighborhoods, and landmarks — never PRT route numbers."
    ),
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
ROUTE_DATA_PATH = DATA_DIR / "route_pairs.json"

def _load_route_names() -> list[str]:
    """Return a list of route names from the route_pairs.json file."""
    with open(ROUTE_DATA_PATH) as f:
        data = json.load(f)
    names = []
    for route_dict in data["routes"]:
        names.extend(route_dict.keys())
    return names


# ---------------------------------------------------------------------------
# Pittsburgh geography knowledge base
# (used by the LLM prompt to ground article generation in real places)
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
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_available_corridors() -> dict:
    """
    List all Pittsburgh transit corridors with their associated neighborhoods,
    key streets, and landmarks. Use this to understand the geography before
    generating targeted news articles.

    Returns a dictionary mapping corridor names to their geographic details.
    """
    return PITTSBURGH_CORRIDORS


@mcp.tool()
def get_corridor_details(corridor_name: str) -> dict:
    """
    Get detailed geographic information for a specific transit corridor.

    Args:
        corridor_name: The name of the corridor (e.g. 'Route 61C (Inbound)').
                       Use list_available_corridors() to see valid names.

    Returns:
        A dictionary with neighborhoods, key_streets, and landmarks for
        the corridor, or an error message if not found.
    """
    if corridor_name in PITTSBURGH_CORRIDORS:
        return {"corridor": corridor_name, **PITTSBURGH_CORRIDORS[corridor_name]}
    return {
        "error": f"Corridor '{corridor_name}' not found.",
        "available": list(PITTSBURGH_CORRIDORS.keys()),
    }


@mcp.tool()
def generate_news_article(
    event_type: str,
    corridor_name: str,
    severity: str = "moderate",
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a single realistic news article describing a transit-disrupting
    event along the specified corridor. The article will reference only
    streets, intersections, neighborhoods, and landmarks — never route numbers
    — so a downstream LLM can reason about which routes are affected.

    Args:
        event_type: One of: fire, traffic_accident, water_main_break,
                    road_closure, medical_emergency, police_activity,
                    special_event, weather, utility_work, bridge_inspection.
        corridor_name: The corridor to target. Use list_available_corridors()
                       for valid values.
        severity: 'minor', 'moderate', or 'severe'. Controls the urgency and
                  scope described in the article. Defaults to 'moderate'.
        seed: Optional integer random seed for reproducibility.

    Returns:
        A dict with keys: headline, lede, body, timestamp, event_type,
        severity, affected_streets, affected_neighborhoods.
    """
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

    # Pick geographic anchors for this article
    primary_street = random.choice(streets)
    cross_street = random.choice([s for s in streets if s != primary_street] or streets)
    neighborhood = random.choice(neighborhoods)
    landmark = random.choice(landmarks)

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")
    time_str = now.strftime("%-I:%M %p")

    # Build a structured prompt payload the caller can forward to Claude
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
        "corridor_hint": corridor_name,  # for internal pipeline use only
        "instructions": (
            "Pass `prompt` to your LLM. The response will be the news article. "
            "Do NOT include `corridor_hint` in what you send to the route-planner."
        ),
    }


@mcp.tool()
def generate_news_batch(
    count: int = 5,
    event_types: Optional[list[str]] = None,
    corridors: Optional[list[str]] = None,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a batch of news articles covering a variety of event types and
    corridors. Useful for creating a diverse feed to test the route-planner LLM.

    Args:
        count: Number of articles to generate (1–20). Defaults to 5.
        event_types: Optional list of event types to draw from. Defaults to
                     all available types.
        corridors: Optional list of corridor names to target. Defaults to all
                   available corridors.
        seed: Optional integer random seed for reproducibility.

    Returns:
        A dict with a 'articles' list, each element being the output of
        generate_news_article(), plus a 'summary' of what was generated.
    """
    count = max(1, min(count, 20))

    if seed is not None:
        random.seed(seed)

    available_corridors = list(PITTSBURGH_CORRIDORS.keys())
    target_corridors = corridors if corridors else available_corridors
    target_events = event_types if event_types else EVENT_TYPES

    # Validate inputs
    bad_corridors = [c for c in target_corridors if c not in available_corridors]
    if bad_corridors:
        return {"error": f"Unknown corridors: {bad_corridors}. Use list_available_corridors()."}

    bad_events = [e for e in target_events if e not in EVENT_TYPES]
    if bad_events:
        return {"error": f"Unknown event types: {bad_events}. Valid: {EVENT_TYPES}"}

    articles = []
    used_corridors = set()

    for i in range(count):
        # Prefer corridors not yet used to maximise variety
        unused = [c for c in target_corridors if c not in used_corridors]
        corridor = random.choice(unused if unused else target_corridors)
        event_type = random.choice(target_events)
        severity = random.choice(SEVERITY_LEVELS)

        article = generate_news_article(
            event_type=event_type,
            corridor_name=corridor,
            severity=severity,
        )
        articles.append(article)
        used_corridors.add(corridor)

    return {
        "articles": articles,
        "count": len(articles),
        "summary": {
            "event_types_used": list({a["event_type"] for a in articles}),
            "corridors_targeted": list({a["corridor_hint"] for a in articles}),
            "severities": list({a["severity"] for a in articles}),
        },
        "instructions": (
            "For each article, pass `prompt` to your LLM to produce the article text. "
            "Strip `corridor_hint` before forwarding articles to the route-planner LLM."
        ),
    }


@mcp.tool()
def get_event_types() -> dict:
    """
    Return the list of supported event types and severity levels that can be
    used with generate_news_article() and generate_news_batch().
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


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("prt://route-data/corridor-map")
def corridor_map_resource() -> str:
    """
    Full corridor-to-geography mapping as JSON. Provides the complete
    Pittsburgh transit geography knowledge base used by the news generator.
    """
    return json.dumps(PITTSBURGH_CORRIDORS, indent=2)


@mcp.resource("prt://route-data/raw-stops")
def raw_stops_resource() -> str:
    """
    Raw route stop coordinate data from route_pairs.json. Contains GPS
    coordinates for each stop on every route — useful for the route-planner
    LLM to perform spatial matching against article locations.
    """
    with open(ROUTE_DATA_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

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
    Reusable prompt template for generating a single PRT news article.
    Call generate_news_article() to get a pre-populated version of this prompt.
    """
    return _build_generation_prompt(
        event_type=event_type,
        severity=severity,
        primary_street=primary_street,
        cross_street=cross_street,
        neighborhood=neighborhood,
        landmark=landmark,
        time_str=time_str,
    )


@mcp.prompt()
def route_impact_analysis_prompt(article_text: str, route_data_json: str) -> str:
    """
    Prompt template for the route-planner LLM. Given a news article and the
    raw route stop data, asks the LLM to identify which routes are affected.

    Args:
        article_text: The generated news article text.
        route_data_json: JSON string of route stop coordinates (from raw-stops resource).
    """
    return f"""You are a Pittsburgh Regional Transit operations analyst.

Below is a news article describing an event in the Pittsburgh area, followed by
PRT route stop coordinate data. Your job is to identify which bus routes are
likely affected by the event described in the article.

## News Article
{article_text}

## PRT Route Stop Data (JSON)
{route_data_json}

## Instructions
1. Extract the affected streets, intersections, and neighborhoods from the article.
2. Cross-reference those locations against the route stop coordinates.
3. List every route that has stops within or adjacent to the affected area.
4. For each affected route, briefly explain why it is impacted.
5. Estimate the severity of the impact: Minor / Moderate / Severe.
6. Suggest a plain-language service advisory message for riders.

Respond in structured JSON with this schema:
{{
  "affected_routes": [
    {{
      "route_name": "string",
      "impact_severity": "Minor | Moderate | Severe",
      "reason": "string",
      "advisory": "string"
    }}
  ],
  "unaffected_routes": ["list of route names with no expected impact"],
  "summary": "one-sentence plain-English summary for public display"
}}
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
