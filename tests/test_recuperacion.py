import os
from pathlib import Path
import subprocess
import sys
from fraseya.infraestructura import RepositorioSQLite


def test_cierre_forzado_revierte_transaccion_y_conserva_catalogo(tmp_path):
    ruta = tmp_path/'prueba.db'
    with RepositorioSQLite(ruta) as repo:
        repo.reemplazar_compartidas(1, 'admin', '2026-10-08', [{'nombre': 'General', 'frases': [
            {'titulo': 'Hola', 'abreviatura': 'hola', 'contenido': 'Hola'}]}])
    programa = """
import sqlite3,sys,time
db=sqlite3.connect(sys.argv[1])
db.execute('BEGIN IMMEDIATE')
db.execute("DELETE FROM FRASE WHERE origen='compartida'")
db.execute("UPDATE CATALOGO SET version=99 WHERE origen='compartida'")
print('transaccion-abierta',flush=True)
time.sleep(30)
"""
    proceso = subprocess.Popen([sys.executable, '-c', programa, str(ruta)], stdout=subprocess.PIPE, text=True)
    try:
        assert proceso.stdout.readline().strip() == 'transaccion-abierta'
        proceso.terminate()
        proceso.wait(timeout=5)
    finally:
        if proceso.poll() is None:
            proceso.kill()
            proceso.wait(timeout=5)
        proceso.stdout.close()
    with RepositorioSQLite(ruta) as repo:
        assert repo.listar_catalogos('compartida')[0]['version'] == 1
        assert repo.listar_frases('compartida')[0]['abreviatura'] == 'hola'
        assert repo.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
