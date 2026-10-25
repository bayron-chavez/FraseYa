import { crearHandler } from './logica.mjs';
Deno.serve(crearHandler((nombre: string) => Deno.env.get(nombre)));
