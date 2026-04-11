"""
Example usage of the LangChain route planning agent.

Run this to test the agent setup.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.route_agent import RoutePlanningAgent


def example_1_basic_route_planning():
    """Example: Plan a basic route."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Route Planning")
    print("=" * 60)

    agent = RoutePlanningAgent()

    response = agent.plan_route(
        start_location="New York, NY",
        end_location="Boston, MA",
        vehicle_battery_capacity=300.0,
        additional_context="Peak hours expected, prefer highways",
    )

    print(f"\nQuery: {response['query']}")
    print(f"\nResult:\n{response['result']}")
    print("\n")


def example_2_custom_query():
    """Example: Ask a custom question."""
    print("=" * 60)
    print("EXAMPLE 2: Custom Query")
    print("=" * 60)

    agent = RoutePlanningAgent()

    response = agent.run(
        "What charging stations are available on I-95 between DC and NYC?"
    )

    print(f"\nQuery: {response['query']}")
    print(f"\nResult:\n{response['result']}")
    print("\n")


def example_3_complex_constraints():
    """Example: Route with complex constraints."""
    print("=" * 60)
    print("EXAMPLE 3: Route with Complex Constraints")
    print("=" * 60)

    agent = RoutePlanningAgent()

    response = agent.plan_route(
        start_location="Philadelphia, PA",
        end_location="Washington, DC",
        vehicle_battery_capacity=250.0,
        additional_context=(
            "Must avoid toll roads, "
            "prefer urban routes with frequent charging stops, "
            "high passenger capacity requirement"
        ),
    )

    print(f"\nQuery: {response['query']}")
    print(f"\nResult:\n{response['result']}")
    print("\n")


if __name__ == "__main__":
    print("\n")
    print("🚌 LangChain EV Bus Route Planning Agent - Examples")
    print("-" * 60)
    print("\nNote: These examples use placeholder tool implementations.")
    print("Connect them to your actual services once ready.\n")

    try:
        # Uncomment to run examples
        # example_1_basic_route_planning()
        # example_2_custom_query()
        # example_3_complex_constraints()

        print("Examples defined but commented out to avoid API calls.")
        print("\nTo test the agent:")
        print("1. Set your OPENAI_API_KEY in .env")
        print("2. Uncomment function calls below")
        print("3. Run: python example_agent_usage.py")

    except Exception as e:
        print(f"Error running examples: {e}")
        print("Make sure you have LangChain dependencies installed:")
        print("  pip install langchain langchain-openai langchain-core")
