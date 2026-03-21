#!/usr/bin/env python3
"""
Tool: compute_candidate_routes

Dijkstra-based graph search → 3 route candidates.
Reads the graph directly from the database — no preprocessing.
"""

import json
import heapq
import uuid
import db


def dijkstra(graph: dict, start: str, end: str, weight_fn) -> tuple[list[str], float]:
    """Return (path, total_cost). Returns ([], inf) if unreachable."""
    heap = [(0.0, start, [start])]
    visited: set = set()
    while heap:
        cost, node, path = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == end:
            return path, cost
        for nb, w in graph.get(node, {}).items():
            if nb not in visited:
                heapq.heappush(heap, (cost + weight_fn(w), nb, path + [nb]))
    return [], float("inf")


def build_route_candidate(graph: dict, path: list[str], optimization: str) -> dict:
    """Compute full stats for a path. Looks up node info from DB."""
    total_time = sum(graph[path[i]][path[i + 1]]["time_min"] for i in range(len(path) - 1))
    total_dist = sum(graph[path[i]][path[i + 1]]["distance_km"] for i in range(len(path) - 1))

    stops_served = []
    has_charging = False
    for nid in path[1:-1]:
        node = db.get_node(nid)
        if node and node["type"] == "bus_stop":
            stops_served.append(nid)
        if node and node["type"] == "charging_station":
            has_charging = True

    steps = []
    for i, nid in enumerate(path):
        node = db.get_node(nid)
        name = node["name"] if node else nid
        ntype = node["type"] if node else "unknown"
        if i == 0:
            steps.append(f"Start: {name} ({ntype})")
        elif i == len(path) - 1:
            steps.append(f"Arrive: {name} ({ntype})")
        else:
            seg = graph[path[i - 1]][nid]
            steps.append(f"  -> {name} ({ntype}) | {seg['distance_km']:.2f} km | {seg['time_min']:.1f} min")

    return {
        "route_id": str(uuid.uuid4())[:8],
        "optimization": optimization,
        "path_node_ids": path,
        "path_names": [db.get_node(n)["name"] if db.get_node(n) else n for n in path],
        "total_time_min": round(total_time, 1),
        "total_distance_km": round(total_dist, 2),
        "stops_served": stops_served,
        "num_stops_served": len(stops_served),
        "includes_charging_station": has_charging,
        "steps": steps,
    }


def compute_candidate_routes(
    start_node_id: str,
    end_node_id: str,
    must_visit: list[str] = [],
) -> str:
    """
    Dijkstra → 3 candidate routes (time, distance, balanced).
    Reads graph and nodes from the database.
    """
    # Validate nodes exist in DB
    for nid in [start_node_id, end_node_id] + must_visit:
        if db.get_node(nid) is None:
            return json.dumps({"error": f"Node '{nid}' not found in database. Valid IDs: {db.get_node_ids()}"})

    # Read graph from DB
    graph = db.get_graph()

    T_NORM, D_NORM = 30.0, 5.0
    weight_configs = [
        ("time_optimal",     lambda w: w["time_min"]),
        ("distance_optimal", lambda w: w["distance_km"]),
        ("balanced",         lambda w: 0.5 * w["time_min"] / T_NORM + 0.5 * w["distance_km"] / D_NORM),
    ]

    candidates = []
    for opt_name, weight_fn in weight_configs:
        waypoints = [start_node_id] + must_visit + [end_node_id]
        full_path: list[str] = []
        feasible = True
        for i in range(len(waypoints) - 1):
            seg_path, cost = dijkstra(graph, waypoints[i], waypoints[i + 1], weight_fn)
            if not seg_path:
                feasible = False
                break
            full_path += seg_path if not full_path else seg_path[1:]
        if not feasible:
            continue
        route = build_route_candidate(graph, full_path, opt_name)
        candidates.append(route)

    if not candidates:
        return json.dumps({"error": "No feasible routes found."})

    start_name = db.get_node(start_node_id)["name"]
    end_name = db.get_node(end_node_id)["name"]

    return json.dumps({
        "start": start_name,
        "end": end_name,
        "must_visit": [db.get_node(n)["name"] for n in must_visit],
        "candidates": candidates,
        "quick_comparison": {
            "fastest_route_id": min(candidates, key=lambda r: r["total_time_min"])["route_id"],
            "shortest_route_id": min(candidates, key=lambda r: r["total_distance_km"])["route_id"],
        },
    }, indent=2)
