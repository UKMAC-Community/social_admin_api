from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth.config import APP_ENVIRONMENT, APP_NAME, APP_VERSION, CORS_ORIGINS
from auth.router import router as auth_router
from posts.images_router import router as images_router
from posts.router import router as posts_router
from qr_links.router import router as qr_links_router


class ApiOverview(BaseModel):
    name: str
    version: str
    environment: str
    documentation: str
    health: str


class HealthStatus(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Backend API for the UKMAC website, including Supabase authentication, "
        "content management, and media uploads."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "UKMAC"},
    license_info={"name": "Proprietary"},
)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get(
    "/",
    response_model=ApiOverview,
    tags=["System"],
    summary="API overview",
    include_in_schema=False,
)
def api_overview() -> ApiOverview:
    return ApiOverview(
        name=APP_NAME,
        version=APP_VERSION,
        environment=APP_ENVIRONMENT,
        documentation="/docs",
        health="/health",
    )


@app.get(
    "/health",
    response_model=HealthStatus,
    tags=["System"],
    summary="Check service health",
    include_in_schema=False,
)
def health_check() -> HealthStatus:
    return HealthStatus(status="ok", service=APP_NAME, version=APP_VERSION)


app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(posts_router, prefix="/posts", tags=["Posts"])
app.include_router(images_router, prefix="/images", tags=["Images"])
app.include_router(qr_links_router, prefix="/qr-links", tags=["QR Links"])
