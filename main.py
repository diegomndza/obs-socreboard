import sys
import os
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QCheckBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_DIR = os.path.join(BASE_DIR, 'TXT')
EXCEL_PATH = os.path.join(BASE_DIR, 'equipos.xlsx')
OUTPUT_HTML = os.path.join(TXT_DIR, 'salida.html')
IMG_PATH = os.path.join(TXT_DIR, 'marcador.png')

# 🔧 POSICIONES PERSONALIZABLES EN PX
POSICIONES = {
    "equipo_local": {"top": 80, "left": 90},
    "marcador_local": {"top": 35, "left": 190},
    "equipo_visita": {"top": 80, "left": 310},
    "marcador_visita": {"top": 35, "left": 300},
    "reloj": {"top": 110, "left": 250},
}

# 🔤 TAMAÑOS DE FUENTE
TAMAÑOS_FUENTE = {
    "marcador": 96,
    "reloj": 32,
    "equipo": 36,
}

# Fuente para matplotlib (debe estar instalada en el sistema o ruta conocida)
FUENTE_MATPLOTLIB = "Novecento Sans Wide"  # Cambia por la que tengas instalada

def leer_equipos_desde_excel(path):
    try:
        df = pd.read_excel(path, sheet_name="equipos", header=None)
        return [str(equipo).strip() for equipo in df[0].dropna()]
    except Exception as e:
        print(f"Error leyendo Excel: {e}")
        return ["Equipo A", "Equipo B"]

class Marcador(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marcador Soccer")
        self.setGeometry(100, 100, 700, 400)

        self.equipos = leer_equipos_desde_excel(EXCEL_PATH)
        self.reloj_segundos = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.actualizar_reloj)

        self.animacion_general = ""
        self.animacion_local = ""
        self.animacion_visita = ""
        self.mostrar_marcador = True

        layout = QVBoxLayout()
        equipos_layout = QHBoxLayout()
        marcador_layout = QHBoxLayout()
        control_layout = QHBoxLayout()

        # Mostrar marcador
        self.switch_mostrar = QCheckBox("Mostrar marcador")
        self.switch_mostrar.setChecked(True)
        self.switch_mostrar.stateChanged.connect(self.toggle_marcador)
        layout.addWidget(self.switch_mostrar)

        # Equipos (ComboBox)
        self.equipo_local = QComboBox()
        self.equipo_local.addItems(self.equipos)

        self.equipo_visita = QComboBox()
        self.equipo_visita.addItems(self.equipos)

        equipos_layout.addWidget(self.equipo_local)
        equipos_layout.addWidget(self.equipo_visita)

        # Marcadores (usamos QLabel para mostrar imagen generada)
        self.imagen_marcador = QLabel()
        self.imagen_marcador.setFixedSize(700, 200)
        self.imagen_marcador.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Reloj (mostrar separado también)
        self.reloj_label = QLabel("00:00")
        control_layout.addWidget(self.reloj_label)

        # Botones
        self.iniciar_btn = QPushButton("Iniciar")
        self.iniciar_btn.clicked.connect(self.iniciar_reloj)

        self.reiniciar_btn = QPushButton("Reiniciar")
        self.reiniciar_btn.clicked.connect(self.reiniciar_reloj)

        self.gol_local_btn = QPushButton("Gol Local")
        self.gol_local_btn.clicked.connect(lambda: self.cambiar_marcador("local", 1))

        self.gol_visita_btn = QPushButton("Gol Visita")
        self.gol_visita_btn.clicked.connect(lambda: self.cambiar_marcador("visita", 1))

        self.anular_local_btn = QPushButton("Anular Gol Local")
        self.anular_local_btn.clicked.connect(lambda: self.cambiar_marcador("local", -1))

        self.anular_visita_btn = QPushButton("Anular Gol Visita")
        self.anular_visita_btn.clicked.connect(lambda: self.cambiar_marcador("visita", -1))

        control_layout.addWidget(self.iniciar_btn)
        control_layout.addWidget(self.reiniciar_btn)
        control_layout.addWidget(self.gol_local_btn)
        control_layout.addWidget(self.gol_visita_btn)
        control_layout.addWidget(self.anular_local_btn)
        control_layout.addWidget(self.anular_visita_btn)

        layout.addLayout(equipos_layout)
        layout.addWidget(self.imagen_marcador)
        layout.addLayout(control_layout)

        self.setLayout(layout)

        self.marcador_local = 0
        self.marcador_visita = 0

        self.actualizar_marcador_imagen()

    def toggle_marcador(self):
        self.mostrar_marcador = self.switch_mostrar.isChecked()
        self.imagen_marcador.setVisible(self.mostrar_marcador)

    def iniciar_reloj(self):
        self.timer.start(1000)

    def reiniciar_reloj(self):
        self.timer.stop()
        self.reloj_segundos = 0
        self.reloj_label.setText("00:00")
        self.actualizar_marcador_imagen()

    def actualizar_reloj(self):
        self.reloj_segundos += 1
        minutos = self.reloj_segundos // 60
        segundos = self.reloj_segundos % 60
        self.reloj_label.setText(f"{minutos:02}:{segundos:02}")
        self.actualizar_marcador_imagen()

    def cambiar_marcador(self, equipo, cambio):
        if equipo == "local":
            nuevo = max(0, self.marcador_local + cambio)
            if nuevo != self.marcador_local:
                self.marcador_local = nuevo
        else:
            nuevo = max(0, self.marcador_visita + cambio)
            if nuevo != self.marcador_visita:
                self.marcador_visita = nuevo
        self.actualizar_marcador_imagen()

    def actualizar_marcador_imagen(self):
        # Generar imagen con matplotlib
        fig, ax = plt.subplots(figsize=(7, 2), dpi=100)
        ax.axis('off')

        texto = f"{self.equipo_local.currentText()}  {self.marcador_local}  -  {self.marcador_visita}  {self.equipo_visita.currentText()}"
        reloj_texto = self.reloj_label.text()

        # Texto marcador
        ax.text(
            0.5, 0.6, texto,
            fontsize=40,
            fontname=FUENTE_MATPLOTLIB,
            fontweight='heavy',
            ha='center',
            va='center',
            color='white'
        )

        # Texto reloj (más pequeño debajo)
        ax.text(
            0.5, 0.25, reloj_texto,
            fontsize=24,
            fontname=FUENTE_MATPLOTLIB,
            fontweight='normal',
            ha='center',
            va='center',
            color='yellow'
        )

        fig.patch.set_facecolor('black')
        ax.set_facecolor('black')

        # Guardar imagen
        fig.savefig(IMG_PATH, bbox_inches='tight', pad_inches=0.2, transparent=False)
        plt.close(fig)

        # Cargar imagen en QLabel
        pixmap = QPixmap(IMG_PATH)
        self.imagen_marcador.setPixmap(pixmap.scaled(
            self.imagen_marcador.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = Marcador()
    ventana.show()
    sys.exit(app.exec())