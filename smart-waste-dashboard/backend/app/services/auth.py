import os
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db_connection

# Since we use Supabase Auth now, tokenUrl is not directly used for login via backend,
# but we keep it so Swagger UI knows it's a bearer token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

def get_user_from_db(user_id: str):
    supabase = get_db_connection()
    res = supabase.table("profiles").select("id, role").eq("id", user_id).execute()
    if res.data:
        return res.data[0]
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    supabase = get_db_connection()
    try:
        # get_user verifies the JWT with Supabase
        user_res = supabase.auth.get_user(token)
        if not user_res.user:
            raise credentials_exception
        user_id = user_res.user.id
    except Exception:
        raise credentials_exception
        
    profile = get_user_from_db(user_id)
    if profile is None:
        raise credentials_exception
    
    return {
        "id": user_id,
        "email": user_res.user.email,
        "role": profile["role"]
    }

async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[dict]:
    if not token:
        return None
        
    supabase = get_db_connection()
    try:
        user_res = supabase.auth.get_user(token)
        if not user_res.user:
            return None
        user_id = user_res.user.id
        
        profile = get_user_from_db(user_id)
        if profile:
            return {
                "id": user_id,
                "email": user_res.user.email,
                "role": profile["role"]
            }
    except Exception:
        return None
    return None

def require_role(allowed_roles: List[str]):
    """Dependency injection to enforce roles."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {allowed_roles}"
            )
        return current_user
    return role_checker
