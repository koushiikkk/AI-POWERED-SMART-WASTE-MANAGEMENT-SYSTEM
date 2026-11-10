import logging
from fastapi import APIRouter, HTTPException
from app.database import get_db_connection
from app.schemas.analysis import AnalysisResponse, ReportPriorityResponse
from app.services.image_analysis import analyze_image, NVIDIA_API_KEY
from app.services.priority_engine import calculate_report_priority
from app.services.aws_service import aws_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ──────────────────────────────────────────────
# POST /api/reports/{report_id}/analyze — Trigger AI analysis
# ──────────────────────────────────────────────
@router.post("/reports/{report_id}/analyze", response_model=AnalysisResponse)
def analyze_report(report_id: int):
    try:
        supabase = get_db_connection()
        res = supabase.table("waste_reports").select("*").eq("id", report_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        
        report = res.data[0]
        image_path = report["image_path"]
        
        if not NVIDIA_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="AI analysis unavailable: NVIDIA_API_KEY not configured"
            )

        supabase.table("waste_reports").update({"analysis_status": "processing"}).eq("id", report_id).execute()

        image_url = supabase.storage.from_("waste-reports").get_public_url(image_path)
        
        result = analyze_image(image_url)

        if result.analysis_status == "analyzed":
            update_data = {
                "analysis_status": result.analysis_status,
                "severity": result.severity,
                "confidence": result.confidence,
                "analysis_reason": result.reason,
                "analysis_provider": result.analysis_provider,
                "analysis_model": result.analysis_model,
                "analyzed_at": "now()"
            }
        else:
            error_reason = f"Analysis failed: {result.error}" if result.error else "Analysis failed"
            update_data = {
                "analysis_status": result.analysis_status,
                "analysis_reason": error_reason,
                "analysis_provider": result.analysis_provider,
                "analysis_model": result.analysis_model
            }

        res_update = supabase.table("waste_reports").update(update_data).eq("id", report_id).execute()

        # AWS Integrations (CloudWatch, DynamoDB, SNS) - Non-blocking
        if result.analysis_status == "analyzed":
            try:
                fill_level = 95.0 if result.severity == "CRITICAL" else (
                    80.0 if result.severity == "HIGH" else (
                        60.0 if result.severity == "MEDIUM" else 25.0
                    )
                )
                bin_id = f"BIN-{report_id}"
                aws_service.process_detection_aws_integrations(
                    bin_id=bin_id,
                    fill_level=fill_level,
                    waste_status=result.severity or "LOW",
                    latitude=float(report.get("latitude", 0.0)),
                    longitude=float(report.get("longitude", 0.0)),
                    confidence=float(result.confidence) if result.confidence is not None else None,
                    reason=result.reason,
                    report_id=report_id,
                    previous_status=report.get("severity"),
                    ai_provider=result.analysis_provider or "NVIDIA NIM",
                    ai_model=result.analysis_model
                )
            except Exception as aws_err:
                logger.warning(f"AWS analysis post-processing non-fatal warning: {aws_err}")
        
        return AnalysisResponse(
            report_id=report_id,
            analysis_status=result.analysis_status,
            severity=result.severity,
            confidence=result.confidence,
            analysis_reason=result.reason,
            analysis_provider=result.analysis_provider,
            analysis_model=result.analysis_model,
            needs_review=result.needs_review,
            analyzed_at=res_update.data[0].get("analyzed_at") if res_update.data else None,
            error=result.error,
        )

    except HTTPException:
        raise
    except Exception as e:
        supabase.table("waste_reports").update({"analysis_status": "failed"}).eq("id", report_id).execute()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# GET /api/reports/{report_id}/priority — Get report priority score
# ──────────────────────────────────────────────
@router.get("/reports/{report_id}/priority", response_model=ReportPriorityResponse)
def get_report_priority(report_id: int):
    try:
        supabase = get_db_connection()
        res = supabase.table("waste_reports").select("*").eq("id", report_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

        report = res.data[0]

        if report["analysis_status"] != "analyzed":
            return ReportPriorityResponse(
                report_id=report_id,
                severity=report.get("severity"),
                confidence=float(report["confidence"]) if report.get("confidence") else None,
                analysis_status=report["analysis_status"],
                priority_score=None,
                priority_level=None,
                reason=f"Report not yet analyzed (status: {report['analysis_status']})",
                confidence_adjusted=False,
                analysis_reason=report.get("analysis_reason"),
            )

        confidence = float(report["confidence"]) if report.get("confidence") is not None else 0.0
        priority = calculate_report_priority(
            severity=report["severity"],
            confidence=confidence,
        )

        return ReportPriorityResponse(
            report_id=report_id,
            severity=report["severity"],
            confidence=confidence,
            analysis_status=report["analysis_status"],
            priority_score=priority["priority_score"],
            priority_level=priority["priority_level"],
            reason=priority["reason"],
            confidence_adjusted=priority["confidence_adjusted"],
            analysis_reason=report.get("analysis_reason"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
