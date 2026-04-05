import os
from dotenv import load_dotenv
from src.google_maps.maps_service import MapsService


def main():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    # Example usage of Google Maps Client
    maps_client = MapsService(api_key)
    origin = "1600 Amphitheatre Pkwy, Mountain View, CA"
    destination = "University of Pittsburgh, PA"

    # distance_info = maps_client.get_routes_api_response(origin, destination)
    # print("Distance Info:", distance_info)

    geocode = maps_client.geocode_address(origin)
    print("Geocode Info:", geocode)


if __name__ == "__main__":
    main()
