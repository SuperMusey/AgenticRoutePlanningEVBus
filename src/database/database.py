"""
In-memory disruption data store for the route planning session.

Stores disruption info, affected routes/stops, and alternative route substitutions
during a session. Data is cleared after each disruption is processed.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.database.database_models import AffectedRoute, Disruption, Substitution, Stop
from src.google_maps.maps_service import MapsService

# route_pairs.json lives at src/PRT routes/route_pairs.json
STOPS_PATH = Path(__file__).parent.parent / "PRT routes" / "route_pairs.json"


class DisruptionStore:
    """
    Maintains the current disruption context and all related information
    (affected stops, substitutions) without exposing raw coordinates to the agent.
    The agent only needs route names and substitution counts.
    """

    def __init__(self, maps_service: MapsService):
        self.current_disruption: Optional[Disruption] = None
        self.maps_service = maps_service
        self.stop_data = self._get_all_bus_stops()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

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
        Extract all bus stops from all routes, deduplicating stops that are
        within 100 m of the previous kept stop and capping each route at 50 stops.

        Returns:
            Dict mapping route name → list of (lat, lng) tuples.
        """
        route_pairs = self._load_route_pairs()
        all_stops: Dict[str, List[Tuple[float, float]]] = {}
        proximity_threshold_km = 0.1

        for route_dict in route_pairs.get("routes", []):
            for route_name, coordinates in route_dict.items():
                filtered_stops: List[Tuple[float, float]] = []
                for coord in coordinates:
                    if not filtered_stops:
                        filtered_stops.append(coord)
                    elif (
                        self.maps_service._haversine_distance(
                            filtered_stops[-1], coord
                        )
                        >= proximity_threshold_km
                    ):
                        filtered_stops.append(coord)

                all_stops[route_name] = [(s[0], s[1]) for s in filtered_stops]

        return all_stops

    # ------------------------------------------------------------------
    # Disruption lifecycle
    # ------------------------------------------------------------------

    def start_disruption(self, address_1: str, address_2: str) -> None:
        """Begin tracking a new disruption between two addresses."""
        self.current_disruption = Disruption(
            disruption_address_1=address_1,
            disruption_address_2=address_2,
        )

    def clear(self) -> None:
        """Clear the current disruption and all associated data."""
        self.current_disruption = None

    # ------------------------------------------------------------------
    # Affected route / stop tracking
    # ------------------------------------------------------------------

    def add_affected_route(self, route_name: str) -> None:
        if not self.current_disruption:
            raise ValueError("No active disruption. Call start_disruption first.")
        if route_name not in self.current_disruption.affected_routes:
            self.current_disruption.affected_routes[route_name] = AffectedRoute(
                route_name=route_name
            )

    def add_affected_stop(
        self, route_name: str, stop_index: int, coordinates: Tuple[float, float]
    ) -> None:
        if not self.current_disruption:
            raise ValueError("No active disruption. Call start_disruption first.")
        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            self.add_affected_route(route_name)
            route = self.current_disruption.affected_routes[route_name]
        route.affected_stops.append(Stop(stop_index=stop_index, coordinates=coordinates))

    def get_affected_stop_indices(self, route_name: str) -> List[int]:
        if not self.current_disruption:
            return []
        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            return []
        return [stop.stop_index for stop in route.affected_stops]

    def is_stop_affected(self, route_name: str, stop_index: int) -> bool:
        if not self.current_disruption:
            return False
        route = self.current_disruption.affected_routes.get(route_name)
        if not route:
            return False
        return any(stop.stop_index == stop_index for stop in route.affected_stops)

    def get_affected_routes(self) -> List[str]:
        if not self.current_disruption:
            return []
        return list(self.current_disruption.affected_routes.keys())

    def set_blocked_road_polyline(self, polyline: List[Tuple[float, float]]) -> None:
        if not self.current_disruption:
            raise ValueError("No active disruption. Call start_disruption first.")
        self.current_disruption.blocked_road_polyline = polyline

    def get_blocked_road_polyline(self) -> List[Tuple[float, float]]:
        if not self.current_disruption:
            return []
        return self.current_disruption.blocked_road_polyline

    # ------------------------------------------------------------------
    # Substitution tracking
    # ------------------------------------------------------------------

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
            substitute_route=substitute_route,
            substitute_stop=Stop(
                stop_index=substitute_stop_index, coordinates=substitute_coordinates
            ),
        )
        # Replace any existing substitution for this stop
        route.substitutions = [
            s
            for s in route.substitutions
            if s.affected_stop.stop_index != affected_stop_index
        ]
        route.substitutions.append(substitution)

    def get_all_route_substitutions(self) -> Dict[str, List[Substitution]]:
        if not self.current_disruption:
            return {}
        return {
            name: route.substitutions
            for name, route in self.current_disruption.affected_routes.items()
        }

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_disruption_summary(self) -> Dict[str, Any]:
        """Return a summary suitable for agent consumption (no raw coordinates)."""
        if not self.current_disruption:
            return {"affected_routes": {}}
        return {
            "affected_routes": {
                route_name: {
                    "affected_stop_count": len(route.affected_stops),
                    "substitutions_made": len(route.substitutions),
                }
                for route_name, route in self.current_disruption.affected_routes.items()
            }
        }
