create table if not exists public.qr_links (
    qr_id uuid primary key default gen_random_uuid(),
    qr_name text not null
        check (char_length(trim(qr_name)) between 1 and 120),
    qr_url text not null check (qr_url ~* '^https?://'),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamp with time zone not null default now(),
    updated_at timestamp with time zone not null default now()
);

alter table public.qr_links
    add column if not exists qr_name text not null default 'Post link'
    check (char_length(trim(qr_name)) between 1 and 120);

alter table public.qr_links alter column qr_name drop default;

drop policy if exists "Anyone can read QR links for published posts" on public.qr_links;
alter table public.qr_links drop column if exists post_id;

create index if not exists qr_links_created_by_idx on public.qr_links(created_by);

drop trigger if exists qr_links_set_updated_at on public.qr_links;
create trigger qr_links_set_updated_at
before update on public.qr_links
for each row
execute function public.set_updated_at();

alter table public.qr_links enable row level security;
