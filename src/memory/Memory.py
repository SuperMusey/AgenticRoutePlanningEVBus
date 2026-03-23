"""
Simplified Memory Management with LangGraph
Covers:
  - Working memory: LangGraph StateGraph (BusSystemState)
  - Maps API cache: TTL-based dict
  - LLM message history: LangChain Message types in state
"""

import hashlib
import json
import time
from datetime import datetime
from typing import Annotated, Optional
from typing import TypedDict

import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from src.models.Bus import Bus, BusStop
from src.models.Map import Location


# ─────────────────────────────────────────────────────────────────────────────
# 1. STATE SCHEMA  (managed by LangGraph)
# ─────────────────────────────────────────────────────────────────────────────


class RouteConstraints(TypedDict):
    min_charge_pct: float
    max_detour_km: float
    priority_stops: list[str]


class BusSystemState(TypedDict):
    bus_id: str
    current_location: Location
    charge_pct: float
    bus_stops: list[BusStop]
    constraints: RouteConstraints
    route_plan: Optional[dict]

    # LLM conversation history
    messages: Annotated[list[BaseMessage], operator.add]

    last_updated: str


# ─────────────────────────────────────────────────────────────────────────────
# 2. MAPS API CACHE
# ─────────────────────────────────────────────────────────────────────────────


class MapsCache:
    """Simple TTL cache for Maps API calls."""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, dict] = {}
        self.ttl = ttl_seconds

    def _key(self, origin: Location, destination: Location, query_type: str) -> str:
        raw = f"{origin['lat']},{origin['lng']}|{destination['lat']},{destination['lng']}|{query_type}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(
        self, origin: Location, destination: Location, query_type: str = "distance"
    ) -> Optional[dict]:
        key = self._key(origin, destination, query_type)
        entry = self._store.get(key)
        if entry and (time.time() - entry["ts"]) < self.ttl:
            return entry["data"]
        return None

    def set(
        self,
        origin: Location,
        destination: Location,
        data: dict,
        query_type: str = "distance",
    ) -> None:
        key = self._key(origin, destination, query_type)
        self._store[key] = {"data": data, "ts": time.time()}


# ─────────────────────────────────────────────────────────────────────────────
# 3. MEMORY MANAGER  (manages graph + maps cache)
# ─────────────────────────────────────────────────────────────────────────────


class MemoryManager:
    """
    Wraps LangGraph StateGraph + Maps Cache.

    Usage:
        memory = MemoryManager()
        graph = memory.build_graph()

        # Use the graph to invoke LLM nodes with persistent state
        result = graph.invoke(initial_state)

        # Access maps cache
        cached = memory.maps.get(origin, destination)
    """

    def __init__(self):
        self.maps = MapsCache(ttl_seconds=300)
        self.graph = None

    def build_context_for_llm(self, state: BusSystemState) -> str:
        """Assemble current state into a context string for the LLM prompt."""
        charge_stops = [s for s in state["bus_stops"] if s.get("has_charging")]

        return f"""
=== Current Bus State ===
Bus ID       : {state["bus_id"]}
Location     : lat={state["current_location"]["lat"]:.4f}, lng={state["current_location"]["lng"]:.4f}
Charge       : {state["charge_pct"]:.1f}%

=== Route Constraints ===
Min charge   : {state["constraints"]["min_charge_pct"]}%
Max detour   : {state["constraints"]["max_detour_km"]} km
Priority     : {state["constraints"]["priority_stops"]}

=== Available Stops ===
{json.dumps([{"id": s["stop_id"], "name": s["name"], "charging": s["has_charging"]} for s in state["bus_stops"]], indent=2)}

=== Charging Stops ===
{json.dumps([{"id": s["stop_id"], "kw": s["charger_kw"]} for s in charge_stops], indent=2)}
"""

    def build_graph(self) -> StateGraph:
        """Build LangGraph with state management."""
        builder = StateGraph(BusSystemState)

        # Your agent nodes will receive `state` and `memory` (this instance)
        # They can call memory.maps.get/set and memory.build_context_for_llm()
        # And return state updates including new messages via:
        #   return {"messages": [AIMessage(content="...")]}

        # Example node (you'll fill in your actual logic):
        def route_planning_node(state: BusSystemState) -> dict:
            # Access context
            context = self.build_context_for_llm(state)
            # Your LLM call here; when done:
            return {
                "messages": [AIMessage(content="Route plan: ...")],
                "route_plan": {...},
            }

        # Add your nodes
        # builder.add_node("route_planning", route_planning_node)
        # builder.set_entry_point("route_planning")
        # builder.add_edge("route_planning", END)

        self.graph = builder.compile()
        return self.graph

    def get_messages(self, state: BusSystemState) -> list[BaseMessage]:
        """Get full conversation history from state."""
        return state.get("messages", [])
