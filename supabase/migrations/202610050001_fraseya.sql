-- Ejecutar en el SQL Editor de un proyecto Supabase nuevo.
begin;

create table public.fraseya_perfiles (
    id uuid primary key references auth.users(id) on delete cascade,
    correo text not null,
    rol text not null default 'usuario' check (rol in ('usuario', 'administrador')),
    activo boolean not null default false
);
alter table public.fraseya_perfiles enable row level security;
revoke all on public.fraseya_perfiles from anon, authenticated;

create function public.fraseya_alta_perfil() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
    insert into public.fraseya_perfiles(id, correo) values (new.id, new.email);
    return new;
end;
$$;
revoke all on function public.fraseya_alta_perfil() from public, anon, authenticated;
create trigger fraseya_nuevo_usuario after insert on auth.users
for each row execute function public.fraseya_alta_perfil();
insert into public.fraseya_perfiles(id, correo)
select id, email from auth.users where email is not null;

create function public.fraseya_perfil()
returns table(id uuid, correo text, rol text)
language sql stable security definer set search_path = '' as $$
    select p.id, p.correo, p.rol from public.fraseya_perfiles p
    where p.id = (select auth.uid()) and p.activo;
$$;
revoke all on function public.fraseya_perfil() from public, anon;
grant execute on function public.fraseya_perfil() to authenticated;

create table public.fraseya_catalogo (
    id integer primary key check (id = 1),
    version bigint not null default 0,
    contenido text,
    metadata jsonb
);
insert into public.fraseya_catalogo(id) values(1);
alter table public.fraseya_catalogo enable row level security;
revoke all on public.fraseya_catalogo from anon, authenticated;
grant select on public.fraseya_catalogo to authenticated;
create policy lectura_miembros on public.fraseya_catalogo for select to authenticated
using (exists(select 1 from public.fraseya_perfil()));

create function public.fraseya_publicar(
    p_version_anterior bigint, p_contenido text, p_metadata jsonb
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
    v_correo text;
    v_actual bigint;
    v_doc jsonb;
    v_categoria jsonb;
    v_frase jsonb;
    v_cantidad bigint := 0;
    v_claves text[] := array[]::text[];
    v_categorias text[] := array[]::text[];
    v_clave text;
    v_fecha text;
    v_meta jsonb;
begin
    select p.correo into v_correo from public.fraseya_perfiles p
    where p.id = (select auth.uid()) and p.activo and p.rol = 'administrador'
    for share;
    if v_correo is null then
        raise insufficient_privilege using message = 'Solo el administrador puede publicar.';
    end if;
    select version into v_actual from public.fraseya_catalogo where id = 1 for update;
    if v_actual is distinct from p_version_anterior then
        raise sqlstate 'PT409' using message = 'El catálogo cambió; prepara otra publicación.';
    end if;
    if p_contenido is null or octet_length(p_contenido) > 5242880 then
        raise exception 'Catálogo vacío o demasiado grande.';
    end if;
    v_doc := p_contenido::jsonb;
    if v_doc->>'formato' is distinct from '1' or jsonb_typeof(v_doc->'categorias') is distinct from 'array' then
        raise exception 'Formato de catálogo inválido.';
    end if;
    for v_categoria in select value from jsonb_array_elements(v_doc->'categorias') loop
        if jsonb_typeof(v_categoria->'nombre') is distinct from 'string'
            or coalesce(btrim(v_categoria->>'nombre'), '') = ''
            or coalesce(v_categoria->>'color', '') !~ '^#[0-9A-Fa-f]{6}$'
            or jsonb_typeof(v_categoria->'frases') is distinct from 'array' then
            raise exception 'Categoría inválida.';
        end if;
        v_clave := lower(v_categoria->>'nombre');
        if v_clave = any(v_categorias) then raise exception 'Categoría repetida.'; end if;
        v_categorias := array_append(v_categorias, v_clave);
        for v_frase in select value from jsonb_array_elements(v_categoria->'frases') loop
            if jsonb_typeof(v_frase->'titulo') is distinct from 'string'
                or coalesce(btrim(v_frase->>'titulo'), '') = ''
                or jsonb_typeof(v_frase->'contenido') is distinct from 'string'
                or coalesce(btrim(v_frase->>'contenido'), '') = ''
                or jsonb_typeof(v_frase->'abreviatura') is distinct from 'string'
                or coalesce(v_frase->>'abreviatura', '') = ''
                or v_frase->>'abreviatura' ~ '[[:space:]]' then
                raise exception 'Frase inválida.';
            end if;
            v_clave := lower(v_frase->>'abreviatura');
            if v_clave = any(v_claves) then raise exception 'Abreviatura repetida.'; end if;
            v_claves := array_append(v_claves, v_clave);
            v_cantidad := v_cantidad + 1;
        end loop;
    end loop;
    if p_metadata->>'sha256' is distinct from encode(sha256(convert_to(p_contenido, 'UTF8')), 'hex')
        or (p_metadata->>'version')::bigint is distinct from v_actual + 1
        or (p_metadata->>'cantidad_frases')::bigint is distinct from v_cantidad then
        raise exception 'Metadatos inconsistentes.';
    end if;
    v_fecha := to_char(clock_timestamp() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"');
    v_meta := jsonb_build_object('formato', 1, 'version', v_actual + 1,
        'fecha', v_fecha, 'autor', v_correo, 'cantidad_frases', v_cantidad,
        'sha256', encode(sha256(convert_to(p_contenido, 'UTF8')), 'hex'));
    update public.fraseya_catalogo set version = v_actual + 1,
        contenido = p_contenido, metadata = v_meta where id = 1;
    return v_meta;
end;
$$;
revoke all on function public.fraseya_publicar(bigint, text, jsonb) from public, anon;
grant execute on function public.fraseya_publicar(bigint, text, jsonb) to authenticated;
commit;
