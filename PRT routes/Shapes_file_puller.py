import matplotlib.pyplot as plt
import pandas as pd
import folium
import json
import os


def process_route(shape_id: str, route_label: str, json_filename: str = "route_pairs.json") -> dict:
    """
    Process a transit route shape and generate map outputs.

    Args:
        shape_id: The shape ID to process (e.g., "shp-61C-02")
        route_label: Human-readable label for the route (e.g., "Route 61C (Inbound)")
        json_filename: Path to the JSON file for storing route coordinates

    Returns:
        The updated JSON data dictionary
    """
    # Load the data
    df = pd.read_csv('GTFS/shapes.txt')

    # Filter for the specific shape_id and sort
    shape_data = df[df['shape_id'] == shape_id].sort_values('shape_pt_sequence')

    if shape_data.empty:
        raise ValueError(f"No data found for shape_id: {shape_id}")

    # Extract coordinates
    lats = shape_data['shape_pt_lat']
    lons = shape_data['shape_pt_lon']

    # --- Matplotlib plot ---
    plt.figure(figsize=(10, 8))
    plt.plot(lons, lats, marker='o', markersize=2, linestyle='-', color='blue', label=route_label)
    plt.title(f'Map Plot for shape_id {shape_id} ({route_label})')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.grid(True)
    plt.legend()
    #plt.show()

    # --- Folium map ---
    avg_lat = lats.mean()
    avg_lon = lons.mean()
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11)

    locations = list(zip(lats, lons))

    folium.PolyLine(locations, color='blue', weight=2.5, opacity=1).add_to(m)
    folium.Marker(locations[0], popup='Start', icon=folium.Icon(color='green')).add_to(m)
    folium.Marker(locations[-1], popup='End', icon=folium.Icon(color='red')).add_to(m)

    html_filename = f"{route_label} output.html"
    m.save(html_filename)
    print(f"Folium map saved to: {html_filename}")

    # --- Update JSON ---
    if os.path.exists(json_filename) and os.path.getsize(json_filename) > 0:
        with open(json_filename, 'r') as f:
            file_data = json.load(f)
    else:
        file_data = {"routes": []}

    file_data["routes"].append({route_label: locations})

    with open(json_filename, 'w') as f:
        json.dump(file_data, f, indent=4)

    print(f"Route '{route_label}' appended to: {json_filename}")
    return file_data


updated_json = process_route("shp-71B-52", "Route 71B (Outbound)")
