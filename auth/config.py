import os
from typing import List

from dotenv import load_dotenv


load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _comma_separated_required_env(name: str) -> List[str]:
    return [value.strip() for value in _required_env(name).split(",") if value.strip()]


def _required_cors_origins(name: str) -> List[str]:
    origins = _comma_separated_required_env(name)
    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS cannot be '*' while authenticated browser requests are enabled. "
            "Use exact origins, for example: https://example.com,http://localhost:3000"
        )
    return origins


APP_NAME = _required_env("APP_NAME")
APP_VERSION = _required_env("APP_VERSION")
APP_ENVIRONMENT = _required_env("APP_ENVIRONMENT")
CORS_ORIGINS = _required_cors_origins("CORS_ORIGINS")
SECRET_KEY = _required_env("SECRET_KEY")
ALGORITHM = _required_env("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(_required_env("ACCESS_TOKEN_EXPIRE_MINUTES"))
SUPABASE_URL = _required_env("SUPABASE_URL")
SUPABASE_ANON_KEY = _required_env("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = _required_env("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_PROFILE_TABLE = _required_env("SUPABASE_PROFILE_TABLE")
SUPABASE_POST_TYPES_TABLE = _required_env("SUPABASE_POST_TYPES_TABLE")
SUPABASE_POSTS_TABLE = _required_env("SUPABASE_POSTS_TABLE")
SUPABASE_IMAGES_TABLE = _required_env("SUPABASE_IMAGES_TABLE")
SUPABASE_QR_LINKS_TABLE = _required_env("SUPABASE_QR_LINKS_TABLE")
SUPABASE_STORAGE_BUCKET = _required_env("SUPABASE_STORAGE_BUCKET")
