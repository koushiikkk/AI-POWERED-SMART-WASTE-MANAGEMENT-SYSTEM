import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from datetime import datetime
from app.database import get_db_connection
from app.schemas.report import WasteReportResponse
from app.services.ai_service import analyze_waste_image
from app.services.priority_engine import calculate_report_priority
from app.services.auth import get_current_user, get_optional_user, require_role
from app.services.routing_engine import haversine_distance
from app.services.aws_service import aws_service

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024

def _validate_image(file: UploadFile) -> None:
    if not file or not file.filename:
        raise HTTPException(status_code=422, detail="Image file is required")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid image type '{file.content_type}'.")
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Invalid file extension '{ext}'.")

def _validate_coordinates(latitude: float, longitude: float) -> None:
    if latitude < -90 or latitude > 90:
        raise HTTPException(status_code=422, detail=f"Invalid latitude {latitude}.")
    if longitude < -180 or longitude > 180:
        raise HTTPException(status_code=422, detail=f"Invalid longitude {longitude}.")

def _find_nearby_location(supabase, lat: float, lon: float, threshold_km: float = 0.1) -> Optional[dict]:
    # Fetch all locations to compute distance (since we can't easily do it in REST without PostGIS RPC)
    # For a real large-scale system, use PostGIS ST_DWithin.
    res = supabase.table("locations").select("id, latitude, longitude, status, capacity, current_level").execute()
    best_loc = None
    min_dist = float('inf')
    
    for loc in res.data:
        if loc.get("latitude") and loc.get("longitude"):
            dist = haversine_distance(lat, lon, float(loc["latitude"]), float(loc["longitude"]))
            if dist < min_dist:
                min_dist = dist
                best_loc = loc
                
    if min_dist <= threshold_km:
        return best_loc
    return None

# ──────────────────────────────────────────────
# POST /api/reports — Submit a citizen waste report (No account required)
# ──────────────────────────────────────────────
@router.post("/reports", response_model=WasteReportResponse, status_code=201)
async def create_report(
    image: UploadFile = File(..., description="Waste image (JPEG, PNG, or WEBP)"),
    latitude: float = Form(..., description="GPS latitude (-90 to 90)"),
    longitude: float = Form(..., description="GPS longitude (-180 to 180)"),
    location_name: Optional[str] = Form(None, description="Optional searched location name or landmark"),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    _validate_image(image)
    _validate_coordinates(latitude, longitude)

    file_content = await image.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail=f"File too large. Max 10MB.")
    if len(file_content) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    _, ext = os.path.splitext(image.filename)
    safe_filename = f"{uuid.uuid4().hex}{ext.lower()}"

    supabase = get_db_connection()

    # Upload to Supabase Storage
    try:
        supabase.storage.from_("waste-reports").upload(
            path=safe_filename,
            file=file_content,
            file_options={"content-type": image.content_type}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {e}")

    # Optional S3 archive copy (fault-tolerant, preserves Supabase primary workflow)
    try:
        aws_service.archive_image_to_s3(
            file_content=file_content,
            filename=safe_filename,
            content_type=image.content_type or "image/jpeg"
        )
    except Exception as s3_err:
        logger.warning(f"Optional S3 archival copy skipped: {s3_err}")

    try:
        data = {
            "image_path": safe_filename,
            "latitude": latitude,
            "longitude": longitude,
            "analysis_status": "pending_analysis",
            "reported_by_user_id": current_user["id"] if current_user else None
        }
        
        # Find or create a nearby location for linking via collection_records later
        nearby = _find_nearby_location(supabase, latitude, longitude, threshold_km=0.1)
        linked_location_id = None
        if nearby:
            linked_location_id = nearby["id"]
            # If user provided a specific landmark/place name, update the location's name if generic
            if location_name and nearby.get("name") in ("Citizen Reported Area", None, ""):
                try:
                    supabase.table("locations").update({"name": location_name.strip()[:100]}).eq("id", linked_location_id).execute()
                except Exception:
                    pass
        else:
            # Create a new location for this citizen report
            loc_title = location_name.strip()[:100] if location_name and location_name.strip() else "Citizen Reported Area"
            loc_area = "Citizen Pinned" if location_name else "Unknown Area"
            if location_name and "," in location_name:
                parts = [p.strip() for p in location_name.split(",")]
                loc_title = parts[0][:100]
                loc_area = ", ".join(parts[1:3])[:100]

            new_loc_res = supabase.table("locations").insert({
                "name": loc_title,
                "area": loc_area,
                "waste_type": "MIXED",
                "capacity": 100.0,
                "current_level": 0.0,
                "status": "LOW",
                "latitude": latitude,
                "longitude": longitude
            }).execute()
            if new_loc_res.data:
                linked_location_id = new_loc_res.data[0]["id"]
            
        res_insert = supabase.table("waste_reports").insert(data).execute()
        if not res_insert.data:
            raise HTTPException(status_code=500, detail="Failed to insert report into database")
            
        report = res_insert.data[0]
        report["image_url"] = supabase.storage.from_("waste-reports").get_public_url(report["image_path"])
        if location_name:
            report["location_name"] = location_name
        
        # Store the linked location ID in memory for the analyze step
        # We pass it via a transient attribute that won't be persisted
        return WasteReportResponse(**report)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# GET /api/reports — List waste reports
# ──────────────────────────────────────────────
@router.get("/reports", response_model=List[WasteReportResponse])
def get_reports(
    current_user: Optional[dict] = Depends(get_optional_user)
):
    try:
        supabase = get_db_connection()
        res = supabase.table("waste_reports").select("*").order("created_at", desc=True).execute()

        # Query collection records to enrich reports with their latest collection status
        try:
            col_res = supabase.table("collection_records").select("report_id, status, completed_at").execute()
            report_col_map = {}
            for c in (col_res.data or []):
                rep_id = c.get("report_id")
                if rep_id:
                    # Prefer completed or latest record
                    if rep_id not in report_col_map or c.get("status") == "completed":
                        report_col_map[rep_id] = c
        except Exception:
            report_col_map = {}

        reports = []
        for report in res.data:
            report["image_url"] = supabase.storage.from_("waste-reports").get_public_url(report["image_path"])
            
            if report.get("severity") and report.get("confidence") is not None:
                priority = calculate_report_priority(report["severity"], report["confidence"])
                report["priority_score"] = priority["priority_score"]
                report["priority_level"] = priority["priority_level"]

            col_info = report_col_map.get(report["id"])
            if col_info:
                report["collection_status"] = col_info.get("status")
                report["completed_at"] = col_info.get("completed_at")
            else:
                report["collection_status"] = "pending"

            reports.append(WasteReportResponse(**report))
        return reports

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# GET /api/reports/{report_id} — Get single report
# ──────────────────────────────────────────────
@router.get("/reports/{report_id}", response_model=WasteReportResponse)
def get_report(
    report_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    try:
        supabase = get_db_connection()
        res = supabase.table("waste_reports").select("*").eq("id", report_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

        report = res.data[0]
        report["image_url"] = supabase.storage.from_("waste-reports").get_public_url(report["image_path"])
        
        if report.get("severity") and report.get("confidence") is not None:
            priority = calculate_report_priority(report["severity"], report["confidence"])
            report["priority_score"] = priority["priority_score"]
            report["priority_level"] = priority["priority_level"]

        # Check collection status
        try:
            col_res = supabase.table("collection_records").select("status, completed_at").eq("report_id", report_id).order("id", desc=True).limit(1).execute()
            if col_res.data:
                report["collection_status"] = col_res.data[0].get("status")
                report["completed_at"] = col_res.data[0].get("completed_at")
            else:
                report["collection_status"] = "pending"
        except Exception:
            report["collection_status"] = "pending"

        return WasteReportResponse(**report)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# POST /api/reports/{report_id}/analyze — Trigger NVIDIA AI analysis
# ──────────────────────────────────────────────
@router.post("/reports/{report_id}/analyze", response_model=WasteReportResponse)
async def analyze_report(
    report_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    try:
        supabase = get_db_connection()
        
        res = supabase.table("waste_reports").select("*").eq("id", report_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
            
        report = res.data[0]
            
        if current_user and current_user.get("role") == "CITIZEN" and report.get("reported_by_user_id") and report.get("reported_by_user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
            
        db_image_path = report["image_path"]
        image_url = supabase.storage.from_("waste-reports").get_public_url(db_image_path)
        
        # We skip updating analysis_status to 'processing' because the database constraint
        # only allows 'pending_analysis', 'analyzed', and 'failed'.

        try:
            ai_result = await analyze_waste_image(image_url)
        except Exception as ai_error:
            supabase.table("waste_reports").update({
                "analysis_status": "failed", 
                "analysis_reason": f"AI Analysis Failed: {str(ai_error)}"
            }).eq("id", report_id).execute()
            raise HTTPException(status_code=502, detail=f"AI Service Error: {str(ai_error)}")

        now = datetime.now().isoformat()
        update_data = {
            "analysis_status": "analyzed",
            "severity": ai_result["severity"],
            "confidence": ai_result["confidence"],
            "analysis_reason": ai_result["reason"],
            "analysis_provider": ai_result["analysis_provider"],
            "analysis_model": ai_result["analysis_model"],
            "analyzed_at": now
        }
        
        res_update = supabase.table("waste_reports").update(update_data).eq("id", report_id).execute()
        
        # ─────────────────────────────────────────────────────────────
        # Automatic Complaint Assignment for ALL priority levels (CRITICAL, HIGH, MEDIUM, LOW)
        # ─────────────────────────────────────────────────────────────
        severity = ai_result.get("severity") or "MEDIUM"
        loc_id = None
        nearby_loc = _find_nearby_location(supabase, float(report["latitude"]), float(report["longitude"]), threshold_km=0.1)
        previous_status = nearby_loc.get("status") if nearby_loc else None
        if nearby_loc:
            loc_id = nearby_loc["id"]
            try:
                supabase.table("locations").update({"status": severity}).eq("id", loc_id).execute()
            except Exception as loc_u_err:
                print(f"Warning updating location status: {loc_u_err}")
        else:
            # Create a location for citizen report if none nearby
            try:
                new_loc = supabase.table("locations").insert({
                    "name": "Citizen Reported Area",
                    "area": "Citizen GPS",
                    "waste_type": "MIXED",
                    "capacity": 100.0,
                    "current_level": 50.0,
                    "status": severity,
                    "latitude": float(report["latitude"]),
                    "longitude": float(report["longitude"])
                }).execute()
                if new_loc.data:
                    loc_id = new_loc.data[0]["id"]
            except Exception as loc_c_err:
                print(f"Warning creating location for report: {loc_c_err}")

        # Check if an active collection record already exists for this report or location
        active_col = None
        if loc_id:
            col_res = supabase.table("collection_records").select("id, status").eq("location_id", loc_id).in_("status", ["pending", "assigned", "in_progress"]).execute()
            if col_res.data:
                active_col = col_res.data[0]
        if not active_col:
            rep_col_res = supabase.table("collection_records").select("id, status").eq("report_id", report_id).in_("status", ["pending", "assigned", "in_progress"]).execute()
            if rep_col_res.data:
                active_col = rep_col_res.data[0]

        target_col_id = None
        if not active_col:
            new_col_data = {
                "report_id": report_id,
                "status": "pending"
            }
            if loc_id:
                new_col_data["location_id"] = loc_id
            try:
                new_col = supabase.table("collection_records").insert(new_col_data).execute()
                if new_col.data:
                    target_col_id = new_col.data[0]["id"]
            except Exception as col_i_err:
                print(f"Warning inserting collection record: {col_i_err}")
        elif active_col.get("status") == "pending":
            target_col_id = active_col["id"]

        if target_col_id:
            try:
                from app.services.auto_assign import auto_assign_complaint
                assign_result = auto_assign_complaint(supabase, target_col_id)
                print(f"Auto-assignment result for {severity} complaint (col #{target_col_id}): {assign_result}")
            except Exception as assign_err:
                print(f"Auto-assignment failed (non-fatal): {assign_err}")
        
        # ─────────────────────────────────────────────────────────────
        # AWS Integration Pipeline (CloudWatch, DynamoDB, SNS) - Non-blocking
        # ─────────────────────────────────────────────────────────────
        try:
            bin_id = str(nearby_loc["id"]) if nearby_loc else f"BIN-{report_id}"
            
            fill_level = 95.0 if ai_result["severity"] == "CRITICAL" else (
                80.0 if ai_result["severity"] == "HIGH" else (
                    60.0 if ai_result["severity"] == "MEDIUM" else 25.0
                )
            )
            if nearby_loc and float(nearby_loc.get("capacity", 0)) > 0:
                loc_fill = (float(nearby_loc.get("current_level", 0)) / float(nearby_loc["capacity"])) * 100
                if loc_fill > 0:
                    fill_level = loc_fill

            aws_service.process_detection_aws_integrations(
                bin_id=bin_id,
                fill_level=fill_level,
                waste_status=ai_result["severity"],
                latitude=float(report["latitude"]),
                longitude=float(report["longitude"]),
                confidence=float(ai_result["confidence"]),
                reason=ai_result.get("reason"),
                report_id=report_id,
                previous_status=previous_status,
                ai_provider=ai_result.get("analysis_provider", "NVIDIA NIM"),
                ai_model=ai_result.get("analysis_model")
            )
        except Exception as aws_err:
            logger.warning(f"AWS detection post-processing non-fatal warning: {aws_err}")

        updated_report = res_update.data[0]
        updated_report["image_url"] = image_url
        
        if updated_report.get("severity") and updated_report.get("confidence") is not None:
            priority = calculate_report_priority(updated_report["severity"], updated_report["confidence"])
            updated_report["priority_score"] = priority["priority_score"]
            updated_report["priority_level"] = priority["priority_level"]
        
        return WasteReportResponse(**updated_report)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
