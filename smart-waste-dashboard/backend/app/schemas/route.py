from pydantic import BaseModel, Field
from typing import List, Optional

class RouteOptimizeRequest(BaseModel):
    start_lat: float = Field(..., description="Starting latitude")
    start_lng: float = Field(..., description="Starting longitude")
    report_ids: List[int] = Field(..., description="List of report IDs to collect")

class RouteStop(BaseModel):
    report_id: int
    sequence: int
    latitude: float
    longitude: float
    priority_score: float
    severity: str
    location_name: str
    action_type: str = "report"

class RouteOptimizeResponse(BaseModel):
    total_distance_km: float
    total_duration_minutes: float
    stops: List[RouteStop]
    geometry: dict
