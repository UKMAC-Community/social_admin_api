import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from posts.schemas import PostContent, PostCreate, PostUpdate
from posts.service import (
    _content_image_ids,
    _legacy_content_from_blocks,
    _validate_content_image_references,
    create_post,
    delete_image,
    update_post,
)


class PostContentSchemaTests(unittest.TestCase):
    def test_accepts_supported_v1_blocks_and_media_id_alias(self) -> None:
        first_image_id = uuid4()
        second_image_id = uuid4()
        content = PostContent.model_validate(
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "heading-1",
                        "type": "heading",
                        "data": {"text": "Article heading", "level": 2},
                    },
                    {
                        "id": "paragraph-1",
                        "type": "paragraph",
                        "data": {"text": "Article paragraph"},
                    },
                    {
                        "id": "image-1",
                        "type": "image",
                        "data": {
                            "media_id": str(first_image_id),
                            "alt": "Wide photo",
                            "alignment": "wide",
                        },
                    },
                    {
                        "id": "gallery-1",
                        "type": "gallery",
                        "data": {
                            "layout": "grid",
                            "columns": 2,
                            "images": [
                                {"mediaId": str(first_image_id), "alt": "First"},
                                {"media_id": str(second_image_id), "alt": "Second"},
                            ],
                        },
                    },
                ],
            }
        )

        self.assertEqual(content.version, 1)
        self.assertEqual(_content_image_ids(content), [first_image_id, second_image_id])
        self.assertEqual(content.blocks[2].data.alignment, "wide")
        self.assertEqual(
            _legacy_content_from_blocks(content),
            "Article heading\n\nArticle paragraph\n\nWide photo\n\nFirst\n\nSecond",
        )

    def test_legacy_content_skips_filename_like_alt_text(self) -> None:
        image_id = uuid4()
        second_image_id = uuid4()
        content = PostContent.model_validate(
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "paragraph-1",
                        "type": "paragraph",
                        "data": {"text": "Real caption text"},
                    },
                    {
                        "id": "image-1",
                        "type": "image",
                        "data": {
                            "media_id": str(image_id),
                            "alt": "telegram-cloud-document-5-6251306229105173422.jpg",
                        },
                    },
                    {
                        "id": "gallery-1",
                        "type": "gallery",
                        "data": {
                            "layout": "grid",
                            "columns": 2,
                            "images": [
                                {"media_id": str(image_id), "alt": "IMG_20240101.png"},
                                {
                                    "media_id": str(second_image_id),
                                    "alt": "A meaningful description",
                                },
                            ],
                        },
                    },
                ],
            }
        )

        self.assertEqual(
            _legacy_content_from_blocks(content),
            "Real caption text\n\nA meaningful description",
        )

    def test_rejects_invalid_block_documents(self) -> None:
        image_id = uuid4()
        invalid_documents = [
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "paragraph-1",
                        "type": "paragraph",
                        "data": {"text": "   "},
                    }
                ],
            },
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "same-id",
                        "type": "paragraph",
                        "data": {"text": "First"},
                    },
                    {
                        "id": "same-id",
                        "type": "paragraph",
                        "data": {"text": "Second"},
                    },
                ],
            },
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "heading-1",
                        "type": "heading",
                        "data": {"text": "Invalid level", "level": 1},
                    }
                ],
            },
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "gallery-1",
                        "type": "gallery",
                        "data": {
                            "layout": "grid",
                            "columns": 5,
                            "images": [
                                {"media_id": str(image_id)},
                                {"media_id": str(uuid4())},
                            ],
                        },
                    }
                ],
            },
        ]

        for document in invalid_documents:
            with self.subTest(document=document), self.assertRaises(ValidationError):
                PostContent.model_validate(document)

    def test_preserves_image_crop_and_size(self) -> None:
        image_id = uuid4()
        content = PostContent.model_validate(
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "adjusted-image",
                        "type": "image",
                        "data": {
                            "media_id": str(image_id),
                            "alt": "Manually cropped image",
                            "alignment": "center",
                            "crop": True,
                            "crop_ratio": 1.2,
                            "crop_x": 30,
                            "crop_y": 70,
                            "width": 45,
                        },
                    }
                ],
            }
        )

        image_data = content.model_dump(mode="json")["blocks"][0]["data"]
        self.assertTrue(image_data["crop"])
        self.assertEqual(image_data["crop_ratio"], 1.2)
        self.assertEqual(image_data["crop_x"], 30)
        self.assertEqual(image_data["crop_y"], 70)
        self.assertEqual(image_data["width"], 45)

    def test_create_requires_legacy_or_structured_content(self) -> None:
        with self.assertRaises(ValidationError):
            PostCreate(title="Missing content", type_id=1)

        payload = PostCreate(
            title="Empty draft",
            type_id=1,
            content_json=PostContent(),
        )
        self.assertEqual(payload.content_json.blocks, [])


class PostContentServiceTests(unittest.TestCase):
    def test_create_dual_writes_structured_and_legacy_content(self) -> None:
        post_id = uuid4()
        content = PostContent.model_validate(
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "heading-1",
                        "type": "heading",
                        "data": {"text": "A heading", "level": 2},
                    },
                    {
                        "id": "paragraph-1",
                        "type": "paragraph",
                        "data": {"text": "A paragraph"},
                    },
                ],
            }
        )
        payload = PostCreate(title="Structured post", type_id=1, content_json=content)
        client = MagicMock()
        table = client.table.return_value
        table.insert.return_value.execute.return_value = SimpleNamespace(
            data=[{"id": str(post_id)}]
        )
        expected_post = object()

        with (
            patch("posts.service._get_post_type"),
            patch("posts.service._client", return_value=client),
            patch("posts.service._insert_images"),
            patch("posts.service.get_post", return_value=expected_post),
        ):
            result = create_post(payload, str(uuid4()))

        inserted_row = table.insert.call_args.args[0]
        self.assertEqual(inserted_row["content"], "A heading\n\nA paragraph")
        self.assertEqual(inserted_row["content_json"]["version"], 1)
        self.assertEqual(len(inserted_row["content_json"]["blocks"]), 2)
        self.assertIs(result, expected_post)

    def test_content_images_must_be_owned_staged_or_attached_to_post(self) -> None:
        image_id = uuid4()
        editor_id = uuid4()
        post_id = uuid4()
        content = PostContent.model_validate(
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "image-1",
                        "type": "image",
                        "data": {"media_id": str(image_id), "alt": "Photo"},
                    }
                ],
            }
        )

        allowed_rows = [
            {
                "id": str(image_id),
                "post_id": None,
                "created_by": str(editor_id),
                "image_url": "https://example.com/image.webp",
            },
            {
                "id": str(image_id),
                "post_id": str(post_id),
                "created_by": str(uuid4()),
                "image_url": "https://example.com/image.webp",
            },
        ]

        for row in allowed_rows:
            client = MagicMock()
            query = client.table.return_value.select.return_value.in_.return_value
            query.execute.return_value = SimpleNamespace(data=[row])
            with patch("posts.service._client", return_value=client):
                rows = _validate_content_image_references(
                    content,
                    editor_id=str(editor_id),
                    post_id=post_id,
                )
            self.assertEqual(rows, [row])

        client = MagicMock()
        query = client.table.return_value.select.return_value.in_.return_value
        query.execute.return_value = SimpleNamespace(
            data=[
                {
                    "id": str(image_id),
                    "post_id": None,
                    "created_by": str(uuid4()),
                    "image_url": "https://example.com/image.webp",
                }
            ]
        )
        with (
            patch("posts.service._client", return_value=client),
            self.assertRaises(HTTPException) as raised,
        ):
            _validate_content_image_references(
                content,
                editor_id=str(editor_id),
                post_id=post_id,
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_update_dual_writes_structured_and_legacy_content(self) -> None:
        post_id = uuid4()
        content = PostContent.model_validate(
            {
                "version": 1,
                "blocks": [
                    {
                        "id": "paragraph-1",
                        "type": "paragraph",
                        "data": {"text": "Updated paragraph"},
                    }
                ],
            }
        )
        client = MagicMock()
        table = client.table.return_value
        update_query = table.update.return_value.eq.return_value
        update_query.execute.return_value = SimpleNamespace(data=[{"id": str(post_id)}])
        expected_post = object()

        with (
            patch("posts.service._client", return_value=client),
            patch("posts.service.get_post", return_value=expected_post),
        ):
            result = update_post(
                post_id,
                payload=PostUpdate(content_json=content),
                editor_id=str(uuid4()),
            )

        updated_row = table.update.call_args.args[0]
        self.assertEqual(updated_row["content"], "Updated paragraph")
        self.assertEqual(updated_row["content_json"]["version"], 1)
        self.assertIs(result, expected_post)

    def test_delete_rejects_an_image_referenced_by_content(self) -> None:
        image_id = uuid4()
        post_id = uuid4()
        image_client = MagicMock()
        image_query = image_client.table.return_value
        image_result = SimpleNamespace(
            data=[
                {
                    "id": str(image_id),
                    "post_id": str(post_id),
                    "storage_path": "posts/gallery/image.webp",
                }
            ]
        )
        image_eq_query = image_query.select.return_value.eq.return_value
        image_limit_query = image_eq_query.limit.return_value
        image_limit_query.execute.return_value = image_result

        post_client = MagicMock()
        post_query = post_client.table.return_value
        post_result = SimpleNamespace(
            data=[
                {
                    "content_json": {
                        "version": 1,
                        "blocks": [
                            {
                                "id": "image-1",
                                "type": "image",
                                "data": {"media_id": str(image_id)},
                            }
                        ],
                    }
                }
            ]
        )
        post_eq_query = post_query.select.return_value.eq.return_value
        post_limit_query = post_eq_query.limit.return_value
        post_limit_query.execute.return_value = post_result

        with (
            patch("posts.service._client", side_effect=[image_client, post_client]),
            self.assertRaises(HTTPException) as raised,
        ):
            delete_image(image_id)

        self.assertEqual(raised.exception.status_code, 409)
        image_client.storage.from_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
