"""
Pydantic schemas for Waste Report resource.
Used for response serialization only — request data arrives as multipart/form-data.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WasteReportResponse(BaseModel):
    """Schema for waste report API responses."""
    id: int
    image_url: str
    latitude: float
    longitude: float
    analysis_status: str
    severity: Optional[str] = None
    confidence: Optional[float] = None
    analysis_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    analysis_provider: Optional[str] = None
    analysis_model: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    priority_score: Optional[float] = None
    priority_level: Optional[str] = None
    collection_status: Optional[str] = None
    completed_at: Optional[datetime] = None
    location_name: Optional[str] = None
