"""One-off backfill: regenerate the legacy `content` text field for every post
from its `content_json`, using the fixed `_legacy_content_from_blocks`. This
removes uploaded-filename text (e.g. "telegram-cloud-document-....jpg") that
leaked into `content` via image alt-text fallback before that bug was fixed.

Usage: python -m scripts.backfill_legacy_content [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.config import SUPABASE_POSTS_TABLE
from auth.providers.supabase import get_supabase_admin_client
from posts.schemas import PostContent
from posts.service import _legacy_content_from_blocks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = get_supabase_admin_client()
    response = (
        client.table(SUPABASE_POSTS_TABLE)
        .select("id,title,content,content_json")
        .execute()
    )
    rows = response.data or []

    changed = 0
    for row in rows:
        content_json = PostContent.model_validate(row.get("content_json") or {"version": 1, "blocks": []})
        new_content = _legacy_content_from_blocks(content_json)
        old_content = row.get("content") or ""

        if new_content == old_content:
            continue

        changed += 1
        print(f"post {row['id']} ({row.get('title')!r}):")
        print(f"  old: {old_content[:120]!r}")
        print(f"  new: {new_content[:120]!r}")

        if not args.dry_run:
            client.table(SUPABASE_POSTS_TABLE).update({"content": new_content}).eq(
                "id", row["id"]
            ).execute()

    print(f"\n{changed} of {len(rows)} posts {'would be' if args.dry_run else ''} updated")


if __name__ == "__main__":
    main()
