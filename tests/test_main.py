import unittest

from fastapi.testclient import TestClient

from main import app


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
                "/images/{image_id}",
                "/posts",
                "/posts/{post_id}",
                "/qr-links",
                "/qr-links/{qr_id}",
            },
        )
        self.assertEqual(set(schema["paths"]["/posts"]), {"get", "post"})
        self.assertEqual(
            set(schema["paths"]["/posts/{post_id}"]),
            {"get", "patch", "delete"},
        )
        self.assertEqual(set(schema["paths"]["/images"]), {"post", "patch"})
        self.assertEqual(set(schema["paths"]["/images/batch"]), {"post"})
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
