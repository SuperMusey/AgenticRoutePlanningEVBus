import os
import polyline
import requests
from requests.compat import quote
from typing import Any, Optional, Union, List, Tuple
from math import radians, cos, sin, asin, sqrt
from dotenv import load_dotenv


class MapsService:
    def __init__(self, api_key):
        self.api_key = api_key

    @classmethod
    def _get_maps_service(cls):
        """Initialize and return MapsService with API key from config."""
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")
        return MapsService(api_key)

    def _haversine_distance(
        self, coord1: Tuple[float, float], coord2: Tuple[float, float]
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.

        Args:
            coord1: (lat, lng) tuple
            coord2: (lat, lng) tuple

        Returns:
            Distance in kilometers (or miles if R is changed to 3958.8)
        """
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        R = 6371

        rlat1 = radians(lat1)
        rlat2 = radians(lat2)
        difflat = rlat2 - rlat1
        difflon = radians(lon2 - lon1)

        a = sin(difflat / 2) * sin(difflat / 2) + cos(rlat1) * cos(rlat2) * sin(
            difflon / 2
        ) * sin(difflon / 2)
        d = 2 * R * asin(sqrt(a))

        return d

    def _distance_point_to_segment(
        self,
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
        # Calculate distances using haversine formula
        ab_distance = self._haversine_distance(segment_start, segment_end)
        ap_distance = self._haversine_distance(segment_start, point)
        bp_distance = self._haversine_distance(segment_end, point)

        if ab_distance == 0:
            return round(ap_distance, 4), True

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

        return round(perp_distance, 4), is_on_segment

    def _is_within_proximity(
        self,
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

            distance, is_on_segment = self._distance_point_to_segment(
                stop_coord, segment_start, segment_end
            )
            if distance <= threshold_km:
                return True

        return False

    def get_routes_api_response(
        self,
        origin: Union[str, Tuple[float, float]],
        destination: Union[str, Tuple[float, float]],
        waypoints: Optional[Union[list[str], List[Tuple[float, float]]]] = None,
    ) -> Any:
        """Fetch directions from Google Maps Route API.
        Args:
            origin (Union[str, Tuple[float, float]]): Starting location (e.g., "New York, NY" or (40.7128, -74.0060)).
            destination (Union[str, Tuple[float, float]]): Ending location (e.g., "Boston, MA" or (42.3601, -71.0589)).
            waypoints (list): List of intermediate locations.
        """
        url = f"https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.routeLabels,routes.duration,routes.legs,routes.distanceMeters,routes.polyline.encodedPolyline",
        }
        body = {}
        if isinstance(origin, tuple) or isinstance(destination, tuple):
            body = {
                "origin": {
                    "location": {
                        "latLng": {"latitude": origin[0], "longitude": origin[1]}
                    }
                },
                "destination": {
                    "location": {
                        "latLng": {
                            "latitude": destination[0],
                            "longitude": destination[1],
                        }
                    }
                },
                "intermediates": [
                    {"location": {"latLng": {"latitude": wp[0], "longitude": wp[1]}}}
                    for wp in waypoints
                ]
                if waypoints
                else [],
                "routingPreference": "TRAFFIC_AWARE",
                "travelMode": "DRIVE",
                "computeAlternativeRoutes": True,
            }
        elif isinstance(origin, str) and isinstance(destination, str):
            body = {
                "origin": {"address": origin},
                "destination": {"address": destination},
                "intermediates": [{"address": wp} for wp in waypoints]
                if waypoints
                else [],
                "routingPreference": "TRAFFIC_AWARE",
                "travelMode": "DRIVE",
                "computeAlternativeRoutes": True,
            }
        response = requests.post(url, headers=headers, json=body)
        return response.json()

    def get_geocode_api_response(self, address: str):
        """Fetch geocoding information from Google Maps Geocoding API.
        Args:
            address (str): The address to geocode (e.g., "1600 Amphitheatre Parkway, Mountain View, CA").
        """
        encoded_address = quote(address, safe="")
        url = f"https://geocode.googleapis.com/v4/geocode/address/{encoded_address}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
        }
        response = requests.get(url, headers=headers)
        return response.json()

    def get_polyline(
        self,
        origin: Union[str, Tuple[float, float]],
        destination: Union[str, Tuple[float, float]],
        waypoints: Optional[Union[list[str], List[Tuple[float, float]]]] = None,
    ) -> Optional[str]:
        """Get the encoded polyline for the route between origin and destination.

        If waypoints exceed 25 (Google Maps API limit), splits the route into
        multiple segments and combines the polylines.

        Args:
            origin: Either an address string or a (lat, lng) tuple
            destination: Either an address string or a (lat, lng) tuple
            waypoints: Either a list of address strings or a list of (lat, lng) tuples

        Returns:
            Encoded polyline string or None
        """
        # If waypoints exceed API limit of 25, split into multiple segments
        if waypoints and len(waypoints) > 25:
            return self._get_polyline_with_segments(origin, destination, waypoints)

        response = self.get_routes_api_response(origin, destination, waypoints)
        if "routes" in response and len(response["routes"]) > 0:
            return response["routes"][0].get("polyline", {}).get("encodedPolyline")
        return None

    def _get_polyline_with_segments(
        self,
        origin: Union[str, Tuple[float, float]],
        destination: Union[str, Tuple[float, float]],
        waypoints: Union[list[str], List[Tuple[float, float]]],
    ) -> Optional[str]:
        """
        Get polyline by splitting long waypoint lists into segments.

        Args:
            origin: Starting location
            destination: Ending location
            waypoints: List of waypoints (may exceed 25)

        Returns:
            Combined encoded polyline string or None
        """
        max_waypoints = 25
        combined_coords = []

        # Decode origin if it's a tuple
        if isinstance(origin, tuple):
            combined_coords.append(origin)

        # Process waypoints in chunks
        for i in range(0, len(waypoints), max_waypoints):
            chunk = waypoints[i : i + max_waypoints]

            # Determine the segment origin and destination
            if i == 0:
                segment_origin = origin
            else:
                # Use last waypoint as origin for next segment
                segment_origin = waypoints[i - 1]

            # Use next chunk's last point or final destination
            if i + max_waypoints >= len(waypoints):
                segment_destination = destination
            else:
                segment_destination = waypoints[i + max_waypoints - 1]

            # Get polyline for this segment
            response = self.get_routes_api_response(
                segment_origin, segment_destination, chunk
            )

            if "routes" not in response or len(response["routes"]) == 0:
                return None

            polyline_str = (
                response["routes"][0].get("polyline", {}).get("encodedPolyline")
            )
            if polyline_str:
                # Decode and add coordinates (skip first point to avoid duplicates)
                coords = self.decode_polyline(polyline_str)
                if combined_coords:
                    coords = coords[1:]  # Skip first point (duplicate)
                combined_coords.extend(coords)

        # Re-encode the combined coordinates
        if combined_coords:
            return polyline.encode(combined_coords)
        return None

    def decode_polyline(self, encoded_polyline: str) -> list[tuple[float, float]]:
        """Decode an encoded polyline string to a list of (lat, lng) tuples.
        Args:
            encoded_polyline (str): Encoded polyline string from Google Maps API.
        Returns:
            List of (lat, lng) tuples representing coordinates along the route.
        """
        return polyline.decode(encoded_polyline)
