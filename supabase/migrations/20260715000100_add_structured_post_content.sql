alter table public.posts
    add column if not exists content_json jsonb;

update public.posts
set content_json = jsonb_build_object(
    'version', 1,
    'blocks',
    case
        when nullif(trim(content), '') is null then '[]'::jsonb
        else jsonb_build_array(
            jsonb_build_object(
                'id', 'legacy-' || id::text,
                'type', 'paragraph',
                'data', jsonb_build_object('text', content)
            )
        )
    end
)
where content_json is null;

alter table public.posts
    alter column content_json
        set default '{"version":1,"blocks":[]}'::jsonb,
    alter column content_json set not null;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'posts_content_json_shape_check'
          and conrelid = 'public.posts'::regclass
    ) then
        alter table public.posts
            add constraint posts_content_json_shape_check
            check (
                jsonb_typeof(content_json) = 'object'
                and content_json->'version' = '1'::jsonb
                and jsonb_typeof(content_json->'blocks') = 'array'
            );
    end if;
end;
$$;
