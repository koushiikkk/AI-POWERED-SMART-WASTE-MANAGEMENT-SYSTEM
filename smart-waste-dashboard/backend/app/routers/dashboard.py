from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from app.database import get_db_connection
from app.services.auth import require_role

router = APIRouter()

@router.get("/dashboard/summary", response_model=Dict[str, Any])
def get_dashboard_summary(current_user: dict = Depends(require_role(["ADMIN"]))):
    try:
        supabase = get_db_connection()

        summary = {
            "total_reports": 0,
            "pending_analysis": 0,
            "analyzed_reports": 0,
            "high_critical_items": 0,
            "collections": {
                "pending": 0,
                "assigned": 0,
                "in_progress": 0,
                "completed": 0
            },
            "severity_distribution": {
                "LOW": 0,
                "MEDIUM": 0,
                "HIGH": 0,
                "CRITICAL": 0
            }
        }

        # 1. Reports metrics & 3. Severity Distribution
        res_reports = supabase.table("waste_reports").select("analysis_status, severity").execute()
        report_severity_counts = { "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0 }
        
        for row in res_reports.data:
            summary["total_reports"] += 1
            status = row.get("analysis_status")
            if status == "pending_analysis":
                summary["pending_analysis"] += 1
            elif status in ("analyzed", "completed"):
                summary["analyzed_reports"] += 1
                sev = row.get("severity")
                if sev and sev in report_severity_counts:
                    report_severity_counts[sev] += 1

        # 2. Collection metrics
        res_collections = supabase.table("collection_records").select("status").execute()
        for row in res_collections.data:
            c_status = row.get("status")
            if c_status in summary["collections"]:
                summary["collections"][c_status] += 1

        summary["severity_distribution"] = report_severity_counts
        
        # 4. High/Critical Items
        summary["high_critical_items"] = report_severity_counts.get("HIGH", 0) + report_severity_counts.get("CRITICAL", 0)

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
