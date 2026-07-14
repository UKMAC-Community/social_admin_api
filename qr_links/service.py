from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from auth.config import (
    SUPABASE_QR_LINKS_TABLE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from auth.providers.supabase import get_supabase_admin_client
from qr_links.schemas import QrLink, QrLinkCreate, QrLinkUpdate


def _client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase admin access is not configured",
        )
    return get_supabase_admin_client()


def _database_error(exc: APIError) -> HTTPException:
    code = getattr(exc, "code", None)

    if code == "23505":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A QR link with this unique value already exists",
        )
    if code == "23503":
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A referenced record does not exist",
        )

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Supabase QR-link request failed",
    )


def _link_from_row(row: dict) -> QrLink:
    return QrLink(**row)


def list_qr_links() -> List[QrLink]:
    query = _client().table(SUPABASE_QR_LINKS_TABLE).select("*")

    try:
        response = query.order("created_at", desc=True).execute()
    except APIError as exc:
        raise _database_error(exc) from exc

    return [_link_from_row(row) for row in response.data or []]


def get_qr_link(qr_id: UUID) -> QrLink:
    try:
        response = (
            _client()
            .table(SUPABASE_QR_LINKS_TABLE)
            .select("*")
            .eq("qr_id", str(qr_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _database_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR link not found",
        )
    return _link_from_row(rows[0])


def create_qr_link(payload: QrLinkCreate, created_by: str) -> QrLink:
    try:
        response = (
            _client()
            .table(SUPABASE_QR_LINKS_TABLE)
            .insert(
                {
                    "qr_name": payload.qr_name,
                    "qr_url": str(payload.qr_url),
                    "created_by": created_by,
                }
            )
            .execute()
        )
    except APIError as exc:
        raise _database_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return the created QR link",
        )
    return _link_from_row(rows[0])


def update_qr_link(qr_id: UUID, payload: QrLinkUpdate) -> QrLink:
    update_data = payload.model_dump(exclude_unset=True, mode="json")
    if not update_data:
        return get_qr_link(qr_id)

    try:
        response = (
            _client()
            .table(SUPABASE_QR_LINKS_TABLE)
            .update(update_data)
            .eq("qr_id", str(qr_id))
            .execute()
        )
    except APIError as exc:
        raise _database_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR link not found",
        )
    return _link_from_row(rows[0])


def delete_qr_link(qr_id: UUID) -> None:
    try:
        response = (
            _client()
            .table(SUPABASE_QR_LINKS_TABLE)
            .delete()
            .eq("qr_id", str(qr_id))
            .execute()
        )
    except APIError as exc:
        raise _database_error(exc) from exc

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR link not found",
        )
