"""
Pydantic schemas for Collection resource.
Used for request validation and response serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CollectionCreate(BaseModel):
    """Schema for creating a new collection request."""
    location_id: Optional[int] = Field(default=None, gt=0, description="ID of the location to collect from")
    report_id: Optional[int] = Field(default=None, gt=0, description="ID of the associated report")
    assigned_to: Optional[str] = Field(default=None, max_length=100, description="Person assigned")


class CollectionUpdate(BaseModel):
    """Schema for updating collection status/assignment via PATCH."""
    status: Optional[str] = Field(default=None, description="New lifecycle status")
    assigned_to: Optional[str] = Field(default=None, max_length=100, description="Person assigned")


class CollectionResponse(BaseModel):
    """Schema for collection API responses."""
    id: int
    location_id: Optional[int] = None
    report_id: Optional[int] = None
    location_name: Optional[str] = None
    area: Optional[str] = None
    status: str
    assigned_to: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    truck_number: Optional[str] = None
    assigned_staff_id: Optional[str] = None
    assigned_staff_email: Optional[str] = None
    image_url: Optional[str] = None
