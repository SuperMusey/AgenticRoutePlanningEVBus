from pydantic import BaseModel
from typing import Dict, List, Tuple


class Stop(BaseModel):
    """Represents an affected stop on a route."""

    stop_index: int
    coordinates: Tuple[float, float]


class Substitution(BaseModel):
    """Represents a substitution for an affected stop."""

    original_route: str
    affected_stop: Stop
    substitute_route: str
    substitute_stop: Stop


class AffectedRoute(BaseModel):
    """Represents a route affected by a disruption."""

    route_name: str
    affected_stops: List[Stop] = []
    substitutions: List[Substitution] = []


class Disruption(BaseModel):
    """Represents a traffic disruption."""

    disruption_address_1: str
    disruption_address_2: str
    affected_routes: Dict[str, AffectedRoute] = {}
    blocked_road_polyline: List[Tuple[float, float]] = []
