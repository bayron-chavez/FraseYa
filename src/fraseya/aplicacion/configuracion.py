"""RF-11: ajustes del usuario (atajo, tecla de confirmación, velocidad, carpeta compartida).

Se guardan como clave/valor en la tabla CONFIGURACION. Un valor inválido o
ausente se reemplaza por el predeterminado al leer, y al guardar se informan
todos los errores a la vez.
"""
from dataclasses import dataclass, replace

from fraseya.infraestructura.escritor_texto import (VELOCIDAD_MAX_MS, VELOCIDAD_MIN_MS,
                                                    VELOCIDAD_PREDETERMINADA_MS)
from fraseya.infraestructura.teclado_global import (ATAJO_PREDETERMINADO, TECLA_PREDETERMINADA,
                                                    TECLAS_CONFIRMACION, interpretar_atajo)
from .gestion_frases import ErroresValidacion

INTERVALO_MIN, INTERVALO_MAX, INTERVALO_PREDETERMINADO = 1, 1440, 15

# Con Ctrl+Alt (AltGr en muchos teclados) las letras y los dígitos escriben símbolos
# (@, €…): un atajo ahí se dispararía al teclear.
_ORDEN_MODIFICADORES = ('ctrl', 'alt', 'shift', 'win')
_RESERVADOS = {'alt+f4', 'ctrl+f4', 'ctrl+shift+n', 'ctrl+shift+t', 'ctrl+shift+w', 'ctrl+shift+i',
               'ctrl+shift+c', 'ctrl+shift+v', 'ctrl+shift+p'}


# Atajos sugeridos en la pantalla de configuración: todos pasan la validación (hay una prueba
# que lo exige). Ninguno usa letras con Ctrl+Alt (AltGr) ni Alt+Shift (cambia el idioma del teclado).
ATAJOS_RECOMENDADOS = (
    ('ctrl+alt+espacio', 'Recomendado: fácil de recordar y sin riesgo de escribir símbolos.'),
    ('ctrl+shift+espacio', 'Cómodo con una sola mano; revisa que tu aplicación no lo use.'),
    ('ctrl+alt+f9', 'Sin conflictos con símbolos; las teclas F casi no se usan en el texto.'),
    ('ctrl+shift+f9', 'Igual que el anterior, con Ctrl+Shift.'),
)


@dataclass(frozen=True)
class Ajustes:
    tecla_confirmacion: str = TECLA_PREDETERMINADA
    atajo_buscador: str = ATAJO_PREDETERMINADO
    velocidad_ms: int = VELOCIDAD_PREDETERMINADA_MS
    carpeta_compartida: str = ''
    intervalo_sincronizacion_min: int = INTERVALO_PREDETERMINADO


CAMPOS = tuple(Ajustes.__dataclass_fields__)


def normalizar_atajo(texto):
    """'Ctrl + Alt + Espacio' -> 'ctrl+alt+espacio' (modificadores en orden fijo)."""
    partes = [p.strip().lower() for p in (texto or '').split('+') if p.strip()]
    if not partes:
        return ''
    *mods, tecla = partes
    mods = sorted(set(mods), key=lambda m: _ORDEN_MODIFICADORES.index(m)
                  if m in _ORDEN_MODIFICADORES else 99)
    return '+'.join([*mods, tecla])


def _error_de_atajo(texto):
    """Mensaje si el atajo no sirve, o None si es válido."""
    try:
        modificadores, vk = interpretar_atajo(texto)
    except ValueError as error:
        return str(error)
    normal = normalizar_atajo(texto)
    if 'win' in modificadores:
        return 'Windows se reserva las combinaciones con la tecla Windows.'
    if normal in _RESERVADOS:
        return f'«{normal}» ya la usan otras aplicaciones; elige otra combinación.'
    es_funcion = 0x70 <= vk <= 0x7B
    if modificadores == {'ctrl', 'alt'} and not es_funcion and vk != 0x20:
        return ('Con Ctrl+Alt solo puedes usar Espacio o una tecla F: en muchos teclados Ctrl+Alt '
                'es AltGr y escribe símbolos como @ o €.')
    if len(modificadores) < 2 and not es_funcion:
        return ('Usa al menos dos modificadores (por ejemplo ctrl+shift+k) para no pisar los '
                'atajos de otras aplicaciones, o una tecla F con uno.')
    return None


class Configuracion:
    def __init__(self, repositorio):
        self.repo = repositorio

    def leer(self):
        """Ajustes guardados; lo inválido o ausente vuelve a su valor predeterminado."""
        base = Ajustes()
        crudo = {c: self.repo.leer_configuracion(c, None) for c in CAMPOS}
        try:
            return self.validar({c: v for c, v in crudo.items() if v is not None}, completar=base)
        except ErroresValidacion:
            return self._tolerante(base, crudo)

    def _tolerante(self, base, crudo):
        """Campo por campo: conserva los válidos y descarta los demás."""
        ajustes = base
        for campo, valor in crudo.items():
            if valor is None:
                continue
            try:
                ajustes = self.validar({campo: valor}, completar=ajustes)
            except ErroresValidacion:
                pass
        return ajustes

    def validar(self, valores, completar=None):
        """Convierte y valida; lanza ErroresValidacion con todos los problemas juntos."""
        actual = completar or Ajustes()
        errores, nuevos = [], {}

        if 'tecla_confirmacion' in valores:
            tecla = str(valores['tecla_confirmacion']).strip().lower()
            if tecla in TECLAS_CONFIRMACION:
                nuevos['tecla_confirmacion'] = tecla
            else:
                errores.append(f'La tecla de confirmación debe ser: {", ".join(TECLAS_CONFIRMACION)}.')

        if 'atajo_buscador' in valores:
            atajo = normalizar_atajo(str(valores['atajo_buscador']))
            mensaje = _error_de_atajo(atajo)
            if mensaje:
                errores.append(mensaje)
            else:
                nuevos['atajo_buscador'] = atajo

        if 'velocidad_ms' in valores:
            velocidad = self._entero(valores['velocidad_ms'])
            if velocidad is None or not VELOCIDAD_MIN_MS <= velocidad <= VELOCIDAD_MAX_MS:
                errores.append(f'La velocidad debe ser un número entre {VELOCIDAD_MIN_MS} y '
                               f'{VELOCIDAD_MAX_MS} ms por carácter.')
            else:
                nuevos['velocidad_ms'] = velocidad

        if 'carpeta_compartida' in valores:
            carpeta = str(valores['carpeta_compartida']).strip().strip('"')
            if any(c in carpeta for c in '<>"|?*\n\r\t'):
                errores.append('La ruta de la carpeta compartida tiene caracteres no válidos.')
            else:
                nuevos['carpeta_compartida'] = carpeta

        if 'intervalo_sincronizacion_min' in valores:
            intervalo = self._entero(valores['intervalo_sincronizacion_min'])
            if intervalo is None or not INTERVALO_MIN <= intervalo <= INTERVALO_MAX:
                errores.append(f'El intervalo de sincronización debe ser un número de minutos entre '
                               f'{INTERVALO_MIN} y {INTERVALO_MAX}.')
            else:
                nuevos['intervalo_sincronizacion_min'] = intervalo

        if errores:
            raise ErroresValidacion(errores)
        return replace(actual, **nuevos)

    def guardar(self, valores):
        """Valida todos los campos y los guarda juntos (o no guarda nada). Devuelve los Ajustes."""
        ajustes = self.validar(valores, completar=self.leer())
        self.repo.guardar_configuraciones({c: str(getattr(ajustes, c)) for c in CAMPOS})
        return ajustes

    def restablecer(self):
        ajustes = Ajustes()
        self.repo.guardar_configuraciones({c: str(getattr(ajustes, c)) for c in CAMPOS})
        return ajustes

    @staticmethod
    def _entero(valor):
        try:
            texto = str(valor).strip()
            return int(texto) if texto.lstrip('-').isdigit() else None
        except (TypeError, ValueError):
            return None
