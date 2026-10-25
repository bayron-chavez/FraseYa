begin;
create table if not exists public.fraseya_empresa_ia (
    id boolean primary key default true check (id),
    perfil jsonb not null,
    actualizado timestamptz not null default now()
);
alter table public.fraseya_empresa_ia enable row level security;
revoke all on public.fraseya_empresa_ia from public, anon, authenticated;

create or replace function public.fraseya_empresa_ia_leer() returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
    if not exists (select 1 from public.fraseya_perfiles where id=(select auth.uid()) and activo) then
        raise insufficient_privilege using message='Cuenta no habilitada.';
    end if;
    return coalesce((select perfil from public.fraseya_empresa_ia where id=true),
        '{"nombre":"","servicios":"","horarios":"","procedimientos":""}'::jsonb);
end;
$$;

create or replace function public.fraseya_empresa_ia_guardar(p_perfil jsonb) returns void
language plpgsql security definer set search_path = '' as $$
declare v_clave text; v_valor jsonb;
begin
    if not exists (select 1 from public.fraseya_perfiles where id=(select auth.uid()) and activo and rol='administrador') then
        raise insufficient_privilege using message='Solo el administrador puede configurar la empresa.';
    end if;
    if jsonb_typeof(p_perfil) is distinct from 'object' or octet_length(p_perfil::text)>16000
       or not (p_perfil ?& array['nombre','servicios','horarios','procedimientos'])
       or (select count(*) from jsonb_object_keys(p_perfil)) <> 4 then
        raise invalid_parameter_value using message='Perfil inválido.';
    end if;
    for v_clave,v_valor in select * from jsonb_each(p_perfil) loop
        if jsonb_typeof(v_valor) <> 'string' or length(p_perfil->>v_clave) >
            (case when v_clave='nombre' then 200 when v_clave='horarios' then 1000 else 4000 end) then
            raise invalid_parameter_value using message='Campo inválido.';
        end if;
    end loop;
    insert into public.fraseya_empresa_ia(id,perfil) values(true,p_perfil)
    on conflict(id) do update set perfil=excluded.perfil,actualizado=now();
end;
$$;
revoke all on function public.fraseya_empresa_ia_leer() from public,anon,authenticated;
revoke all on function public.fraseya_empresa_ia_guardar(jsonb) from public,anon,authenticated;
grant execute on function public.fraseya_empresa_ia_leer() to authenticated;
grant execute on function public.fraseya_empresa_ia_guardar(jsonb) to authenticated;
commit;
