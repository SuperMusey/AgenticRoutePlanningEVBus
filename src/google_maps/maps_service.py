from typing import Optional

import requests
from requests.compat import quote


class MapsService:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_routes_api_response(
        self, origin: str, destination: str, waypoints: Optional[list[str]] = None
    ):
        """Fetch directions from Google Maps Route API.
        Args:
            origin (str): Starting location (e.g., "New York, NY").
            destination (str): Ending location (e.g., "Boston, MA").
            waypoints (list): List of intermediate locations.
        """
        url = f"https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.routeLabels,routes.duration,routes.legs,routes.distanceMeters,routes.polyline.encodedPolyline",
        }
        body = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "intermediates": [{"address": wp} for wp in waypoints] if waypoints else [],
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

    def is_within_distance(
        self, origin: str, destination: str, threshold_meters: int
    ) -> bool:
        """Check if the distance between origin and destination is within a specified threshold."""
        response = self.get_routes_api_response(origin, destination)
        if "routes" in response and len(response["routes"]) > 0:
            distance = response["routes"][0].get("distanceMeters", float("inf"))
            return distance <= threshold_meters
        return False

    def get_polyline(
        self, origin: str, destination: str, waypoints: Optional[list[str]] = None
    ) -> Optional[str]:
        """Get the encoded polyline for the route between origin and destination."""
        response = self.get_routes_api_response(origin, destination, waypoints)
        if "routes" in response and len(response["routes"]) > 0:
            return response["routes"][0].get("polyline", {}).get("encodedPolyline")
        return None

    def geocode_address(self, address: str) -> Optional[dict]:
        """Geocode an address to get its latitude and longitude."""
        response = self.get_geocode_api_response(address)
        if "results" in response and len(response["results"]) > 0:
            location = response["results"][0]["location"]
            return {"lat": location["latitude"], "lng": location["longitude"]}
        return None
