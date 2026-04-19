"""
MCP tools: identify affected Pittsburgh PRT bus routes and suggest alternatives.

blocked_roads.json uses the same format as route_pairs.json:
  { "routes": [{ "road_name": [[lat, lng], ...] }] }

Module-level singletons (maps_service, store) are initialised once at import time.
Google-backed tools degrade gracefully when GOOGLE_MAPS_API_KEY is missing.
"""

import json
import logging
from typing import Any, Dict, List, Tuple

from src.config import BLOCKED_ROADS_PATH
from src.google_maps.maps_service import MapsService
from src.database.database import DisruptionStore

logger = logging.getLogger(__name__)

maps_service = MapsService._get_maps_service(require_api_key=False)
store = DisruptionStore(maps_service)


def _save_blocked_roads_payload(
    road_name: str, coordinates: List[Tuple[float, float]]
) -> Dict[str, Any]:
    payload = {"routes": [{road_name: [[lat, lng] for lat, lng in coordinates]}]}
    BLOCKED_ROADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BLOCKED_ROADS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info(
        "Saved blocked road '%s' (%d points) to %s",
        road_name,
        len(coordinates),
        BLOCKED_ROADS_PATH,
    )
    return {
        "success": True,
        "road_name": road_name,
        "points_saved": len(coordinates),
        "path": str(BLOCKED_ROADS_PATH),
    }


def _normalize_coordinates(
    coordinates: List[List[float]],
) -> List[Tuple[float, float]]:
    if len(coordinates) < 2:
        raise ValueError("At least two coordinate pairs are required.")

    normalized: List[Tuple[float, float]] = []
    for idx, coord in enumerate(coordinates):
        if len(coord) != 2:
            raise ValueError(
                f"Coordinate at index {idx} must contain exactly [lat, lng]."
            )

        lat = float(coord[0])
        lng = float(coord[1])
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude at index {idx} is out of range: {lat}")
        if not -180 <= lng <= 180:
            raise ValueError(f"Longitude at index {idx} is out of range: {lng}")
        normalized.append((lat, lng))

    return normalized


def _google_maps_required_error(tool_name: str) -> Dict[str, Any]:
    return {
        "success": False,
        "error": (
            f"{tool_name} requires GOOGLE_MAPS_API_KEY for Google Maps routing. "
            "To run without API keys, call save_blocked_road_polyline and then "
            "identify_affected_routes_from_blocked_roads."
        ),
    }


def _run_proximity_check(
    polyline_path: List[Tuple[float, float]],
    disruption_address_1: str,
    disruption_address_2: str,
) -> Dict[str, int]:
    """
    Check all PRT stops for proximity to a polyline and populate the session store.
    Returns a dict mapping route_name → affected stop count.
    """
    store.start_disruption(disruption_address_1, disruption_address_2)
    store.set_blocked_road_polyline(polyline_path)
    all_stops = store.stop_data
    affected_routes_summary: Dict[str, int] = {}
    proximity_threshold_km = 0.1

    for route_name, stops in all_stops.items():
        affected_stop_indices = []
        for idx, stop_coord in enumerate(stops):
            if maps_service._is_within_proximity(
                stop_coord, polyline_path, proximity_threshold_km
            ):
                affected_stop_indices.append((idx, stop_coord))

        affected_stop_indices = sorted(set(affected_stop_indices))
        if affected_stop_indices:
            store.add_affected_route(route_name)
            for stop_idx, stop_coord in affected_stop_indices:
                store.add_affected_stop(route_name, stop_idx, stop_coord)
            affected_routes_summary[route_name] = len(affected_stop_indices)

    return affected_routes_summary


def register(mcp) -> None:
    @mcp.tool()
    def save_blocked_roads(
        road_name: str,
        address_1: str,
        address_2: str,
    ) -> Dict[str, Any]:
        """
        Fetch the road polyline from Google Maps and save it to blocked_roads.json
        in the same format as route_pairs.json:
          { "routes": [{ "<road_name>": [[lat, lng], ...] }] }

        Call this after extracting the disruption corridor from a news article.
        identify_affected_routes_from_blocked_roads will read the coordinates
        directly without a second Google Maps call.

        Args:
            road_name: Descriptive name for the blocked segment (e.g. "Forbes Ave closure").
            address_1: Starting address of the disruption corridor in Pittsburgh, PA.
            address_2: Ending address of the disruption corridor in Pittsburgh, PA.
        """
        try:
            if not maps_service.has_api_key:
                return _google_maps_required_error("save_blocked_roads")

            encoded_polyline = maps_service.get_polyline(address_1, address_2)
            if not encoded_polyline:
                return {"success": False, "error": "Could not fetch polyline from Google Maps"}

            coordinates = maps_service.decode_polyline(encoded_polyline)
            return _save_blocked_roads_payload(road_name, coordinates)
        except Exception as e:
            logger.error("save_blocked_roads failed: %s", e)
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def save_blocked_road_polyline(
        road_name: str,
        coordinates: List[List[float]],
    ) -> Dict[str, Any]:
        """
        Save a blocked road polyline directly without calling Google Maps.

        Use this tool when coordinates are already known and the server is
        running without GOOGLE_MAPS_API_KEY. The saved file can then be consumed by
        identify_affected_routes_from_blocked_roads.

        Args:
            road_name: Descriptive name for the blocked segment.
            coordinates: Ordered list of [lat, lng] pairs for the blocked road.
        """
        try:
            normalized_coordinates = _normalize_coordinates(coordinates)
            return _save_blocked_roads_payload(road_name, normalized_coordinates)
        except Exception as e:
            logger.error("save_blocked_road_polyline failed: %s", e)
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def identify_affected_routes_from_blocked_roads() -> Dict[str, Any]:
        """
        Identify affected Pittsburgh PRT bus routes using the saved blocked_roads.json.

        Reads the road polyline saved by save_blocked_roads (same format as
        route_pairs.json) and checks every PRT stop for proximity within 100 m.
        No Google Maps call is made — the polyline is used directly from the file.

        Call save_blocked_roads first to populate the file.
        """
        try:
            if not BLOCKED_ROADS_PATH.exists():
                return {
                    "success": False,
                    "error": "No blocked roads data found. Call save_blocked_roads first.",
                }
            with open(BLOCKED_ROADS_PATH, "r") as f:
                payload = json.load(f)

            routes = payload.get("routes", [])
            if not routes:
                return {"success": False, "error": "blocked_roads.json contains no routes."}

            # Extract road name and polyline from the first route entry
            route_entry = routes[0]
            road_name, coordinates = next(iter(route_entry.items()))
            polyline_path = [tuple(coord) for coord in coordinates]

            # Use road_name as both addresses for the session label
            affected_routes_summary = _run_proximity_check(
                polyline_path, road_name, road_name
            )

            return {
                "success": True,
                "road_name": road_name,
                "polyline_points": len(polyline_path),
                "affected_routes_found": len(affected_routes_summary),
                "affected_routes": affected_routes_summary,
            }

        except Exception as e:
            logger.error("identify_affected_routes_from_blocked_roads failed: %s", e)
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def identify_affected_routes_between_locations(
        disruption_address_1: str,
        disruption_address_2: str,
    ) -> Dict[str, Any]:
        """
        Identify Pittsburgh PRT bus routes affected by a disruption between two addresses.

        Fetches the road polyline from Google Maps, then checks every PRT stop
        for proximity within 100 m. Use identify_affected_routes_from_blocked_roads
        instead if the polyline has already been saved to blocked_roads.json.

        Args:
            disruption_address_1: Starting address of the disruption corridor (Pittsburgh, PA).
            disruption_address_2: Ending address of the disruption corridor (Pittsburgh, PA).
        """
        try:
            if not maps_service.has_api_key:
                return _google_maps_required_error(
                    "identify_affected_routes_between_locations"
                )

            encoded_polyline = maps_service.get_polyline(
                disruption_address_1, disruption_address_2
            )
            if not encoded_polyline:
                return {"success": False, "error": "Could not extract polyline from Google Maps response"}

            polyline_path = maps_service.decode_polyline(encoded_polyline)
            affected_routes_summary = _run_proximity_check(
                polyline_path, disruption_address_1, disruption_address_2
            )

            return {
                "success": True,
                "affected_routes_found": len(affected_routes_summary),
                "affected_routes": affected_routes_summary,
            }

        except Exception as e:
            logger.error("identify_affected_routes failed: %s", e)
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def suggest_alternative_route(route_name: str) -> Dict[str, Any]:
        """
        Find substitute stops for an affected Pittsburgh PRT bus route.

        For each affected stop on the route, locates the nearest unaffected stop
        on a different route and records the substitution in the session database.
        Call an identify_affected_routes tool before this one.

        Args:
            route_name: Name of the affected route (e.g. "61C (Outbound)").
        """
        try:
            all_stops = store.stop_data
            affected_stops_indices = store.get_affected_stop_indices(route_name)
            if not affected_stops_indices:
                return {
                    "success": False,
                    "route_name": route_name,
                    "error": (
                        f"No affected stops found for '{route_name}'. "
                        "Call an identify_affected_routes tool first."
                    ),
                }

            original_route_stops = all_stops.get(route_name, [])
            if not original_route_stops:
                return {
                    "success": False,
                    "route_name": route_name,
                    "error": f"Route '{route_name}' not found in stop data.",
                }

            affected_set = sorted(set(affected_stops_indices))
            blocked_polyline = store.get_blocked_road_polyline()
            substitutions_made = 0

            for affected_idx in affected_set:
                affected_coord = original_route_stops[affected_idx]
                closest_stop = None
                closest_distance = float("inf")
                closest_route = None
                closest_idx = None

                for other_route_name, other_stops in all_stops.items():
                    if (
                        route_name.split("(")[0].strip()
                        == other_route_name.split("(")[0].strip()
                    ):
                        continue
                    for other_idx, other_coord in enumerate(other_stops):
                        if store.is_stop_affected(other_route_name, other_idx):
                            continue
                        if maps_service._is_within_proximity(
                            other_coord, blocked_polyline, threshold_km=0.1
                        ):
                            continue
                        distance = maps_service._haversine_distance(
                            affected_coord, other_coord
                        )
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_stop = other_coord
                            closest_route = other_route_name
                            closest_idx = other_idx

                if closest_stop:
                    store.add_substitution(
                        route_name=route_name,
                        affected_stop_index=affected_idx,
                        original_coordinates=affected_coord,
                        substitute_coordinates=closest_stop,
                        substitute_route=closest_route,
                        substitute_stop_index=closest_idx,
                        distance_km=round(closest_distance, 4),
                    )
                    substitutions_made += 1

            return {
                "success": True,
                "route_name": route_name,
                "substitutions_made": substitutions_made,
                "affected_stops_count": len(affected_set),
            }

        except Exception as e:
            logger.error("suggest_alternative_route failed: %s", e)
            return {"success": False, "route_name": route_name, "error": str(e)}

    @mcp.tool()
    def get_disruption_summary() -> Dict[str, Any]:
        """
        Retrieve a summary of the current disruption session.

        Returns affected route names, stop counts, substitution counts, and full
        substitution details. Call after suggest_alternative_route for all routes.
        """
        return {
            "summary": store.get_disruption_summary(),
            "substitutions": {
                route_name: [sub.model_dump(mode="json") for sub in subs]
                for route_name, subs in store.get_all_route_substitutions().items()
            },
        }

    @mcp.tool()
    def clear_disruption_session() -> Dict[str, str]:
        """
        Reset the disruption session store.

        Clears all affected routes, stops, and substitutions.
        Call this before processing a new disruption event.
        """
        store.clear()
        return {"status": "cleared"}
