import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("backend/.env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY")

if not url or not key:
    print("Supabase credentials not found in backend/.env")
    sys.exit(1)

supabase: Client = create_client(url, key)

print("Clearing old data...")
supabase.table("route_stops").delete().neq("id", -1).execute()
supabase.table("route_plans").delete().neq("id", -1).execute()
supabase.table("trucks").delete().neq("id", -1).execute()
supabase.table("collection_records").delete().neq("id", -1).execute()
supabase.table("waste_reports").delete().neq("id", -1).execute()
supabase.table("waste_records").delete().neq("id", -1).execute()
supabase.table("locations").delete().neq("id", -1).execute()

chennai_locations = [
    {
        "name": "Demo Collection Point - Anna Nagar",
        "area": "Anna Nagar",
        "waste_type": "MIXED",
        "capacity": 500.0,
        "current_level": 450.0,
        "status": "CRITICAL",
        "latitude": 13.0850,
        "longitude": 80.2100
    },
    {
        "name": "Demo Waste Hotspot - T. Nagar",
        "area": "T. Nagar",
        "waste_type": "PLASTIC",
        "capacity": 300.0,
        "current_level": 150.0,
        "status": "MEDIUM",
        "latitude": 13.0392,
        "longitude": 80.2330
    },
    {
        "name": "Demo Collection Point - Adyar",
        "area": "Adyar",
        "waste_type": "ORGANIC",
        "capacity": 400.0,
        "current_level": 320.0,
        "status": "HIGH",
        "latitude": 13.0012,
        "longitude": 80.2565
    },
    {
        "name": "Demo Waste Hotspot - Velachery",
        "area": "Velachery",
        "waste_type": "MIXED",
        "capacity": 600.0,
        "current_level": 100.0,
        "status": "LOW",
        "latitude": 12.9780,
        "longitude": 80.2210
    },
    {
        "name": "Demo Collection Point - Mylapore",
        "area": "Mylapore",
        "waste_type": "RECYCLABLE",
        "capacity": 250.0,
        "current_level": 200.0,
        "status": "HIGH",
        "latitude": 13.0335,
        "longitude": 80.2698
    }
]

print("Seeding locations...")
for loc in chennai_locations:
    res = supabase.table("locations").insert(loc).execute()
    if res.data:
        loc_id = res.data[0]['id']
        # Insert a waste record for it
        supabase.table("waste_records").insert({
            "location_id": loc_id,
            "recorded_level": loc['current_level']
        }).execute()
        
        # If High/Critical, insert a pending collection
        if loc['status'] in ['HIGH', 'CRITICAL']:
            supabase.table("collection_records").insert({
                "location_id": loc_id,
                "status": "pending"
            }).execute()

print("Seeding trucks...")
trucks = [
    {
        "truck_number": "TN-01-AB-1234",
        "capacity": 1000.0,
        "current_load": 0.0,
        "status": "AVAILABLE",
        "start_latitude": 13.0827, # Chennai Central Depot
        "start_longitude": 80.2707
    },
    {
        "truck_number": "TN-02-CD-5678",
        "capacity": 1500.0,
        "current_load": 0.0,
        "status": "AVAILABLE",
        "start_latitude": 12.9850, # South Depot
        "start_longitude": 80.2250
    }
]

supabase.table("trucks").insert(trucks).execute()

print("Chennai data seeded successfully!")
