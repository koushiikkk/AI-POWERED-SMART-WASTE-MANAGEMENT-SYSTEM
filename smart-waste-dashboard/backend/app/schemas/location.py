"""
Pydantic schemas for Location resource.
Used for request validation and response serialization.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class LocationCreate(BaseModel):
    """Schema for creating a new location."""
    name: str = Field(..., min_length=1, max_length=100, description="Location name")
    area: str = Field(..., min_length=1, max_length=100, description="Area/district")
    waste_type: str = Field(..., min_length=1, max_length=50, description="Type of waste")
    capacity: float = Field(..., gt=0, description="Maximum capacity")
    current_level: float = Field(default=0.0, ge=0, description="Current fill level")

    @field_validator("current_level")
    @classmethod
    def level_must_not_exceed_capacity(cls, v, info):
        """current_level must not exceed capacity in normal MVP operation."""
        if "capacity" in info.data and v > info.data["capacity"]:
            raise ValueError("current_level cannot exceed capacity")
        return v


class LocationUpdate(BaseModel):
    """Schema for updating an existing location."""
    name: str = Field(..., min_length=1, max_length=100)
    area: str = Field(..., min_length=1, max_length=100)
    waste_type: str = Field(..., min_length=1, max_length=50)
    capacity: float = Field(..., gt=0)
    current_level: float = Field(..., ge=0)

    @field_validator("current_level")
    @classmethod
    def level_must_not_exceed_capacity(cls, v, info):
        if "capacity" in info.data and v > info.data["capacity"]:
            raise ValueError("current_level cannot exceed capacity")
        return v


class LocationResponse(BaseModel):
    """Schema for location API responses. Status is derived by backend."""
    id: int
    name: str
    area: str
    waste_type: str
    capacity: float
    current_level: float
    status: str
    created_at: Optional[datetime] = None
