
import os

from dotenv import load_dotenv
from supabase import Client, create_client


# Load variables from the local .env file.
# On deployment, environment variables can be supplied by the host.
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SECRET_KEY "
        "must be configured in your environment."
    )

if not SUPABASE_URL.startswith(("https://", "http://")):
    raise RuntimeError(
        "SUPABASE_URL must be a valid HTTP or HTTPS URL."
    )


# Create one shared Supabase client.
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)
