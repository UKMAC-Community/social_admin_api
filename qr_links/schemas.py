from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class QrLinkCreate(BaseModel):
    qr_name: str = Field(min_length=1, max_length=120)
    qr_url: HttpUrl

    @field_validator("qr_name")
    @classmethod
    def clean_qr_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("QR name cannot be empty")
        return value


class QrLinkUpdate(BaseModel):
    qr_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    qr_url: Optional[HttpUrl] = None

    @field_validator("qr_name")
    @classmethod
    def clean_qr_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("QR name cannot be empty")
        return value

    @model_validator(mode="after")
    def require_change(self):
        if self.qr_name is None and self.qr_url is None:
            raise ValueError("Provide qr_name or qr_url")
        return self


class QrLink(BaseModel):
    qr_id: UUID
    qr_name: str
    qr_url: HttpUrl
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class QrLinkSummary(BaseModel):
    qr_name: str
    qr_url: HttpUrl
