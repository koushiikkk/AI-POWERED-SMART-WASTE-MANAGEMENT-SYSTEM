"""
Smart Waste Management Dashboard — FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from app.routers import locations
from app.routers import collections
from app.routers import smart
from app.routers import reports
from app.routers import analysis
from app.routers import dashboard
from app.routers import routes
from app.routers import auth

app = FastAPI(
    title="Smart Waste Management Dashboard API",
    description="REST API for managing waste collection locations, records, and analytics.",
    version="1.0.0",
)

# CORS configuration
frontend_origins_env = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in frontend_origins_env.split(",") if origin.strip()]

# Add local development fallbacks if not in a strict production mode
if "localhost" not in frontend_origins_env and "127.0.0.1" not in frontend_origins_env:
    pass # In pure production, trust only what's passed
else:
    allowed_origins.extend([
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ])
    
# Remove duplicates
allowed_origins = list(set(allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Register routers
app.include_router(locations.router, prefix="/api", tags=["Locations"])
app.include_router(collections.router, prefix="/api", tags=["Collections"])
app.include_router(smart.router, prefix="/api", tags=["Smart Recommendations"])
app.include_router(reports.router, prefix="/api", tags=["Citizen Reports"])
app.include_router(analysis.router, prefix="/api", tags=["AI Image Analysis"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(routes.router, prefix="/api", tags=["Routes"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

# Mount uploads directory for serving uploaded images
upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Smart Waste Management Dashboard API"}
