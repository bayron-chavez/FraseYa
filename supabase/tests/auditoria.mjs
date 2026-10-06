// PostgreSQL aislado; no se conecta al proyecto Supabase real.
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const { PGlite } = process.argv[2] ? await import(process.argv[2]) : await import('@electric-sql/pglite');
const db = new PGlite();
let controles = 0;
const admin = '00000000-0000-0000-0000-000000000001';
const usuario = '00000000-0000-0000-0000-000000000002';
const inactivo = '00000000-0000-0000-0000-000000000003';
async function rol(nombre, id = '') {
  await db.exec('reset role');
  await db.query("select set_config('request.jwt.claim.sub',$1,false)",[id]);
  await db.exec(`set role ${nombre}`); // Solo constantes internas de esta prueba.
}
async function rechaza(sql, args=[]) {
  await assert.rejects(db.query(sql,args));
  controles++;
}
function catalogo(texto="'; DROP TABLE public.fraseya_perfiles; --") {
  const contenido=JSON.stringify({formato:1,categorias:[{nombre:'General',color:'#123456',frases:[
    {titulo:'Prueba',abreviatura:'hola',contenido:texto}]}]});
  return [contenido,{formato:1,version:1,cantidad_frases:1,
    sha256:createHash('sha256').update(contenido).digest('hex')}];
}
try {
  await db.exec(`create role anon; create role authenticated; create schema auth;
    create table auth.users(id uuid primary key,email text);
    create function auth.uid() returns uuid language sql stable as
    $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
    grant usage on schema auth to anon,authenticated;
    alter default privileges in schema public grant all on tables to anon,authenticated;
    alter default privileges in schema public grant execute on functions to anon,authenticated;`);
  for (const nombre of ['202610050001_fraseya.sql','202610050002_seguridad.sql']) {
    await db.exec(await readFile(new URL('../migrations/'+nombre,import.meta.url),'utf8'));
  }
  await db.query('insert into auth.users values($1,$2),($3,$4),($5,$6)',
    [admin,'admin@example.test',usuario,'usuario@example.test',inactivo,'inactivo@example.test']);
  await db.query("update public.fraseya_perfiles set activo=true,rol='administrador' where id=$1",[admin]);
  await db.query('update public.fraseya_perfiles set activo=true where id=$1',[usuario]);
  const [contenido,meta]=catalogo();
  const publicar='select public.fraseya_publicar($1,$2,$3) as resultado';
  await rol('anon');
  await rechaza('select * from public.fraseya_catalogo');
  await rechaza('select * from public.fraseya_perfiles');
  await rechaza(publicar,[0,contenido,meta]);
  await rechaza('select public.fraseya_perfil()');
  await rol('authenticated',inactivo);
  assert.equal((await db.query('select * from public.fraseya_catalogo')).rows.length,0); controles++;
  await rechaza(publicar,[0,contenido,meta]);
  await rol('authenticated',usuario);
  assert.equal((await db.query('select * from public.fraseya_catalogo')).rows.length,1); controles++;
  await rechaza("update public.fraseya_perfiles set rol='administrador' where id=$1",[usuario]);
  await rechaza("update public.fraseya_catalogo set version=99 where id=1");
  await rechaza('delete from public.fraseya_catalogo');
  await rechaza(publicar,[0,contenido,meta]);
  await rol('authenticated',admin);
  await rechaza(publicar,[null,contenido,meta]);
  await rechaza(publicar,[0,contenido,{...meta,sha256:'0'.repeat(64)}]);
  const desconocido=JSON.stringify({...JSON.parse(contenido),ejecutar:'DROP TABLE auth.users'});
  await rechaza(publicar,[0,desconocido,{...meta,sha256:createHash('sha256').update(desconocido).digest('hex')}]);
  const r=await db.query(publicar,[0,contenido,meta]);
  assert.equal(r.rows[0].resultado.version,1); controles++;
  assert.equal(r.rows[0].resultado.autor,'admin@example.test'); controles++;
  assert.equal((await db.query('select contenido from public.fraseya_catalogo')).rows[0].contenido,contenido); controles++;
  await rechaza(publicar,[0,contenido,meta]);
  await rol('postgres');
  assert.equal((await db.query('select count(*)::int as n from public.fraseya_perfiles')).rows[0].n,3); controles++;
  await db.query("update public.fraseya_perfiles set rol='usuario' where id=$1",[admin]);
  await rol('authenticated',admin);
  await rechaza(publicar,[1,contenido,{...meta,version:2}]);
  await rol('postgres');
  const auditoria = await db.exec(await readFile(new URL('../auditoria_permisos.sql',import.meta.url),'utf8'));
  for (const fila of auditoria[0].rows) { assert.equal(fila.correcto,true,fila.control); controles++; }
  console.log(`${controles} controles PostgreSQL correctos: permisos, RLS, revocación, inyección y atomicidad.`);
} finally { await db.close(); }
