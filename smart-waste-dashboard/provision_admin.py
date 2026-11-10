import os
from dotenv import load_dotenv
from supabase import create_client, Client
import time

load_dotenv("backend/.env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY")

if not url or not key:
    raise ValueError("Missing Supabase URL or Secret Key")

supabase: Client = create_client(url, key)

ADMIN_EMAIL = "koushikvaliveti@gmail.com"
ADMIN_PASSWORD = "SRMktr@2023"

try:
    print(f"Creating admin user {ADMIN_EMAIL}...")
    # Attempt to create the user via admin API
    res = supabase.auth.admin.create_user({
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "email_confirm": True
    })
    user = res.user
    print(f"User created with ID: {user.id}")

    # Wait a second for trigger/propagation if any
    time.sleep(1)

    # Insert into profiles
    try:
        supabase.table("profiles").insert({
            "id": user.id,
            "role": "ADMIN"
        }).execute()
        print("Profile created with role ADMIN")
    except Exception as e:
        print(f"Profile might already exist or error: {e}")
        # Update just in case
        supabase.table("profiles").update({"role": "ADMIN"}).eq("id", user.id).execute()
        print("Profile updated with role ADMIN")

except Exception as e:
    print(f"Error creating user (might already exist): {e}")
    # Try fetching existing user if they exist? Supabase doesn't have an easy get_user_by_email in python sdk sometimes.
    # Let's list users
    users_res = supabase.auth.admin.list_users()
    admin_user = next((u for u in users_res if u.email == ADMIN_EMAIL), None)
    if admin_user:
        print(f"Found existing user with ID: {admin_user.id}")
        supabase.table("profiles").upsert({
            "id": admin_user.id,
            "role": "ADMIN"
        }).execute()
        print("Upserted profile with role ADMIN")
        
        # update password
        supabase.auth.admin.update_user_by_id(admin_user.id, {"password": ADMIN_PASSWORD})
        print("Updated password for existing admin user")
    else:
        print("Could not find or create admin user.")

print("Done provisioning admin.")

