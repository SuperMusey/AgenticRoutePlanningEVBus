#!/usr/bin/env python3
"""
Tool: inject_charging_station

Pure routing function:
  Leg 1: current position → charging station
  Leg 2: charging station → original destination

No database query, no graph write. Just two calls to compute_candidate_routes.

The server can call this multiple times with different stations
and compare the results to pick the best one.
"""

import json
from compute_candidate_routes import compute_candidate_routes


def inject_charging_station(
    current_node_id: str,
    destination_node_id: str,
    station_id: str,
) -> str:
    """
    Split the journey into two legs through the charging station.

    Parameters:
      current_node_id     — where the bus is now
      destination_node_id — where it originally wants to go
      station_id          — the charging station to route through

    Returns two legs, each with 3 Dijkstra candidates.
    """
    leg_1 = json.loads(compute_candidate_routes(current_node_id, station_id))
    leg_2 = json.loads(compute_candidate_routes(station_id, destination_node_id))

    return json.dumps({
        "legs": [
            {"leg": 1, "from": current_node_id, "to": station_id, "routes": leg_1},
            {"leg": 2, "from": station_id, "to": destination_node_id, "routes": leg_2},
        ]
    }, indent=2)
