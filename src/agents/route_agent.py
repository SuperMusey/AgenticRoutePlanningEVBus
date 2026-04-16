"""
LangChain-based Route Planning Agent using ReAct pattern.
"""

import os
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from src.agents.tools.route_tools import (
    identify_affected_routes_between_locations,
    suggest_alternative_route,
    store,
)
from src.agents.prompts.route_planning_system_prompt import ROUTE_PLANNING_SYSTEM_PROMPT
from dotenv import load_dotenv


class RoutePlanningAgent:
    """
    A LangChain agent specialized for route planning.
    """

    def __init__(self):
        """
        Initialize the route planning agent.
        """
        load_dotenv()

        # Initialize the LLM
        self.llm = self._initialize_llm()

        # Define tools
        self.tools = self._define_tools()

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Create the agent
        self.agent = self._create_agent(self.system_prompt)

    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize the Gemini LLM"""
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    def _load_system_prompt(self) -> str:
        """Load the system prompt for the route planning agent."""
        return ROUTE_PLANNING_SYSTEM_PROMPT

    def _define_tools(self) -> List:
        """
        Define all tools available to the agent.

        Returns:
            List of LangChain tool objects
        """
        tools = [
            identify_affected_routes_between_locations,
            suggest_alternative_route,
        ]

        return tools

    def _create_agent(self, system_prompt: str) -> Any:
        """Create the ReAct agent."""

        # Create the agent
        agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
        ).with_retry(stop_after_attempt=10)

        return agent

    def disruption_prompt(self, disruption_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a traffic disruption by passing disruption data to the agent.
        """
        # Format disruption info as a query for the agent
        query = HumanMessage(
            content=f"""A traffic disruption has occurred. Please analyze:
{disruption_data}
Please identify which bus routes are affected and suggest alternative routes for them."""
        )

        # for chunk in self.agent.stream(
        #     {"messages": [query]},
        #     stream_mode="updates",
        #     version="v2",
        # ):
        #     if chunk["type"] == "updates":
        #         for step, data in chunk["data"].items():
        #             print(f"step: {step}")
        #             print(f"content: {data['messages'][-1].content_blocks}")
        #     if chunk["type"] == "messages":
        #         token, metadata = chunk["data"]
        #         print(f"node: {metadata['langgraph_node']}")
        #         print(f"content: {token.content_blocks}")
        #         print("\n")

        # Run the agent with the disruption query
        result = self.agent.invoke({"messages": [query]})

        return {
            "success": True,
            "disruption_data": disruption_data,
            "agent_analysis": result,
        }


def main():
    """Example usage."""
    # Initialize agent
    agent = RoutePlanningAgent()

    # Example 1: Plan a route
    print("=" * 70)

    disruption_data = {
        "event_type": "road closure",
        "roads_affected": ["Forbes Avenue"],
        "intersections": ["Murray Avenue", "Shady Avenue"],
        "area_description": "Forbes Avenue between Murray Avenue and Shady Avenue in Pittsburgh",
        "severity": "high",
        "duration_hours_estimate": 48,
        "additional_info": "Port Authority bus routes 61C and 61D will be affected",
    }

    disruption_response = agent.disruption_prompt(disruption_data)
    print("Agent response to disruption:")
    print(disruption_response)

    print("=" * 70)
    print(f"Store at end of session: {store.get_disruption_summary()}")
    print("=" * 70)
    print("Substitutions list:")
    for route_name, substitutions in store.get_all_route_substitutions().items():
        print(f"  {route_name}:")
        for s in substitutions:
            print(f"    {s.model_dump_json()}")
    print("=" * 70)
    print("Substituted routes:")
    new_routes = store.create_substituted_routes(store.get_all_route_substitutions())
    print("New routes after substitutions:")
    print(new_routes.keys())
    for route_name, route in new_routes.items():
        print(
            f"  {route_name} polyline: {store.get_polyline_for_route(route_name, route)}"
        )


if __name__ == "__main__":
    main()
