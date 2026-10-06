-- Aplicar UNA VEZ en SQL Editor sobre el proyecto existente. Conserva cuentas y catálogo.
begin;
alter table public.fraseya_perfiles enable row level security;
alter table public.fraseya_catalogo enable row level security;
revoke all on public.fraseya_perfiles from public, anon, authenticated;
revoke select(id,correo,rol,activo), insert(id,correo,rol,activo), update(id,correo,rol,activo), references(id,correo,rol,activo)
    on public.fraseya_perfiles from public, anon, authenticated;
revoke all on public.fraseya_catalogo from public, anon, authenticated;
revoke select(id,version,contenido,metadata), insert(id,version,contenido,metadata), update(id,version,contenido,metadata), references(id,version,contenido,metadata)
    on public.fraseya_catalogo from public, anon, authenticated;
grant select on public.fraseya_catalogo to authenticated;
revoke all on function public.fraseya_alta_perfil() from public, anon, authenticated;
revoke all on function public.fraseya_perfil() from public, anon, authenticated;
grant execute on function public.fraseya_perfil() to authenticated;
-- Una política restrictiva evita que otra política permisiva abra el catálogo a cuentas inactivas.
create policy solo_miembros_activos on public.fraseya_catalogo as restrictive
    for select to authenticated using (exists(select 1 from public.fraseya_perfil()));
create or replace function public.fraseya_publicar(
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
    if jsonb_typeof(v_doc) is distinct from 'object'
        or jsonb_typeof(v_doc->'formato') is distinct from 'number'
        or v_doc->>'formato' is distinct from '1'
        or jsonb_typeof(v_doc->'categorias') is distinct from 'array'
        or exists(select 1 from jsonb_object_keys(v_doc) k where k not in ('formato','categorias')) then
        raise exception 'Formato de catálogo inválido.';
    end if;
    if jsonb_array_length(v_doc->'categorias') > 500 then raise exception 'Demasiadas categorías.'; end if;
    for v_categoria in select value from jsonb_array_elements(v_doc->'categorias') loop
        if jsonb_typeof(v_categoria) is distinct from 'object'
            or exists(select 1 from jsonb_object_keys(v_categoria) k where k not in ('nombre','color','frases'))
            or jsonb_typeof(v_categoria->'nombre') is distinct from 'string'
            or coalesce(btrim(v_categoria->>'nombre'), '') = ''
            or length(v_categoria->>'nombre') > 200
            or coalesce(v_categoria->>'color', '') !~ '^#[0-9A-Fa-f]{6}$'
            or jsonb_typeof(v_categoria->'frases') is distinct from 'array' then
            raise exception 'Categoría inválida.';
        end if;
        v_clave := lower(v_categoria->>'nombre');
        if v_clave = any(v_categorias) then raise exception 'Categoría repetida.'; end if;
        v_categorias := array_append(v_categorias, v_clave);
        for v_frase in select value from jsonb_array_elements(v_categoria->'frases') loop
            if jsonb_typeof(v_frase) is distinct from 'object'
                or exists(select 1 from jsonb_object_keys(v_frase) k where k not in ('titulo','abreviatura','contenido'))
                or jsonb_typeof(v_frase->'titulo') is distinct from 'string'
                or coalesce(btrim(v_frase->>'titulo'), '') = ''
                or length(v_frase->>'titulo') > 500
                or jsonb_typeof(v_frase->'contenido') is distinct from 'string'
                or coalesce(btrim(v_frase->>'contenido'), '') = ''
                or length(v_frase->>'contenido') > 100000
                or jsonb_typeof(v_frase->'abreviatura') is distinct from 'string'
                or coalesce(v_frase->>'abreviatura', '') = ''
                or length(v_frase->>'abreviatura') > 100
                or v_frase->>'abreviatura' ~ '[[:space:]]' then
                raise exception 'Frase inválida.';
            end if;
            v_clave := lower(v_frase->>'abreviatura');
            if v_clave = any(v_claves) then raise exception 'Abreviatura repetida.'; end if;
            v_claves := array_append(v_claves, v_clave);
            v_cantidad := v_cantidad + 1;
            if v_cantidad > 10000 then raise exception 'Demasiadas frases.'; end if;
        end loop;
    end loop;
    if jsonb_typeof(p_metadata) is distinct from 'object'
        or jsonb_typeof(p_metadata->'formato') is distinct from 'number'
        or p_metadata->>'formato' is distinct from '1'
        or p_metadata->>'sha256' is distinct from encode(sha256(convert_to(p_contenido, 'UTF8')), 'hex')
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
