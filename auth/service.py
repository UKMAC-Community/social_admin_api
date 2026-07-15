from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase_auth.errors import AuthApiError

from auth.config import (
    SUPABASE_ANON_KEY,
    SUPABASE_PROFILE_TABLE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from auth.providers.supabase import get_supabase_admin_client, get_supabase_client
from auth.roles import (
    CONTENT_DASHBOARD_ROLES,
    STAFF_DASHBOARD_ROLES,
    USER_MANAGEMENT_ROLES,
    role_values,
)
from auth.schemas import (
    SupabaseCreateUserRequest,
    SupabaseProfile,
    SupabaseRefreshRequest,
    SupabaseSession,
    SupabaseUser,
)


supabase_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _require_supabase_auth_config() -> None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth is not configured",
        )


def _require_supabase_admin_config() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase admin access is not configured",
        )


def _invalid_credentials(detail: str = "Invalid Supabase credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _session_response(session) -> SupabaseSession:
    if session is None or session.access_token is None:
        raise _invalid_credentials()

    return SupabaseSession(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type or "bearer",
    )


def sign_in_with_supabase(email: str, password: str) -> SupabaseSession:
    _require_supabase_auth_config()

    client = get_supabase_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": str(email), "password": password}
        )
    except AuthApiError as exc:
        if exc.status in (400, 401):
            raise _invalid_credentials() from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase authentication failed",
        ) from exc

    return _session_response(response.session)


def refresh_supabase_session(payload: SupabaseRefreshRequest) -> SupabaseSession:
    _require_supabase_auth_config()

    client = get_supabase_client()
    try:
        response = client.auth.refresh_session(payload.refresh_token)
    except AuthApiError as exc:
        if exc.status in (400, 401, 403):
            raise _invalid_credentials("Invalid refresh token") from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase token refresh failed",
        ) from exc

    return _session_response(response.session)


def get_supabase_user(token: str) -> SupabaseUser:
    _require_supabase_auth_config()

    client = get_supabase_client()
    try:
        result = client.auth.get_user(token)
    except AuthApiError as exc:
        if exc.status in (400, 401, 403):
            raise _invalid_credentials("Could not validate Supabase credentials") from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase authentication failed",
        ) from exc

    user = result.user
    if user is None:
        raise _invalid_credentials("Could not validate Supabase credentials")

    return SupabaseUser(id=user.id, email=user.email)


def get_current_supabase_user(
    token: str = Depends(supabase_oauth2_scheme),
) -> SupabaseUser:
    return get_supabase_user(token)


def _profile_from_row(row: dict) -> SupabaseProfile:
    return SupabaseProfile(
        id=row.get("id"),
        email=row.get("email"),
        role=row.get("role"),
        full_name=row.get("full_name"),
        data=row,
    )


def get_supabase_profile(user_id: str) -> SupabaseProfile:
    _require_supabase_admin_config()

    client = get_supabase_admin_client()
    response = (
        client.table(SUPABASE_PROFILE_TABLE)
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return _profile_from_row(rows[0])


def require_current_user_role(
    current_user: SupabaseUser,
    allowed_roles: set[str],
    detail: str,
) -> SupabaseUser:
    profile = get_supabase_profile(current_user.id)

    if profile.role is None or profile.role.value not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    return current_user


def get_current_admin_user(
    current_user: SupabaseUser = Depends(get_current_supabase_user),
) -> SupabaseUser:
    return require_current_user_role(
        current_user,
        role_values(USER_MANAGEMENT_ROLES),
        "Admin role is required",
    )


def get_current_content_dashboard_user(
    current_user: SupabaseUser = Depends(get_current_supabase_user),
) -> SupabaseUser:
    return require_current_user_role(
        current_user,
        role_values(CONTENT_DASHBOARD_ROLES),
        "Content dashboard access is required",
    )


def get_current_staff_dashboard_user(
    current_user: SupabaseUser = Depends(get_current_supabase_user),
) -> SupabaseUser:
    return require_current_user_role(
        current_user,
        role_values(STAFF_DASHBOARD_ROLES),
        "Staff dashboard access is required",
    )


def create_supabase_user(payload: SupabaseCreateUserRequest) -> SupabaseProfile:
    _require_supabase_admin_config()

    client = get_supabase_admin_client()
    user_metadata = {
        "role": payload.role.value,
        "full_name": payload.full_name,
    }

    try:
        response = client.auth.admin.create_user(
            {
                "email": str(payload.email),
                "password": payload.password,
                "email_confirm": payload.email_confirm,
                "user_metadata": user_metadata,
            }
        )
    except AuthApiError as exc:
        if exc.code in ("email_exists", "user_already_exists") or exc.status == 422:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supabase user already exists",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase user creation failed",
        ) from exc

    user = response.user
    profile_data = {
        "id": user.id,
        "email": user.email,
        "role": payload.role.value,
        "full_name": payload.full_name,
    }
    profile_response = (
        client.table(SUPABASE_PROFILE_TABLE).upsert(profile_data).execute()
    )
    rows = profile_response.data or []

    return _profile_from_row(rows[0] if rows else profile_data)
