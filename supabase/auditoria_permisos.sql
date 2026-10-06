-- Consulta de auditoría SOLO LECTURA: ejecutar después de ambas migraciones.
select 'RLS ' || c.relname as control, c.relrowsecurity as correcto
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relname in ('fraseya_catalogo','fraseya_perfiles')
union all
select 'Anon no lee catálogo', not has_table_privilege('anon','public.fraseya_catalogo','SELECT')
union all select 'Anon no lee perfiles', not has_table_privilege('anon','public.fraseya_perfiles','SELECT')
union all select 'Usuario no cambia roles',
    not has_any_column_privilege('authenticated','public.fraseya_perfiles','UPDATE')
union all select 'Usuario no inserta perfiles',
    not has_any_column_privilege('authenticated','public.fraseya_perfiles','INSERT')
union all select 'Usuario no borra perfiles', not has_table_privilege('authenticated','public.fraseya_perfiles','DELETE')
union all select 'Usuario no escribe catálogo directamente',
    not has_any_column_privilege('authenticated','public.fraseya_catalogo','UPDATE')
    and not has_any_column_privilege('authenticated','public.fraseya_catalogo','INSERT')
    and not has_table_privilege('authenticated','public.fraseya_catalogo','DELETE')
union all select 'Anon no publica',
    not has_function_privilege('anon','public.fraseya_publicar(bigint,text,jsonb)','EXECUTE')
union all select 'Usuario no llama trigger interno',
    not has_function_privilege('authenticated','public.fraseya_alta_perfil()','EXECUTE')
union all select 'Restricción de miembros activos', exists(
    select 1 from pg_policies where schemaname='public' and tablename='fraseya_catalogo'
    and policyname='solo_miembros_activos' and permissive='RESTRICTIVE');

-- Revisar cualquier función adicional y política no prevista.
select schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
from pg_policies where schemaname='public' and tablename like 'fraseya_%';
select p.proname, p.prosecdef as security_definer, p.proconfig
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname like 'fraseya_%';
