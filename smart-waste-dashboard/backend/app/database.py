import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

def get_db_connection() -> Client:
    """
    Returns a Supabase client configured with the service role key.
    Since we are in the trusted backend, we can bypass RLS for administrative actions if needed,
    but we will still use the standard PostgREST API for queries.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise ConnectionError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY")
    return create_client(url, key)
