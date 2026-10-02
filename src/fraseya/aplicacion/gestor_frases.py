"""Casos de uso de la ventana principal: gestión de frases propias (RF-04)."""
import sqlite3

PROPIA = 'propia'
COMPARTIDA = 'compartida'


class GestorFrases:
    def __init__(self, repo):
        self.repo = repo
        self._categoria = self._categoria_propia()

    def _categoria_propia(self):
        fila = self.repo.db.execute('''SELECT c.id FROM CATEGORIA c JOIN CATALOGO ca
            ON ca.id = c.catalogo_id WHERE ca.origen = 'propia' ORDER BY c.id LIMIT 1''').fetchone()
        if fila:
            return fila[0]
        catalogo = self.repo.crear_catalogo('Personal', PROPIA)
        return self.repo.crear_categoria(catalogo, 'General')

    def listar(self):
        return self.repo.listar_frases()

    def _validar_abreviatura(self, abreviatura, excepto_id=None):
        abreviatura = (abreviatura or '').strip()
        if not abreviatura:
            raise ValueError('La abreviatura no puede estar vacía.')
        existente = self.repo.db.execute(
            'SELECT id FROM FRASE WHERE abreviatura = ? COLLATE NOCASE', (abreviatura,)).fetchone()
        if existente and existente[0] != excepto_id:
            raise ValueError(f'La abreviatura «{abreviatura}» ya está en uso.')
        return abreviatura

    def _propia(self, ident):
        frase = self.repo.obtener_frase(ident)
        if frase['origen'] == COMPARTIDA:
            raise ValueError('Las frases compartidas son de solo lectura.')
        return frase

    def crear(self, titulo, abreviatura, contenido):
        abreviatura = self._validar_abreviatura(abreviatura)
        return self.repo.crear_frase(self._categoria, titulo, abreviatura, contenido, PROPIA)

    def editar(self, ident, titulo, abreviatura, contenido):
        frase = self._propia(ident)
        abreviatura = self._validar_abreviatura(abreviatura, ident)
        self.repo.actualizar_frase(ident, frase['categoria_id'], titulo, abreviatura, contenido)

    def duplicar(self, ident):
        """Crea una copia propia con una abreviatura libre (abrev2, abrev3, ...)."""
        original = self.repo.obtener_frase(ident)
        n = 2
        while True:
            try:
                nueva = self._validar_abreviatura(f'{original["abreviatura"]}{n}')
                break
            except ValueError:
                n += 1
        return self.repo.crear_frase(self._categoria, original['titulo'], nueva,
                                    original['contenido'], PROPIA)

    def eliminar(self, ident):
        self._propia(ident)
        try:
            self.repo.eliminar_frase(ident)
        except sqlite3.Error as error:
            raise ValueError(f'No se pudo eliminar la frase: {error}') from error
