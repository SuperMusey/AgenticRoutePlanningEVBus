"""
Pydantic models for Bus and Bus Stop.
"""

from pydantic import BaseModel, Field
from typing import Literal


class Bus(BaseModel):
    """Represents a bus in the system."""

    id: str
    current_location: str = Field(
        ..., description="Current location of the bus"
    )  # for now
    charge_capacity: int = Field(
        default=100, description="Maximum charge capacity of the bus"
    )
    current_charge: int = Field(
        default=0, description="Current charge level of the bus"
    )
    capacity: int = Field(
        default=50, description="Maximum passenger capacity of the bus"
    )
    current_passengers: int = Field(
        default=0, description="Current number of passengers on the bus"
    )


class BusStop(BaseModel):
    """Represents a bus stop in the system."""

    id: str
    location: str = Field(..., description="Location of the bus stop")  # for now
    stop_type: Literal["charge", "pick_drop"] = Field(
        default="pick_drop", description="Type of bus stop: 'charge' or 'pick_drop'"
    )
