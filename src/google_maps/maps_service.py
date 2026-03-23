import requests


class MapsService:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_api_response(self, origin, destination):
        """Fetch directions from Google Maps Route API.
        Args:
            origin (str): Starting location (e.g., "New York, NY").
            destination (str): Ending location (e.g., "Boston, MA").
        """
        url = f"https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
        }
        body = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": "TRANSIT",
        }

        response = requests.post(url, headers=headers, json=body)
        return response.json()