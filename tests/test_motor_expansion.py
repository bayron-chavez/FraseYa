from fraseya.aplicacion.motor_expansion import LARGO_MAXIMO, MotorExpansion


class EscritorFalso:
    def __init__(self):
        self.llamadas = []

    def reemplazar(self, borrar, texto):
        self.llamadas.append((borrar, texto))


class Ventanas:
    """Ventana activa controlable y registro de activaciones."""
    def __init__(self):
        self.actual = 100
        self.activadas = []

    def activar(self, ventana):
        self.activadas.append(ventana)


FRASES = [
    {'abreviatura': 'hola', 'contenido': 'Buenos días, ¿en qué puedo ayudarle?'},
    {'abreviatura': 'cierre', 'contenido': 'Gracias {nombre}, su caso {orden} quedó registrado.'},
]


def motor(pedir=None, frases=FRASES):
    escritor, ventanas = EscritorFalso(), Ventanas()
    m = MotorExpansion(escritor, pedir or (lambda nombres, iniciales: None),
                       ventana_activa=lambda: ventanas.actual,
                       activar_ventana=ventanas.activar, lanzar=lambda trabajo: trabajo())
    m.actualizar_frases(frases)
    return m, escritor, ventanas


def escribir(m, texto):
    for c in texto:
        m.caracter(c)


def test_formulario_recibe_contexto_tanto_teclado_como_buscador():
    recibidos = []
    escritor = EscritorFalso()
    contenido = 'Hola {nombre}, te atiende {nombre_2}'

    def pedir(nombres, iniciales, frase):
        recibidos.append((nombres, frase))
        return {'nombre': 'Ana', 'nombre_2': 'Luis'}

    m = MotorExpansion(escritor, lambda *_: None, lanzar=lambda trabajo: trabajo(),
                       pedir_con_contexto=pedir)
    m.actualizar_frases([{'abreviatura': 'saludo', 'contenido': contenido}])
    escribir(m, 'saludo')
    m.confirmar()
    m.insertar(contenido, None)
    assert recibidos == [(['nombre', 'nombre_2'], contenido)] * 2
    assert escritor.llamadas == [(6, 'Hola Ana, te atiende Luis'),
                                 (0, 'Hola Ana, te atiende Luis')]


def test_expande_al_confirmar_una_abreviatura_existente():
    m, escritor, _ = motor()
    escribir(m, 'hola')
    assert m.confirmar() is True
    assert escritor.llamadas == [(4, 'Buenos días, ¿en qué puedo ayudarle?')]


def test_sin_la_tecla_de_confirmacion_no_se_expande():
    m, escritor, _ = motor()
    escribir(m, 'hola')
    assert escritor.llamadas == []


def test_confirmar_sin_coincidencia_no_expande_ni_traga_la_tecla():
    m, escritor, _ = motor()
    escribir(m, 'xyz')
    assert m.confirmar() is False
    assert escritor.llamadas == [] and m.escrito == ''


def test_confirmar_sin_haber_escrito_nada():
    m, escritor, _ = motor()
    assert m.confirmar() is False


def test_no_distingue_mayusculas():
    m, escritor, _ = motor()
    escribir(m, 'HoLa')
    assert m.confirmar() is True
    assert escritor.llamadas[0][0] == 4


def test_la_abreviatura_debe_ser_la_palabra_completa():
    m, escritor, _ = motor()
    escribir(m, 'xhola')
    assert m.confirmar() is False
    escribir(m, 'hola!')
    assert m.confirmar() is False
    assert escritor.llamadas == []


def test_retroceso_corrige_lo_escrito():
    m, escritor, _ = motor()
    escribir(m, 'holx')
    m.retroceso()
    m.caracter('a')
    assert m.confirmar() is True


def test_reiniciar_descarta_lo_escrito():
    m, _, _ = motor()
    escribir(m, 'hol')
    m.reiniciar()
    m.caracter('a')
    assert m.confirmar() is False


def test_frase_con_variables_pide_el_formulario_y_escribe_el_resultado():
    pedidos = []

    def pedir(nombres, iniciales):
        pedidos.append(nombres)
        return {'nombre': 'Ana', 'orden': '1234'}

    m, escritor, ventanas = motor(pedir)
    escribir(m, 'cierre')
    m.confirmar()
    assert pedidos == [['nombre', 'orden']]
    assert escritor.llamadas == [(6, 'Gracias Ana, su caso 1234 quedó registrado.')]
    assert ventanas.activadas == [100]     # se devuelve el foco a donde se escribía


def test_frase_sin_variables_no_abre_formulario_ni_cambia_el_foco():
    def no_debe_llamarse(*_):
        raise AssertionError('No debe abrirse el formulario')

    m, escritor, ventanas = motor(no_debe_llamarse)
    escribir(m, 'hola')
    m.confirmar()
    assert escritor.llamadas and ventanas.activadas == []


def test_cancelar_el_formulario_deja_la_abreviatura_sin_tocar():
    m, escritor, _ = motor(lambda nombres, iniciales: None)
    escribir(m, 'cierre')
    assert m.confirmar() is True      # la tecla se consumió
    assert escritor.llamadas == []    # pero no se borró ni escribió nada


def test_si_cambias_de_ventana_a_mitad_no_se_expande():
    m, escritor, ventanas = motor()
    escribir(m, 'hol')
    ventanas.actual = 200
    m.caracter('a')
    assert m.confirmar() is False
    assert escritor.llamadas == []


def test_actualizar_frases_incorpora_las_nuevas_y_olvida_las_borradas():
    m, escritor, _ = motor()
    m.actualizar_frases([{'abreviatura': 'nueva', 'contenido': 'Texto nuevo'}])
    escribir(m, 'hola')
    assert m.confirmar() is False
    escribir(m, 'nueva')
    assert m.confirmar() is True
    assert escritor.llamadas == [(5, 'Texto nuevo')]


def test_ignora_las_teclas_mientras_expande():
    cola = []
    escritor, ventanas = EscritorFalso(), Ventanas()
    m = MotorExpansion(escritor, lambda *_: None, lambda: 1, lambda _v: None, lanzar=cola.append)
    m.actualizar_frases(FRASES)
    escribir(m, 'hola')
    assert m.confirmar() is True
    escribir(m, 'hola')                  # ocupado: se descarta
    assert m.confirmar() is False
    cola[0]()                            # termina la expansión
    escribir(m, 'hola')
    assert m.confirmar() is True


def test_un_texto_larguisimo_no_acumula_memoria():
    m, _, _ = motor()
    escribir(m, 'a' * (LARGO_MAXIMO + 5))
    assert len(m.escrito) <= LARGO_MAXIMO


def test_un_error_al_escribir_no_deja_el_motor_bloqueado():
    class EscritorQueFalla(EscritorFalso):
        def reemplazar(self, *_):
            raise OSError('SendInput falló')

    m = MotorExpansion(EscritorQueFalla(), lambda *_: None, lambda: 1, lambda _v: None,
                       lanzar=lambda trabajo: None)
    m.actualizar_frases(FRASES)
    escribir(m, 'hola')
    trabajos = []
    m._lanzar = trabajos.append
    assert m.confirmar() is True
    try:
        trabajos[0]()
    except OSError:
        pass
    escribir(m, 'hola')
    assert m.confirmar() is True         # volvió a estar disponible


# ---- inserción desde el buscador rápido (RF-02) ---------------------------

def test_insertar_escribe_sin_borrar_y_devuelve_el_foco():
    m, escritor, ventanas = motor()
    assert m.insertar('Buenos días', 777) is True
    assert escritor.llamadas == [(0, 'Buenos días')]
    assert ventanas.activadas == [777]


def test_insertar_con_campos_pide_el_formulario():
    pedidos = []

    def pedir(nombres, iniciales):
        pedidos.append(nombres)
        return {'nombre': 'Ana', 'orden': '9'}

    m, escritor, ventanas = motor(pedir)
    m.insertar('Hola {nombre}, caso {orden}', 777)
    assert pedidos == [['nombre', 'orden']]
    assert escritor.llamadas == [(0, 'Hola Ana, caso 9')]
    assert ventanas.activadas == [777]


def test_insertar_cancelado_devuelve_el_foco_pero_no_escribe():
    m, escritor, ventanas = motor(lambda nombres, iniciales: None)
    m.insertar('Hola {nombre}', 777)
    assert escritor.llamadas == [] and ventanas.activadas == [777]


def test_insertar_ocupado_rechaza_una_segunda_peticion():
    cola = []
    escritor, ventanas = EscritorFalso(), Ventanas()
    m = MotorExpansion(escritor, lambda *_: None, lambda: 1, ventanas.activar, lanzar=cola.append)
    assert m.insertar('uno', 5) is True
    assert m.insertar('dos', 5) is False
    cola[0]()
    assert m.insertar('tres', 5) is True


def test_insertar_descarta_lo_que_se_venia_escribiendo():
    m, _, _ = motor()
    escribir(m, 'hol')
    m.insertar('texto', 1)
    assert m.escrito == ''
