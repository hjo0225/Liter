from supabase import Client, create_client

from app.core.config import settings


def create_supabase(key: str) -> Client:
    return create_client(settings.SUPABASE_URL, key)


supabase: Client = create_supabase(settings.SUPABASE_SERVICE_ROLE_KEY)
supabase_anon: Client = create_supabase(settings.SUPABASE_ANON_KEY)
