import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {PGlite}=await import(process.argv[2]);
const db=new PGlite();
const id='00000000-0000-0000-0000-000000000001';
const bloqueado='00000000-0000-0000-0000-000000000002';
async function rol(nombre,uid='') {
  await db.exec('reset role');
  await db.query("select set_config('request.jwt.claim.sub',$1,false)",[uid]);
  await db.exec(`set role ${nombre}`);
}
try {
  await db.exec(`create role anon; create role authenticated; create schema auth;
    create table auth.users(id uuid primary key,email text);
    create function auth.uid() returns uuid language sql stable as
    $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
    grant usage on schema auth to anon,authenticated;
    alter default privileges in schema public grant all on tables to anon,authenticated;
    alter default privileges in schema public grant execute on functions to anon,authenticated;`);
  for(const archivo of ['202610050001_fraseya.sql','202610050002_seguridad.sql','202610100003_ia.sql','202610100004_empresa_ia.sql'])
    await db.exec(await readFile(new URL('../migrations/'+archivo,import.meta.url),'utf8'));
  await db.query('insert into auth.users values($1,$2),($3,$4)',[id,'uno@example.test',bloqueado,'dos@example.test']);
  await db.query('update public.fraseya_perfiles set activo=false where id=$1',[bloqueado]);
  await db.query('update public.fraseya_perfiles set activo=true where id=$1',[id]);
  await rol('anon');
  await assert.rejects(db.query('select public.fraseya_ia_reservar()'));
  await assert.rejects(db.query('select * from public.fraseya_ia_limites'));
  await assert.rejects(db.query('select public.fraseya_empresa_ia_leer()'));
  await rol('authenticated',bloqueado);
  await assert.rejects(db.query('select public.fraseya_ia_reservar()'));
  await assert.rejects(db.query('select public.fraseya_empresa_ia_leer()'));
  await rol('authenticated',id);
  const perfil={nombre:"Empresa ' ; DROP TABLE prueba; --",servicios:'Internet',horarios:'Lunes a viernes',procedimientos:'Consultar tipo de conexión'};
  await assert.rejects(db.query('select public.fraseya_empresa_ia_guardar($1::jsonb)',[JSON.stringify(perfil)]));
  await assert.rejects(db.query('select * from public.fraseya_empresa_ia'));
  await rol('postgres');
  await db.query("update public.fraseya_perfiles set rol='administrador' where id=$1",[id]);
  await rol('authenticated',id);
  await db.query('select public.fraseya_empresa_ia_guardar($1::jsonb)',[JSON.stringify(perfil)]);
  assert.deepEqual((await db.query('select public.fraseya_empresa_ia_leer() as perfil')).rows[0].perfil,perfil);
  await assert.rejects(db.query('select public.fraseya_empresa_ia_guardar($1::jsonb)',[JSON.stringify({...perfil,rol:'administrador'})]));
  await assert.rejects(db.query('select public.fraseya_empresa_ia_guardar($1::jsonb)',[JSON.stringify({...perfil,nombre:'x'.repeat(201)})]));
  await assert.rejects(db.query('update public.fraseya_empresa_ia set perfil=\'{}\''));
  for(let i=0;i<5;i++) assert.equal((await db.query('select public.fraseya_ia_reservar() as ok')).rows[0].ok,true);
  assert.equal((await db.query('select public.fraseya_ia_reservar() as ok')).rows[0].ok,false);
  await assert.rejects(db.query('delete from public.fraseya_ia_limites'));
  await assert.rejects(db.query('update public.fraseya_ia_limites set cantidad=0'));
  await rol('postgres');
  await db.exec("delete from public.fraseya_ia_limites where tipo='minuto'; update public.fraseya_ia_limites set cantidad=50 where tipo='dia'");
  await rol('authenticated',id);
  assert.equal((await db.query('select public.fraseya_ia_reservar() as ok')).rows[0].ok,false);
  await rol('postgres');
  await db.exec("update public.fraseya_ia_limites set cantidad=1 where tipo='dia'; update public.fraseya_ia_limites set cantidad=1000 where tipo='global'");
  await rol('authenticated',id);
  assert.equal((await db.query('select public.fraseya_ia_reservar() as ok')).rows[0].ok,false);
  console.log('Permisos IA y empresa: anónimo/inactivo bloqueados, edición solo administrador, campos y SQL protegidos, límites correctos.');
} finally { await db.close(); }
