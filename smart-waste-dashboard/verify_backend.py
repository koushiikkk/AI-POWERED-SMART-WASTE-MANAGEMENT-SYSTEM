import os
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

load_dotenv("backend/.env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")

supabase: Client = create_client(url, key)

ADMIN_EMAIL = "rishidattamanda@gmail.com"
ADMIN_PASSWORD = "AdminPassword123!"

try:
    print(f"Logging in as {ADMIN_EMAIL}...")
    res = supabase.auth.sign_in_with_password({
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    token = res.session.access_token
    print("Successfully logged in.")

    print("\nTesting GET /api/auth/me ...")
    r = requests.get("http://127.0.0.1:8000/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    print(r.status_code, r.json())

    print("\nTesting GET /api/auth/staff ...")
    r = requests.get("http://127.0.0.1:8000/api/auth/staff", headers={"Authorization": f"Bearer {token}"})
    print(r.status_code, r.json())
    
except Exception as e:
    print(f"Error: {e}")
