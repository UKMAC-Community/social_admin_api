import os
from typing import List

from dotenv import load_dotenv


load_dotenv()


APP_NAME = os.getenv("APP_NAME", "UKMAC Website API")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "development")


def _comma_separated_env(name: str, default: str = "") -> List[str]:
    return [
        value.strip()
        for value in os.getenv(name, default).split(",")
        if value.strip()
    ]


CORS_ORIGINS = _comma_separated_env("CORS_ORIGINS")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_PROFILE_TABLE = os.getenv("SUPABASE_PROFILE_TABLE", "profiles")
SUPABASE_POST_TYPES_TABLE = os.getenv("SUPABASE_POST_TYPES_TABLE", "post_types")
SUPABASE_POSTS_TABLE = os.getenv("SUPABASE_POSTS_TABLE", "posts")
SUPABASE_IMAGES_TABLE = os.getenv("SUPABASE_IMAGES_TABLE", "images")
SUPABASE_QR_LINKS_TABLE = os.getenv("SUPABASE_QR_LINKS_TABLE", "qr_links")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "website")
