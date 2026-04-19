"""
MCP server for Pittsburgh EV bus route disruption detection and re-routing.

Tools:
  read_news_file                              - read a downloaded article/bulletin
  load_blocked_roads                          - inspect saved blocked-road data
  save_blocked_roads                          - fetch/save a blocked-road polyline
  save_blocked_road_polyline                  - save known coordinates without Google Maps
  identify_affected_routes_between_locations  - find affected PRT bus routes
  identify_affected_routes_from_blocked_roads - find routes from saved polyline data
  suggest_alternative_route                   - find substitute stops for a route
  get_disruption_summary                      - retrieve current session results
  clear_disruption_session                    - reset session state
  list_available_corridors                    - list corridors for article generation
  get_corridor_details                        - geographic details for one corridor
  get_event_types                             - supported event types and severities
  generate_news_article                       - generate a synthetic disruption article prompt
  generate_news_batch                         - generate a batch of article prompts

Prompts:
  classify_disruption     - classification prompt template
  extract_disruption_data - extraction prompt template
  orchestrator_system     - full orchestration workflow instructions
  route_planning_system   - route planning agent instructions
  news_article_prompt     - reusable article generation template
"""

from mcp.server.fastmcp import FastMCP

from src.tools import news_tools, route_tools, news_generator_tools
from src.prompts import (
    classify_prompt,
    extraction_prompt,
    orchestrator_prompt,
    route_planning_prompt,
    news_generator_prompt,
)

mcp = FastMCP(
    "EV Bus Route Planning",
    instructions=(
        "Pittsburgh PRT bus route disruption detection and re-routing assistant. "
        "Read articles with read_news_file, classify them with the "
        "classify_disruption prompt, extract structured disruption fields with "
        "extract_disruption_data, then process each disruption corridor serially. "
        "Use save_blocked_roads plus identify_affected_routes_from_blocked_roads "
        "when a corridor should be persisted, or identify_affected_routes_between_locations "
        "when Google Maps address routing is available. For each affected route, "
        "call suggest_alternative_route, then get_disruption_summary, and finally "
        "clear_disruption_session before the next event."
    ),
)

news_tools.register(mcp)
route_tools.register(mcp)
news_generator_tools.register(mcp)
classify_prompt.register(mcp)
extraction_prompt.register(mcp)
orchestrator_prompt.register(mcp)
route_planning_prompt.register(mcp)
news_generator_prompt.register(mcp)

if __name__ == "__main__":
    mcp.run()
