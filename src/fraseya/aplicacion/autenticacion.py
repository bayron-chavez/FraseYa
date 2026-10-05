"""Cuentas locales con contraseñas derivadas y sesiones por instalación."""
from dataclasses import dataclass
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str
    token: str


class Autenticacion:
    def __init__(self, ruta):
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(ruta))
        self.db.execute('''CREATE TABLE IF NOT EXISTS usuario (
            nombre TEXT PRIMARY KEY COLLATE NOCASE, rol TEXT NOT NULL
            CHECK(rol IN ('administrador','usuario')), sal BLOB NOT NULL, clave BLOB NOT NULL)''')
        self.db.commit()
        self._sesiones = {}

    def cerrar(self):
        self._sesiones.clear()
        self.db.close()

    def tiene_usuarios(self):
        return self.db.execute('SELECT 1 FROM usuario LIMIT 1').fetchone() is not None

    def _crear(self, nombre, clave, rol):
        nombre = nombre.strip()
        if not nombre or len(nombre) > 64:
            raise ValueError('El nombre debe tener entre 1 y 64 caracteres.')
        if len(clave) < 10:
            raise ValueError('La contraseña debe tener al menos 10 caracteres.')
        if rol not in ('administrador', 'usuario'):
            raise ValueError('Rol inválido.')
        sal = secrets.token_bytes(16)
        derivada = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, 600000)
        try:
            with self.db:
                self.db.execute('INSERT INTO usuario VALUES(?,?,?,?)', (nombre, rol, sal, derivada))
        except sqlite3.IntegrityError:
            raise ValueError('Ese nombre de usuario ya existe.') from None

    def crear_administrador_inicial(self, nombre, clave):
        # BEGIN IMMEDIATE evita que dos arranques creen administradores iniciales.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.tiene_usuarios():
                raise PermissionError('La cuenta inicial ya está creada.')
            self._crear(nombre, clave, 'administrador')
        except Exception:
            self.db.rollback()
            raise

    def iniciar_sesion(self, nombre, clave):
        fila = self.db.execute('SELECT nombre,rol,sal,clave FROM usuario WHERE nombre=?', (nombre.strip(),)).fetchone()
        sal = fila[2] if fila else b'0' * 16
        calculada = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, 600000)
        if not fila or not hmac.compare_digest(calculada, fila[3]):
            raise PermissionError('Usuario o contraseña incorrectos.')
        sesion = Sesion(fila[0], fila[1], secrets.token_urlsafe(32))
        self._sesiones[sesion.token] = sesion
        return sesion

    def validar(self, sesion, administrador=False):
        if not isinstance(sesion, Sesion) or self._sesiones.get(sesion.token) != sesion:
            raise PermissionError('Inicia sesión para continuar.')
        if administrador and sesion.rol != 'administrador':
            raise PermissionError('Solo el administrador puede realizar esta acción.')

    def crear_usuario(self, sesion, nombre, clave, rol='usuario'):
        self.validar(sesion, administrador=True)
        self._crear(nombre, clave, rol)

    def listar_usuarios(self, sesion):
        self.validar(sesion, administrador=True)
        return [{'nombre': nombre, 'rol': rol} for nombre, rol in
                self.db.execute('SELECT nombre,rol FROM usuario ORDER BY nombre COLLATE NOCASE')]

    def _usuario(self, nombre):
        fila = self.db.execute('SELECT nombre,rol FROM usuario WHERE nombre=?', (nombre,)).fetchone()
        if not fila:
            raise ValueError('La cuenta ya no existe.')
        return fila

    def _invalidar(self, nombre, conservar=None):
        for token, sesion in list(self._sesiones.items()):
            if sesion.usuario == nombre and token != conservar:
                self._sesiones.pop(token, None)

    def actualizar_usuario(self, sesion, nombre_actual, nombre, rol, clave=None):
        self.validar(sesion, administrador=True)
        nombre = nombre.strip()
        if not nombre or len(nombre) > 64:
            raise ValueError('El nombre debe tener entre 1 y 64 caracteres.')
        if rol not in ('administrador', 'usuario'):
            raise ValueError('Rol inválido.')
        if clave is not None and len(clave) < 10:
            raise ValueError('La contraseña debe tener al menos 10 caracteres.')
        sal = secrets.token_bytes(16) if clave is not None else None
        derivada = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, 600000) if clave is not None else None
        self.db.execute('BEGIN IMMEDIATE')
        try:
            actual, rol_actual = self._usuario(nombre_actual)
            if actual == sesion.usuario and (nombre != actual or rol != rol_actual):
                raise ValueError('No puedes cambiar el nombre o rol de la cuenta con la que estás conectado.')
            if rol_actual == 'administrador' and rol != 'administrador':
                cantidad = self.db.execute("SELECT COUNT(*) FROM usuario WHERE rol='administrador'").fetchone()[0]
                if cantidad <= 1:
                    raise ValueError('Debe quedar al menos un administrador.')
            self.db.execute('UPDATE usuario SET nombre=?,rol=? WHERE nombre=?', (nombre, rol, actual))
            if clave is not None:
                self.db.execute('UPDATE usuario SET sal=?,clave=? WHERE nombre=?', (sal, derivada, nombre))
            self.db.commit()
        except sqlite3.IntegrityError:
            self.db.rollback()
            raise ValueError('Ese nombre de usuario ya existe.') from None
        except Exception:
            self.db.rollback()
            raise
        self._invalidar(actual, conservar=sesion.token if actual == sesion.usuario else None)

    def eliminar_usuario(self, sesion, nombre):
        self.validar(sesion, administrador=True)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            actual, rol = self._usuario(nombre)
            if actual == sesion.usuario:
                raise ValueError('No puedes eliminar la cuenta con la que estás conectado.')
            if rol == 'administrador':
                cantidad = self.db.execute("SELECT COUNT(*) FROM usuario WHERE rol='administrador'").fetchone()[0]
                if cantidad <= 1:
                    raise ValueError('Debe quedar al menos un administrador.')
            self.db.execute('DELETE FROM usuario WHERE nombre=?', (actual,))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self._invalidar(actual)

    def salir(self, sesion):
        self._sesiones.pop(sesion.token, None)
