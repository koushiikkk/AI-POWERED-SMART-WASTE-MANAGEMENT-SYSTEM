from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.database import get_db_connection
from app.schemas.location import LocationCreate, LocationUpdate, LocationResponse
from app.services.waste_logic import calculate_waste_status
from app.services.auth import require_role
from datetime import datetime

router = APIRouter()

# ──────────────────────────────────────────────
# GET /api/locations — List all locations
# ──────────────────────────────────────────────
@router.get("/locations", response_model=List[LocationResponse])
def get_locations(current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        res = supabase.table("locations").select("*").order("id").execute()
        
        locations = []
        for loc in res.data:
            # Re-derive status from current data
            loc["status"] = calculate_waste_status(
                float(loc["current_level"]), float(loc["capacity"])
            )
            locations.append(loc)
        return locations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# GET /api/locations/{id} — Get single location
# ──────────────────────────────────────────────
@router.get("/locations/{location_id}", response_model=LocationResponse)
def get_location(location_id: int, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        res = supabase.table("locations").select("*").eq("id", location_id).execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")

        loc = res.data[0]
        loc["status"] = calculate_waste_status(
            float(loc["current_level"]), float(loc["capacity"])
        )
        return loc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# POST /api/locations — Create a new location
# ──────────────────────────────────────────────
@router.post("/locations", response_model=LocationResponse, status_code=201)
def create_location(location: LocationCreate, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        status = calculate_waste_status(location.current_level, location.capacity)

        supabase = get_db_connection()
        data = {
            "name": location.name,
            "area": location.area,
            "waste_type": location.waste_type,
            "capacity": float(location.capacity),
            "current_level": float(location.current_level),
            "status": status
        }
        res = supabase.table("locations").insert(data).execute()
        
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create location")
            
        loc = res.data[0]
        loc["status"] = status
        return loc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# PUT /api/locations/{id} — Update a location
# ──────────────────────────────────────────────
@router.put("/locations/{location_id}", response_model=LocationResponse)
def update_location(location_id: int, location: LocationUpdate, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        
        # Check existence
        res_check = supabase.table("locations").select("id").eq("id", location_id).execute()
        if not res_check.data:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")

        status = calculate_waste_status(location.current_level, location.capacity)
        
        data = {
            "name": location.name,
            "area": location.area,
            "waste_type": location.waste_type,
            "capacity": float(location.capacity),
            "current_level": float(location.current_level),
            "status": status
        }
        
        res = supabase.table("locations").update(data).eq("id", location_id).execute()
        
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to update location")
            
        loc = res.data[0]
        loc["status"] = status
        return loc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# ──────────────────────────────────────────────
# DELETE /api/locations/{id} — Delete a location
# ──────────────────────────────────────────────
@router.delete("/locations/{location_id}", status_code=204)
def delete_location(location_id: int, current_user: dict = Depends(require_role(["STAFF", "ADMIN"]))):
    try:
        supabase = get_db_connection()
        
        res_check = supabase.table("locations").select("id").eq("id", location_id).execute()
        if not res_check.data:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")

        supabase.table("locations").delete().eq("id", location_id).execute()
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
