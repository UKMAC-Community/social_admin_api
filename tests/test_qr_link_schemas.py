import unittest

from pydantic import ValidationError

from qr_links.schemas import QrLinkCreate, QrLinkUpdate


class QrLinkSchemaTests(unittest.TestCase):
    def test_create_cleans_name(self) -> None:
        payload = QrLinkCreate(
            qr_name="  Main entrance  ",
            qr_url="https://example.com/posts/example",
        )

        self.assertEqual(payload.qr_name, "Main entrance")

    def test_update_requires_at_least_one_change(self) -> None:
        with self.assertRaises(ValidationError):
            QrLinkUpdate()


if __name__ == "__main__":
    unittest.main()
