"""
Route-specific tools for the EV bus route planning agent.

These tools integrate with the existing Google Maps service.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from langchain_core.tools import tool
from src.google_maps.maps_service import MapsService
from src.agents.database.disruption_store import DisruptionStore
from math import radians, cos, sin, asin, sqrt

STOPS_PATH = Path(__file__).parent.parent.parent / "PRT routes" / "route_pairs.json"
store = DisruptionStore(id=1)


def _get_maps_service() -> MapsService:
    """Initialize and return MapsService with API key from config."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment")
    return MapsService(api_key)


def _load_route_pairs() -> Dict[str, Any]:
    """Load route pairs from JSON file."""
    try:
        with open(STOPS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading route_pairs.json: {e}")
        return {"routes": []}


def _get_all_bus_stops() -> Dict[str, List[Tuple[float, float]]]:
    """
    Extract all bus stops from all routes.

    Returns:
        Dict mapping route name to list of (lat, lng) coordinates
    """
    route_pairs = _load_route_pairs()
    all_stops = {}

    for route_dict in route_pairs.get("routes", []):
        for route_name, coordinates in route_dict.items():
            stops = [(coord[0], coord[1]) for coord in coordinates]
            print(f"[Tools] Loaded {len(stops)} stops for route: {route_name}")
            all_stops[route_name] = stops
    return all_stops


def _distance_point_to_segment(
    point: Tuple[float, float],
    segment_start: Tuple[float, float],
    segment_end: Tuple[float, float],
) -> Tuple[float, bool]:
    """
    Calculate perpendicular distance from a point to a line segment.

    Args:
        point: (lat, lng) of the bus stop
        segment_start: (lat, lng) of segment start
        segment_end: (lat, lng) of segment end

    Returns:
        Tuple of (perpendicular_distance_km, is_on_segment)
    """
    lat1, lon1 = segment_start
    lat2, lon2 = segment_end
    lat_p, lon_p = point

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    lat_p_rad = radians(lat_p)
    lon_p_rad = radians(lon_p)

    R = 6371  # Earth radius in km

    # Distance A→B
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    ab_distance = R * 2 * asin(sqrt(a)) if a > 0 else 0

    # Distance A→Stop
    dlat = lat_p_rad - lat1_rad
    dlon = lon_p_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat_p_rad) * sin(dlon / 2) ** 2
    ap_distance = R * 2 * asin(sqrt(a)) if a > 0 else 0

    # Distance B→Stop
    dlat = lat_p_rad - lat2_rad
    dlon = lon_p_rad - lon2_rad
    a = sin(dlat / 2) ** 2 + cos(lat2_rad) * cos(lat_p_rad) * sin(dlon / 2) ** 2
    bp_distance = R * 2 * asin(sqrt(a)) if a > 0 else 0

    if ab_distance == 0:
        return ap_distance, True

    # Projection ratio (0 = at start, 1 = at end)
    projection_ratio = (ap_distance**2 + ab_distance**2 - bp_distance**2) / (
        2 * ab_distance**2
    )
    is_on_segment = 0 <= projection_ratio <= 1

    if is_on_segment:
        # Perpendicular distance using Heron's formula
        s = (ap_distance + bp_distance + ab_distance) / 2
        area = sqrt(
            max(0, s * (s - ap_distance) * (s - bp_distance) * (s - ab_distance))
        )
        perp_distance = 2 * area / ab_distance if ab_distance > 0 else ap_distance
    else:
        # If not on segment, use distance to nearest endpoint
        perp_distance = min(ap_distance, bp_distance)

    return perp_distance, is_on_segment


def _haversine_distance(
    coord1: Tuple[float, float], coord2: Tuple[float, float]
) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.

    Args:
        coord1: (lat, lng) tuple
        coord2: (lat, lng) tuple

    Returns:
        Distance in kilometers
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers

    return c * r


def _is_within_proximity(
    stop_coord: Tuple[float, float],
    polyline_path: List[Tuple[float, float]],
    threshold_km: float,
) -> bool:
    """
    Check if a stop is within a specified proximity to the polyline path.

    Args:
        stop_coord: (lat, lng) of bus stop
        polyline_path: List of (lat, lng) tuples forming the actual road
        threshold_km: Proximity threshold in kilometers

    Returns:
        True if the stop is within the threshold, False otherwise
    """
    if len(polyline_path) < 2:
        return False

    # Check distance to each segment in the polyline
    for i in range(len(polyline_path) - 1):
        segment_start = polyline_path[i]
        segment_end = polyline_path[i + 1]

        distance, is_on_segment = _distance_point_to_segment(
            stop_coord, segment_start, segment_end
        )
        if distance < threshold_km:
            return True

    return False


@tool
def identify_affected_routes_between_locations(
    disruption_address_1: str, disruption_address_2: str
) -> Dict[str, Any]:
    """
    Identify bus routes and stops affected by a disruption between two locations.

    Stores affected routes and stops in the disruption database and returns
    simplified response (route names and affected stop counts only).

    Args:
        disruption_address_1: Starting location address of the disruption
        disruption_address_2: Ending location address of the disruption

    Returns:
        Dict with success status, affected route names, and stop counts
    """
    try:
        maps = _get_maps_service()
        # Start new disruption context
        store.start_disruption(disruption_address_1, disruption_address_2)

        encoded_polyline = maps.get_polyline(disruption_address_1, disruption_address_2)

        if not encoded_polyline:
            return {
                "success": False,
                "error": "Could not extract polyline from route response",
            }

        # Decode polyline to actual coordinates using library
        polyline_path = maps.decode_polyline(encoded_polyline)

        all_stops = _get_all_bus_stops()
        affected_routes_summary = {}
        proximity_threshold_km = 0.1  # 100 meters

        for route_name, stops in all_stops.items():
            affected_stop_indices = []
            print(
                f"[Identify Tool] Checking route: {route_name} with {len(stops)} stops"
            )
            for idx, stop_coord in enumerate(stops):
                is_affected = _is_within_proximity(
                    stop_coord, polyline_path, proximity_threshold_km
                )
                if is_affected:
                    affected_stop_indices.append((idx, stop_coord))

            affected_stop_indices = sorted(
                set(affected_stop_indices)
            )  # Remove duplicates and sort

            for stop_idx, stop_coord in affected_stop_indices:
                print(f"  Affected stop index: {stop_idx}, coordinates: {stop_coord}")

            if affected_stop_indices:
                store.add_affected_route(route_name)
                for stop_idx, stop_coord in affected_stop_indices:
                    store.add_affected_stop(route_name, stop_idx, stop_coord)

                affected_routes_summary[route_name] = len(affected_stop_indices)

        return {
            "success": True,
            "affected_routes_found": len(affected_routes_summary),
            "affected_routes": affected_routes_summary,  # Dict[route_name] -> stop_count
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def suggest_alternative_route(
    route_name: str,
    disruption_address_1: str,
    disruption_address_2: str,
) -> Dict[str, Any]:
    """
    Suggest an alternative route by finding nearby substitute stops from other routes.

    Fetches affected stop indices from the disruption database, finds the closest
    substitute stops from other routes, and stores substitutions in the database.
    Returns only success status (no detailed coordinates to agent).

    Args:
        route_name: Name of the affected bus route
        disruption_address_1: Starting location address of the disruption
        disruption_address_2: Ending location address of the disruption

    Returns:
        Dict with success status and route name (simplified response)
    """
    try:
        maps = _get_maps_service()
        all_stops = _get_all_bus_stops()

        # Get affected stop indices from database
        affected_stops_indices = store.get_affected_stop_indices(route_name)
        if not affected_stops_indices:
            return {
                "success": False,
                "error": f"No affected stops found for {route_name} in database",
                "route_name": route_name,
            }

        # Get the original route
        original_route_stops = all_stops.get(route_name, [])
        if not original_route_stops:
            return {
                "success": False,
                "error": f"Route {route_name} not found",
                "route_name": route_name,
            }

        # Get disruption polyline to check substitutes against
        encoded_disruption_polyline = maps.get_polyline(
            disruption_address_1, disruption_address_2
        )
        if not encoded_disruption_polyline:
            return {
                "success": False,
                "error": "Could not get disruption polyline",
                "route_name": route_name,
            }

        disruption_polyline = maps.decode_polyline(encoded_disruption_polyline)
        disruption_proximity_threshold_km = 0.1  # 100 meters

        # Convert to sorted set
        affected_set = sorted(set(affected_stops_indices))
        substitutions_made = 0

        # For each affected stop, find closest substitute from other routes
        for affected_idx in affected_set:
            affected_coord = original_route_stops[affected_idx]

            # Find closest stop from other routes that is NOT in the disruption area
            closest_stop = None
            closest_distance = float("inf")
            closest_route = None
            closest_idx = None

            for other_route_name, other_stops in all_stops.items():
                if (
                    route_name.split("(")[0].strip()
                    == other_route_name.split("(")[0].strip()
                ):
                    continue  # Skip the same route (ignoring direction)

                for other_bus_stop_idx, other_bus_stop_coord in enumerate(other_stops):
                    # Check if this substitute stop is in the disruption area
                    is_in_disruption = _is_within_proximity(
                        other_bus_stop_coord,
                        disruption_polyline,
                        disruption_proximity_threshold_km,
                    )

                    # Skip this substitute if it's in the disruption area
                    if is_in_disruption:
                        continue

                    # Calculate distance using Haversine
                    distance = _haversine_distance(affected_coord, other_bus_stop_coord)

                    if distance < closest_distance:
                        closest_distance = distance
                        closest_stop = other_bus_stop_coord
                        closest_route = other_route_name
                        closest_idx = other_bus_stop_idx

            # Store substitution in database
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
        return {
            "success": False,
            "error": str(e),
            "route_name": route_name,
        }
