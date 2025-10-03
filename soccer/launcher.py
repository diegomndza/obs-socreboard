import sys
import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marcador Soccer - Launcher")
        self.setGeometry(200, 200, 300, 150)

        layout = QVBoxLayout()

        btn_config = QPushButton("Configurar")
        btn_config.clicked.connect(self.abrir_config)
        layout.addWidget(btn_config)

        btn_transmitir = QPushButton("Transmitir")
        btn_transmitir.clicked.connect(self.abrir_transmision)
        layout.addWidget(btn_transmitir)

        self.setLayout(layout)

    def abrir_config(self):
        os.system(f"{sys.executable} {os.path.join(BASE_DIR,'configuracion.py')}")

    def abrir_transmision(self):
        os.system(f"{sys.executable} {os.path.join(BASE_DIR,'app.py')}")

if __name__=="__main__":
    app = QApplication(sys.argv)
    ventana = Launcher()
    ventana.show()
    sys.exit(app.exec())