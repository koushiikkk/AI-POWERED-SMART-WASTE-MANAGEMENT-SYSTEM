"""
Pydantic schemas for AI Image Analysis resource.
Used for response serialization of analysis endpoints.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AnalysisResponse(BaseModel):
    """Schema for POST /api/reports/{id}/analyze response."""
    report_id: int
    analysis_status: str  # pending_analysis | processing | analyzed | failed
    severity: Optional[str] = None
    confidence: Optional[float] = None
    analysis_reason: Optional[str] = None
    analysis_provider: Optional[str] = None
    analysis_model: Optional[str] = None
    needs_review: bool = False
    analyzed_at: Optional[datetime] = None
    error: Optional[str] = None


class ReportPriorityResponse(BaseModel):
    """Schema for GET /api/reports/{id}/priority response."""
    report_id: int
    severity: Optional[str] = None
    confidence: Optional[float] = None
    analysis_status: str
    priority_score: Optional[float] = None
    priority_level: Optional[str] = None
    reason: Optional[str] = None
    confidence_adjusted: bool = False
    analysis_reason: Optional[str] = None
