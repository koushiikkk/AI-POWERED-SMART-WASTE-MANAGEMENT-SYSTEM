from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Dict, List, Any
from app.database import get_db_connection
from app.services.auth import require_role
from app.services.priority_engine import generate_collection_recommendations
from datetime import datetime

router = APIRouter()

@router.get("/smart/recommendations", response_model=Dict[str, Any])
def get_recommendations(
    current_user: dict = Depends(require_role(["STAFF", "ADMIN"])),
    status: Optional[str] = Query(
        default=None,
        description="Filter by priority level: LOW, MEDIUM, HIGH, CRITICAL",
    ),
    limit: Optional[int] = Query(
        default=None,
        gt=0,
        le=100,
        description="Maximum number of recommendations to return",
    ),
):
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if status is not None:
        status_upper = status.upper()
        if status_upper not in valid_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter '{status}'",
            )
        status = status_upper

    try:
        supabase = get_db_connection()
        res = supabase.table("locations").select(
            "id, name, area, waste_type, capacity, current_level, collection_records(status, created_at)"
        ).execute()
        
        locations_data = []
        for loc in res.data:
            pending_created_at = None
            pending_records = [c for c in loc.get("collection_records", []) if c["status"] == "pending"]
            if pending_records:
                # Get the earliest created_at string
                min_created_at_str = min([c["created_at"] for c in pending_records])
                if min_created_at_str:
                    # fromisoformat handles most ISO 8601 strings in Python 3.7+
                    # Supabase strings are like 2026-08-14T11:21:18+00:00
                    try:
                        pending_created_at = datetime.fromisoformat(min_created_at_str)
                    except ValueError:
                        # Fallback if unsupported format
                        pending_created_at = datetime.strptime(min_created_at_str.split('+')[0].split('.')[0], "%Y-%m-%dT%H:%M:%S")
                
            locations_data.append({
                "location_id": loc["id"],
                "location_name": loc["name"],
                "area": loc["area"],
                "waste_type": loc["waste_type"],
                "capacity": loc["capacity"],
                "current_level": loc["current_level"],
                "pending_created_at": pending_created_at
            })

        recommendations = generate_collection_recommendations(locations_data)

        if status:
            recommendations = [r for r in recommendations if r["priority_level"] == status]

        if limit:
            recommendations = recommendations[:limit]

        return {
            "count": len(recommendations),
            "algorithm": "Priority Score = 0.5 * Fill Ratio + 0.3 * Status Weight + 0.2 * Waiting Time",
            "score_range": "0-100",
            "recommendations": recommendations,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation engine error: {e}")
