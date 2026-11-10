import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("backend/.env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY")

supabase: Client = create_client(url, key)

try:
    res = supabase.auth.admin.list_users()
    print("Auth Users:")
    for u in res:
        print(u.email, getattr(u, 'role', 'unknown'))
except Exception as e:
    print("Error querying auth.users:", e)
