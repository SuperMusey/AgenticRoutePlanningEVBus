"""
In-memory disruption data store for the route planning agent.

Stores disruption info, affected routes/stops, and alternative route substitutions
during a session. Data is cleared after the session ends.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from math import radians, cos, sin, asin, sqrt
from src.agents.database.database_models import (
    AffectedRoute,
    Disruption,
    Substitution,
    Stop,
)
from src.google_maps.maps_service import MapsService

STOPS_PATH = Path(__file__).parent.parent.parent / "PRT routes" / "route_pairs.json"


class DisruptionStore:
    """
    This class maintains the current disruption context and all related
    information (affected stops, substitutions) without exposing details
    to the agent. The agent only needs to know route names and that
    substitutions have been made.
    """

    def __init__(self, maps_service: MapsService):
        self.current_disruption: Optional[Disruption] = None
        self.maps_service = maps_service
        self.stop_data = self._get_all_bus_stops()

    def _load_route_pairs(self) -> Dict[str, Any]:
        """Load route pairs from JSON file."""
        try:
            with open(STOPS_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading route_pairs.json: {e}")
            return {"routes": []}

    def _get_all_bus_stops(self) -> Dict[str, List[Tuple[float, float]]]:
        """
        Extract all bus stops from all routes, filtering to keep stops that are
        far enough apart (>0.1 km) and limiting to 50 stops per route.

        Returns:
            Dict mapping route name to list of (lat, lng) coordinates
        """
        route_pairs = self._load_route_pairs()
        all_stops = {}
        proximity_threshold_km = 0.1  # 100 meters

        for route_dict in route_pairs.get("routes", []):
            for route_name, coordinates in route_dict.items():
                filtered_stops = []
                for coord in coordinates:
                    # Keep first stop
                    if not filtered_stops:
                        filtered_stops.append(coord)
                    # Keep stop if far enough from last kept stop
                    elif (
                        self.maps_service._haversine_distance(filtered_stops[-1], coord)
                        >= proximity_threshold_km
                    ):
                        filtered_stops.append(coord)

                all_stops[route_name] = [(s[0], s[1]) for s in filtered_stops]
        return all_stops

    def start_disruption(self, address_1: str, address_2: str) -> None:
        """
        Start tracking a new disruption.

        Args:
            address_1: Starting address of disruption
            address_2: Ending address of disruption
        """
        self.current_disruption = Disruption(
            disruption_address_1=address_1,
            disruption_address_2=address_2,
        )

    def add_affected_route(self, route_name: str) -> None:
        """
        Add an affected route to the current disruption.

        Args:
            route_name: Name of the affected route
        """
        if not self.current_disruption:
            raise ValueError("No active disruption. Call start_disruption first.")

        if route_name not in self.current_disruption.affected_routes:
            self.current_disruption.affected_routes[route_name] = AffectedRoute(
                route_name=route_name
            )

    def add_affected_stop(
        self, route_name: str, stop_index: int, coordinates: Tuple[float, float]
    ) -> None:
        """
        Add an affected stop to a route.

        Args:
            route_name: Name of the route
            stop_index: Index of the affected stop
            coordinates: (lat, lng) of the stop
        """
        if not self.current_disruption:
            raise ValueError("No active disruption. Call start_disruption first.")

        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            self.add_affected_route(route_name)
            route = self.current_disruption.affected_routes[route_name]

        # Avoid duplicates
        route.affected_stops.append(
            Stop(stop_index=stop_index, coordinates=coordinates)
        )

    def get_affected_stop_indices(self, route_name: str) -> List[int]:
        """
        Get list of affected stop indices for a route.

        Args:
            route_name: Name of the route

        Returns:
            List of affected stop indices
        """
        if not self.current_disruption:
            return []

        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            return []

        return [stop.stop_index for stop in route.affected_stops]

    def add_substitution(
        self,
        route_name: str,
        affected_stop_index: int,
        original_coordinates: Tuple[float, float],
        substitute_coordinates: Tuple[float, float],
        substitute_route: str,
        substitute_stop_index: int,
        distance_km: float,
    ) -> None:
        """
        Record a substitution for an affected stop.

        Args:
            route_name: Name of the affected route
            affected_stop_index: Index of the affected stop
            original_coordinates: Original stop coordinates
            substitute_coordinates: Substitute stop coordinates
            substitute_route: Route of the substitute stop
            substitute_stop_index: Index of substitute stop in its route
            distance_km: Distance between original and substitute
        """
        if not self.current_disruption:
            raise ValueError("No active disruption. Call start_disruption first.")

        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            self.add_affected_route(route_name)
            route = self.current_disruption.affected_routes[route_name]

        substitution = Substitution(
            original_route=route_name,
            affected_stop=Stop(
                stop_index=affected_stop_index, coordinates=original_coordinates
            ),
            substitute_stop=Stop(
                stop_index=substitute_stop_index, coordinates=substitute_coordinates
            ),
            substitute_route=substitute_route,
        )

        # Replace if substitution for this stop already exists
        route.substitutions = [
            s
            for s in route.substitutions
            if s.affected_stop.stop_index != affected_stop_index
        ]
        route.substitutions.append(substitution)

    def get_all_route_substitutions(self) -> Dict[str, List[Substitution]]:
        """
        Get all substitutions for all routes.

        Returns:
            Dict mapping route name -> List of Substitutions
        """
        if not self.current_disruption:
            return {}
        all_substitutions = {}
        affected_routes = self.current_disruption.affected_routes
        for affected_route in affected_routes.values():
            all_substitutions[affected_route.route_name] = affected_route.substitutions
        return all_substitutions

    def get_affected_routes(self) -> List[str]:
        """
        Get list of all affected routes in current disruption.

        Returns:
            List of route names
        """
        if not self.current_disruption:
            return []

        return list(self.current_disruption.affected_routes.keys())

    def is_stop_affected(self, route_name: str, stop_index: int) -> bool:
        """
        Check if a specific stop is affected by the disruption.

        Args:
            route_name: Name of the route
            stop_index: Index of the stop
        Returns:
            True if the stop is affected, False otherwise
        """
        if not self.current_disruption:
            return False

        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            return False

        return any(stop.stop_index == stop_index for stop in route.affected_stops)

    def clear(self) -> None:
        """Clear the current disruption and all data."""
        self.current_disruption = None

    def get_disruption_summary(self) -> Dict:
        """
        Get a summary of the current disruption for agent consumption.

        Returns:
            Dict with affected routes and stop counts only (no coordinates)
        """
        if not self.current_disruption:
            return {"affected_routes": {}}

        summary = {}
        for route_name, route in self.current_disruption.affected_routes.items():
            summary[route_name] = {
                "affected_stop_count": len(route.affected_stops),
                "substitutions_made": len(route.substitutions),
            }

        return {"affected_routes": summary}
