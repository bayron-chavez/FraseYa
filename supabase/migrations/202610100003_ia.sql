begin;
create table if not exists public.fraseya_ia_limites (
    usuario uuid not null,
    periodo timestamptz not null,
    tipo text not null check (tipo in ('minuto','dia','global')),
    cantidad integer not null check (cantidad >= 0),
    primary key (usuario,periodo,tipo)
);
alter table public.fraseya_ia_limites enable row level security;
revoke all on public.fraseya_ia_limites from public, anon, authenticated;

create or replace function public.fraseya_ia_reservar() returns boolean
language plpgsql security definer set search_path = '' as $$
declare
    v_usuario uuid := (select auth.uid());
    v_minuto timestamptz := date_trunc('minute', now());
    v_dia timestamptz := date_trunc('day', now() at time zone 'UTC') at time zone 'UTC';
    v_global uuid := '00000000-0000-0000-0000-000000000000';
begin
    if v_usuario is null or not exists (
        select 1 from public.fraseya_perfiles where id=v_usuario and activo
    ) then
        raise insufficient_privilege using message = 'Cuenta no habilitada.';
    end if;
    -- Serializa las reservas en todos los equipos: no se evita reiniciando el cliente.
    perform pg_catalog.pg_advisory_xact_lock(202610100003);
    delete from public.fraseya_ia_limites where periodo < v_dia - interval '2 days';
    if coalesce((select cantidad from public.fraseya_ia_limites where usuario=v_usuario and periodo=v_minuto and tipo='minuto'),0) >= 5
       or coalesce((select cantidad from public.fraseya_ia_limites where usuario=v_usuario and periodo=v_dia and tipo='dia'),0) >= 50
       or coalesce((select cantidad from public.fraseya_ia_limites where usuario=v_global and periodo=v_dia and tipo='global'),0) >= 1000 then
        return false;
    end if;
    insert into public.fraseya_ia_limites(usuario,periodo,tipo,cantidad)
    values (v_usuario,v_minuto,'minuto',1), (v_usuario,v_dia,'dia',1), (v_global,v_dia,'global',1)
    on conflict (usuario,periodo,tipo) do update set cantidad=public.fraseya_ia_limites.cantidad+1;
    return true;
end;
$$;
revoke all on function public.fraseya_ia_reservar() from public, anon, authenticated;
grant execute on function public.fraseya_ia_reservar() to authenticated;
commit;
