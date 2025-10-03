import sys, os, json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QComboBox, QGridLayout, QFontComboBox
)
from PyQt6.QtGui import QFont

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

TIPOS_FONDOS = [
    "normal", "gol_local", "gol_visita", "cambio_local",
    "cambio_visita", "tarjeta_local", "tarjeta_visita",
    "extra", "stats"
]

ELEMENTOS = ["equipo_local","marcador_local","equipo_visita","marcador_visita","reloj"]

# Cargar o inicializar config
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH,"r",encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}

# Inicializar posiciones y tamaños si no existen
for tipo in TIPOS_FONDOS:
    if "posiciones" not in config:
        config["posiciones"] = {}
    if tipo not in config["posiciones"]:
        config["posiciones"][tipo] = {}
    for elem in ELEMENTOS:
        if elem not in config["posiciones"][tipo]:
            defaults_pos = {
                "equipo_local": {"top":80,"left":90,"size":36,"font":"Arial"},
                "marcador_local": {"top":35,"left":190,"size":96,"font":"Arial"},
                "equipo_visita": {"top":80,"left":310,"size":36,"font":"Arial"},
                "marcador_visita": {"top":35,"left":300,"size":96,"font":"Arial"},
                "reloj": {"top":110,"left":250,"size":32,"font":"Arial"}
            }
            config["posiciones"][tipo][elem] = defaults_pos[elem]

class Configuracion(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuración Marcador Completo")
        self.setGeometry(100,100,700,500)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Selector de tipo de marcador
        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(TIPOS_FONDOS)
        self.tipo_combo.currentTextChanged.connect(self.cambiar_tipo)
        self.layout.addWidget(QLabel("Selecciona tipo de marcador/fondo:"))
        self.layout.addWidget(self.tipo_combo)

        # Grid de posiciones y tamaños
        self.grid = QGridLayout()
        self.spinboxes = {}  # {"equipo_local": {"top":SpinBox, "left":SpinBox, "size":SpinBox, "font":FontComboBox}, ...}
        for i, elem in enumerate(ELEMENTOS):
            self.grid.addWidget(QLabel(elem+" Top:"), i, 0)
            spin_top = QSpinBox()
            spin_top.setRange(0,1000)
            self.grid.addWidget(spin_top, i, 1)

            self.grid.addWidget(QLabel(elem+" Left:"), i, 2)
            spin_left = QSpinBox()
            spin_left.setRange(0,1000)
            self.grid.addWidget(spin_left, i, 3)

            self.grid.addWidget(QLabel(elem+" Size:"), i, 4)
            spin_size = QSpinBox()
            spin_size.setRange(10,200)
            self.grid.addWidget(spin_size, i, 5)

            self.grid.addWidget(QLabel(elem+" Font:"), i, 6)
            font_box = QFontComboBox()
            self.grid.addWidget(font_box, i, 7)

            self.spinboxes[elem] = {"top":spin_top,"left":spin_left,"size":spin_size,"font":font_box}

        self.layout.addLayout(self.grid)

        # Botón guardar
        self.guardar_btn = QPushButton("Guardar y Volver a Transmitir")
        self.guardar_btn.clicked.connect(self.guardar)
        self.layout.addWidget(self.guardar_btn)

        # Inicializar con el primer tipo
        self.cambiar_tipo(TIPOS_FONDOS[0])

    def cambiar_tipo(self, tipo):
        self.tipo_actual = tipo
        for elem in ELEMENTOS:
            cfg = config["posiciones"][tipo][elem]
            self.spinboxes[elem]["top"].setValue(cfg["top"])
            self.spinboxes[elem]["left"].setValue(cfg["left"])
            self.spinboxes[elem]["size"].setValue(cfg.get("size",36))
            # CORRECCIÓN: QFont desde string
            self.spinboxes[elem]["font"].setCurrentFont(QFont(cfg.get("font","Arial")))

    def guardar(self):
        for elem in ELEMENTOS:
            cfg = config["posiciones"][self.tipo_actual][elem]
            cfg["top"] = self.spinboxes[elem]["top"].value()
            cfg["left"] = self.spinboxes[elem]["left"].value()
            cfg["size"] = self.spinboxes[elem]["size"].value()
            cfg["font"] = self.spinboxes[elem]["font"].currentFont().family()
        with open(CONFIG_PATH,"w",encoding="utf-8") as f:
            json.dump(config,f,indent=2)
        self.close()  # Cierra la ventana y vuelve al launcher

if __name__=="__main__":
    app = QApplication(sys.argv)
    ventana = Configuracion()
    ventana.show()
    sys.exit(app.exec())