"""
Route-specific tools for the EV bus route planning agent.

These tools integrate with the existing Google Maps service.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from langchain_core.tools import tool
from src.google_maps.maps_service import MapsService
from src.agents.database.database import DisruptionStore

# Configure logging
logging.basicConfig(
    filename="tool_log.txt",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
maps_service = MapsService._get_maps_service()
store = DisruptionStore(maps_service)


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
        # Start new disruption context
        store.start_disruption(disruption_address_1, disruption_address_2)

        encoded_polyline = maps_service.get_polyline(
            disruption_address_1, disruption_address_2
        )

        if not encoded_polyline:
            return {
                "success": False,
                "error": "Could not extract polyline from route response",
            }

        # Decode polyline to actual coordinates using library
        polyline_path = maps_service.decode_polyline(encoded_polyline)

        all_stops = store.stop_data
        affected_routes_summary = {}
        proximity_threshold_km = 0.1  # 100 meters
        logger.debug(
            f"[Identify Tool] Checking proximity of bus stops to disruption polyline {polyline_path} with threshold {proximity_threshold_km} km"
        )
        for route_name, stops in all_stops.items():
            affected_stop_indices = []
            logger.debug(
                f"[Identify Tool] Checking route: {route_name} with {len(stops)} stops"
            )
            for idx, stop_coord in enumerate(stops):
                logger.debug(
                    f"  Checking {route_name} - Stop {idx} at coordinates {stop_coord}"
                )
                is_affected = maps_service._is_within_proximity(
                    stop_coord, polyline_path, proximity_threshold_km
                )
                if is_affected:
                    logger.debug("    --> Affected stop")
                    affected_stop_indices.append((idx, stop_coord))
                else:
                    logger.debug("    --> Not affected")

            affected_stop_indices = sorted(
                set(affected_stop_indices)
            )  # Remove duplicates and sort

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
) -> Dict[str, Any]:
    """
    Suggest an alternative route by finding nearby substitute stops from other routes.

    Fetches affected stop indices from the disruption database, finds the closest
    substitute stops from other routes, and stores substitutions in the database.
    Returns only success status (no detailed coordinates to agent).

    Args:
        route_name: Name of the affected bus route

    Returns:
        Dict with success status, route name, number of substitutions made, and affected stop count
    """
    try:
        all_stops = store.stop_data

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

                    if store.is_stop_affected(other_route_name, other_bus_stop_idx):
                        continue  # Skip stops that are already affected

                    # Calculate distance using Haversine
                    distance = maps_service._haversine_distance(
                        affected_coord, other_bus_stop_coord
                    )

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
