"""Casos de uso de RF-04: gestionar frases propias (compartidas son de solo lectura)."""
import sqlite3
import re

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
        for categoria in self.repo.listar_categorias():
            if categoria['catalogo_id'] in compartidos and categoria['nombre'].casefold() not in nombres:
                self.repo.crear_categoria(catalogo_id, categoria['nombre'], categoria['color'])
                nombres.add(categoria['nombre'].casefold())
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

    def listar(self, texto='', categoria_id=None):
        """Todas las frases (propias y compartidas) con el nombre y color de su categoría."""
        categorias = {c['id']: c for c in self.repo.listar_categorias()}
        clave = texto.strip().lower()
        resultado = []
        for f in self.repo.listar_frases(categoria_id=categoria_id):
            cat = categorias.get(f['categoria_id'], {})
            f['categoria'] = cat.get('nombre', '')
            f['color'] = cat.get('color', '#64748B')
            if clave and clave not in ' '.join((f['titulo'], f['abreviatura'], f['categoria'],
                                                f['contenido'])).lower():
                continue
            resultado.append(f)
        return resultado

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
        self._propia(ident)
        self.validar(titulo, abreviatura, contenido, categoria_id, ignorar_id=ident)
        self._traducir(self.repo.actualizar_frase, ident, categoria_id, titulo, abreviatura.strip(), contenido)

    def duplicar(self, ident, abreviatura=None):
        """Copia propia y editable de cualquier frase, con una abreviatura nueva."""
        original = self.repo.obtener_frase(ident)
        abreviatura = abreviatura or self._abreviatura_libre(original['abreviatura'])
        categoria_id = self.categorias_propias()[0]['id']
        if original['origen'] == 'propia':
            categoria_id = original['categoria_id']
        return self.crear(original['titulo'] + ' (copia)', abreviatura, original['contenido'], categoria_id)

    def eliminar(self, ident):
        self._propia(ident)
        self.repo.eliminar_frase(ident)

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
