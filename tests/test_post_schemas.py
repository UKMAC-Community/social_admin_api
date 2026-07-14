import unittest
from datetime import datetime, timezone
from uuid import uuid4

from posts.schemas import PostImage, PostImageCreate, PostImageUpload


class PostImageSchemaTests(unittest.TestCase):
    def test_create_accepts_frontend_image_url(self) -> None:
        image = PostImageCreate(image_url="https://example.com/image.jpg")

        self.assertEqual(image.image_path, "https://example.com/image.jpg")
        self.assertEqual(
            image.model_dump(by_alias=True)["image_url"],
            "https://example.com/image.jpg",
        )

    def test_create_still_accepts_legacy_image_path(self) -> None:
        image = PostImageCreate(image_path="https://example.com/legacy.jpg")

        self.assertEqual(image.image_path, "https://example.com/legacy.jpg")

    def test_response_uses_frontend_image_url(self) -> None:
        image = PostImage(
            id=uuid4(),
            post_id=uuid4(),
            image_role="gallery",
            image_path="https://example.com/image.jpg",
            sort_order=0,
            created_at=datetime.now(timezone.utc),
        )

        payload = image.model_dump(mode="json", by_alias=True)
        self.assertEqual(payload["image_url"], "https://example.com/image.jpg")
        self.assertEqual(payload["image_role"], "gallery")
        self.assertNotIn("image_path", payload)

    def test_upload_includes_public_url(self) -> None:
        upload = PostImageUpload(
            image_id=uuid4(),
            bucket="website",
            path="posts/gallery/image.jpg",
            url="https://example.com/image.jpg",
            content_type="image/jpeg",
        )

        self.assertEqual(upload.url, "https://example.com/image.jpg")


if __name__ == "__main__":
    unittest.main()
