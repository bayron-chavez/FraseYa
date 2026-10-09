"""Límite local de peticiones, complementario a la protección de Supabase."""
from collections import deque
from threading import Lock
import math
import time


class LimiteAcceso:
    def __init__(self, reloj=time.monotonic, maximo=5, ventana=60):
        self.reloj, self.maximo, self.ventana = reloj, maximo, ventana
        self.intentos = deque()
        self.bloqueado_hasta = 0
        self.lock = Lock()

    def reservar(self):
        with self.lock:
            ahora = self.reloj()
            while self.intentos and self.intentos[0] <= ahora - self.ventana:
                self.intentos.popleft()
            espera = self.bloqueado_hasta - ahora
            if len(self.intentos) >= self.maximo:
                espera = max(espera, self.intentos[0] + self.ventana - ahora)
            if espera > 0:
                raise ValueError(f'Demasiados intentos. Espera {math.ceil(espera)} segundos para volver a intentar.')
            self.intentos.append(ahora)

    def bloquear(self, segundos=300):
        with self.lock:
            self.bloqueado_hasta = max(self.bloqueado_hasta, self.reloj() + segundos)
