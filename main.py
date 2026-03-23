import os
from dotenv import load_dotenv
from src.google_maps.maps_service import MapsService


def main():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    # Example usage of Google Maps Client
    maps_client = MapsService(api_key)
    origin = "San Francisco, CA"
    destination = "Los Angeles, CA"

    distance_info = maps_client.get_api_response(origin, destination)
    print("Distance Info:", distance_info)


if __name__ == "__main__":
    main()
