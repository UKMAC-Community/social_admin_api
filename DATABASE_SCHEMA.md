# UKMAC Database Schema

Last reviewed: 2026-07-15

## Scope

This document describes the database structure defined by:

- `supabase/schema.sql`
- Every SQL file in `supabase/migrations/`
- The database fields used by the `auth`, `posts`, and `qr_links` services

It describes the expected schema after all repository migrations have run. The
live Supabase project can differ if a migration has not been applied.

## Table inventory

| Table | Owner | Status | Purpose |
| --- | --- | --- | --- |
| `auth.users` | Supabase Auth | Managed | Authentication identities and login metadata |
| `public.profiles` | Application | Active | Application role and display information for each user |
| `public.post_types` | Application | Active | Lookup table for post categories |
| `public.posts` | Application | Active | Website post content and publishing state |
| `public.images` | Application | Active | Staged and attached post images |
| `public.qr_links` | Application | Active | Saved names and URLs used to regenerate QR codes |
| `public.post_images` | Application | Legacy | Old post-image table retained during the image-table rollout |
| `storage.buckets` | Supabase Storage | Managed | Storage bucket configuration |
| `storage.objects` | Supabase Storage | Managed | Uploaded file metadata |

There are five active application-owned tables, one legacy application table,
and three relevant Supabase-managed tables.

## Relationships

```mermaid
erDiagram
    AUTH_USERS ||--o| PROFILES : "has profile"
    AUTH_USERS ||--o{ POSTS : "creates"
    AUTH_USERS ||--o{ IMAGES : "uploads"
    AUTH_USERS ||--o{ QR_LINKS : "creates"
    POST_TYPES ||--o{ POSTS : "categorizes"
    POSTS ||--o{ IMAGES : "contains"
    POSTS ||--o{ POST_IMAGES_LEGACY : "contained"
    STORAGE_BUCKETS ||--o{ STORAGE_OBJECTS : "contains"

    AUTH_USERS {
        uuid id PK
        text email
        jsonb raw_user_meta_data
    }
    PROFILES {
        uuid id PK_FK
        text email
        text role
        text full_name
        timestamptz created_at
        timestamptz updated_at
    }
    POST_TYPES {
        integer id PK
        text name
        text slug UK
    }
    POSTS {
        uuid id PK
        text title
        text slug UK
        text content
        jsonb content_json
        integer type_id FK
        text cover_image
        boolean published
        boolean featured
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }
    IMAGES {
        uuid id PK
        uuid post_id FK
        text image_role
        text image_url
        text storage_bucket
        text storage_path
        text original_filename
        text content_type
        bigint size_bytes
        text caption
        integer sort_order
        uuid created_by FK
        timestamptz created_at
    }
    QR_LINKS {
        uuid qr_id PK
        text qr_name
        text qr_url
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }
    POST_IMAGES_LEGACY {
        uuid id PK
        uuid post_id FK
        text image_path
        text caption
        integer sort_order
        timestamptz created_at
    }
```

`images.post_id` is nullable because an uploaded image is staged before it is
attached to a post. `qr_links` intentionally has no relationship to `posts`.

## `auth.users` — Supabase authentication users

This is a Supabase-managed table. The application should not recreate or
directly alter its full schema. Relevant fields used by this project are:

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `uuid` | User identity referenced by application tables |
| `email` | `text` | Login email copied into `public.profiles` |
| `raw_user_meta_data` | `jsonb` | Supplies `role` and `full_name` when the profile trigger runs |

Referenced by:

- `profiles.id` with `ON DELETE CASCADE`
- `posts.created_by` with `ON DELETE SET NULL`
- `images.created_by` with `ON DELETE SET NULL`
- `qr_links.created_by` with `ON DELETE SET NULL`

## `public.profiles` — application users and roles

One profile is associated with one Supabase Auth user.

| Column | Type | Null | Default | Rules and purpose |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | — | Primary key; foreign key to `auth.users.id`; cascades on user deletion |
| `email` | `text` | Yes | — | Profile copy of the authentication email |
| `role` | `text` | No | `'manager'` | Authorization role |
| `full_name` | `text` | Yes | — | User display name |
| `created_at` | `timestamptz` | No | `now()` | Creation time |
| `updated_at` | `timestamptz` | No | `now()` | Updated automatically before every update |

### Constraints and indexes

- Primary key: `id`
- Foreign key: `id -> auth.users.id ON DELETE CASCADE`
- Current migration check: `role IN ('admin', 'manager')`
- Index: `profiles_role_idx (role)`

### Automation

- `auth_users_create_profile` runs after an `auth.users` insert.
- `create_profile_for_new_user()` copies email, role, and full name from the new
  Auth user. Any role other than `admin` or `manager` currently becomes
  `manager`.
- `profiles_set_updated_at` refreshes `updated_at` before an update.

### Row-level security

- RLS is enabled.
- Policy `Users can read own profile` permits a user to select the row where
  `auth.uid() = id`.
- No direct client insert, update, or delete policy is defined.
- Backend administrative operations use the Supabase service-role client.

### Role access model used by the backend

| Role | Content dashboard | Staff dashboard | User management |
| --- | :---: | :---: | :---: |
| `superadmin` | Yes | Yes | Yes |
| `admin` | Yes | Yes | Yes |
| `content_manager` | Yes | No | No |
| `staff_manager` | No | Yes | No |
| `manager` (legacy) | Yes | No | No |

This is the Python authorization model. The database constraint does not yet
support all of these values; see the schema differences section below.

## `public.post_types` — post category lookup

| Column | Type | Null | Default | Rules and purpose |
| --- | --- | --- | --- | --- |
| `id` | `integer` | No | Identity | Primary key |
| `name` | `text` | No | — | Human-readable category name |
| `slug` | `text` | No | — | Unique URL/API-safe category identifier |

### Seeded rows

| ID | Name | Slug |
| ---: | --- | --- |
| `1` | Announcement | `announcement` |
| `2` | News | `news` |
| `3` | Hiring | `hiring` |
| `4` | Event | `event` |

### Security

- RLS is enabled.
- Policy `Anyone can read post types` allows all selects.
- Writes are performed through the backend service-role client.

## `public.posts` — website content

| Column | Type | Null | Default | Rules and purpose |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | Primary key |
| `title` | `text` | No | — | Display title |
| `slug` | `text` | No | — | Unique public URL slug; generated from title when omitted |
| `content` | `text` | No | — | Legacy plain-text post body, kept in sync for existing clients |
| `content_json` | `jsonb` | No | `{"version":1,"blocks":[]}` | Versioned paragraph, heading, image, and gallery blocks |
| `type_id` | `integer` | No | — | Foreign key to `post_types.id` |
| `cover_image` | `text` | Yes | — | Denormalized public URL of the current cover image |
| `published` | `boolean` | No | `false` | Whether public APIs and RLS may expose the post |
| `featured` | `boolean` | No | `false` | Whether the post is highlighted |
| `created_by` | `uuid` | Yes | — | Creator; foreign key to `auth.users.id`; becomes null if the user is deleted |
| `created_at` | `timestamptz` | No | `now()` | Creation time |
| `updated_at` | `timestamptz` | No | `now()` | Updated automatically before every update |

### Constraints and indexes

- Primary key: `id`
- Unique constraint: `slug`
- `content_json` must be an object with version `1` and an array named `blocks`
- Foreign key: `type_id -> post_types.id` using PostgreSQL's default
  `NO ACTION` behavior
- Foreign key: `created_by -> auth.users.id ON DELETE SET NULL`
- Index: `posts_type_id_idx (type_id)`
- Index: `posts_published_created_at_idx (published, created_at DESC)`
- Index: `posts_featured_idx (featured)`

### Automation and deletion

- `posts_set_updated_at` refreshes `updated_at` before an update.
- Deleting a post cascades to attached rows in `images` and the legacy
  `post_images` table.
- The backend first deletes attached storage objects before deleting the post.
- `cover_image` duplicates the URL of the `images` row whose role is `cover`.

### Row-level security

- RLS is enabled.
- Policy `Anyone can read published posts` allows select only when
  `published = true`.
- Draft access and all writes go through the authorized backend service.

### Structured article content

- `content_json` version 1 supports `paragraph`, `heading`, `image`, and
  grid `gallery` blocks in their displayed order.
- Image and gallery blocks reference `images.id` using `media_id`; image files
  and public URLs are not stored inside the JSON document.
- The backend rejects deletion of an image while a content block still
  references it. Remove the block reference and save the post first.
- `content` remains as a plain-text compatibility field. Structured writes
  generate its value automatically, while legacy text-only writes are stored
  as a version 1 paragraph block in `content_json`.

## `public.images` — staged, cover, and gallery images

| Column | Type | Null | Default | Rules and purpose |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | Primary key; returned to the frontend as `image_id` |
| `post_id` | `uuid` | Yes | — | Parent post; null while the upload is staged; cascades when post is deleted |
| `image_role` | `text` | No | `'gallery'` | Must be `cover` or `gallery` |
| `image_url` | `text` | No | — | Public image URL returned to clients |
| `storage_bucket` | `text` | No | `'website'` | Supabase Storage bucket |
| `storage_path` | `text` | Yes | — | Object path used to delete the physical file |
| `original_filename` | `text` | Yes | — | Name supplied during upload |
| `content_type` | `text` | Yes | — | Uploaded MIME type |
| `size_bytes` | `bigint` | Yes | — | File size; must be zero or greater when present |
| `caption` | `text` | Yes | — | Optional image caption |
| `sort_order` | `integer` | No | `0` | Gallery order; must be zero or greater |
| `created_by` | `uuid` | Yes | — | Uploader; becomes null if the Auth user is deleted |
| `created_at` | `timestamptz` | No | `now()` | Upload-record creation time |

### Constraints and indexes

- `image_role IN ('cover', 'gallery')`
- `size_bytes IS NULL OR size_bytes >= 0`
- `sort_order >= 0`
- Foreign key: `post_id -> posts.id ON DELETE CASCADE`
- Foreign key: `created_by -> auth.users.id ON DELETE SET NULL`
- Index: `images_post_id_sort_order_idx (post_id, sort_order)`
- Index: `images_created_by_idx (created_by)`
- Partial unique index `images_one_cover_per_post_idx` allows only one attached
  cover per post.

### Image lifecycle

1. Uploading creates an `images` row with `post_id = NULL`.
2. Attaching sets `post_id`, assigns the first image as `cover`, and assigns the
   remaining images as `gallery`.
3. Reordering makes the first selected image the cover and writes gallery
   `sort_order` values beginning at zero.
4. Removing a cover promotes the first remaining image and updates
   `posts.cover_image`.
5. Deleting through the backend also removes the object from Supabase Storage
   when `storage_path` is present.

### Row-level security

- RLS is enabled.
- Policy `Anyone can read images for published posts` permits select only when
  the related post exists and is published.
- Staged images and images belonging to draft posts are not publicly readable
  through direct table access.

## `public.qr_links` — saved QR destinations

The database stores a name and URL only. QR image data is generated by the
frontend and is not stored.

| Column | Type | Null | Default | Rules and purpose |
| --- | --- | --- | --- | --- |
| `qr_id` | `uuid` | No | `gen_random_uuid()` | Primary key |
| `qr_name` | `text` | No | — | Trimmed display name between 1 and 120 characters |
| `qr_url` | `text` | No | — | HTTP or HTTPS destination URL |
| `created_by` | `uuid` | Yes | — | Creator; becomes null if the Auth user is deleted |
| `created_at` | `timestamptz` | No | `now()` | Creation time |
| `updated_at` | `timestamptz` | No | `now()` | Updated automatically before every update |

### Constraints and indexes

- `char_length(trim(qr_name)) BETWEEN 1 AND 120`
- `qr_url` must match `^https?://` case-insensitively
- Foreign key: `created_by -> auth.users.id ON DELETE SET NULL`
- Index: `qr_links_created_by_idx (created_by)`
- There is currently no uniqueness constraint on `qr_name` or `qr_url`.
- There is no `post_id`; the migration removes it if it exists.

### Automation and security

- `qr_links_set_updated_at` refreshes `updated_at` before an update.
- RLS is enabled, but no select or write policy is currently defined.
- The authenticated API works because it uses the service-role client after
  checking the user's content-dashboard role.

## `public.post_images` — legacy image table

This table was replaced by `public.images`. The image migration copies its rows
into `images`, but intentionally keeps the old table during rollout.

| Column | Type | Null | Default | Rules and purpose |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | Primary key |
| `post_id` | `uuid` | No | — | Foreign key to `posts.id`; cascades on post deletion |
| `image_path` | `text` | No | — | Legacy image URL/path; renamed from `image_url` when needed |
| `caption` | `text` | Yes | — | Optional caption |
| `sort_order` | `integer` | No | `0` | Display order |
| `created_at` | `timestamptz` | No | `now()` | Creation time |

Additional details:

- Index: `post_images_post_id_sort_order_idx (post_id, sort_order)`
- RLS policy permits reads only for images whose parent post is published.
- Current Python services use `public.images`, not `public.post_images`.
- Drop this table only after confirming that every environment uses the new
  image service and that migrated row counts match.

## Supabase Storage

### `storage.buckets`

The migration upserts one application bucket:

| ID | Name | Public |
| --- | --- | --- |
| `website` | `website` | `true` |

### `storage.objects`

Supabase manages the complete table structure. The application writes files to
paths similar to `posts/gallery/<generated-file-name>` and stores the matching
bucket and path in `public.images`.

Policy `Anyone can read website files` permits selects where
`bucket_id = 'website'`.

## Database functions and triggers

| Function or trigger | Runs on | Purpose |
| --- | --- | --- |
| `public.set_updated_at()` | Shared function | Replaces `NEW.updated_at` with `now()` |
| `profiles_set_updated_at` | `profiles` before update | Maintains profile update time |
| `posts_set_updated_at` | `posts` before update | Maintains post update time |
| `qr_links_set_updated_at` | `qr_links` before update | Maintains QR-link update time |
| `public.create_profile_for_new_user()` | Shared function | Builds or updates a profile from a new Auth user |
| `auth_users_create_profile` | `auth.users` after insert | Calls the profile creation function |

The `pgcrypto` extension supplies `gen_random_uuid()`.

## Row-level security summary

| Table | RLS | Direct access currently allowed |
| --- | --- | --- |
| `profiles` | Enabled | A user can select their own profile |
| `post_types` | Enabled | Anyone can select |
| `posts` | Enabled | Anyone can select published rows |
| `images` | Enabled | Anyone can select images attached to published posts |
| `qr_links` | Enabled | No direct access policy |
| `post_images` | Enabled | Anyone can select legacy images attached to published posts |
| `storage.objects` | Enabled by Supabase | Anyone can read files in the public `website` bucket |

No application-table policy grants direct insert, update, or delete access.
Administrative writes are made by the backend service-role client after API role
checks. The service-role key must never be exposed to a browser.

## Important schema differences to resolve

### 1. Role constraint does not match the Python role model

`auth/roles.py` supports:

- `superadmin`
- `admin`
- `content_manager`
- `staff_manager`
- `manager` as a legacy role

The current `profiles.role` migration and profile trigger permit only:

- `admin`
- `manager`

As a result, creating a `superadmin`, `content_manager`, or `staff_manager` can
fail the database check, and the Auth-user trigger can silently convert the role
to `manager`. Add a migration that updates both the role check and
`create_profile_for_new_user()` before using the expanded role model.

### 2. `supabase/schema.sql` is not a complete snapshot

The snapshot contains `post_types`, `posts`, `images`, and `qr_links`, but it
does not create `profiles` or describe the retained `post_images` table. Use the
migrations when auditing an existing database, or update the snapshot so a new
environment receives the same schema.

### 3. Two representations of the cover image exist

The cover is represented by both:

- `posts.cover_image`
- The `images` row with `image_role = 'cover'`

The backend synchronizes them, but direct database edits can make them
inconsistent. Treat the `images` row as the ordered media record and
`posts.cover_image` as a denormalized public URL.

### 4. The legacy image table still exists

`post_images` is intentionally retained. Plan a later cleanup migration after
the rollout is verified.

### 5. QR links allow duplicates

The API has handling for PostgreSQL unique-conflict errors, but the table has no
unique constraint on `qr_name` or `qr_url`. Add one only if duplicate saved URLs
are not allowed by the product requirements.

### 6. The public storage bucket bypasses post visibility

The `website` bucket is public. Even though table RLS hides staged images and
images belonging to draft posts, anyone who knows a file's public Storage URL
can read it. Use a private bucket and signed URLs if draft media must remain
private.

### 7. Saved QR links are shared across content users

The backend authorizes the user's role but does not filter QR queries or updates
by `created_by`. Every permitted content-dashboard user can currently list,
update, and delete every saved QR link.

### 8. Replacing a cover can leave an orphaned Storage object

When a new cover is attached, the service directly deletes the previous cover's
database row. That path does not remove the old file from `storage.objects`, so
unused files can remain in the bucket.

### 9. Storage bucket configuration must stay synchronized

The SQL files hard-code the `website` bucket, while Python reads the bucket name
from `SUPABASE_STORAGE_BUCKET`. A different environment value creates a mismatch
between database policies and application uploads.

### 10. Auth metadata currently controls initial elevated roles

`create_profile_for_new_user()` trusts the `role` value in
`auth.users.raw_user_meta_data` and currently accepts `admin`. If public Supabase
signup permits callers to set arbitrary metadata, a caller could request an
elevated initial profile. Keep public signup disabled for administrative users or
derive privileged roles only from trusted server-side data.

### 11. Common lookups do not all have dedicated indexes

Current services look up staged images by `image_url` and sort QR links by
`created_at DESC`, but the repository defines no dedicated indexes for those
paths. Confirm query performance with production data before adding indexes.

## Migration history

| Migration | Main effect |
| --- | --- |
| `20260712000100_create_profiles_and_post_types.sql` | Creates profiles, post types, posts, the original image table, triggers, RLS, and storage setup |
| `20260712000200_rename_post_image_url_to_path.sql` | Renames legacy `post_images.image_url` to `image_path` |
| `20260713000100_create_images_table.sql` | Creates the current image table and copies legacy and cover-image records |
| `20260713000200_create_qr_links_table.sql` | Creates standalone named QR URLs and removes the old post relationship |
| `20260715000100_add_structured_post_content.sql` | Adds versioned JSONB post blocks and backfills legacy text as paragraph blocks |
