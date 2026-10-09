import sys
from PIL import Image
from fraseya.presentacion.identidad import recurso


def test_icono_multiresolucion_y_logo_disponibles():
    with Image.open(recurso('fraseya.ico')) as icono:
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= icono.ico.sizes()
    with Image.open(recurso('logo.png')) as logo:
        assert logo.width == logo.height


def test_recursos_se_resuelven_dentro_del_ejecutable(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert recurso('logo.png') == tmp_path / 'assets' / 'logo.png'
