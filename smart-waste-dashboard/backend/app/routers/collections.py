from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from app.database import get_db_connection
from app.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse
)
from app.services.auth import require_role
from app.services.collection_logic import validate_collection_transition, VALID_STATUSES

router = APIRouter()

def _get_truck_and_user_maps(supabase):
    try:
        trucks_res = supabase.table("trucks").select("id, truck_number, assigned_staff_id").execute()
        trucks_map = {str(t["id"]): t for t in (trucks_res.data or [])}
    except Exception:
        trucks_map = {}

    try:
        auth_users_res = supabase.auth.admin.list_users()
        user_email_map = {u.id: u.email for u in auth_users_res}
    except Exception:
        user_email_map = {}

    return trucks_map, user_email_map


def _validate_truck_has_staff_driver(supabase, truck_id):
    """
    Ensure the vehicle exists, has an assigned driver, and that driver has role 'STAFF'.
    Raises HTTPException(400 or 404) on validation failure.
    """
    try:
        t_id = int(truck_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid truck ID: {truck_id}")

    t_res = supabase.table("trucks").select("id, truck_number, assigned_staff_id").eq("id", t_id).execute()
    if not t_res.data:
        raise HTTPException(status_code=404, detail=f"Truck with ID {truck_id} not found.")

    truck = t_res.data[0]
    staff_id = truck.get("assigned_staff_id")
    if not staff_id:
        raise HTTPException(
            status_code=400,
            detail=f"Truck '{truck.get('truck_number')}' has no assigned driver. Cannot dispatch to an unassigned truck."
        )

    p_res = supabase.table("profiles").select("id, role").eq("id", staff_id).execute()
    if not p_res.data or p_res.data[0].get("role") != "STAFF":
        raise HTTPException(
            status_code=400,
            detail=f"Driver assigned to truck '{truck.get('truck_number')}' is not an authorized STAFF member."
        )
    return truck


def _enrich_collection(supabase, row, trucks_map=None, user_email_map=None):
    loc = row.get("locations") or {}
    rep = row.get("waste_reports") or {}
    rep_id = row.get("report_id")
    assigned_val = str(row.get("assigned_to")) if row.get("assigned_to") else None

    truck_info = trucks_map.get(assigned_val) if (trucks_map and assigned_val) else None
    truck_num = truck_info.get("truck_number") if truck_info else (f"Truck #{assigned_val}" if assigned_val else None)
    staff_id = truck_info.get("assigned_staff_id") if truck_info else None
    staff_email = user_email_map.get(staff_id) if (user_email_map and staff_id) else None

    image_url = None
    if rep.get("image_path"):
        try:
            image_url = supabase.storage.from_("waste-reports").get_public_url(rep["image_path"])
        except Exception:
            pass

    c = {
        "id": row["id"],
        "location_id": row["location_id"],
        "report_id": row["report_id"],
        "status": row["status"],
        "assigned_to": row["assigned_to"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "truck_number": truck_num,
        "assigned_staff_id": staff_id,
        "assigned_staff_email": staff_email,
        "image_url": image_url
    }
    if row.get("location_id"):
        c["location_name"] = loc.get("name")
        c["area"] = loc.get("area")
    elif rep_id:
        c["location_name"] = f"Citizen Report #{rep_id}"
        c["area"] = "Citizen GPS"
    else:
        c["location_name"] = "Unknown"
        c["area"] = "Unknown"

    return c


# ──────────────────────────────────────────────
# GET /api/collections — List all collections
# ──────────────────────────────────────────────
@router.get("/collections", response_model=List[CollectionResponse])
def get_collections(current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        res = supabase.table("collection_records").select(
            "id, location_id, report_id, status, assigned_to, created_at, completed_at, "
            "locations(name, area), waste_reports(id, image_path)"
        ).order("created_at", desc=True).execute()

        trucks_map, user_email_map = _get_truck_and_user_maps(supabase)

        collections = []
        for row in (res.data or []):
            collections.append(_enrich_collection(supabase, row, trucks_map, user_email_map))

        return collections
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


# ──────────────────────────────────────────────
# GET /api/collections/{id} — Get single collection
# ──────────────────────────────────────────────
@router.get("/collections/{collection_id}", response_model=CollectionResponse)
def get_collection(collection_id: int, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        res = supabase.table("collection_records").select(
            "id, location_id, report_id, status, assigned_to, created_at, completed_at, "
            "locations(name, area), waste_reports(id, image_path)"
        ).eq("id", collection_id).execute()

        if not res.data:
            raise HTTPException(status_code=404, detail=f"Collection {collection_id} not found")

        trucks_map, user_email_map = _get_truck_and_user_maps(supabase)
        return _enrich_collection(supabase, res.data[0], trucks_map, user_email_map)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# POST /api/collections — Create a new collection
# ──────────────────────────────────────────────
@router.post("/collections", response_model=CollectionResponse, status_code=201)
def create_collection(collection: CollectionCreate, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()

        if not collection.location_id and not collection.report_id:
            raise HTTPException(status_code=400, detail="Must provide either location_id or report_id")

        if collection.location_id:
            res_loc = supabase.table("locations").select("id").eq("id", collection.location_id).execute()
            if not res_loc.data:
                raise HTTPException(status_code=404, detail=f"Location {collection.location_id} not found.")
        
        if collection.report_id:
            res_rep = supabase.table("waste_reports").select("id").eq("id", collection.report_id).execute()
            if not res_rep.data:
                raise HTTPException(status_code=404, detail=f"Report {collection.report_id} not found.")

        if collection.assigned_to:
            _validate_truck_has_staff_driver(supabase, collection.assigned_to)

        data = {
            "location_id": collection.location_id,
            "report_id": collection.report_id,
            "status": "pending",
            "assigned_to": collection.assigned_to
        }
        res_insert = supabase.table("collection_records").insert(data).execute()
        
        if not res_insert.data:
            raise HTTPException(status_code=500, detail="Failed to create collection")
            
        new_id = res_insert.data[0]["id"]

        # Trigger automatic assignment if not manually pre-assigned
        if not collection.assigned_to:
            try:
                from app.services.auto_assign import auto_assign_complaint
                auto_assign_complaint(supabase, new_id)
            except Exception as assign_err:
                print(f"Auto-assign error on collection create: {assign_err}")

        # Fetch newly created
        res = supabase.table("collection_records").select(
            "id, location_id, report_id, status, assigned_to, created_at, completed_at, "
            "locations(name, area), waste_reports(id, image_path)"
        ).eq("id", new_id).execute()

        trucks_map, user_email_map = _get_truck_and_user_maps(supabase)
        return _enrich_collection(supabase, res.data[0], trucks_map, user_email_map)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# PATCH /api/collections/{id} — Update collection
# ──────────────────────────────────────────────
@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
def update_collection(collection_id: int, update_data: CollectionUpdate, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()

        res_check = supabase.table("collection_records").select("id, status, assigned_to, location_id, report_id").eq("id", collection_id).execute()
        if not res_check.data:
            raise HTTPException(status_code=404, detail=f"Collection {collection_id} not found")

        current = res_check.data[0]
        current_status = current["status"]
        current_assigned = current["assigned_to"]

        new_status = update_data.status if update_data.status is not None else current_status
        new_assigned = update_data.assigned_to if update_data.assigned_to is not None else current_assigned

        if update_data.status is not None and update_data.status != current_status:
            is_valid, error_msg = validate_collection_transition(current_status, update_data.status)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)

        if new_status == "assigned" and not new_assigned:
            raise HTTPException(
                status_code=400,
                detail="assigned_to is required when status is 'assigned'"
            )

        # Enforce that assigned truck has an authorized STAFF driver
        if new_assigned and (update_data.assigned_to is not None or new_status in ("assigned", "in_progress")):
            _validate_truck_has_staff_driver(supabase, new_assigned)

        update_dict = {
            "status": new_status,
            "assigned_to": new_assigned
        }
        
        if new_status == "completed" and current_status != "completed":
            update_dict["completed_at"] = datetime.utcnow().isoformat()

            # Reset associated location level to 0.0 and status to LOW
            loc_id = current.get("location_id")
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
                    print(f"Error resetting location {loc_id}: {loc_err}")

            # Check if truck has any remaining active collections; if not, set to AVAILABLE
            truck_to_check = new_assigned or current_assigned
            if truck_to_check:
                try:
                    rem_res = supabase.table("collection_records").select("id").eq("assigned_to", truck_to_check).in_("status", ["assigned", "in_progress"]).neq("id", collection_id).execute()
                    if not rem_res.data:
                        supabase.table("trucks").update({
                            "status": "AVAILABLE",
                            "current_load": 0.0
                        }).eq("id", int(truck_to_check)).execute()
                except Exception as tr_err:
                    print(f"Error checking truck availability: {tr_err}")

        res_update = supabase.table("collection_records").update(update_dict).eq("id", collection_id).execute()

        res = supabase.table("collection_records").select(
            "id, location_id, report_id, status, assigned_to, created_at, completed_at, "
            "locations(name, area), waste_reports(id, image_path)"
        ).eq("id", collection_id).execute()

        trucks_map, user_email_map = _get_truck_and_user_maps(supabase)
        return _enrich_collection(supabase, res.data[0], trucks_map, user_email_map)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
