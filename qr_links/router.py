from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from auth.schemas import SupabaseUser
from posts.service import get_current_post_editor
from qr_links.schemas import QrLink, QrLinkCreate, QrLinkSummary, QrLinkUpdate
from qr_links.service import (
    create_qr_link,
    delete_qr_link,
    get_qr_link,
    list_qr_links,
    update_qr_link,
)


router = APIRouter()


@router.get("", response_model=List[QrLinkSummary], summary="List saved QR URLs")
def qr_links(
    _: SupabaseUser = Depends(get_current_post_editor),
):
    return list_qr_links()


@router.get("/{qr_id}", response_model=QrLink, summary="Get QR link")
def qr_link(
    qr_id: UUID,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    return get_qr_link(qr_id)


@router.post(
    "",
    response_model=QrLink,
    status_code=status.HTTP_201_CREATED,
    summary="Save post URL",
    description="Store a post URL for future QR use without generating a QR image.",
)
def add_qr_link(
    payload: QrLinkCreate,
    current_user: SupabaseUser = Depends(get_current_post_editor),
):
    return create_qr_link(payload, current_user.id)


@router.patch("/{qr_id}", response_model=QrLink, summary="Update post URL")
def edit_qr_link(
    qr_id: UUID,
    payload: QrLinkUpdate,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    return update_qr_link(qr_id, payload)


@router.delete(
    "/{qr_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete QR link",
)
def remove_qr_link(
    qr_id: UUID,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    delete_qr_link(qr_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
