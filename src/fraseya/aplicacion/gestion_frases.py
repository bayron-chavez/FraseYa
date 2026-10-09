"""Casos de uso de RF-04: gestionar frases propias (compartidas son de solo lectura)."""
import sqlite3
import re
import json

CATALOGO_PROPIO = 'Mis frases'
CATEGORIA_PREDETERMINADA = 'General'


class ErroresValidacion(ValueError):
    """Todos los problemas de un formulario; `errores` los lista, str() los une con ' | '."""

    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__(' | '.join(self.errores))


class GestionFrases:
    def __init__(self, repositorio):
        self.repo = repositorio
        self._ultima_eliminada = None

    @staticmethod
    def _clave_favorita(frase):
        # Las sincronizaciones reemplazan IDs; origen y abreviatura son estables.
        return json.dumps([frase['origen'], frase['abreviatura'].lower()], ensure_ascii=False)

    def favoritas(self):
        return set(json.loads(self.repo.leer_configuracion('frases_favoritas', '[]')))

    def es_favorita(self, frase):
        return self._clave_favorita(frase) in self.favoritas()

    def _guardar_favoritas(self, favoritas):
        self.repo.guardar_configuracion('frases_favoritas', json.dumps(sorted(favoritas), ensure_ascii=False))

    def alternar_favorita(self, ident):
        frase = self.repo.obtener_frase(ident)
        favoritas = self.favoritas()
        clave = self._clave_favorita(frase)
        activa = clave not in favoritas
        if activa:
            favoritas.add(clave)
        else:
            favoritas.remove(clave)
        self._guardar_favoritas(favoritas)
        return activa

    def puede_deshacer(self):
        return self._ultima_eliminada is not None

    def deshacer_eliminacion(self):
        if self._ultima_eliminada is None:
            raise ValueError('No hay una eliminación propia para deshacer en esta sesión.')
        frase, era_favorita = self._ultima_eliminada
        categorias = self.categorias_propias()
        categoria_id = frase['categoria_id']
        if categoria_id not in {c['id'] for c in categorias}:
            categoria_id = next((c['id'] for c in categorias if c['nombre'] == 'General'), categorias[0]['id'])
        # La validación rechaza conflictos nuevos; conserva la copia para reintentar.
        ident = self.crear(frase['titulo'], frase['abreviatura'], frase['contenido'], categoria_id)
        if era_favorita:
            favoritas = self.favoritas()
            favoritas.add(self._clave_favorita(frase))
            self._guardar_favoritas(favoritas)
        self._ultima_eliminada = None
        return ident

    def _catalogo_propio(self):
        existentes = self.repo.listar_catalogos('propia')
        if existentes:
            return existentes[0]['id']
        return self.repo.crear_catalogo(CATALOGO_PROPIO, 'propia')

    def categorias_propias(self):
        """Categorías donde pueden guardarse frases propias; crea 'General' si no hay ninguna."""
        catalogo_id = self._catalogo_propio()
        categorias = self.repo.listar_categorias(catalogo_id)
        if not categorias:
            self.repo.crear_categoria(catalogo_id, CATEGORIA_PREDETERMINADA)
            categorias = self.repo.listar_categorias(catalogo_id)
        nombres = {c['nombre'].casefold() for c in categorias}
        compartidos = {c['id'] for c in self.repo.listar_catalogos('compartida')}
        pendientes = {o['anterior'].casefold() for o in self.operaciones_categorias()}
        remotas = [c for c in self.repo.listar_categorias() if c['catalogo_id'] in compartidos]
        espejos = json.loads(self.repo.leer_configuracion('categorias_espejo', '{}'))
        remotas_por_nombre = {c['nombre'].casefold(): c for c in remotas}
        for categoria in categorias:
            ident, nombre = str(categoria['id']), categoria['nombre'].casefold()
            if nombre in pendientes:
                espejos.pop(ident, None)
                continue
            remota = remotas_por_nombre.get(nombre)
            if remota:
                if categoria['color'] != remota['color']:
                    self.repo.actualizar_categoria(categoria['id'], categoria['nombre'], remota['color'])
                espejos[ident] = nombre
            elif (nombre != 'general' and espejos.get(ident) == nombre
                    and not self.repo.listar_frases(categoria_id=categoria['id'])):
                self.repo.eliminar_categoria(categoria['id'])
                espejos.pop(ident, None)
                nombres.discard(nombre)
        for categoria in remotas:
            if (categoria['catalogo_id'] in compartidos and categoria['nombre'].casefold() not in nombres
                    and categoria['nombre'].casefold() not in pendientes):
                ident = self.repo.crear_categoria(catalogo_id, categoria['nombre'], categoria['color'])
                espejos[str(ident)] = categoria['nombre'].casefold()
                nombres.add(categoria['nombre'].casefold())
        self.repo.guardar_configuracion('categorias_espejo', json.dumps(espejos))
        categorias = self.repo.listar_categorias(catalogo_id)
        return categorias

    def crear_categoria(self, nombre, autenticacion, sesion, color='#64748B'):
        """Crea una categoría del administrador para la próxima publicación."""
        if autenticacion is None or sesion is None:
            raise PermissionError('Inicia sesión como administrador para crear categorías.')
        autenticacion.validar(sesion, administrador=True)
        nombre = (nombre or '').strip()
        if not nombre or len(nombre) > 200:
            raise ValueError('El nombre debe tener entre 1 y 200 caracteres.')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('El color debe tener formato #RRGGBB.')
        if any(c['nombre'].casefold() == nombre.casefold() for c in self.categorias_propias()):
            raise ValueError('Ya existe una categoría con ese nombre.')
        return self.repo.crear_categoria(self._catalogo_propio(), nombre, color)

    def operaciones_categorias(self):
        return json.loads(self.repo.leer_configuracion('operaciones_categorias', '[]'))

    def editar_categoria(self, ident, nombre, color, autenticacion, sesion, eliminar=False):
        if autenticacion is None or sesion is None:
            raise PermissionError('Solo el administrador puede gestionar categorías.')
        autenticacion.validar(sesion, administrador=True)
        categorias = self.categorias_propias()
        actual = next((c for c in categorias if c['id'] == ident), None)
        if actual is None:
            raise ValueError('Selecciona una categoría del editor.')
        nombre = (nombre or '').strip()
        if not eliminar:
            if not nombre or len(nombre) > 200 or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ValueError('Indica un nombre de 1 a 200 caracteres y un color válido.')
            if any(c['id'] != ident and c['nombre'].casefold() == nombre.casefold() for c in categorias):
                raise ValueError('Ya existe una categoría con ese nombre.')
        else:
            if actual['nombre'].casefold() == 'general':
                raise ValueError('La categoría General se conserva como categoría predeterminada.')
            ids = {c['id'] for c in self.repo.listar_categorias()
                   if c['nombre'].casefold() == actual['nombre'].casefold()}
            if any(f['categoria_id'] in ids for f in self.repo.listar_frases()):
                raise ValueError('La categoría contiene frases. Reasígnalas antes de eliminarla.')
        operaciones = self.operaciones_categorias()
        operaciones.append({'anterior': actual['nombre'], 'nombre': None if eliminar else nombre, 'color': color})
        with self.repo.db:
            if eliminar:
                self.repo.db.execute('DELETE FROM CATEGORIA WHERE id=?', (ident,))
            else:
                self.repo.db.execute('UPDATE CATEGORIA SET nombre=?,color=? WHERE id=?', (nombre, color, ident))
            self.repo.db.execute('INSERT INTO CONFIGURACION(clave,valor) VALUES(?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor',
                ('operaciones_categorias', json.dumps(operaciones)))

    def listar(self, texto='', categoria_id=None):
        """Todas las frases (propias y compartidas) con el nombre y color de su categoría."""
        categorias = {c['id']: c for c in self.repo.listar_categorias()}
        clave = texto.strip().lower()
        resultado = []
        favoritas = self.favoritas()
        for f in self.repo.listar_frases(categoria_id=categoria_id):
            cat = categorias.get(f['categoria_id'], {})
            f['categoria'] = cat.get('nombre', '')
            f['color'] = cat.get('color', '#64748B')
            f['favorita'] = self._clave_favorita(f) in favoritas
            if clave and clave not in ' '.join((f['titulo'], f['abreviatura'], f['categoria'],
                                                f['contenido'])).lower():
                continue
            resultado.append(f)
        return sorted(resultado, key=lambda f: not f['favorita'])

    def _errores_abreviatura(self, abreviatura, ignorar_id=None):
        abreviatura = (abreviatura or '').strip()
        if not abreviatura:
            return ['La abreviatura no puede estar vacía.']
        if any(c.isspace() for c in abreviatura):
            return ['La abreviatura no puede contener espacios.']
        for f in self.repo.listar_frases():
            if f['id'] != ignorar_id and f['abreviatura'].lower() == abreviatura.lower():
                return [f'La abreviatura "{abreviatura}" ya está en uso.']
        return []

    def validar(self, titulo, abreviatura, contenido, categoria_id, ignorar_id=None):
        """Lanza ErroresValidacion con todos los campos incorrectos, no solo el primero."""
        errores = []
        if not (titulo or '').strip():
            errores.append('El título no puede estar vacío.')
        if len(titulo or '') > 500 or len(abreviatura or '') > 100 or len(contenido or '') > 100000:
            errores.append('Máximos: título 500, abreviatura 100 y contenido 100000 caracteres.')
        errores += self._errores_abreviatura(abreviatura, ignorar_id)
        if not (contenido or '').strip():
            errores.append('El contenido no puede estar vacío.')
        if categoria_id not in {c['id'] for c in self.categorias_propias()}:
            errores.append('Elige una categoría propia.')
        if errores:
            raise ErroresValidacion(errores)

    def _propia(self, ident):
        frase = self.repo.obtener_frase(ident)
        if frase['origen'] != 'propia':
            raise PermissionError('Las frases compartidas son de solo lectura; duplícala para editarla.')
        return frase

    def crear(self, titulo, abreviatura, contenido, categoria_id):
        self.validar(titulo, abreviatura, contenido, categoria_id)
        return self._traducir(self.repo.crear_frase, categoria_id, titulo, abreviatura.strip(), contenido)

    def editar(self, ident, titulo, abreviatura, contenido, categoria_id):
        anterior = self._propia(ident)
        self.validar(titulo, abreviatura, contenido, categoria_id, ignorar_id=ident)
        self._traducir(self.repo.actualizar_frase, ident, categoria_id, titulo, abreviatura.strip(), contenido)
        favoritas = self.favoritas()
        clave = self._clave_favorita(anterior)
        if clave in favoritas:
            favoritas.remove(clave)
            favoritas.add(self._clave_favorita(self.repo.obtener_frase(ident)))
            self._guardar_favoritas(favoritas)

    def duplicar(self, ident, abreviatura=None):
        """Copia propia y editable de cualquier frase, con una abreviatura nueva."""
        original = self.repo.obtener_frase(ident)
        abreviatura = abreviatura or self._abreviatura_libre(original['abreviatura'])
        categoria_id = self.categorias_propias()[0]['id']
        if original['origen'] == 'propia':
            categoria_id = original['categoria_id']
        return self.crear(original['titulo'] + ' (copia)', abreviatura, original['contenido'], categoria_id)

    def eliminar(self, ident):
        frase = self._propia(ident)
        favoritas = self.favoritas()
        clave = self._clave_favorita(frase)
        era_favorita = clave in favoritas
        self.repo.eliminar_frase(ident)
        favoritas.discard(clave)
        self._guardar_favoritas(favoritas)
        self._ultima_eliminada = (frase, era_favorita)

    def _abreviatura_libre(self, base):
        usadas = {f['abreviatura'].lower() for f in self.repo.listar_frases()}
        n = 2
        while f'{base}{n}'.lower() in usadas:
            n += 1
        return f'{base}{n}'

    @staticmethod
    def _traducir(operacion, *args):
        try:
            return operacion(*args)
        except sqlite3.IntegrityError as error:
            raise ValueError(f'No se pudo guardar la frase: {error}') from error
