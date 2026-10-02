"""SQLite local. Todas las escrituras públicas son transaccionales.

Los resultados son diccionarios para poder integrarse con las entidades de Diego
sin depender de su implementación. Las abreviaturas son únicas globalmente.
"""
import os
from pathlib import Path
import re
import sqlite3


class RepositorioSQLite:
    def __init__(self, ruta=None):
        if ruta is None:
            ruta = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'FraseYa' / 'fraseya.db'
        if str(ruta) != ':memory:':
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(ruta))
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.execute('PRAGMA busy_timeout = 5000')
        try:
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f'Versión de esquema no compatible: {version}')
            # No modifica la BD de dos tablas del prototipo anterior.
            existentes = {r[0].upper() for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if version == 0 and existentes:
                raise ValueError('La base existente requiere una migración explícita.')
            script = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
            self.db.executescript('BEGIN IMMEDIATE;\n' + script + '\nPRAGMA user_version = 1;\nCOMMIT;')
        except Exception:
            self.db.close()
            raise

    def cerrar(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()

    @staticmethod
    def _texto(valor, campo):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f'{campo} no puede estar vacío.')
        return valor.strip()

    @staticmethod
    def _origen(origen):
        if origen not in ('propia', 'compartida'):
            raise ValueError('Origen inválido.')
        return origen

    @staticmethod
    def _version(version):
        if type(version) is not int or version < 0:
            raise ValueError('La versión debe ser un entero no negativo.')
        return version

    def _fila(self, sql, args):
        row = self.db.execute(sql, args).fetchone()
        if row is None:
            raise LookupError('Registro no encontrado.')
        return dict(row)

    def _filas(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def crear_catalogo(self, nombre, origen='propia', version=0, autor='', fecha_publicacion=None):
        with self.db:
            return self.db.execute('''INSERT INTO CATALOGO(nombre,origen,version,autor,fecha_publicacion)
                VALUES(?,?,?,?,?)''', (self._texto(nombre, 'Nombre'), self._origen(origen),
                self._version(version), autor, fecha_publicacion)).lastrowid

    def obtener_catalogo(self, ident):
        return self._fila('SELECT * FROM CATALOGO WHERE id=?', (ident,))

    def listar_catalogos(self, origen=None):
        if origen is None:
            return self._filas('SELECT * FROM CATALOGO ORDER BY id')
        return self._filas('SELECT * FROM CATALOGO WHERE origen=? ORDER BY id', (self._origen(origen),))

    def crear_categoria(self, catalogo_id, nombre, color='#64748B'):
        with self.db:
            return self.db.execute('INSERT INTO CATEGORIA(catalogo_id,nombre,color) VALUES(?,?,?)',
                (catalogo_id, self._texto(nombre, 'Nombre'), color)).lastrowid

    def obtener_categoria(self, ident):
        return self._fila('SELECT * FROM CATEGORIA WHERE id=?', (ident,))

    def listar_categorias(self, catalogo_id=None):
        return self._filas('SELECT * FROM CATEGORIA' +
            (' WHERE catalogo_id=?' if catalogo_id is not None else '') + ' ORDER BY nombre',
            (catalogo_id,) if catalogo_id is not None else ())

    def actualizar_categoria(self, ident, nombre, color):
        with self.db:
            self.obtener_categoria(ident)
            self.db.execute('UPDATE CATEGORIA SET nombre=?,color=? WHERE id=?',
                            (self._texto(nombre, 'Nombre'), color, ident))

    def eliminar_categoria(self, ident):
        # No borra frases por accidente: una categoría ocupada se rechaza.
        with self.db:
            self.obtener_categoria(ident)
            self.db.execute('DELETE FROM CATEGORIA WHERE id=?', (ident,))

    @staticmethod
    def _marcadores(contenido):
        return list(dict.fromkeys(re.findall(r'\{(\w+)\}', contenido)))

    def _guardar_variables(self, frase_id, contenido):
        self.db.execute('DELETE FROM VARIABLE WHERE frase_id=?', (frase_id,))
        self.db.executemany('INSERT INTO VARIABLE(frase_id,nombre,orden) VALUES(?,?,?)',
            [(frase_id, nombre, orden) for orden, nombre in enumerate(self._marcadores(contenido))])

    def _crear_frase(self, categoria_id, titulo, abreviatura, contenido, origen):
        titulo = self._texto(titulo, 'Título')
        abreviatura = self._texto(abreviatura, 'Abreviatura')
        contenido = self._texto(contenido, 'Contenido')
        ident = self.db.execute('''INSERT INTO FRASE(categoria_id,titulo,abreviatura,contenido,origen)
            VALUES(?,?,?,?,?)''', (categoria_id, titulo, abreviatura, contenido,
                                  self._origen(origen))).lastrowid
        self._guardar_variables(ident, contenido)
        return ident

    def crear_frase(self, categoria_id, titulo, abreviatura, contenido, origen='propia'):
        with self.db:
            return self._crear_frase(categoria_id, titulo, abreviatura, contenido, origen)

    def obtener_frase(self, ident):
        frase = self._fila('SELECT * FROM FRASE WHERE id=?', (ident,))
        frase['variables'] = self.listar_variables(ident)
        return frase

    def listar_frases(self, origen=None, categoria_id=None):
        where, args = [], []
        if origen is not None:
            where.append('origen=?')
            args.append(self._origen(origen))
        if categoria_id is not None:
            where.append('categoria_id=?')
            args.append(categoria_id)
        ids = self.db.execute('SELECT id FROM FRASE' +
            (' WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY titulo,id', args).fetchall()
        return [self.obtener_frase(r[0]) for r in ids]

    def actualizar_frase(self, ident, categoria_id, titulo, abreviatura, contenido):
        with self.db:
            self.obtener_frase(ident)
            contenido = self._texto(contenido, 'Contenido')
            self.db.execute('''UPDATE FRASE SET categoria_id=?,titulo=?,abreviatura=?,contenido=?,
                actualizado=CURRENT_TIMESTAMP WHERE id=?''', (categoria_id,
                self._texto(titulo, 'Título'), self._texto(abreviatura, 'Abreviatura'), contenido, ident))
            self._guardar_variables(ident, contenido)

    def eliminar_frase(self, ident):
        with self.db:
            self.obtener_frase(ident)
            self.db.execute('DELETE FROM FRASE WHERE id=?', (ident,))

    def listar_variables(self, frase_id):
        return self._filas('SELECT * FROM VARIABLE WHERE frase_id=? ORDER BY orden', (frase_id,))

    def crear_variable(self, frase_id, nombre, orden):
        with self.db:
            return self.db.execute('INSERT INTO VARIABLE(frase_id,nombre,orden) VALUES(?,?,?)',
                (frase_id, self._texto(nombre, 'Nombre'), orden)).lastrowid

    def actualizar_variable(self, ident, nombre, orden):
        with self.db:
            self._fila('SELECT id FROM VARIABLE WHERE id=?', (ident,))
            self.db.execute('UPDATE VARIABLE SET nombre=?,orden=? WHERE id=?',
                            (self._texto(nombre, 'Nombre'), orden, ident))

    def eliminar_variable(self, ident):
        with self.db:
            self._fila('SELECT id FROM VARIABLE WHERE id=?', (ident,))
            self.db.execute('DELETE FROM VARIABLE WHERE id=?', (ident,))

    def guardar_configuracion(self, clave, valor):
        if not isinstance(valor, str):
            raise ValueError('La configuración se guarda como texto.')
        with self.db:
            self.db.execute('''INSERT INTO CONFIGURACION(clave,valor) VALUES(?,?)
                ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor''',
                (self._texto(clave, 'Clave'), valor))

    def leer_configuracion(self, clave, predeterminado=None):
        row = self.db.execute('SELECT valor FROM CONFIGURACION WHERE clave=?', (clave,)).fetchone()
        return row[0] if row else predeterminado

    def registrar_sincronizacion(self, estado, version_aplicada=None, detalle=''):
        if version_aplicada is not None:
            self._version(version_aplicada)
        with self.db:
            return self.db.execute('''INSERT INTO SINCRONIZACION(estado,version_aplicada,detalle)
                VALUES(?,?,?)''', (estado, version_aplicada, detalle)).lastrowid

    def listar_sincronizaciones(self):
        return self._filas('SELECT * FROM SINCRONIZACION ORDER BY id DESC')

    def reemplazar_compartidas(self, version, autor, fecha_publicacion, categorias):
        """Reemplaza el conjunto compartido completo o no cambia nada.

        categorias: lista de {nombre, color, frases: [{titulo, abreviatura, contenido}]}.
        Una abreviatura compartida en conflicto con una propia rechaza toda la
        actualización. Nunca elimina ni modifica frases propias.
        """
        self._version(version)
        with self.db:
            self.db.execute('DELETE FROM FRASE WHERE origen=?', ('compartida',))
            self.db.execute('DELETE FROM CATALOGO WHERE origen=?', ('compartida',))
            catalogo_id = self.db.execute('''INSERT INTO CATALOGO(nombre,version,fecha_publicacion,autor,origen)
                VALUES(?,?,?,?,?)''', ('Compartido', version, fecha_publicacion, autor, 'compartida')).lastrowid
            for categoria in categorias:
                categoria_id = self.db.execute('''INSERT INTO CATEGORIA(catalogo_id,nombre,color)
                    VALUES(?,?,?)''', (catalogo_id, self._texto(categoria['nombre'], 'Nombre'),
                    categoria.get('color', '#64748B'))).lastrowid
                for frase in categoria['frases']:
                    self._crear_frase(categoria_id, frase['titulo'], frase['abreviatura'],
                                      frase['contenido'], 'compartida')
            self.db.execute('''INSERT INTO SINCRONIZACION(estado,version_aplicada)
                VALUES('actualizada',?)''', (version,))
            return catalogo_id
