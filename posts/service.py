import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status
from postgrest.exceptions import APIError
from storage3.exceptions import StorageApiError

from auth.config import (
    SUPABASE_IMAGES_TABLE,
    SUPABASE_POST_TYPES_TABLE,
    SUPABASE_POSTS_TABLE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_STORAGE_BUCKET,
    SUPABASE_URL,
)
from auth.providers.supabase import get_supabase_admin_client
from auth.schemas import SupabaseUser
from auth.service import get_current_supabase_user, get_supabase_profile
from posts.schemas import (
    Post,
    PostCreate,
    PostImage,
    PostImageAttach,
    PostImageCreate,
    PostImageUpload,
    PostImageUpdate,
    PostType,
    PostUpdate,
)


ALLOWED_IMAGE_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "image/webp",
}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


def _require_supabase_admin_config() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase admin access is not configured",
        )


def get_current_post_editor(
    current_user: SupabaseUser = Depends(get_current_supabase_user),
) -> SupabaseUser:
    profile = get_supabase_profile(current_user.id)

    if profile.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager role is required",
        )

    return current_user


def _db_error(exc: APIError) -> HTTPException:
    code = getattr(exc, "code", None)
    detail = getattr(exc, "message", None) or str(exc)

    if code == "23505":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A row with this unique value already exists",
        )
    if code == "23503":
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referenced row does not exist",
        )

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Supabase database request failed: {detail}",
    )


def _client():
    _require_supabase_admin_config()
    return get_supabase_admin_client()


def _storage_error(exc: StorageApiError) -> HTTPException:
    detail = getattr(exc, "message", None) or str(exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Supabase storage request failed: {detail}",
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "post"


def _safe_file_name(filename: str) -> str:
    stem = Path(filename).stem or "image"
    suffix = Path(filename).suffix.lower()
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-") or "image"
    return f"{uuid4()}-{safe_stem}{suffix}"


def _public_storage_url(bucket: str, path: str) -> str:
    encoded_bucket = quote(bucket, safe="")
    encoded_path = quote(path, safe="/")
    return (
        f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/"
        f"{encoded_bucket}/{encoded_path}"
    )


def _post_type_from_row(row: dict) -> PostType:
    return PostType(id=row["id"], name=row["name"], slug=row["slug"])


def _image_from_row(row: dict) -> PostImage:
    return PostImage(
        **{**row, "image_url": row.get("image_url") or row.get("image_path")}
    )


def _post_from_row(
    row: dict,
    post_type: Optional[PostType] = None,
    images: Optional[List[PostImage]] = None,
) -> Post:
    return Post(
        **row,
        type=post_type,
        images=images or [],
    )


def _get_post_type(type_id: int) -> PostType:
    client = _client()
    try:
        response = (
            client.table(SUPABASE_POST_TYPES_TABLE)
            .select("*")
            .eq("id", type_id)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post type does not exist",
        )

    return _post_type_from_row(rows[0])


def _get_post_type_by_slug(slug: str) -> PostType:
    client = _client()
    try:
        response = (
            client.table(SUPABASE_POST_TYPES_TABLE)
            .select("*")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post type not found",
        )

    return _post_type_from_row(rows[0])


def _type_map_for_rows(rows: Iterable[dict]) -> Dict[int, PostType]:
    type_ids = sorted({row["type_id"] for row in rows})
    if not type_ids:
        return {}

    client = _client()
    try:
        response = (
            client.table(SUPABASE_POST_TYPES_TABLE)
            .select("*")
            .in_("id", type_ids)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    return {row["id"]: _post_type_from_row(row) for row in response.data or []}


def _images_for_post_ids(post_ids: Iterable[str]) -> Dict[str, List[PostImage]]:
    ids = list(post_ids)
    if not ids:
        return {}

    client = _client()
    try:
        response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("*")
            .in_("post_id", ids)
            .order("image_role")
            .order("sort_order")
            .order("created_at")
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    image_map: Dict[str, List[PostImage]] = {post_id: [] for post_id in ids}
    for row in response.data or []:
        image_map.setdefault(row["post_id"], []).append(_image_from_row(row))

    return image_map


def _posts_from_rows(rows: List[dict]) -> List[Post]:
    type_map = _type_map_for_rows(rows)
    image_map = _images_for_post_ids([row["id"] for row in rows])

    return [
        _post_from_row(
            row,
            post_type=type_map.get(row["type_id"]),
            images=image_map.get(row["id"], []),
        )
        for row in rows
    ]


def list_post_types() -> List[PostType]:
    client = _client()
    try:
        response = (
            client.table(SUPABASE_POST_TYPES_TABLE)
            .select("*")
            .order("id")
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    return [_post_type_from_row(row) for row in response.data or []]


def upload_post_image(
    *,
    folder: str,
    filename: str,
    content: bytes,
    content_type: Optional[str],
    created_by: str,
    image_role: str = "gallery",
) -> PostImageUpload:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, WebP, GIF, and SVG image uploads are allowed",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(content) > MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image upload is larger than 10 MB",
        )

    path = f"posts/{folder}/{_safe_file_name(filename)}"
    client = _client()
    bucket = client.storage.from_(SUPABASE_STORAGE_BUCKET)

    try:
        bucket.upload(
            path,
            content,
            {
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
    except StorageApiError as exc:
        raise _storage_error(exc) from exc

    image_row = {
        "post_id": None,
        "image_role": image_role,
        "image_url": _public_storage_url(SUPABASE_STORAGE_BUCKET, path),
        "storage_bucket": SUPABASE_STORAGE_BUCKET,
        "storage_path": path,
        "original_filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "created_by": created_by,
    }

    try:
        response = client.table(SUPABASE_IMAGES_TABLE).insert(image_row).execute()
    except APIError as exc:
        try:
            bucket.remove([path])
        except StorageApiError:
            pass
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return the created image record",
        )

    return PostImageUpload(
        image_id=rows[0]["id"],
        bucket=SUPABASE_STORAGE_BUCKET,
        path=path,
        url=image_row["image_url"],
        content_type=content_type,
    )


def attach_uploaded_image(image_id: UUID, payload: PostImageAttach) -> PostImage:
    get_post(payload.post_id, published_only=False)
    client = _client()

    try:
        image_result = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("id,post_id,image_role")
            .eq("id", str(image_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    if not image_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    image_role = payload.image_role
    if image_role is None:
        current_image = image_result.data[0]
        if (
            str(current_image.get("post_id")) == str(payload.post_id)
            and current_image.get("image_role") in ("cover", "gallery")
        ):
            image_role = current_image["image_role"]
        else:
            try:
                cover_result = (
                    client.table(SUPABASE_IMAGES_TABLE)
                    .select("id")
                    .eq("post_id", str(payload.post_id))
                    .eq("image_role", "cover")
                    .limit(1)
                    .execute()
                )
            except APIError as exc:
                raise _db_error(exc) from exc
            image_role = "gallery" if cover_result.data else "cover"

    if image_role == "cover":
        try:
            client.table(SUPABASE_IMAGES_TABLE).delete().eq(
                "post_id", str(payload.post_id)
            ).eq("image_role", "cover").neq("id", str(image_id)).execute()
        except APIError as exc:
            raise _db_error(exc) from exc

    update_data = {
        "post_id": str(payload.post_id),
        "image_role": image_role,
        "caption": payload.caption,
    }
    if image_role == "gallery":
        update_data["sort_order"] = (
            payload.sort_order
            if payload.sort_order is not None
            else _next_image_sort_order(payload.post_id)
        )

    try:
        response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .update(update_data)
            .eq("id", str(image_id))
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    image = _image_from_row(rows[0])
    if image_role == "cover":
        try:
            client.table(SUPABASE_POSTS_TABLE).update(
                {"cover_image": image.image_path}
            ).eq("id", str(payload.post_id)).execute()
        except APIError as exc:
            raise _db_error(exc) from exc

    return image


def reorder_post_images(post_id: UUID, image_ids: List[UUID]) -> List[PostImage]:
    get_post(post_id, published_only=False)
    client = _client()
    ordered_ids = [str(image_id) for image_id in image_ids]

    if len(set(ordered_ids)) != len(ordered_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image order contains duplicate image IDs",
        )

    try:
        existing_result = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("id")
            .eq("post_id", str(post_id))
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    existing_ids = {str(row["id"]) for row in existing_result.data or []}
    if set(ordered_ids) != existing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image order must include every image attached to the post",
        )

    try:
        client.table(SUPABASE_IMAGES_TABLE).update(
            {"image_role": "gallery"}
        ).eq("post_id", str(post_id)).execute()

        reordered_images = []
        for index, image_id in enumerate(ordered_ids):
            response = (
                client.table(SUPABASE_IMAGES_TABLE)
                .update(
                    {
                        "image_role": "cover" if index == 0 else "gallery",
                        "sort_order": 0 if index == 0 else index - 1,
                    }
                )
                .eq("id", image_id)
                .eq("post_id", str(post_id))
                .execute()
            )
            rows = response.data or []
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image not found",
                )
            reordered_images.append(_image_from_row(rows[0]))

        client.table(SUPABASE_POSTS_TABLE).update(
            {"cover_image": reordered_images[0].image_path}
        ).eq("id", str(post_id)).execute()
    except APIError as exc:
        raise _db_error(exc) from exc

    return reordered_images


def _attach_staged_cover_by_url(post_id: UUID, image_url: str) -> None:
    client = _client()
    try:
        response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("id")
            .eq("image_url", image_url)
            .is_("post_id", "null")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if rows:
        attach_uploaded_image(
            UUID(rows[0]["id"]),
            PostImageAttach(post_id=post_id, image_role="cover"),
        )


def delete_image(image_id: UUID) -> None:
    client = _client()
    try:
        result = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("*")
            .eq("id", str(image_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = result.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    image = rows[0]
    storage_path = image.get("storage_path")
    if storage_path:
        try:
            storage_bucket = image.get("storage_bucket") or SUPABASE_STORAGE_BUCKET
            client.storage.from_(storage_bucket).remove([storage_path])
        except StorageApiError as exc:
            raise _storage_error(exc) from exc

    try:
        client.table(SUPABASE_IMAGES_TABLE).delete().eq(
            "id", str(image_id)
        ).execute()
    except APIError as exc:
        raise _db_error(exc) from exc

    if image.get("image_role") == "cover" and image.get("post_id"):
        try:
            next_result = (
                client.table(SUPABASE_IMAGES_TABLE)
                .select("*")
                .eq("post_id", image["post_id"])
                .order("sort_order")
                .order("created_at")
                .limit(1)
                .execute()
            )
            next_rows = next_result.data or []
            next_cover = None
            if next_rows:
                next_image = next_rows[0]
                client.table(SUPABASE_IMAGES_TABLE).update(
                    {"image_role": "cover", "sort_order": 0}
                ).eq("id", next_image["id"]).execute()
                next_cover = _image_from_row(next_image).image_path

            client.table(SUPABASE_POSTS_TABLE).update(
                {"cover_image": next_cover}
            ).eq("id", image["post_id"]).execute()
        except APIError as exc:
            raise _db_error(exc) from exc


def list_posts(
    *,
    published: Optional[bool],
    featured: Optional[bool],
    type_id: Optional[int],
    type_slug: Optional[str],
    limit: int,
    offset: int,
) -> List[Post]:
    client = _client()
    query = client.table(SUPABASE_POSTS_TABLE).select("*")

    if published is not None:
        query = query.eq("published", published)
    if featured is not None:
        query = query.eq("featured", featured)
    if type_id is not None:
        query = query.eq("type_id", type_id)
    if type_slug is not None:
        query = query.eq("type_id", _get_post_type_by_slug(type_slug).id)

    try:
        response = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    return _posts_from_rows(response.data or [])


def get_post(post_id: UUID, *, published_only: bool) -> Post:
    client = _client()
    query = (
        client.table(SUPABASE_POSTS_TABLE)
        .select("*")
        .eq("id", str(post_id))
        .limit(1)
    )
    if published_only:
        query = query.eq("published", True)

    try:
        response = query.execute()
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return _posts_from_rows([rows[0]])[0]


def get_post_by_slug(slug: str, *, published_only: bool) -> Post:
    client = _client()
    query = (
        client.table(SUPABASE_POSTS_TABLE)
        .select("*")
        .eq("slug", slug)
        .limit(1)
    )
    if published_only:
        query = query.eq("published", True)

    try:
        response = query.execute()
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return _posts_from_rows([rows[0]])[0]


def _insert_images(post_id: UUID, images: List[PostImageCreate]) -> List[PostImage]:
    if not images:
        return []

    created_images = []
    client = _client()
    for index, image in enumerate(images):
        sort_order = image.sort_order if image.sort_order is not None else index
        try:
            staged = (
                client.table(SUPABASE_IMAGES_TABLE)
                .select("*")
                .eq("image_url", image.image_path)
                .is_("post_id", "null")
                .limit(1)
                .execute()
            )
            staged_rows = staged.data or []
            if staged_rows:
                response = (
                    client.table(SUPABASE_IMAGES_TABLE)
                    .update(
                        {
                            "post_id": str(post_id),
                            "image_role": "gallery",
                            "caption": image.caption,
                            "sort_order": sort_order,
                        }
                    )
                    .eq("id", staged_rows[0]["id"])
                    .execute()
                )
            else:
                response = (
                    client.table(SUPABASE_IMAGES_TABLE)
                    .insert(
                        {
                            "post_id": str(post_id),
                            "image_role": "gallery",
                            "image_url": image.image_path,
                            "caption": image.caption,
                            "sort_order": sort_order,
                        }
                    )
                    .execute()
                )
        except APIError as exc:
            raise _db_error(exc) from exc

        created_images.extend(_image_from_row(row) for row in response.data or [])

    return created_images


def _next_image_sort_order(post_id: UUID) -> int:
    client = _client()
    try:
        response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("sort_order")
            .eq("post_id", str(post_id))
            .eq("image_role", "gallery")
            .order("sort_order", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        return 0

    return rows[0]["sort_order"] + 1


def create_post(payload: PostCreate, created_by: str) -> Post:
    _get_post_type(payload.type_id)

    row = {
        "title": payload.title,
        "slug": payload.slug or _slugify(payload.title),
        "content": payload.content,
        "type_id": payload.type_id,
        "cover_image": payload.cover_image,
        "published": payload.published,
        "featured": payload.featured,
        "created_by": created_by,
    }

    client = _client()
    try:
        response = client.table(SUPABASE_POSTS_TABLE).insert(row).execute()
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return the created post",
        )

    post_id = UUID(rows[0]["id"])
    if payload.cover_image:
        _attach_staged_cover_by_url(post_id, payload.cover_image)
    _insert_images(post_id, payload.images)
    return get_post(post_id, published_only=False)


def update_post(post_id: UUID, payload: PostUpdate) -> Post:
    update_data = payload.model_dump(exclude_unset=True, exclude={"images"})

    if "type_id" in update_data:
        _get_post_type(update_data["type_id"])
    if "slug" in update_data and update_data["slug"] is None:
        current_post = get_post(post_id, published_only=False)
        update_data["slug"] = _slugify(update_data.get("title") or current_post.title)

    if update_data:
        client = _client()
        try:
            response = (
                client.table(SUPABASE_POSTS_TABLE)
                .update(update_data)
                .eq("id", str(post_id))
                .execute()
            )
        except APIError as exc:
            raise _db_error(exc) from exc

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )
    else:
        get_post(post_id, published_only=False)

    if payload.images is not None:
        client = _client()
        try:
            client.table(SUPABASE_IMAGES_TABLE).delete().eq(
                "post_id", str(post_id)
            ).eq("image_role", "gallery").execute()
        except APIError as exc:
            raise _db_error(exc) from exc
        _insert_images(post_id, payload.images)

    if "cover_image" in update_data and update_data["cover_image"]:
        _attach_staged_cover_by_url(post_id, update_data["cover_image"])

    return get_post(post_id, published_only=False)


def delete_post(post_id: UUID) -> None:
    client = _client()
    try:
        image_response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("id")
            .eq("post_id", str(post_id))
            .execute()
        )
        for image in image_response.data or []:
            delete_image(UUID(image["id"]))

        response = (
            client.table(SUPABASE_POSTS_TABLE)
            .delete()
            .eq("id", str(post_id))
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )


def add_post_image(post_id: UUID, payload: PostImageCreate) -> PostImage:
    get_post(post_id, published_only=False)
    if payload.sort_order is None:
        payload = PostImageCreate(
            image_path=payload.image_path,
            caption=payload.caption,
            sort_order=_next_image_sort_order(post_id),
        )
    image = _insert_images(post_id, [payload])
    return image[0]


def update_post_image(
    post_id: UUID,
    image_id: UUID,
    payload: PostImageUpdate,
) -> PostImage:
    update_data = payload.model_dump(exclude_unset=True)
    if "image_path" in update_data:
        update_data["image_url"] = update_data.pop("image_path")
    if not update_data:
        return get_post_image(post_id, image_id)

    client = _client()
    try:
        response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .update(update_data)
            .eq("id", str(image_id))
            .eq("post_id", str(post_id))
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post image not found",
        )

    return _image_from_row(rows[0])


def get_post_image(post_id: UUID, image_id: UUID) -> PostImage:
    client = _client()
    try:
        response = (
            client.table(SUPABASE_IMAGES_TABLE)
            .select("*")
            .eq("id", str(image_id))
            .eq("post_id", str(post_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _db_error(exc) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post image not found",
        )

    return _image_from_row(rows[0])


def delete_post_image(post_id: UUID, image_id: UUID) -> None:
    get_post_image(post_id, image_id)
    delete_image(image_id)
