"""Lanzador de la primera etapa visual Qt. Por defecto usa datos temporales."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from fraseya.infraestructura import RepositorioSQLite
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.presentacion.qt_vista import VentanaQt


def main():
    app=QApplication(sys.argv)
    with RepositorioSQLite(':memory:') as repo:
        gestion=GestionFrases(repo); categoria=gestion.categorias_propias()[0]['id']
        frases=[('Asistencia con la conexión','!conexion','Estimado/a {nombre}, lamentamos los inconvenientes con su conexión. ¿Podría indicarnos si la lentitud ocurre en todos sus dispositivos y si utiliza Wi-Fi o cable?'),
                ('Seguimiento de pedido','!pedido','Estimado/a {nombre}, para consultar su pedido {pedido}, ¿podría confirmar la fecha de compra?'),
                ('Bienvenida a atención al cliente','!bienvenida','Estimado/a {nombre}, gracias por contactarnos. ¿En qué podemos ayudarle hoy?'),
                ('Cierre de atención','!cierre','Gracias por su tiempo, {nombre}. Quedamos atentos si necesita ayuda adicional.')]
        for titulo,abreviatura,contenido in frases: gestion.crear(titulo,abreviatura,contenido,categoria)
        gestion.alternar_favorita(gestion.listar()[0]['id'])
        ventana=VentanaQt(gestion,demostracion=True); ventana.show()
        return app.exec()


if __name__=='__main__': sys.exit(main())
