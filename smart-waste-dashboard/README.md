# Smart Waste Management Platform

## Problem
Traditional municipal waste management relies on manual inspection, delayed complaints, uniform urgency without severity triage, and blind collection routing resulting in overflowing bins and inefficient fuel usage.

## Solution
A modern tactile municipal intelligence platform that creates an end-to-end digital pipeline:
`Citizen Report` → `GPS Tagging` → `Supabase Storage` → `FastAPI` → `NVIDIA Vision AI` → `Explainable Severity` → `Priority Engine` → `OpenRouteService Real-Road Routing` → `Staff Collection Console` → `Executive Command Center`.

## Tech Stack
- **Frontend**: React (Vite) + Modern Tactile Skeuomorphic UI + Leaflet & React-Leaflet
- **Backend**: Python 3.12 + FastAPI + Pydantic v2 + Uvicorn
- **Database & Storage**: Supabase PostgreSQL + PostGIS + Supabase Storage (`waste-reports`)
- **Authentication & RBAC**: Supabase Auth + JWT OAuth2 Bearer Tokens (Citizen Anonymous, Staff, Admin)
- **AI Vision**: NVIDIA NIM (`meta/llama-3.2-90b-vision-instruct`)
- **Geospatial & Routing**: OpenRouteService Driving Matrix & Directions API + Leaflet OSM

## Architecture
```
Public Citizen / Anonymous User
      ↓ (Photo + GPS)
React Frontend (Skeuomorphic Console)
      ↓ (REST API / Bearer Token)
FastAPI Backend (Authentication, RBAC & Logic)
      ├──→ Supabase Storage (Image Uploads)
      ├──→ Supabase PostgreSQL (Locations, Reports, Collections, Profiles)
      ├──→ NVIDIA NIM API (Multimodal Waste Severity & Confidence)
      ├──→ Priority Scoring Engine (0.5 Fill + 0.3 Severity + 0.2 Wait)
      └──→ OpenRouteService (Real-Road Driving Matrix & Route Geometry)
```

## Environment Variables

### Frontend (`frontend/.env`)
Create a `.env` file from `.env.example`:
```
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_PUBLISHABLE_KEY=your_supabase_anon_key
VITE_API_URL=http://127.0.0.1:8000/api
```

### Backend (`backend/.env`)
Create a `.env` file from `.env.example`:
```
FRONTEND_ORIGIN=http://localhost:5173
NVIDIA_API_KEY=your_nvidia_nim_api_key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.2-90b-vision-instruct
SUPABASE_URL=your_supabase_url
SUPABASE_SECRET_KEY=your_supabase_service_role_key
```
*(Database variables are not used in Supabase REST architecture but kept for local reference)*

## Running the Application

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Automated Verification Tests
```bash
cd backend
python ../tests/test_master_flows.py
```

## Netlify Deployment

1. Set the **Build Command** to `npm run build`
2. Set the **Publish Directory** to `dist`
3. Add the following Environment Variables in Netlify UI:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_PUBLISHABLE_KEY`
   - `VITE_API_URL` (Point to your production FastAPI backend URL)
4. Routing is handled automatically by the included `netlify.toml` file.

## Security Notes
- The Supabase Secret Role key and NVIDIA API keys are securely stored in the backend and NEVER exposed to the frontend.
- `.env` files are explicitly ignored in `.gitignore` to prevent secret leakage to GitHub.

## Known Limitations
- The application relies on external AI analysis APIs (NVIDIA NIM), requiring active connectivity.
- Offline support is not currently implemented.
