from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)


def new_supabase_client() -> Client:
    """Client Supabase non partagé (pas de lru_cache).

    À utiliser quand plusieurs threads OS écrivent en parallèle : le client
    (et son httpx.Client synchrone sous-jacent) n'est pas thread-safe pour des
    écritures concurrentes — le partager entre threads corrompt le pool de
    connexions (ReadError/EAGAIN aléatoires). Un client par thread évite ça.
    """
    return create_client(settings.supabase_url, settings.supabase_service_key)
