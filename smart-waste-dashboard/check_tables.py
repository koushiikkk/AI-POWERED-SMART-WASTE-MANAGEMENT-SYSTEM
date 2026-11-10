import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("backend/.env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY")

supabase: Client = create_client(url, key)

print("Checking 'users' table...")
try:
    res = supabase.table("users").select("*").limit(1).execute()
    print("Users table exists:", res.data)
except Exception as e:
    print("Error querying users table:", e)

print("Checking 'profiles' table...")
try:
    res = supabase.table("profiles").select("*").limit(1).execute()
    print("Profiles table exists:", res.data)
except Exception as e:
    print("Error querying profiles table:", e)
