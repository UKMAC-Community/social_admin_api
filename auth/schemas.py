from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field

from auth.roles import UserRole


class SupabaseSession(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class SupabaseUser(BaseModel):
    id: str
    email: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None


class SupabaseLoginRequest(BaseModel):
    email: EmailStr
    password: str


class SupabaseRefreshRequest(BaseModel):
    refresh_token: str


class SupabaseCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: UserRole
    full_name: Optional[str] = None
    email_confirm: bool = True


class SupabaseProfile(BaseModel):
    id: str
    email: Optional[str] = None
    role: Optional[UserRole] = None
    full_name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
