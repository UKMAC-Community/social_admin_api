create or replace function public.is_valid_post_image_presentation(document jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
    block_value jsonb;
    image_data jsonb;
    numeric_value numeric;
begin
    if jsonb_typeof(document) is distinct from 'object'
       or jsonb_typeof(document->'blocks') is distinct from 'array' then
        return false;
    end if;

    for block_value in
        select value from jsonb_array_elements(document->'blocks')
    loop
        if block_value->>'type' is distinct from 'image' then
            continue;
        end if;

        image_data := block_value->'data';
        if jsonb_typeof(image_data) is distinct from 'object' then
            return false;
        end if;

        if image_data ? 'crop'
           and jsonb_typeof(image_data->'crop') not in ('boolean', 'null') then
            return false;
        end if;

        if image_data ? 'crop_ratio'
           and jsonb_typeof(image_data->'crop_ratio') <> 'null' then
            if jsonb_typeof(image_data->'crop_ratio') <> 'number' then
                return false;
            end if;
            numeric_value := (image_data->>'crop_ratio')::numeric;
            if numeric_value < 0.1 or numeric_value > 10 then
                return false;
            end if;
        end if;

        if image_data ? 'crop_x'
           and jsonb_typeof(image_data->'crop_x') <> 'null' then
            if jsonb_typeof(image_data->'crop_x') <> 'number' then
                return false;
            end if;
            numeric_value := (image_data->>'crop_x')::numeric;
            if numeric_value < 0 or numeric_value > 100 then
                return false;
            end if;
        end if;

        if image_data ? 'crop_y'
           and jsonb_typeof(image_data->'crop_y') <> 'null' then
            if jsonb_typeof(image_data->'crop_y') <> 'number' then
                return false;
            end if;
            numeric_value := (image_data->>'crop_y')::numeric;
            if numeric_value < 0 or numeric_value > 100 then
                return false;
            end if;
        end if;

        if image_data ? 'width'
           and jsonb_typeof(image_data->'width') <> 'null' then
            if jsonb_typeof(image_data->'width') <> 'number' then
                return false;
            end if;
            numeric_value := (image_data->>'width')::numeric;
            if numeric_value < 25 or numeric_value > 100 then
                return false;
            end if;
        end if;
    end loop;

    return true;
end;
$$;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'posts_content_image_presentation_check'
          and conrelid = 'public.posts'::regclass
    ) then
        alter table public.posts
            add constraint posts_content_image_presentation_check
            check (public.is_valid_post_image_presentation(content_json))
            not valid;
    end if;
end;
$$;

alter table public.posts
    validate constraint posts_content_image_presentation_check;

comment on function public.is_valid_post_image_presentation(jsonb) is
    'Validates optional crop position, crop ratio, and width fields in image content blocks.';

