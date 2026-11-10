import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env
load_dotenv(dotenv_path=".env")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY") # Use Service Role Key

if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY")

supabase: Client = create_client(url, key)

print("Connected to Supabase")

# Load MySQL dump
with open("mysql_dump.json", "r") as f:
    dump = json.load(f)

# The migration order is important to respect foreign keys
# 1. users -> profiles (Wait, users were inserted, but we need to map to auth.users if we use Supabase Auth.
# Since we are creating citizens and staff, it's better to recreate them in Supabase Auth via Admin API)
# Actually, the prompt says "Migrate existing real project data...". The existing users are demo accounts ('citizen', 'staff', 'admin').
# The prompt also says "REMOVE Demo Accounts: citizen/staff/admin". So we don't need to migrate users!
# But we do need to migrate locations, waste_records, waste_reports, collection_records.

print("Migrating locations...")
locations_data = []
for row in dump.get("locations", []):
    locations_data.append({
        "id": row["id"],
        "name": row["name"],
        "area": row["area"],
        "waste_type": row["waste_type"],
        "capacity": float(row["capacity"]),
        "current_level": float(row["current_level"]),
        "status": row["status"],
        "created_at": row["created_at"]
    })
if locations_data:
    res = supabase.table("locations").insert(locations_data).execute()
    print(f"Inserted {len(res.data)} locations")

print("Migrating waste_records...")
waste_records_data = []
for row in dump.get("waste_records", []):
    waste_records_data.append({
        "id": row["id"],
        "location_id": row["location_id"],
        "recorded_level": float(row["recorded_level"]),
        "recorded_at": row["recorded_at"]
    })
if waste_records_data:
    res = supabase.table("waste_records").insert(waste_records_data).execute()
    print(f"Inserted {len(res.data)} waste records")

# Next is waste_reports.
# We also need to upload the images in `backend/uploads/` to Supabase Storage bucket `waste-reports`
print("Migrating images and waste_reports...")
waste_reports_data = []
for row in dump.get("waste_reports", []):
    image_path = row["image_path"] # e.g. "uploads/test_image.jpg"
    file_name = os.path.basename(image_path)
    
    # Upload to Supabase Storage if file exists
    local_path = image_path
    if not os.path.exists(local_path):
        local_path = os.path.join(os.path.dirname(__file__), image_path)
        
    storage_path = file_name
    
    if os.path.exists(local_path):
        with open(local_path, "rb") as img_file:
            # Upload to 'waste-reports' bucket
            print(f"Uploading {local_path} to Storage...")
            try:
                supabase.storage.from_("waste-reports").upload(
                    file=img_file,
                    path=storage_path,
                    file_options={"content-type": "image/jpeg"} # Assuming JPEG for now
                )
                print(f"Uploaded {storage_path}")
            except Exception as e:
                print(f"Error uploading {storage_path}: {e}")
    else:
        print(f"Warning: Image file {local_path} not found locally.")

    # We need to map `image_path` to the storage path
    wr_dict = {
        "id": row["id"],
        "image_path": storage_path,
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "analysis_status": row["analysis_status"],
        "severity": row["severity"],
        "confidence": float(row["confidence"]) if row.get("confidence") else None,
        "analysis_reason": row["analysis_reason"],
        "created_at": row["created_at"],
        "analysis_provider": row.get("analysis_provider"),
        "analysis_model": row.get("analysis_model"),
        "analyzed_at": row.get("analyzed_at")
    }
    # Note: reported_by_user_id was linked to the 'users' table, which is deprecated. We'll leave it NULL (anonymous) for old reports.
    waste_reports_data.append(wr_dict)

if waste_reports_data:
    res = supabase.table("waste_reports").insert(waste_reports_data).execute()
    print(f"Inserted {len(res.data)} waste reports")

print("Migrating collection_records...")
collection_records_data = []
for row in dump.get("collection_records", []):
    collection_records_data.append({
        "id": row["id"],
        "location_id": row["location_id"],
        "status": row["status"],
        "assigned_to": row["assigned_to"],
        "created_at": row["created_at"],
        "completed_at": row.get("completed_at"),
        "report_id": row.get("report_id")
    })
if collection_records_data:
    res = supabase.table("collection_records").insert(collection_records_data).execute()
    print(f"Inserted {len(res.data)} collection records")

print("Migration completed successfully!")
