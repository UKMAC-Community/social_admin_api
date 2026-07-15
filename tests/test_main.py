import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app


def post_response(*, slug: str = "current-announcement") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "title": "Current announcement",
        "slug": slug,
        "content": "The latest content",
        "content_json": {"version": 1, "blocks": []},
        "type_id": 1,
        "cover_image": None,
        "published": True,
        "featured": False,
        "created_by": uuid4(),
        "created_at": now,
        "updated_at": now,
        "type": None,
        "images": [],
    }


class MainApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_api_overview(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], app.title)
        self.assertEqual(response.json()["documentation"], "/docs")

    def test_health_check(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": app.title,
                "version": app.version,
            },
        )

    @patch("posts.public_router.list_posts", return_value=[])
    def test_public_posts_do_not_require_a_token(self, list_posts_mock) -> None:
        response = self.client.get("/public/posts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(
            response.headers["cache-control"],
            "no-store, max-age=0, must-revalidate",
        )
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["expires"], "0")
        list_posts_mock.assert_called_once_with(
            published=True,
            featured=None,
            type_id=None,
            type_slug=None,
            limit=20,
            offset=0,
        )

    def test_public_posts_do_not_expose_write_methods(self) -> None:
        response = self.client.post("/public/posts", json={})

        self.assertEqual(response.status_code, 405)

    @patch("posts.public_router.get_post_by_slug")
    def test_public_post_by_slug_is_published_and_not_cached(
        self,
        get_post_by_slug_mock,
    ) -> None:
        post_id = uuid4()
        now = datetime.now(timezone.utc)
        get_post_by_slug_mock.return_value = {
            "id": post_id,
            "title": "Current announcement",
            "slug": "current-announcement",
            "content": "The latest content",
            "content_json": {
                "version": 1,
                "blocks": [],
            },
            "cover_image": None,
            "featured": False,
            "created_at": now,
            "updated_at": now,
            "type": None,
            "images": [],
        }

        response = self.client.get("/public/posts/slug/current-announcement")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(post_id))
        self.assertEqual(
            response.headers["cache-control"],
            "no-store, max-age=0, must-revalidate",
        )
        get_post_by_slug_mock.assert_called_once_with(
            "current-announcement",
            published_only=True,
        )

    def test_public_post_by_slug_does_not_expose_write_methods(self) -> None:
        response = self.client.post(
            "/public/posts/slug/current-announcement",
            json={},
        )

        self.assertEqual(response.status_code, 405)

    @patch("posts.router.list_posts", return_value=[])
    def test_legacy_public_post_list_is_not_cached(self, _list_posts_mock) -> None:
        response = self.client.get("/posts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["cache-control"],
            "no-store, max-age=0, must-revalidate",
        )

    @patch("posts.router.get_post_by_slug")
    def test_legacy_public_post_slug_is_not_cached(
        self,
        get_post_by_slug_mock,
    ) -> None:
        get_post_by_slug_mock.return_value = post_response()

        response = self.client.get("/posts/slug/current-announcement")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["cache-control"],
            "no-store, max-age=0, must-revalidate",
        )
        get_post_by_slug_mock.assert_called_once_with(
            "current-announcement",
            published_only=True,
        )

    @patch("posts.router.get_post")
    def test_legacy_public_post_by_id_is_not_cached(self, get_post_mock) -> None:
        payload = post_response()
        get_post_mock.return_value = payload

        response = self.client.get(f"/posts/{payload['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["cache-control"],
            "no-store, max-age=0, must-revalidate",
        )
        get_post_mock.assert_called_once_with(payload["id"], published_only=True)

    @patch("posts.public_router.list_posts")
    def test_public_posts_hide_internal_fields(self, list_posts_mock) -> None:
        post_id = uuid4()
        now = datetime.now(timezone.utc)
        list_posts_mock.return_value = [
            {
                "id": post_id,
                "title": "Public announcement",
                "slug": "public-announcement",
                "content": "Published content",
                "content_json": {
                    "version": 1,
                    "blocks": [
                        {
                            "id": "paragraph-1",
                            "type": "paragraph",
                            "data": {"text": "Published content"},
                        }
                    ],
                },
                "type_id": 1,
                "cover_image": "https://example.com/cover.webp",
                "published": True,
                "featured": False,
                "created_by": uuid4(),
                "created_at": now,
                "updated_at": now,
                "type": {
                    "id": 1,
                    "name": "Announcement",
                    "slug": "announcement",
                },
                "images": [
                    {
                        "id": uuid4(),
                        "post_id": post_id,
                        "image_role": "cover",
                        "image_url": "https://example.com/cover.webp",
                        "caption": None,
                        "sort_order": 0,
                        "created_at": now,
                    }
                ],
            }
        ]

        response = self.client.get("/public/posts")

        self.assertEqual(response.status_code, 200)
        post = response.json()[0]
        self.assertNotIn("created_by", post)
        self.assertNotIn("published", post)
        self.assertNotIn("type_id", post)
        self.assertNotIn("post_id", post["images"][0])
        self.assertNotIn("created_at", post["images"][0])
        self.assertEqual(post["content_json"]["version"], 1)
        self.assertEqual(post["content_json"]["blocks"][0]["type"], "paragraph")
        self.assertEqual(
            post["images"][0]["image_url"],
            "https://example.com/cover.webp",
        )

    def test_openapi_metadata(self) -> None:
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["info"]["title"], app.title)
        self.assertEqual(schema["info"]["version"], app.version)
        self.assertEqual(
            set(schema["paths"]),
            {
                "/auth/login",
                "/auth/refresh",
                "/auth/me",
                "/auth/me/profile",
                "/auth/users",
                "/images",
                "/images/batch",
                "/images/order",
                "/images/{image_id}",
                "/public/posts",
                "/public/posts/slug/{slug}",
                "/posts",
                "/posts/{post_id}",
                "/qr-links",
                "/qr-links/{qr_id}",
            },
        )
        self.assertEqual(set(schema["paths"]["/posts"]), {"get", "post"})
        self.assertEqual(set(schema["paths"]["/public/posts"]), {"get"})
        self.assertEqual(
            set(schema["paths"]["/public/posts/slug/{slug}"]),
            {"get"},
        )
        self.assertEqual(
            set(schema["paths"]["/posts/{post_id}"]),
            {"get", "patch", "delete"},
        )
        self.assertEqual(set(schema["paths"]["/images"]), {"post", "patch"})
        self.assertEqual(set(schema["paths"]["/images/batch"]), {"post"})
        self.assertEqual(set(schema["paths"]["/images/order"]), {"patch"})
        self.assertEqual(
            set(schema["paths"]["/images/{image_id}"]),
            {"patch", "delete"},
        )
        self.assertEqual(
            set(schema["paths"]["/qr-links"]),
            {"get", "post"},
        )
        self.assertEqual(
            set(schema["paths"]["/qr-links/{qr_id}"]),
            {"get", "patch", "delete"},
        )


if __name__ == "__main__":
    unittest.main()
