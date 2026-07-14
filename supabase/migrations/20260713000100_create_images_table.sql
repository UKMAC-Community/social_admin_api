create table if not exists public.images (
    id uuid primary key default gen_random_uuid(),
    post_id uuid references public.posts(id) on delete cascade,
    image_role text not null default 'gallery'
        check (image_role in ('cover', 'gallery')),
    image_url text not null,
    storage_bucket text not null default 'website',
    storage_path text,
    original_filename text,
    content_type text,
    size_bytes bigint check (size_bytes is null or size_bytes >= 0),
    caption text,
    sort_order integer not null default 0 check (sort_order >= 0),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamp with time zone not null default now()
);

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'post_images'
          and column_name = 'image_path'
    ) then
        execute $migration$
            insert into public.images (
                id,
                post_id,
                image_role,
                image_url,
                caption,
                sort_order,
                created_at
            )
            select
                id,
                post_id,
                'gallery',
                image_path,
                caption,
                sort_order,
                created_at
            from public.post_images
            on conflict (id) do nothing
        $migration$;
    elsif exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'post_images'
          and column_name = 'image_url'
    ) then
        execute $migration$
            insert into public.images (
                id,
                post_id,
                image_role,
                image_url,
                caption,
                sort_order,
                created_at
            )
            select
                id,
                post_id,
                'gallery',
                image_url,
                caption,
                sort_order,
                created_at
            from public.post_images
            on conflict (id) do nothing
        $migration$;
    end if;
end;
$$;

insert into public.images (
    post_id,
    image_role,
    image_url,
    created_by
)
select
    posts.id,
    'cover',
    posts.cover_image,
    posts.created_by
from public.posts
where posts.cover_image is not null
  and posts.cover_image <> ''
  and not exists (
      select 1
      from public.images
      where images.post_id = posts.id
        and images.image_role = 'cover'
  );

create index if not exists images_post_id_sort_order_idx
    on public.images(post_id, sort_order);
create index if not exists images_created_by_idx on public.images(created_by);
create unique index if not exists images_one_cover_per_post_idx
    on public.images(post_id)
    where image_role = 'cover' and post_id is not null;

alter table public.images enable row level security;

drop policy if exists "Anyone can read images for published posts" on public.images;
create policy "Anyone can read images for published posts"
on public.images
for select
using (
    exists (
        select 1
        from public.posts
        where posts.id = images.post_id
          and posts.published = true
    )
);

-- Keep the old table during rollout so the migration is non-destructive.
-- It can be dropped after every deployed service uses public.images.
