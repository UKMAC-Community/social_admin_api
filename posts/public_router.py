from typing import List, Optional

from fastapi import APIRouter, Query, Response

from posts.cache_headers import set_no_store_headers
from posts.schemas import PublicPost
from posts.service import get_post_by_slug, list_posts


router = APIRouter()


@router.get(
    "",
    response_model=List[PublicPost],
    summary="List public posts",
    description=(
        "Return published posts without requiring an access token. This public "
        "router exposes no create, update, or delete operations."
    ),
)
def public_posts(
    response: Response,
    featured: Optional[bool] = None,
    type_id: Optional[int] = None,
    type_slug: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    set_no_store_headers(response)
    return list_posts(
        published=True,
        featured=featured,
        type_id=type_id,
        type_slug=type_slug,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/slug/{slug}",
    response_model=PublicPost,
    summary="Get public post by slug",
    description="Return one published post without requiring an access token.",
)
def public_post_by_slug(slug: str, response: Response):
    set_no_store_headers(response)
    return get_post_by_slug(slug, published_only=True)
