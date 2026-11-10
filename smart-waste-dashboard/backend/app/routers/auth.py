import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.database import get_db_connection
from app.services.auth import get_current_user, require_role

router = APIRouter()

class CreateStaffRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "role": current_user["role"]
    }

@router.get("/staff")
async def list_staff_members(current_user: dict = Depends(require_role(["ADMIN"]))):
    """Admin-only endpoint to list all authorized staff."""
    try:
        supabase = get_db_connection()
        res = supabase.table("profiles").select("id, role, created_at").eq("role", "STAFF").execute()
        staff_profiles = res.data or []
        
        users_dict = {}
        try:
            # Get users from Auth Admin API to get emails
            auth_users_res = supabase.auth.admin.list_users()
            users_dict = {u.id: u.email for u in auth_users_res}
        except Exception as auth_err:
            print(f"Auth Admin API Error: {auth_err}")
            # If 403 Forbidden, we gracefully fallback
        
        result = []
        for profile in staff_profiles:
            result.append({
                "id": profile["id"],
                "role": profile["role"],
                "created_at": profile["created_at"],
                "email": users_dict.get(profile["id"], "Staff Member")
            })
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@router.post("/staff", status_code=201)
async def create_staff_member(payload: CreateStaffRequest, current_user: dict = Depends(require_role(["ADMIN"]))):
    """Admin-only endpoint to provision a new staff account."""
    try:
        supabase = get_db_connection()
        
        # Create user via Supabase Admin API
        user_res = supabase.auth.admin.create_user({
            "email": payload.email,
            "password": payload.password,
            "email_confirm": True
        })
        new_user_id = user_res.user.id
        
        # Insert into profiles table
        res = supabase.table("profiles").insert({
            "id": new_user_id,
            "role": "STAFF"
        }).execute()
        
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create staff profile")
            
        created = res.data[0]
        return {
            "id": created["id"],
            "email": payload.email,
            "role": created["role"],
            "created_at": created.get("created_at")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating staff: {e}")
