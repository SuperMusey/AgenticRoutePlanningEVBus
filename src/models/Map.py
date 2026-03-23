from pydantic import BaseModel, Field
from typing import Literal


class Location(BaseModel):
    """Represents a location in the system."""

    id: str
    lat: float = Field(..., description="Latitude of the location")
    lng: float = Field(..., description="Longitude of the location")
