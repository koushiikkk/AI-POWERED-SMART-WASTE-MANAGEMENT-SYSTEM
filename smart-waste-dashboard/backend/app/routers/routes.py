from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.database import get_db_connection
from app.services.routing_engine import calculate_smart_route, calculate_baseline_route
from app.services.auth import get_current_user, require_role

router = APIRouter()

class RouteOptimizationRequest(BaseModel):
    start_lat: float
    start_lng: float
    truck_id: Optional[int] = None
    report_ids: Optional[List[int]] = [] # Can route specific reports
    location_ids: Optional[List[int]] = [] # Or specific locations

class TruckAssignmentRequest(BaseModel):
    truck_id: int
    staff_id: Optional[str] = None

class StopCompletionRequest(BaseModel):
    collection_id: Optional[int] = None
    route_plan_id: Optional[int] = None
    route_stop_id: Optional[int] = None
    report_id: Optional[int] = None
    location_id: Optional[int] = None
    truck_id: Optional[int] = None

class FinishShiftRequest(BaseModel):
    route_plan_id: Optional[int] = None
    truck_id: Optional[int] = None

@router.get("/routes/trucks")
def get_trucks(current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        if current_user["role"] == "STAFF":
            res = supabase.table("trucks").select("*").eq("assigned_staff_id", current_user["id"]).execute()
            return res.data or []
        else:
            res = supabase.table("trucks").select("*").order("id").execute()
            trucks = res.data or []
            try:
                auth_users_res = supabase.auth.admin.list_users()
                user_email_map = {u.id: u.email for u in auth_users_res}
            except Exception:
                user_email_map = {}
            for t in trucks:
                s_id = t.get("assigned_staff_id")
                t["assigned_staff_email"] = user_email_map.get(s_id) if s_id else None
            return trucks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@router.post("/routes/trucks/assign")
def assign_truck(req: TruckAssignmentRequest, current_user: dict = Depends(require_role(["ADMIN"]))):
    """Admin-only endpoint to assign or unassign a collection truck to/from a staff member."""
    try:
        supabase = get_db_connection()
        
        # 1. Verify truck exists
        truck_res = supabase.table("trucks").select("*").eq("id", req.truck_id).execute()
        if not truck_res.data:
            raise HTTPException(status_code=404, detail=f"Truck with ID {req.truck_id} not found.")
        truck = truck_res.data[0]
        
        # 2. If unassigning (staff_id is None or empty)
        if not req.staff_id:
            # Revert any incomplete collections assigned to this truck back to pending with no driver
            try:
                supabase.table("collection_records").update({
                    "status": "pending",
                    "assigned_to": None
                }).eq("assigned_to", str(req.truck_id)).in_("status", ["assigned", "in_progress"]).execute()
            except Exception as rev_err:
                print(f"Warning: Failed to revert collections on truck unassign: {rev_err}")

            update_res = supabase.table("trucks").update({
                "assigned_staff_id": None,
                "status": "AVAILABLE"
            }).eq("id", req.truck_id).execute()
            
            if not update_res.data:
                raise HTTPException(status_code=500, detail="Failed to unassign truck in database.")
                
            updated = update_res.data[0]
            updated["assigned_staff_email"] = None
            return {
                "message": f"Truck {truck['truck_number']} has been unassigned.",
                "truck": updated
            }
            
        # 3. Assigning to a staff member
        staff_id = req.staff_id.strip()
        
        # 3a. Validate staff member exists and has role STAFF
        profile_res = supabase.table("profiles").select("*").eq("id", staff_id).execute()
        if not profile_res.data:
            raise HTTPException(status_code=400, detail=f"User with ID {staff_id} does not exist.")
        if profile_res.data[0].get("role") != "STAFF":
            raise HTTPException(status_code=400, detail="Only users with the STAFF role can be assigned a collection truck.")
            
        # 3b. Prevent assigning multiple trucks to the same staff member
        existing_truck = supabase.table("trucks").select("id, truck_number").eq("assigned_staff_id", staff_id).neq("id", req.truck_id).execute()
        if existing_truck.data:
            assigned_num = existing_truck.data[0]["truck_number"]
            raise HTTPException(
                status_code=400,
                detail=f"This staff member is already assigned to truck '{assigned_num}'. Each staff member can only have one active truck. Please unassign '{assigned_num}' first."
            )
            
        # 3c. Prevent assigning the same truck to multiple staff members simultaneously
        if truck.get("assigned_staff_id") and truck["assigned_staff_id"] != staff_id:
            raise HTTPException(
                status_code=400,
                detail=f"Truck '{truck['truck_number']}' is currently assigned to another staff member. Please unassign it first."
            )
            
        # 3d. Update truck record
        # Note: 'trucks_status_check' permits ('AVAILABLE', 'IN_TRANSIT', 'MAINTENANCE', 'OFF_DUTY').
        # Driver assignment is recorded in 'assigned_staff_id'. The vehicle's operational status is 'AVAILABLE'.
        update_res = supabase.table("trucks").update({
            "assigned_staff_id": staff_id,
            "status": "AVAILABLE"
        }).eq("id", req.truck_id).execute()
        
        if not update_res.data:
            raise HTTPException(status_code=500, detail="Failed to save truck assignment to database.")
            
        updated = update_res.data[0]
        
        staff_email = None
        try:
            auth_user = supabase.auth.admin.get_user_by_id(staff_id)
            if auth_user and auth_user.user:
                staff_email = auth_user.user.email
        except Exception:
            pass
            
        updated["assigned_staff_email"] = staff_email
        
        return {
            "message": f"Truck '{updated['truck_number']}' successfully assigned to {staff_email or 'staff member'}.",
            "truck": updated
        }
        
    except HTTPException:
        raise
    except Exception as e:
        detail_msg = getattr(e, "message", None) or str(e)
        raise HTTPException(status_code=500, detail=f"Database error during assignment: {detail_msg}")

@router.post("/routes/trucks/{truck_id}/unassign")
def unassign_truck(truck_id: int, current_user: dict = Depends(require_role(["ADMIN"]))):
    return assign_truck(TruckAssignmentRequest(truck_id=truck_id, staff_id=None), current_user=current_user)

def _check_route_plan_completed(supabase, route_plan_id: int) -> bool:
    if not route_plan_id:
        return False
    try:
        stops_res = supabase.table("route_stops").select("location_id, report_id").eq("route_plan_id", route_plan_id).execute()
        stops = stops_res.data or []
        if not stops:
            return True
        cols_res = supabase.table("collection_records").select("id, location_id, report_id, status").execute()
        cols = cols_res.data or []
        rep_col_map = {c["report_id"]: c for c in cols if c.get("report_id")}
        loc_col_map = {c["location_id"]: c for c in cols if c.get("location_id")}
        
        for st in stops:
            col = None
            if st.get("report_id"):
                col = rep_col_map.get(st["report_id"])
            elif st.get("location_id"):
                col = loc_col_map.get(st["location_id"])
            if not col or col.get("status") != "completed":
                return False
        return True
    except Exception:
        return False

def _check_truck_route_completed(supabase, truck_id) -> bool:
    if not truck_id:
        return False
    try:
        res = supabase.table("collection_records").select("id").eq("assigned_to", str(truck_id)).in_("status", ["assigned", "in_progress"]).execute()
        return len(res.data or []) == 0
    except Exception:
        return False

@router.post("/routes/optimize")
def optimize_route(req: RouteOptimizationRequest, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        
        # Enforce that truck exists and has an authorized driver
        if req.truck_id:
            t_check = supabase.table("trucks").select("id, truck_number, assigned_staff_id").eq("id", req.truck_id).execute()
            if not t_check.data:
                raise HTTPException(status_code=404, detail=f"Truck with ID {req.truck_id} not found.")
            truck_rec = t_check.data[0]
            if not truck_rec.get("assigned_staff_id"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Truck '{truck_rec.get('truck_number')}' has no assigned driver. Cannot generate a route."
                )

            # Enforce that STAFF can only optimize route for their own assigned truck
            if current_user["role"] == "STAFF":
                if truck_rec["assigned_staff_id"] != current_user["id"]:
                    raise HTTPException(status_code=403, detail="Forbidden: You can only generate routes for your own assigned vehicle.")
            else:
                p_check = supabase.table("profiles").select("id, role").eq("id", truck_rec["assigned_staff_id"]).execute()
                if not p_check.data or p_check.data[0].get("role") != "STAFF":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Driver assigned to truck '{truck_rec.get('truck_number')}' is not an authorized STAFF member."
                    )
        elif current_user["role"] == "STAFF":
            raise HTTPException(status_code=400, detail="A valid truck ID must be provided.")

        # 0. Fetch collection records to check completion status and active assignments
        cols_res = supabase.table("collection_records").select("id, location_id, report_id, status, assigned_to").execute()
        all_cols = cols_res.data or []
        
        # Track pending/assigned collection records and completed collections
        active_rep_cols = {}
        active_loc_cols = {}
        completed_rep_ids = set()
        completed_loc_ids = set()
        
        # Sort collections by id ascending so newer records for same location take precedence
        sorted_cols = sorted(all_cols, key=lambda c: c.get("id", 0))
        for c in sorted_cols:
            status = c.get("status")
            rep_id = c.get("report_id")
            loc_id = c.get("location_id")
            
            if rep_id:
                if status == "completed":
                    completed_rep_ids.add(rep_id)
                elif status in ("pending", "assigned", "in_progress"):
                    active_rep_cols[rep_id] = c
                    completed_rep_ids.discard(rep_id)
            if loc_id:
                if status == "completed":
                    completed_loc_ids.add(loc_id)
                elif status in ("pending", "assigned", "in_progress"):
                    active_loc_cols[loc_id] = c
                    completed_loc_ids.discard(loc_id) # Newer pending collection makes location eligible again
        
        # Exclude reports/locations actively assigned to another truck
        other_truck_rep_ids = {
            r for r, c in active_rep_cols.items() 
            if c.get("assigned_to") and str(c.get("assigned_to")) != str(req.truck_id)
        }
        other_truck_loc_ids = {
            l for l, c in active_loc_cols.items() 
            if c.get("assigned_to") and str(c.get("assigned_to")) != str(req.truck_id)
        }

        rep_to_col = {}
        loc_to_col = {}
        for c in sorted_cols:
            if c.get("report_id"):
                rep_to_col[c["report_id"]] = c
            if c.get("location_id"):
                loc_to_col[c["location_id"]] = c

        # Filter out already completed items and items assigned to other trucks
        valid_rep_ids = [r for r in (req.report_ids or []) if r not in completed_rep_ids and r not in other_truck_rep_ids]
        valid_loc_ids = [l for l in (req.location_ids or []) if l not in completed_loc_ids and l not in other_truck_loc_ids]

        # Prevent duplicate stops when a citizen report is linked to a location
        rep_linked_locs = {rep_to_col[r]["location_id"] for r in valid_rep_ids if r in rep_to_col and rep_to_col[r].get("location_id")}
        valid_loc_ids = [l for l in valid_loc_ids if l not in rep_linked_locs]

        if not valid_rep_ids and not valid_loc_ids:
            # Check if all requested reports or all reports for this vehicle are already completed
            requested_reps = set(req.report_ids or [])
            all_requested_completed = requested_reps and requested_reps.issubset(completed_rep_ids)
            
            truck_cols = [c for c in all_cols if str(c.get("assigned_to")) == str(req.truck_id)]
            all_truck_completed = truck_cols and all(c.get("status") == "completed" for c in truck_cols)
            
            has_pending_anywhere = any(c.get("status") in ("pending", "assigned", "in_progress") for c in all_cols)
            
            if all_requested_completed or all_truck_completed or not has_pending_anywhere:
                raise HTTPException(status_code=400, detail="All current collection reports have been completed. No pending collections are available.")
            else:
                raise HTTPException(status_code=400, detail="No eligible collection locations are currently available for this route.")

        stops_to_route = []
        
        # 1. Fetch Location stops
        if valid_loc_ids:
            loc_res = supabase.table("locations").select("id, name, area, latitude, longitude, status").in_("id", valid_loc_ids).execute()
            for loc in loc_res.data:
                p_map = {"CRITICAL": 95, "HIGH": 75, "MEDIUM": 50, "LOW": 25}
                col_for_loc = loc_to_col.get(loc["id"])
                stops_to_route.append({
                    "type": "location",
                    "location_id": loc["id"],
                    "collection_id": col_for_loc.get("id") if col_for_loc else None,
                    "name": loc["name"],
                    "lat": float(loc["latitude"]),
                    "lon": float(loc["longitude"]),
                    "severity": loc["status"],
                    "priority_score": p_map.get(loc["status"], 50)
                })
                
        # 2. Fetch Report stops
        if valid_rep_ids:
            rep_res = supabase.table("waste_reports").select("id, latitude, longitude, severity, confidence, analysis_status, analysis_reason").in_("id", valid_rep_ids).execute()
            for rep in rep_res.data:
                from app.services.priority_engine import calculate_report_priority
                priority_info = {"priority_score": 50}
                
                if rep.get("severity") and rep.get("confidence") is not None:
                    priority_info = calculate_report_priority(rep["severity"], float(rep["confidence"]))
                
                col_for_rep = rep_to_col.get(rep["id"])
                stops_to_route.append({
                    "type": "report",
                    "report_id": rep["id"],
                    "collection_id": col_for_rep.get("id") if col_for_rep else None,
                    "name": f"Citizen Report #{rep['id']}",
                    "lat": float(rep["latitude"]),
                    "lon": float(rep["longitude"]),
                    "severity": rep["severity"] or "UNKNOWN",
                    "priority_score": priority_info["priority_score"],
                    "reason": rep.get("analysis_reason"),
                    "confidence": rep.get("confidence")
                })
                
        if not stops_to_route:
            raise HTTPException(status_code=400, detail="No stops provided for routing.")
            
        start_loc = {"lat": req.start_lat, "lon": req.start_lng}
        
        smart_route_result = calculate_smart_route(start_loc, stops_to_route)
        baseline_route_result = calculate_baseline_route(start_loc, stops_to_route)
        
        # Save the smart route as the definitive route plan
        plan_insert = supabase.table("route_plans").insert({
            "staff_id": current_user["id"],
            "truck_id": req.truck_id,
            "start_latitude": req.start_lat,
            "start_longitude": req.start_lng,
            "total_distance": smart_route_result["total_distance_km"],
            "estimated_duration": smart_route_result["total_duration_minutes"]
        }).execute()
        
        if plan_insert.data:
            plan_id = plan_insert.data[0]["id"]
            smart_route_result["route_plan_id"] = plan_id
            
            # Insert stops
            stop_inserts = []
            for st in smart_route_result["stops"]:
                stop_inserts.append({
                    "route_plan_id": plan_id,
                    "location_id": st.get("location_id"),
                    "report_id": st.get("report_id"),
                    "sequence_number": st["sequence"],
                    "distance_from_previous": st.get("distance_from_previous_km"),
                    "estimated_duration": st.get("estimated_duration_minutes"),
                    "priority_score": st.get("priority_score")
                })
                
            if stop_inserts:
                saved_stops = supabase.table("route_stops").insert(stop_inserts).execute()
                # Attach route_stop_id to stops
                if saved_stops.data:
                    seq_to_id = {s["sequence_number"]: s["id"] for s in saved_stops.data}
                    for st in smart_route_result["stops"]:
                        st["route_stop_id"] = seq_to_id.get(st["sequence"])
                        st["route_plan_id"] = plan_id
                        st["is_completed"] = False

        # Update collections status: first stop is 'in_progress' (active destination), remaining are 'assigned' (scheduled)
        for idx, st in enumerate(smart_route_result["stops"]):
            col_id = st.get("collection_id")
            if col_id:
                st_status = "in_progress" if idx == 0 else "assigned"
                try:
                    supabase.table("collection_records").update({
                        "status": st_status,
                        "assigned_to": str(req.truck_id)
                    }).eq("id", col_id).execute()
                except Exception as e:
                    print(f"Warning: Failed to update collection #{col_id} status to {st_status}: {e}")

        # Update truck status to 'IN_TRANSIT'
        if req.truck_id:
            try:
                supabase.table("trucks").update({"status": "IN_TRANSIT"}).eq("id", req.truck_id).execute()
            except Exception as e:
                print(f"Warning: Failed to update truck status: {e}")
        
        return {
            "smart_route": smart_route_result,
            "baseline_route": baseline_route_result,
            **smart_route_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Routing error: {e}")

@router.get("/routes/active")
def get_active_route(truck_id: Optional[int] = None, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    """Retrieve the currently active route for the logged in staff member or specified truck."""
    try:
        supabase = get_db_connection()
        target_truck_id = truck_id
        truck_data = None

        if current_user["role"] == "STAFF":
            t_res = supabase.table("trucks").select("*").eq("assigned_staff_id", current_user["id"]).execute()
            if not t_res.data:
                return {"has_active_route": False, "message": "No vehicle assigned to this driver."}
            truck_data = t_res.data[0]
            target_truck_id = truck_data["id"]
        elif target_truck_id:
            t_res = supabase.table("trucks").select("*").eq("id", target_truck_id).execute()
            truck_data = t_res.data[0] if t_res.data else None

        if not target_truck_id:
            return {"has_active_route": False, "message": "No truck specified."}

        # Find the most recent route plan for this truck
        plan_res = supabase.table("route_plans").select("*").eq("truck_id", target_truck_id).order("created_at", desc=True).limit(1).execute()
        if not plan_res.data:
            return {"has_active_route": False}

        latest_plan = plan_res.data[0]
        plan_id = latest_plan["id"]

        # Fetch route stops
        stops_res = supabase.table("route_stops").select("*").eq("route_plan_id", plan_id).order("sequence_number").execute()
        db_stops = stops_res.data or []
        if not db_stops:
            return {"has_active_route": False}

        # Fetch all collection records for status lookup
        cols_res = supabase.table("collection_records").select("id, location_id, report_id, status, completed_at, assigned_to").order("id").execute()
        cols = cols_res.data or []
        rep_col_map = {}
        loc_col_map = {}
        for c in cols:
            if c.get("report_id"):
                if c["report_id"] not in rep_col_map or str(c.get("assigned_to")) == str(target_truck_id):
                    rep_col_map[c["report_id"]] = c
            if c.get("location_id"):
                if str(c.get("assigned_to")) == str(target_truck_id):
                    loc_col_map[c["location_id"]] = c
                elif c["location_id"] not in loc_col_map:
                    loc_col_map[c["location_id"]] = c

        # Fetch reports for enrichment
        rep_ids = [st["report_id"] for st in db_stops if st.get("report_id")]
        rep_details = {}
        if rep_ids:
            r_res = supabase.table("waste_reports").select("*").in_("id", rep_ids).execute()
            for r in (r_res.data or []):
                r["image_url"] = supabase.storage.from_("waste-reports").get_public_url(r["image_path"]) if r.get("image_path") else None
                rep_details[r["id"]] = r

        # Fetch locations for enrichment
        loc_ids = [st["location_id"] for st in db_stops if st.get("location_id")]
        loc_details = {}
        if loc_ids:
            l_res = supabase.table("locations").select("*").in_("id", loc_ids).execute()
            for l in (l_res.data or []):
                loc_details[l["id"]] = l

        enriched_stops = []
        completed_count = 0
        first_incomplete_idx = None

        for idx, st in enumerate(db_stops):
            col = None
            if st.get("report_id"):
                col = rep_col_map.get(st["report_id"])
            elif st.get("location_id"):
                col = loc_col_map.get(st["location_id"])

            is_collected = (col.get("status") == "completed") if col else False
            if is_collected:
                completed_count += 1
            elif first_incomplete_idx is None:
                first_incomplete_idx = idx

            rep_info = rep_details.get(st.get("report_id")) if st.get("report_id") else None
            loc_info = loc_details.get(st.get("location_id")) if st.get("location_id") else None

            lat = float(rep_info["latitude"]) if rep_info else (float(loc_info["latitude"]) if loc_info else 0.0)
            lon = float(rep_info["longitude"]) if rep_info else (float(loc_info["longitude"]) if loc_info else 0.0)
            name = f"Citizen Report #{st['report_id']}" if st.get("report_id") else (loc_info.get("name") if loc_info else f"Stop #{st['sequence_number']}")
            severity = (rep_info.get("severity") if rep_info else (loc_info.get("status") if loc_info else None)) or "MEDIUM"

            # Realistic waste unit calculation based on location sensor or AI severity
            if loc_info and float(loc_info.get("current_level") or 0.0) > 0:
                waste_units = float(loc_info["current_level"])
            else:
                sev_weights = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}
                waste_units = sev_weights.get((severity or "").upper(), 50.0)

            enriched_stops.append({
                "id": st["id"],
                "route_stop_id": st["id"],
                "route_plan_id": plan_id,
                "sequence": st["sequence_number"],
                "location_id": st.get("location_id"),
                "report_id": st.get("report_id"),
                "collection_id": col.get("id") if col else None,
                "type": "report" if st.get("report_id") else "location",
                "name": name,
                "lat": lat,
                "lon": lon,
                "severity": severity,
                "waste_units": waste_units,
                "priority_score": st.get("priority_score", 50.0),
                "distance_from_previous_km": float(st.get("distance_from_previous") or 0.0),
                "estimated_duration_minutes": float(st.get("estimated_duration") or 0.0),
                "is_completed": is_collected,
                "status": col.get("status") if col else "assigned",
                "completed_at": col.get("completed_at") if col else None,
                "image_url": rep_info.get("image_url") if rep_info else None,
                "reason": rep_info.get("analysis_reason") if rep_info else None,
                "confidence": rep_info.get("confidence") if rep_info else None
            })

        is_route_complete = (completed_count == len(enriched_stops)) and (len(enriched_stops) > 0)
        current_stop_index = len(enriched_stops) if is_route_complete else (first_incomplete_idx if first_incomplete_idx is not None else 0)

        # An active route exists ONLY if there are pending stops left to collect
        has_active_route = (not is_route_complete) and (len(enriched_stops) > 0)
        
        # If the truck has already completed all stops or is back to AVAILABLE with no in-progress stops
        if truck_data and truck_data.get("status") == "AVAILABLE" and is_route_complete:
            has_active_route = False

        total_projected_load = sum(s.get("waste_units", 50.0) for s in enriched_stops)
        collected_load = sum(s.get("waste_units", 50.0) for s in enriched_stops if s.get("is_completed"))

        if not has_active_route:
            return {
                "has_active_route": False,
                "is_route_complete": is_route_complete,
                "route_plan_id": plan_id,
                "truck_id": target_truck_id,
                "truck": truck_data,
                "stops": enriched_stops,
                "current_stop_index": current_stop_index,
                "total_stops": len(enriched_stops),
                "completed_stops": completed_count,
                "total_projected_load": total_projected_load,
                "collected_load": collected_load,
                "total_distance_km": float(latest_plan.get("total_distance") or 0),
                "total_duration_minutes": float(latest_plan.get("estimated_duration") or 0),
                "start_latitude": float(latest_plan.get("start_latitude") or 13.0827),
                "start_longitude": float(latest_plan.get("start_longitude") or 80.2707),
                "message": "All stops on the most recent route have been completed. No active route in progress."
            }

        start_loc = {
            "lat": float(latest_plan.get("start_latitude") or 13.0827),
            "lng": float(latest_plan.get("start_longitude") or 80.2707)
        }
        route_geometry = None
        try:
            from app.services.routing_engine import get_route_geometry
            route_geometry = get_route_geometry(start_loc, enriched_stops)
        except Exception:
            pass

        return {
            "has_active_route": True,
            "is_route_complete": False,
            "route_plan_id": plan_id,
            "truck_id": target_truck_id,
            "truck": truck_data,
            "stops": enriched_stops,
            "current_stop_index": current_stop_index,
            "total_stops": len(enriched_stops),
            "completed_stops": completed_count,
            "total_projected_load": total_projected_load,
            "collected_load": collected_load,
            "total_distance_km": float(latest_plan.get("total_distance") or 0),
            "total_duration_minutes": float(latest_plan.get("estimated_duration") or 0),
            "start_latitude": float(latest_plan.get("start_latitude") or 13.0827),
            "start_longitude": float(latest_plan.get("start_longitude") or 80.2707),
            "geometry": route_geometry
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch active route: {e}")

@router.post("/routes/stops/complete")
def complete_stop(req: StopCompletionRequest, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    """Mark a collection stop as collected in the database."""
    try:
        supabase = get_db_connection()
        
        # 1. Authorization check for staff
        if current_user["role"] == "STAFF" and req.truck_id:
            t_check = supabase.table("trucks").select("id").eq("id", req.truck_id).eq("assigned_staff_id", current_user["id"]).execute()
            if not t_check.data:
                raise HTTPException(status_code=403, detail="Forbidden: You are only authorized to complete stops for your assigned vehicle.")

        # 2. Find target collection record
        col_record = None
        if req.collection_id:
            res = supabase.table("collection_records").select("*").eq("id", req.collection_id).execute()
            if res.data:
                col_record = res.data[0]
        elif req.report_id:
            res = supabase.table("collection_records").select("*").eq("report_id", req.report_id).order("id", desc=True).execute()
            if res.data:
                col_record = res.data[0]
        elif req.location_id:
            res = supabase.table("collection_records").select("*").eq("location_id", req.location_id).order("id", desc=True).execute()
            if res.data:
                col_record = res.data[0]
        elif req.route_stop_id:
            st_res = supabase.table("route_stops").select("*").eq("id", req.route_stop_id).execute()
            if st_res.data:
                st = st_res.data[0]
                if st.get("report_id"):
                    res = supabase.table("collection_records").select("*").eq("report_id", st["report_id"]).order("id", desc=True).execute()
                elif st.get("location_id"):
                    res = supabase.table("collection_records").select("*").eq("location_id", st["location_id"]).order("id", desc=True).execute()
                if res and res.data:
                    col_record = res.data[0]

        if not col_record:
            raise HTTPException(status_code=404, detail="Collection record not found for this stop.")

        truck_id_to_check = req.truck_id or col_record.get("assigned_to")

        # 3. Idempotency: If already completed, return success cleanly
        if col_record.get("status") == "completed":
            is_complete = False
            if req.route_plan_id:
                is_complete = _check_route_plan_completed(supabase, req.route_plan_id)
            if not is_complete and truck_id_to_check:
                is_complete = _check_truck_route_completed(supabase, truck_id_to_check)

            return {
                "status": "completed",
                "message": "Stop was already marked as collected.",
                "collection": col_record,
                "route_completed": is_complete
            }

        # 4. Persist collection completion in database
        now_iso = datetime.utcnow().isoformat()
        update_res = supabase.table("collection_records").update({
            "status": "completed",
            "completed_at": now_iso
        }).eq("id", col_record["id"]).execute()

        if not update_res.data:
            raise HTTPException(status_code=500, detail="Failed to save collection completion to database.")

        updated_col = update_res.data[0]

        # 5. Reset physical location current_level to 0.0 and status to LOW
        loc_id = col_record.get("location_id")
        if loc_id:
            try:
                supabase.table("locations").update({
                    "current_level": 0.0,
                    "status": "LOW"
                }).eq("id", loc_id).execute()

                supabase.table("waste_records").insert({
                    "location_id": loc_id,
                    "recorded_level": 0.0
                }).execute()
            except Exception as loc_err:
                print(f"Warning: Failed to update location level: {loc_err}")

        # 6. Update truck's physical current_load
        stop_waste = 50.0
        if col_record.get("report_id"):
            try:
                r = supabase.table("waste_reports").select("severity").eq("id", col_record["report_id"]).execute()
                if r.data:
                    sev = (r.data[0].get("severity") or "").upper()
                    sev_map = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}
                    stop_waste = sev_map.get(sev, 50.0)
            except Exception:
                pass
        elif col_record.get("location_id"):
            try:
                l = supabase.table("locations").select("current_level").eq("id", col_record["location_id"]).execute()
                if l.data and float(l.data[0].get("current_level") or 0.0) > 0:
                    stop_waste = float(l.data[0]["current_level"])
            except Exception:
                pass

        if truck_id_to_check:
            try:
                t_res = supabase.table("trucks").select("current_load, capacity").eq("id", int(truck_id_to_check)).execute()
                if t_res.data:
                    old_load = float(t_res.data[0].get("current_load") or 0.0)
                    cap = float(t_res.data[0].get("capacity") or 1000.0)
                    new_load = min(cap, round(old_load + stop_waste, 1))
                    supabase.table("trucks").update({"current_load": new_load}).eq("id", int(truck_id_to_check)).execute()
            except Exception as t_err:
                print(f"Warning: Failed to update truck current_load: {t_err}")

        # 7. Check if all route stops for this route plan or truck are completed
        is_route_complete = False
        if req.route_plan_id:
            is_route_complete = _check_route_plan_completed(supabase, req.route_plan_id)
        if not is_route_complete and truck_id_to_check:
            is_route_complete = _check_truck_route_completed(supabase, truck_id_to_check)

        if is_route_complete and truck_id_to_check:
            try:
                supabase.table("trucks").update({
                    "status": "AVAILABLE",
                    "current_load": 0.0
                }).eq("id", int(truck_id_to_check)).execute()
            except Exception:
                pass
        else:
            # 8. Advance the next stop in sequence from 'assigned' to 'in_progress'
            if req.route_plan_id:
                try:
                    all_plan_stops = (
                        supabase.table("route_stops")
                        .select("id, report_id, location_id, sequence_number")
                        .eq("route_plan_id", req.route_plan_id)
                        .order("sequence_number")
                        .execute()
                        .data or []
                    )
                    for nxt in all_plan_stops:
                        nxt_col = None
                        if nxt.get("report_id"):
                            c_res = supabase.table("collection_records").select("id, status").eq("report_id", nxt["report_id"]).execute()
                            nxt_col = c_res.data[0] if c_res.data else None
                        elif nxt.get("location_id"):
                            c_res = supabase.table("collection_records").select("id, status").eq("location_id", nxt["location_id"]).execute()
                            nxt_col = c_res.data[0] if c_res.data else None

                        if nxt_col and nxt_col.get("status") in ("assigned", "pending"):
                            supabase.table("collection_records").update({
                                "status": "in_progress"
                            }).eq("id", nxt_col["id"]).execute()
                            break
                except Exception as adv_err:
                    print(f"Warning: Failed to advance next stop to in_progress: {adv_err}")

        return {
            "status": "completed",
            "message": "Stop successfully marked as collected in database.",
            "collection": updated_col,
            "route_completed": is_route_complete
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error completing stop: {e}")

@router.post("/routes/shift/finish")
def finish_shift(req: FinishShiftRequest, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    """Finalize the driver shift. Verifies route completion, releases the truck back to AVAILABLE."""
    try:
        supabase = get_db_connection()
        
        target_truck_id = req.truck_id
        if not target_truck_id and current_user["role"] == "STAFF":
            t_res = supabase.table("trucks").select("id").eq("assigned_staff_id", current_user["id"]).execute()
            if t_res.data:
                target_truck_id = t_res.data[0]["id"]
                
        if not target_truck_id:
            raise HTTPException(status_code=400, detail="Truck ID must be provided or linked to the active driver.")

        # Check authorization if staff
        if current_user["role"] == "STAFF":
            t_check = supabase.table("trucks").select("id").eq("id", target_truck_id).eq("assigned_staff_id", current_user["id"]).execute()
            if not t_check.data:
                raise HTTPException(status_code=403, detail="Forbidden: You can only finish shifts for your assigned vehicle.")

        # Check plan completion if plan_id provided or latest plan exists
        plan_id = req.route_plan_id
        if not plan_id:
            latest_plan_res = supabase.table("route_plans").select("id").eq("truck_id", target_truck_id).order("created_at", desc=True).limit(1).execute()
            if latest_plan_res.data:
                plan_id = latest_plan_res.data[0]["id"]

        if plan_id:
            is_complete = _check_route_plan_completed(supabase, plan_id)
            if not is_complete:
                raise HTTPException(status_code=400, detail="Cannot finish shift: Not all assigned stops on this route have been completed.")

        # Release truck to AVAILABLE and reset load
        supabase.table("trucks").update({
            "status": "AVAILABLE",
            "current_load": 0.0
        }).eq("id", target_truck_id).execute()

        return {
            "status": "completed",
            "message": "Shift successfully finalized. Truck released to AVAILABLE."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error finishing shift: {e}")

class ActiveRouteUpdateRequest(BaseModel):
    truck_id: int
    collection_id: int
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None

@router.post("/routes/update-active")
def update_active_route(req: ActiveRouteUpdateRequest, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    """
    Insert a new collection stop into the currently active route for a truck.
    Called when auto_assign determines a complaint should be added mid-route.
    """
    try:
        supabase = get_db_connection()

        # Enforce that truck exists and has an authorized driver
        t_check = supabase.table("trucks").select("id, truck_number, assigned_staff_id").eq("id", req.truck_id).execute()
        if not t_check.data:
            raise HTTPException(status_code=404, detail=f"Truck with ID {req.truck_id} not found.")
        truck_rec = t_check.data[0]
        if not truck_rec.get("assigned_staff_id"):
            raise HTTPException(
                status_code=400,
                detail=f"Truck '{truck_rec.get('truck_number')}' has no assigned driver."
            )

        if current_user["role"] == "STAFF":
            if truck_rec["assigned_staff_id"] != current_user["id"]:
                raise HTTPException(status_code=403, detail="Forbidden: You can only update routes for your assigned vehicle.")

        # Delegate to auto_assign service
        from app.services.auto_assign import auto_assign_complaint
        result = auto_assign_complaint(supabase, req.collection_id)

        # Fetch updated route stops for the response
        plan_res = supabase.table("route_plans").select("*").eq("truck_id", req.truck_id).order("created_at", desc=True).limit(1).execute()
        updated_stops = []
        if plan_res.data:
            plan_id = plan_res.data[0]["id"]
            stops_res = supabase.table("route_stops").select("*").eq("route_plan_id", plan_id).order("sequence_number").execute()
            updated_stops = stops_res.data or []

        return {
            "auto_assign_result": result,
            "updated_route_stops": updated_stops,
            "message": result.get("message", "Route update evaluated.")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route update error: {e}")


@router.get("/routes/pending-unassigned")
def get_pending_unassigned(current_user: dict = Depends(require_role(["ADMIN"]))):
    """
    Returns collection records that are still 'pending' and not yet assigned to any truck.
    Useful for the admin portal to show complaints that could not be auto-assigned
    (capacity exceeded, truck unavailable, detour too large, etc.).
    """
    try:
        supabase = get_db_connection()

        # Fetch trucks to identify which vehicles have an authorized driver
        trucks_res = supabase.table("trucks").select("id, assigned_staff_id").execute()
        trucks_with_driver = {str(t["id"]) for t in (trucks_res.data or []) if t.get("assigned_staff_id")}

        # Include genuine 'pending' records AND active collections orphaned without a driver
        res = supabase.table("collection_records").select(
            "id, location_id, report_id, status, assigned_to, created_at"
        ).execute()

        all_cols = res.data or []
        pending = [
            c for c in all_cols
            if c.get("status") == "pending" or (
                c.get("status") in ("assigned", "in_progress") and str(c.get("assigned_to")) not in trucks_with_driver
            )
        ]

        # Enrich with location/report details
        enriched = []
        for col in pending:
            entry = {
                "id": col["id"],
                "report_id": col.get("report_id"),
                "location_id": col.get("location_id"),
                "status": col["status"],
                "assigned_to": col.get("assigned_to"),
                "created_at": col.get("created_at"),
                "location_name": None,
                "severity": None,
                "latitude": None,
                "longitude": None,
            }
            if col.get("location_id"):
                loc_res = supabase.table("locations").select("name, area, status, latitude, longitude").eq("id", col["location_id"]).execute()
                if loc_res.data:
                    l = loc_res.data[0]
                    entry["location_name"] = l.get("name")
                    entry["area"] = l.get("area")
                    entry["severity"] = l.get("status")
                    entry["latitude"] = l.get("latitude")
                    entry["longitude"] = l.get("longitude")
            if col.get("report_id"):
                rep_res = supabase.table("waste_reports").select("latitude, longitude, severity, confidence, analysis_reason").eq("id", col["report_id"]).execute()
                if rep_res.data:
                    r = rep_res.data[0]
                    entry["location_name"] = entry["location_name"] or f"Citizen Report #{col['report_id']}"
                    entry["severity"] = r.get("severity")
                    entry["latitude"] = r.get("latitude")
                    entry["longitude"] = r.get("longitude")
                    entry["analysis_reason"] = r.get("analysis_reason")
                    entry["confidence"] = r.get("confidence")
            enriched.append(entry)

        return enriched
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/routes/{plan_id}/cancel")
def cancel_route(plan_id: int, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    """End or cancel a route while preserving already completed stops."""
    try:
        supabase = get_db_connection()
        plan_res = supabase.table("route_plans").select("*").eq("id", plan_id).execute()
        if not plan_res.data:
            raise HTTPException(status_code=404, detail="Route plan not found")
        plan = plan_res.data[0]
        truck_id = plan["truck_id"]
        
        # Incomplete collections assigned to this truck revert to 'assigned'
        supabase.table("collection_records").update({"status": "assigned"}).eq("assigned_to", str(truck_id)).eq("status", "in_progress").execute()
        
        # Reset truck to AVAILABLE
        supabase.table("trucks").update({"status": "AVAILABLE"}).eq("id", truck_id).execute()
        return {"message": "Route ended. Completed stops remain recorded in database."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error ending route: {e}")
