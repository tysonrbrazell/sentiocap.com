"""
Supabase client setup.

The service-role client is used in all API operations — it bypasses RLS so
the backend can enforce its own auth/authz logic via JWT validation.

For user-scoped Supabase operations (e.g., Supabase Auth), pass the user's
JWT via get_user_client().
"""
from supabase import create_client, Client
from config import settings


def get_supabase() -> Client:
    """Return a Supabase client using the service role key (bypasses RLS)."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


def get_user_client(user_jwt: str) -> Client:
    """Return a Supabase client scoped to the authenticated user.

    This uses the anon key but injects the user's JWT so RLS policies apply.
    Useful for Supabase Auth operations (password verification, etc.).
    """
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )
    client.auth.set_session(user_jwt, "")  # type: ignore[arg-type]
    return client


# Module-level service client (lazily initialized)
_supabase_client: Client | None = None


def get_db() -> Client:
    """FastAPI dependency — returns the shared service-role client."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = get_supabase()
    return _supabase_client
