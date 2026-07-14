from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from auth.schemas import SupabaseUser
from posts.schemas import (
    ImageAttachRequest,
    ImageBatchAttachRequest,
    PostImage,
    PostImageAttach,
    PostImageUpload,
)
from posts.service import (
    attach_uploaded_image,
    delete_image,
    get_current_post_editor,
    reorder_post_images,
    upload_post_image,
)


router = APIRouter()


@router.post(
    "",
    response_model=PostImageUpload,
    status_code=status.HTTP_201_CREATED,
    summary="Upload image",
    description=(
        "Upload an image to Supabase Storage and immediately create an image "
        "record with a UUID. The image can be attached to a post afterward."
    ),
)
async def upload_image(
    file: UploadFile = File(...),
    current_user: SupabaseUser = Depends(get_current_post_editor),
):
    return upload_post_image(
        folder="gallery",
        filename=file.filename or "image",
        content=await file.read(),
        content_type=file.content_type,
        created_by=current_user.id,
        image_role="gallery",
    )


@router.post(
    "/batch",
    response_model=List[PostImageUpload],
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple images",
    description="Upload multiple staged images in one drag-and-drop request.",
)
async def upload_multiple_images(
    files: List[UploadFile] = File(...),
    current_user: SupabaseUser = Depends(get_current_post_editor),
):
    uploads = []
    for file in files:
        uploads.append(
            upload_post_image(
                folder="gallery",
                filename=file.filename or "image",
                content=await file.read(),
                content_type=file.content_type,
                created_by=current_user.id,
                image_role="gallery",
            )
        )
    return uploads


@router.patch(
    "",
    response_model=List[PostImage],
    summary="Attach multiple images to post",
    description=(
        "Attach images in order. The first image becomes the cover when the post "
        "does not already have one; remaining images become gallery images."
    ),
)
def attach_multiple_images(
    payload: ImageBatchAttachRequest,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    return [
        attach_uploaded_image(
            image_id,
            PostImageAttach(post_id=payload.post_id),
        )
        for image_id in payload.image_ids
    ]


@router.patch(
    "/order",
    response_model=List[PostImage],
    summary="Reorder post images",
    description=(
        "Persist the complete image order. The first image becomes the cover and "
        "all remaining images become gallery images."
    ),
)
def reorder_images(
    payload: ImageBatchAttachRequest,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    return reorder_post_images(payload.post_id, payload.image_ids)


@router.patch(
    "/{image_id}",
    response_model=PostImage,
    summary="Attach image to post",
    description="Attach a previously uploaded image UUID to a post.",
)
def attach_image(
    image_id: UUID,
    payload: ImageAttachRequest,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    return attach_uploaded_image(
        image_id,
        PostImageAttach(
            post_id=payload.post_id,
            caption=payload.caption,
            sort_order=payload.sort_order,
        ),
    )


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete image",
)
def remove_image(
    image_id: UUID,
    _: SupabaseUser = Depends(get_current_post_editor),
):
    delete_image(image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
