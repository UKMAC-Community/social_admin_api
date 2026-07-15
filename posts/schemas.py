from datetime import datetime
from typing import Annotated, List, Literal, Optional, Union
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class PostType(BaseModel):
    id: int
    name: str
    slug: str


class PostImageBase(BaseModel):
    image_path: str = Field(
        min_length=1,
        validation_alias=AliasChoices("image_url", "image_path"),
        serialization_alias="image_url",
        description="Public URL returned by the image upload endpoint.",
        examples=[
            "https://your-project-ref.supabase.co/storage/v1/object/public/"
            "website/posts/gallery/example.jpg"
        ],
    )
    caption: Optional[str] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class PostImageCreate(PostImageBase):
    pass


class PostImageUpdate(BaseModel):
    image_path: Optional[str] = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("image_url", "image_path"),
        serialization_alias="image_url",
        description="Public URL returned by the image upload endpoint.",
        examples=[
            "https://your-project-ref.supabase.co/storage/v1/object/public/"
            "website/posts/gallery/example.jpg"
        ],
    )
    caption: Optional[str] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class PostImage(BaseModel):
    id: UUID
    post_id: UUID
    image_role: Literal["cover", "gallery"]
    image_path: str = Field(
        validation_alias=AliasChoices("image_url", "image_path"),
        serialization_alias="image_url",
        description="Public URL of the gallery image.",
    )
    caption: Optional[str] = None
    sort_order: int = 0
    created_at: datetime


class PostImageUpload(BaseModel):
    image_id: UUID
    bucket: str
    path: str
    url: str
    content_type: str


class PostImageAttach(BaseModel):
    post_id: UUID
    image_role: Optional[Literal["cover", "gallery"]] = None
    caption: Optional[str] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class ImageAttachRequest(BaseModel):
    post_id: UUID
    caption: Optional[str] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class ImageBatchAttachRequest(BaseModel):
    post_id: UUID
    image_ids: List[UUID] = Field(min_length=1)


class ParagraphBlockData(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)

    @field_validator("text")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Paragraph text cannot be blank")
        return value


class HeadingBlockData(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    level: Literal[2, 3, 4] = 2

    @field_validator("text")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Heading text cannot be blank")
        return value


class ContentImageReference(BaseModel):
    media_id: UUID = Field(
        validation_alias=AliasChoices("media_id", "mediaId"),
        description="UUID returned by the image upload endpoint.",
    )
    alt: str = Field(default="", max_length=500)
    caption: Optional[str] = Field(default=None, max_length=1_000)


class ImageBlockData(ContentImageReference):
    alignment: Literal["center", "wide"] = "center"
    crop: bool = False
    crop_ratio: Optional[float] = Field(default=None, ge=0.1, le=10)
    crop_x: Optional[float] = Field(default=None, ge=0, le=100)
    crop_y: Optional[float] = Field(default=None, ge=0, le=100)
    width: Optional[float] = Field(default=None, ge=25, le=100)


class GalleryBlockData(BaseModel):
    layout: Literal["grid"] = "grid"
    columns: int = Field(default=2, ge=2, le=4)
    images: List[ContentImageReference] = Field(min_length=2, max_length=24)


class ParagraphBlock(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["paragraph"]
    data: ParagraphBlockData


class HeadingBlock(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["heading"]
    data: HeadingBlockData


class ImageBlock(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["image"]
    data: ImageBlockData


class GalleryBlock(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["gallery"]
    data: GalleryBlockData


ContentBlock = Annotated[
    Union[ParagraphBlock, HeadingBlock, ImageBlock, GalleryBlock],
    Field(discriminator="type"),
]


class PostContent(BaseModel):
    version: Literal[1] = 1
    blocks: List[ContentBlock] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_unique_block_ids(self):
        block_ids = [block.id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("Content block IDs must be unique")
        return self


class PostCreate(BaseModel):
    title: str = Field(min_length=1)
    slug: Optional[str] = Field(default=None, min_length=1)
    content: Optional[str] = Field(default=None, min_length=1)
    content_json: Optional[PostContent] = None
    type_id: int
    cover_image: Optional[str] = None
    published: bool = False
    featured: bool = False
    images: List[PostImageCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self):
        if self.content is None and self.content_json is None:
            raise ValueError("Either content or content_json is required")
        return self


class PostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    slug: Optional[str] = Field(default=None, min_length=1)
    content: Optional[str] = Field(default=None, min_length=1)
    content_json: Optional[PostContent] = None
    type_id: Optional[int] = None
    cover_image: Optional[str] = None
    published: Optional[bool] = None
    featured: Optional[bool] = None
    images: Optional[List[PostImageCreate]] = None


class Post(BaseModel):
    id: UUID
    title: str
    slug: str
    content: str
    content_json: PostContent = Field(default_factory=PostContent)
    type_id: int
    cover_image: Optional[str] = None
    published: bool
    featured: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    type: Optional[PostType] = None
    images: List[PostImage] = Field(default_factory=list)


class PublicPostImage(BaseModel):
    id: UUID
    image_role: Literal["cover", "gallery"]
    image_path: str = Field(
        validation_alias=AliasChoices("image_url", "image_path"),
        serialization_alias="image_url",
        description="Public URL of the post image.",
    )
    caption: Optional[str] = None
    sort_order: int = 0


class PublicPost(BaseModel):
    id: UUID
    title: str
    slug: str
    content: str
    content_json: PostContent = Field(default_factory=PostContent)
    cover_image: Optional[str] = None
    featured: bool
    created_at: datetime
    updated_at: datetime
    type: Optional[PostType] = None
    images: List[PublicPostImage] = Field(default_factory=list)
