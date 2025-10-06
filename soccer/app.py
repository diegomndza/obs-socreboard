import sys
import os
import json
import re
import pandas as pd
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QDialog, QSpinBox, QRadioButton,
    QButtonGroup, QMessageBox, QFileDialog
)
from PyQt6.QtCore import QTimer
import random
from PyQt6.QtCore import Qt
import subprocess, socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(BASE_DIR, 'equipos.xlsx')
JUGADORES_PATH = os.path.join(BASE_DIR, 'jugadores.xlsx')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
OUTPUT_HTML = os.path.join(BASE_DIR, 'TXT', 'salida.html')
OUTPUT_STATE = os.path.join(BASE_DIR, 'TXT', 'estado.json')
os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)

FONDOS = {
    "normal": "marcador-soccer-partido",
    "gol_local": "marcador-soccer-local-gol",
    "gol_visita": "marcador-soccer-visita-gol",
    "cambio_local": "marcador-soccer-cambio-local",
    "cambio_visita": "marcador-soccer-cambio-visita",
    "tarjeta_local": "marcador-soccer-tarjeta-local",
    "tarjeta_visita": "marcador-soccer-tarjeta-visita",
    "tiempo_extra": "marcador-soccer-extra",
    "stats": "marcador-soccer-stats"
}

# ------------------ Config ------------------
def cargar_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH,'r',encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    cfg = {
        "fondos": FONDOS,
        "posiciones": {
            tipo: {
                "marcador_local":{"top":35,"left":190},
                "marcador_visita":{"top":35,"left":300},
                "equipo_local":{"top":80,"left":90},
                "equipo_visita":{"top":80,"left":310},
                "reloj":{"top":110,"left":250}
            } for tipo in FONDOS
        },
        "animaciones": {tipo:"slideInDown" for tipo in FONDOS},
        "fuente":"Arial",
        "equipo_local":"Equipo A",
        "equipo_visita":"Equipo B",
        "marcador_local":0,
        "marcador_visita":0,
        "brand_logo": "",
        "logo_local": "",
        "logo_visita": "",
        # ---- nuevos campos para reloj persistente ----
        "running": False,
        "start_epoch_ms": 0,
        "elapsed_ms": 0
    }
    with open(CONFIG_PATH,'w',encoding='utf-8') as f:
        json.dump(cfg,f,indent=2)
    return cfg

def guardar_config(cfg):
    with open(CONFIG_PATH,'w',encoding='utf-8') as f:
        json.dump(cfg,f,indent=2)

# ------------------ Utils ------------------
_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")

def _normalize_hex_color(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    if _HEX_RE.match(s):
        return s if s.startswith("#") else f"#{s}"
    return ""

def _contrast_text(hex_color: str) -> str:
    try:
        hc = _normalize_hex_color(hex_color)
        r = int(hc[1:3], 16); g = int(hc[3:5], 16); b = int(hc[5:7], 16)
        luminance = 0.2126*r + 0.7152*g + 0.0722*b
        return "#000000" if luminance > 160 else "#ffffff"
    except Exception:
        return "#ffffff"

def rel_from_html(abs_path: str) -> str:
    try:
        if abs_path and os.path.exists(abs_path):
            return os.path.relpath(abs_path, os.path.dirname(OUTPUT_HTML)).replace('\\','/')
    except Exception:
        pass
    return ""

def _fix_ext(p):
    if not p: return p
    if p.startswith(("http://","https://","data:")): return p
    root, ext = os.path.splitext(p)
    if ext.lower() in (".png",".jpg",".jpeg"): return p
    if ext == "": return root + ".png"
    return p

# ------------------ Excel ------------------
def leer_equipos():
    """Lee 'equipos' -> (nombres, colores, imagenes)"""
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="equipos")
        lowered = {c.lower(): c for c in df.columns}
        col_equipo = lowered.get("equipo", df.columns[0])
        names = df[col_equipo].astype(str).str.strip().tolist()

        if "color" in lowered:
            colors_raw = df[lowered["color"]].astype(str).str.strip().tolist()
        elif df.shape[1] >= 2:
            colors_raw = df.iloc[:, 1].astype(str).str.strip().tolist()
        else:
            colors_raw = [""] * len(names)

        if "imagen" in lowered:
            imgs_raw = df[lowered["imagen"]].astype(str).str.strip().tolist()
        elif df.shape[1] >= 3:
            imgs_raw = df.iloc[:, 2].astype(str).str.strip().tolist()
        else:
            imgs_raw = [""] * len(names)

        colors, images = {}, {}
        base_dir_xlsx = os.path.dirname(EXCEL_PATH)
        html_dir = os.path.dirname(OUTPUT_HTML)
        for idx, (n, c, img) in enumerate(zip(names, colors_raw, imgs_raw)):
            c_norm = _normalize_hex_color(c) if isinstance(c, str) else ""
            if not c_norm:
                c_norm = "#D32F2F" if idx == 0 else "#1976D2"
            colors[n] = c_norm

            img = _fix_ext((img or "").strip())
            if img and not img.lower().startswith(("http://","https://","data:")):
                abs_img = os.path.normpath(os.path.join(base_dir_xlsx, img))
                if os.path.exists(abs_img):
                    rel = os.path.relpath(abs_img, html_dir).replace('\\','/')
                    images[n] = rel
                else:
                    images[n] = ""
            else:
                images[n] = img
        return names, colors, images
    except Exception:
        return ["Equipo A", "Equipo B"], {"Equipo A": "#D32F2F", "Equipo B": "#1976D2"}, {"Equipo A": "", "Equipo B": ""}

def leer_jugadores(sheet):
    try:
        xls = pd.ExcelFile(JUGADORES_PATH)
        candidates = [sheet, sheet.lower(), sheet.upper(), sheet.title()]
        alias = ["visita", "visitantes", "ovisitantes", "visitante"]
        sheets = {s.lower(): s for s in xls.sheet_names}
        resolved = None
        for cand in candidates:
            if cand and cand.lower() in sheets:
                resolved = sheets[cand.lower()]; break
        if resolved is None and sheet.lower() in ("visita","visitantes","ovisitantes","visitante"):
            for a in alias:
                if a in sheets:
                    resolved = sheets[a]; break
        if resolved is None: resolved = xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=resolved, header=None)
        lista = []
        for _, row in df.iterrows():
            nombre = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ""
            numero = str(int(row.iloc[1])) if (len(row) > 1 and not pd.isna(row.iloc[1])) else ""
            if nombre: lista.append(f"{numero} {nombre}".strip())
        return lista
    except Exception:
        return []

# ------------------ App ------------------
class Marcador(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marcador Soccer")
        self.setGeometry(100,100,720,340)

        self.config = cargar_config()
        self.equipos, self.team_colors, self.team_images = leer_equipos()

        # ---- Reloj persistente ----
        self.running = bool(self.config.get("running", False))
        self.start_epoch_ms = int(self.config.get("start_epoch_ms", 0))
        self.elapsed_ms = int(self.config.get("elapsed_ms", 0))
        self.periodo = 1
        self.base_minutos = 0  # 0 en 1T, 45 en 2T

        self.pause_count = 0
        self.reset_count = 0
        self.red_local = 0
        self.red_visita = 0
        self.flash = ""
        self.flash_timer = QTimer()
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(lambda: (setattr(self, "flash", ""), self.actualizar_html()))
        self.tiempo_anadido_min = 0
        self.mostrar_extra = False
        self.tipo_fondo = "normal"
        self.html_prev = ""

        # -------- UI --------
        layout = QVBoxLayout()
        equipos_layout = QHBoxLayout()
        logos_layout = QHBoxLayout()
        marcador_layout = QHBoxLayout()
        control_layout = QHBoxLayout()

        # Toast
        self.toast_label = QLabel("")
        self.toast_label.setVisible(False)
        self.toast_label.setStyleSheet("padding:6px 10px; background:#222; color:#fff; border-radius:6px;")

        # Combos equipos
        self.equipo_local = QComboBox(); self.equipo_local.addItems(self.equipos)
        self.equipo_local.setCurrentText(self.config.get("equipo_local","Equipo A"))
        self.equipo_visita = QComboBox(); self.equipo_visita.addItems(self.equipos)
        self.equipo_visita.setCurrentText(self.config.get("equipo_visita","Equipo B"))
        self.equipo_local.currentTextChanged.connect(lambda _: self.guardar_estado())
        self.equipo_visita.currentTextChanged.connect(lambda _: self.guardar_estado())
        equipos_layout.addWidget(QLabel("Local:"));  equipos_layout.addWidget(self.equipo_local)
        equipos_layout.addSpacing(16)
        equipos_layout.addWidget(QLabel("Visita:")); equipos_layout.addWidget(self.equipo_visita)

        # Botones para cargar logos desde la UI
        btn_logo_local = QPushButton("📁 Logo Local")
        btn_logo_visita = QPushButton("📁 Logo Visita")
        btn_logo_brand = QPushButton("📁 Logo Marcador")
        btn_logo_local.clicked.connect(lambda: self._seleccionar_logo('logo_local'))
        btn_logo_visita.clicked.connect(lambda: self._seleccionar_logo('logo_visita'))
        btn_logo_brand.clicked.connect(lambda: self._seleccionar_logo('brand_logo'))
        logos_layout.addWidget(btn_logo_local)
        logos_layout.addWidget(btn_logo_visita)
        logos_layout.addWidget(btn_logo_brand)

        # Marcadores en la app (solo referencia)
        self.marc_local = QLabel(str(self.config.get("marcador_local",0)))
        self.marc_visita = QLabel(str(self.config.get("marcador_visita",0)))
        marcador_layout.addWidget(self.marc_local)
        marcador_layout.addWidget(QLabel(" : "))
        marcador_layout.addWidget(self.marc_visita)

        # Reloj
        self.reloj_label = QLabel("00:00")
        control_layout.addWidget(self.reloj_label)

        # Controles
        self.btn_iniciar = QPushButton("Iniciar"); self.btn_iniciar.clicked.connect(self.toggle_reloj); control_layout.addWidget(self.btn_iniciar)
        self.btn_reset = QPushButton("Reset"); self.btn_reset.clicked.connect(self.reset_click); control_layout.addWidget(self.btn_reset)

        self.extra_spin = QSpinBox(); self.extra_spin.setRange(0, 15); self.extra_spin.setSuffix(" min"); self.extra_spin.setValue(0); control_layout.addWidget(self.extra_spin)
        self.btn_extra = QPushButton("Tiempo añadido"); self.btn_extra.clicked.connect(self.aplicar_tiempo_anadido); control_layout.addWidget(self.btn_extra)

        self.btn_1t = QPushButton("1T"); self.btn_1t.clicked.connect(lambda: self.set_periodo(1)); control_layout.addWidget(self.btn_1t)
        self.btn_2t = QPushButton("2T"); self.btn_2t.clicked.connect(lambda: self.set_periodo(2)); control_layout.addWidget(self.btn_2t)

        for txt,func in [
            ("Gol Local", lambda:self.gol("local")),
            ("Gol Visita", lambda:self.gol("visita")),
            ("Cambio", self.cambio_popup),
            ("Tarjeta", self.tarjeta_popup),
            ("Stats", self.stats_popup)
        ]:
            b = QPushButton(txt); b.clicked.connect(func); control_layout.addWidget(b)

        # Botón para copiar HTML al portapapeles
        self.btn_copy_html = QPushButton("Copiar HTML")
        self.btn_copy_html.clicked.connect(self.copy_html)
        control_layout.addWidget(self.btn_copy_html)

        # Botón para copiar la URL del marcador (link utilizado en OBS)
        self.btn_copy_link = QPushButton("Copiar URL")
        self.btn_copy_link.clicked.connect(self.copy_link)
        control_layout.addWidget(self.btn_copy_link)

        layout.addLayout(equipos_layout)
        layout.addLayout(logos_layout)
        layout.addLayout(marcador_layout)
        layout.addLayout(control_layout)
        layout.addWidget(self.toast_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.setLayout(layout)

        # HTTP
        self.http_proc = None
        self.http_port = None  # puerto utilizado por el servidor HTTP
        def _port_free(port:int)->bool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                return s.connect_ex(("127.0.0.1", port)) != 0
        self._port_free = _port_free

        def _start_http_server(port:int=3333):
            """
            Inicia un servidor HTTP en el primer puerto libre a partir de `port`.
            Guarda el puerto elegido en `self.http_port` y muestra la URL completa.
            """
            try:
                p = port
                started = False
                for _ in range(10):
                    if self._port_free(p):
                        # Iniciar el servidor en el puerto disponible
                        self.http_proc = subprocess.Popen(
                            [sys.executable, "-m", "http.server", str(p)],
                            cwd=BASE_DIR,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        self.http_port = p
                        self.notificar(f"HTTP listo: http://localhost:{p}/TXT/salida.html", 3500)
                        started = True
                        break
                    p += 1
                if not started:
                    # Todos los puertos probados están ocupados
                    self.notificar("No se pudo iniciar el servidor HTTP (puertos ocupados)", 4000)
            except Exception as e:
                print("[http.server]", e)
        self._start_http_server = _start_http_server

        try: self._start_http_server(3333)
        except Exception: pass

        # Overlay
        self.overlay = {"type": None, "data": {}}
        self.overlay_timer = QTimer(); self.overlay_timer.setSingleShot(True); self.overlay_timer.timeout.connect(self._ocultar_overlay)

        # Pide logos al arrancar (NO obliga)
        self._pedir_logos_iniciales(always=False)

        # Atajo para permitir cerrar: Ctrl+Shift+Q (habilita cierre por 5s)
        self._allow_close = False
        self._close_btn = QPushButton("", self)
        self._close_btn.setShortcut("Ctrl+Shift+Q")
        self._close_btn.clicked.connect(self._enable_close)
        self._close_btn.setVisible(False)

        self.actualizar_html()

        self.timer = QTimer(); self.timer.timeout.connect(self.actualizar_reloj)
        self.tick_ms = 300
        self.timer.start(self.tick_ms)

    # ---------- Logos ----------
    def _seleccionar_logo(self, key):
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona imagen", BASE_DIR, "Imágenes (*.png *.jpg *.jpeg)")
        if path:
            rel = rel_from_html(path)
            self.config[key] = rel
            guardar_config(self.config)
            self.actualizar_html()
            self.notificar(f"{key.replace('_',' ').title()} actualizado", 2000)

    def _pedir_logos_iniciales(self, always=False):
        def pedir(titulo, preset=""):
            start_dir = BASE_DIR
            path, _ = QFileDialog.getOpenFileName(self, titulo, start_dir, "Imágenes (*.png *.jpg *.jpeg)")
            return rel_from_html(path)
        if always or not self.config.get("brand_logo"):
            brand_rel = pedir("Logo marcador:", self.config.get("brand_logo",""))
            if brand_rel: self.config["brand_logo"] = brand_rel
        if always or not self.config.get("logo_local"):
            logo_l_rel = pedir("Logo local:", self.config.get("logo_local",""))
            if logo_l_rel: self.config["logo_local"] = logo_l_rel
        if always or not self.config.get("logo_visita"):
            logo_v_rel = pedir("Logo visita:", self.config.get("logo_visita",""))
            if logo_v_rel: self.config["logo_visita"] = logo_v_rel
        guardar_config(self.config)

    # ---------- Helpers reloj ----------
    def _tiempo_total_ms(self) -> int:
        base_ms = self.base_minutos * 60 * 1000
        live_ms = 0
        if self.running and self.start_epoch_ms:
            now_ms = int(time.time() * 1000)
            live_ms = max(0, now_ms - self.start_epoch_ms)
        return base_ms + self.elapsed_ms + live_ms

    def _tiempo_total_segundos(self) -> int:
        return self._tiempo_total_ms() // 1000

    # ---------- Reloj ----------
    def toggle_reloj(self):
        if self.running:
            if self.pause_count >= 1:
                resp = QMessageBox.question(
                    self, "Pausar reloj",
                    "¿Seguro que quieres pausar el reloj?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return
            self.pause_count += 1
            # consolidar tiempo
            now_ms = int(time.time() * 1000)
            self.elapsed_ms += max(0, now_ms - self.start_epoch_ms)
            self.start_epoch_ms = 0
            self.running = False
        else:
            self.start_epoch_ms = int(time.time() * 1000)
            self.running = True
        self.btn_iniciar.setText("Pausar" if self.running else "Iniciar")
        # persistir
        self.config.update({
            "running": self.running,
            "start_epoch_ms": self.start_epoch_ms,
            "elapsed_ms": self.elapsed_ms
        })
        guardar_config(self.config)
        self.actualizar_html()

    def reset_click(self):
        if self.reset_count >= 1:
            resp = QMessageBox.question(
                self, "Confirmar reset",
                "¿Seguro que quieres reiniciar el partido?\nSe pondrá el reloj en 0:00 y se vacían eventos temporales.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self.reset_count += 1
        self.reset_reloj()

    def reset_reloj(self):
        self.running = False
        self.periodo = 1
        self.base_minutos = 0
        self.elapsed_ms = 0
        self.start_epoch_ms = 0
        self.tiempo_anadido_min = 0
        self.mostrar_extra = False
        self.marc_local.setText("0")
        self.marc_visita.setText("0")
        self.red_local = 0
        self.red_visita = 0
        self.flash = ""
        self.flash_timer.stop()
        self.btn_iniciar.setText("Iniciar")
        # persistir
        self.config.update({
            "running": self.running,
            "start_epoch_ms": self.start_epoch_ms,
            "elapsed_ms": self.elapsed_ms
        })
        guardar_config(self.config)
        self.actualizar_html()

    def aplicar_tiempo_anadido(self):
        self.tiempo_anadido_min = int(self.extra_spin.value())
        self.mostrar_extra = self.tiempo_anadido_min > 0
        # no arrancamos el reloj aquí: se queda en el estado actual
        self.running = False
        self.start_epoch_ms = 0
        self.btn_iniciar.setText("Iniciar")
        self.config.update({
            "running": self.running,
            "start_epoch_ms": self.start_epoch_ms,
            "elapsed_ms": self.elapsed_ms
        })
        guardar_config(self.config)
        self.actualizar_html()

    def set_periodo(self, num: int):
        self.periodo = 1 if num != 2 else 2
        self.base_minutos = 0 if self.periodo == 1 else 45
        # Reiniciamos el conteo del tiempo jugado dentro del periodo
        self.elapsed_ms = 0
        self.start_epoch_ms = 0
        self.mostrar_extra = False
        self.flash = ""
        self.flash_timer.stop()
        self.running = False
        self.btn_iniciar.setText("Iniciar")
        self.config.update({
            "running": self.running,
            "start_epoch_ms": self.start_epoch_ms,
            "elapsed_ms": self.elapsed_ms
        })
        guardar_config(self.config)
        self.actualizar_html()

    def notificar(self, mensaje: str, ms: int = 3000):
        self.toast_label.setText(mensaje)
        self.toast_label.setVisible(True)
        self.toast_label.repaint()
        QTimer.singleShot(ms, lambda: self.toast_label.setVisible(False))

    def mostrar_overlay(self, tipo: str, data: dict, fondo_key: str = "stats", dur_ms: int = 6000):
        self.overlay = {"type": tipo, "data": data}
        self.tipo_fondo = fondo_key if fondo_key in FONDOS else "normal"
        self.overlay_timer.start(dur_ms)
        self.actualizar_html()

    def _ocultar_overlay(self):
        self.overlay = {"type": None, "data": {}}
        self.tipo_fondo = "normal"
        self.actualizar_html()

    def actualizar_reloj(self):
        total_seg = self._tiempo_total_segundos()
        m, s = divmod(total_seg, 60)
        self.reloj_label.setText(f"{m:02}:{s:02}")
        # fin de periodo
        if (self.periodo == 1 and total_seg >= 45 * 60) or (self.periodo == 2 and total_seg >= 90 * 60):
            if self.running:
                now_ms = int(time.time() * 1000)
                self.elapsed_ms += max(0, now_ms - self.start_epoch_ms)
                self.start_epoch_ms = 0
                self.running = False
                self.btn_iniciar.setText("Iniciar")
                self.config.update({
                    "running": self.running,
                    "start_epoch_ms": self.start_epoch_ms,
                    "elapsed_ms": self.elapsed_ms
                })
                guardar_config(self.config)
        self.actualizar_html()

    def gol(self,equipo):
        try:
            if equipo=="local":
                self.marc_local.setText(str(int(self.marc_local.text())+1))
            else:
                self.marc_visita.setText(str(int(self.marc_visita.text())+1))

            def _after_delay():
                try:
                    jugador = self.seleccionar_anotador(equipo)
                    if not isinstance(jugador, str):
                        jugador = '' if jugador is None else str(jugador)
                    data = {
                        "equipo": equipo,
                        "local": int(self.marc_local.text()),
                        "visita": int(self.marc_visita.text()),
                        "jugador": jugador
                    }
                    self.mostrar_overlay("goal", data, fondo_key="normal", dur_ms=5500)
                    self.guardar_estado()
                except Exception as e:
                    print("[gol:_after_delay]", e)
                    data = {"equipo": equipo, "local": int(self.marc_local.text()), "visita": int(self.marc_visita.text()), "jugador": ""}
                    self.mostrar_overlay("goal", data, fondo_key="normal", dur_ms=5500)
            QTimer.singleShot(1200, _after_delay)

        except Exception as e:
            print("[gol] error:", e)
            self.notificar(f"Error en gol: {e}")

    def seleccionar_anotador(self, equipo: str):
        dlg = QDialog(self); dlg.setWindowTitle("Anotador"); dlg.setGeometry(180, 180, 360, 240)
        v = QVBoxLayout(); dlg.setLayout(v)
        v.addWidget(QLabel(f"Selecciona el anotador ({'LOCAL' if equipo=='local' else 'VISITA'})"))
        lista = QComboBox(); v.addWidget(lista)
        jugadores = self.jugadores_equipo_actual("local" if equipo=="local" else "visita")
        if not jugadores: jugadores = [""]
        lista.addItems(jugadores)
        fila = QHBoxLayout(); v.addLayout(fila)
        btn_ok = QPushButton("Aceptar"); btn_cancel = QPushButton("Cancelar")
        fila.addWidget(btn_ok); fila.addWidget(btn_cancel)
        sel = {"value": None}
        btn_ok.clicked.connect(lambda: (sel.__setitem__("value", lista.currentText().strip()), dlg.accept()))
        btn_cancel.clicked.connect(lambda: (sel.__setitem__("value", None), dlg.reject()))
        dlg.exec()
        return sel["value"]

    def cambio_popup(self):
        dlg = QDialog(self); dlg.setWindowTitle("Cambio"); dlg.setGeometry(150,150,460,240)
        layout = QVBoxLayout(); dlg.setLayout(layout)

        fila_top = QHBoxLayout(); layout.addLayout(fila_top)
        fila_top.addWidget(QLabel("Equipo:"))
        combo_equipo = QComboBox(); combo_equipo.addItems(["local","visita"]); fila_top.addWidget(combo_equipo)

        fila_sale = QHBoxLayout(); layout.addLayout(fila_sale)
        fila_sale.addWidget(QLabel("Sale:")); combo_sale = QComboBox(); fila_sale.addWidget(combo_sale)

        fila_entra = QHBoxLayout(); layout.addLayout(fila_entra)
        fila_entra.addWidget(QLabel("Entra:")); combo_entra = QComboBox(); fila_entra.addWidget(combo_entra)

        def cargar_jugadores():
            jugadores = self.jugadores_equipo_actual(combo_equipo.currentText())
            combo_sale.clear(); combo_entra.clear()
            combo_sale.addItems(jugadores); combo_entra.addItems(jugadores)
        combo_equipo.currentIndexChanged.connect(lambda _: cargar_jugadores()); cargar_jugadores()

        btn = QPushButton("Aceptar"); layout.addWidget(btn)

        def aceptar():
            equipo = combo_equipo.currentText()
            sale = combo_sale.currentText()
            entra = combo_entra.currentText()
            if sale == entra and sale != "":
                self.notificar("El que sale y el que entra no pueden ser el mismo", 3000); return
            data = {"equipo": equipo, "sale": sale, "entra": entra}
            self.mostrar_overlay("sub", data, fondo_key="normal", dur_ms=5500)
            dlg.close()
        btn.clicked.connect(aceptar)
        dlg.exec()

    def tarjeta_popup(self):
        dlg = QDialog(self); dlg.setWindowTitle("Tarjeta"); dlg.setGeometry(150,150,360,320)
        layout = QVBoxLayout()
        combo_equipo = QComboBox(); combo_equipo.addItems(["local","visita"]); layout.addWidget(combo_equipo)
        combo_jugador = QComboBox(); layout.addWidget(combo_jugador)

        def actualizar_jugadores(idx):
            combo_jugador.clear(); combo_jugador.addItems(self.jugadores_equipo_actual(combo_equipo.currentText()))
        combo_equipo.currentIndexChanged.connect(actualizar_jugadores); actualizar_jugadores(0)

        fila_color = QHBoxLayout(); layout.addLayout(fila_color)
        rb_yellow = QRadioButton("Amarilla"); rb_red = QRadioButton("Roja"); rb_yellow.setChecked(True)
        grp = QButtonGroup(dlg); grp.setExclusive(True); grp.addButton(rb_yellow); grp.addButton(rb_red)
        fila_color.addWidget(rb_yellow); fila_color.addWidget(rb_red)

        btn = QPushButton("Aceptar"); layout.addWidget(btn); dlg.setLayout(layout)

        def aceptar():
            equipo = combo_equipo.currentText(); jugador = combo_jugador.currentText()
            t = "amarilla" if rb_yellow.isChecked() else "roja"
            self.flash = "yellow" if t == "amarilla" else "red"; self.flash_timer.start(3000)
            if t == "roja":
                if equipo == "local": self.red_local += 1
                else: self.red_visita += 1
            data = {"equipo": equipo, "jugador": jugador, "tipo": t}
            self.mostrar_overlay("card", data, fondo_key="normal", dur_ms=5500)
            dlg.close(); self.actualizar_html()
        btn.clicked.connect(aceptar)
        dlg.exec()

    def stats_popup(self):
        dlg = QDialog(self); dlg.setWindowTitle("Estadísticas"); dlg.setGeometry(160, 160, 420, 300)
        layout = QVBoxLayout(); dlg.setLayout(layout)
        tipo = QComboBox(); tipo.addItems(["Disparos a puerta","Posesión %","Faltas","Pases %","Tiros de esquina"]); layout.addWidget(tipo)
        fila_valores = QHBoxLayout(); layout.addLayout(fila_valores)
        sp_local = QSpinBox(); sp_local.setRange(0, 100); sp_local.setValue(0)
        sp_visita = QSpinBox(); sp_visita.setRange(0, 100); sp_visita.setValue(0)
        fila_valores.addWidget(QLabel("Local")); fila_valores.addWidget(sp_local)
        fila_valores.addWidget(QLabel("Visita")); fila_valores.addWidget(sp_visita)
        prog_layout = QHBoxLayout(); layout.addLayout(prog_layout)
        prog_layout.addWidget(QLabel("Programar en ≤ (s):"))
        sp_rand = QSpinBox(); sp_rand.setRange(5, 120); sp_rand.setValue(30); prog_layout.addWidget(sp_rand)
        fila_btn = QHBoxLayout(); layout.addLayout(fila_btn)
        btn_mostrar = QPushButton("Mostrar ahora"); btn_prog = QPushButton("Programar aleatorio")
        fila_btn.addWidget(btn_mostrar); fila_btn.addWidget(btn_prog)

        def do_show():
            data = {"titulo": tipo.currentText(), "local": int(sp_local.value()), "visita": int(sp_visita.value())}
            self.mostrar_overlay("stats", data, fondo_key="stats", dur_ms=7000); dlg.close()
        def do_prog():
            delay = random.randint(5, int(sp_rand.value())) * 1000
            self.notificar(f"Stats '{tipo.currentText()}' en ~{delay//1000}s")
            QTimer.singleShot(delay, lambda: self.mostrar_overlay("stats", {
                "titulo": tipo.currentText(), "local": int(sp_local.value()), "visita": int(sp_visita.value())
            }, fondo_key="stats", dur_ms=7000)); dlg.close()

        btn_mostrar.clicked.connect(do_show); btn_prog.clicked.connect(do_prog)
        dlg.exec()

    def jugadores_equipo_actual(self, lado: str) -> list:
        preferida = "panteras" if lado == "local" else "visita"
        lista = leer_jugadores(preferida)
        if lista: return lista
        equipo = self.equipo_local.currentText() if lado == "local" else self.equipo_visita.currentText()
        return leer_jugadores(equipo) or []

    # ---------- Render HTML ----------
    def _background_url(self) -> str:
        fondos_dir = os.path.join(BASE_DIR, 'fondos')
        fondo_png = f"{FONDOS.get(self.tipo_fondo, 'marcador-soccer-partido')}.png"
        abs_path = os.path.join(fondos_dir, fondo_png)
        if os.path.exists(abs_path):
            return os.path.relpath(abs_path, os.path.dirname(OUTPUT_HTML)).replace('\\', '/')
        else:
            print(f"Warning: Background image not found at {abs_path}")
            return ''

    def actualizar_html(self):
        try:
            # Colores + logos
            color_local = self.team_colors.get(self.equipo_local.currentText(), "#D32F2F")
            color_visita = self.team_colors.get(self.equipo_visita.currentText(), "#1976D2")
            color_text_local = _contrast_text(color_local)
            color_text_visita = _contrast_text(color_visita)

            brand_png_rel = self.config.get("brand_logo","").strip()
            if not brand_png_rel:
                guess = os.path.join(BASE_DIR, 'assets', 'logo.png')
                brand_png_rel = rel_from_html(guess)

            img_local = _fix_ext(self.config.get("logo_local","").strip() or self.team_images.get(self.equipo_local.currentText(), ""))
            img_visita = _fix_ext(self.config.get("logo_visita","").strip() or self.team_images.get(self.equipo_visita.currentText(), ""))
            if img_local and "://" not in img_local and not img_local.startswith(("data:",)):
                if os.path.isabs(img_local): img_local = rel_from_html(img_local)
            if img_visita and "://" not in img_visita and not img_visita.startswith(("data:",)):
                if os.path.isabs(img_visita): img_visita = rel_from_html(img_visita)

            crestMidL_html = (f"<img class='crest' src='{img_local}' alt='' onerror=\"this.style.display='none'\"/>" if img_local else "")
            crestMidR_html = (f"<img class='crest' src='{img_visita}' alt='' onerror=\"this.style.display='none'\"/>" if img_visita else "")

            # Reloj (usando persistencia)
            total_seg = self._tiempo_total_segundos()
            m_vis, s_vis = divmod(total_seg, 60)
            reloj_txt = f"{m_vis:02}:{s_vis:02}"

            # Resolver imagen de stats (offline)
            try:
                cand1 = os.path.join(BASE_DIR, 'assets', 'stats.png')
                cand2 = os.path.join(BASE_DIR, 'stats.png')
                if os.path.exists(cand1):
                    stats_png_rel = os.path.relpath(cand1, os.path.dirname(OUTPUT_HTML)).replace('\\','/')
                elif os.path.exists(cand2):
                    stats_png_rel = os.path.relpath(cand2, os.path.dirname(OUTPUT_HTML)).replace('\\','/')
                else:
                    stats_png_rel = 'stats.png'
            except Exception:
                stats_png_rel = 'stats.png'

            # ------- Overlays grandes -------
            overlay_html = ""
            if self.overlay.get("type") == "stats":
                d = self.overlay.get("data", {})
                titulo = d.get("titulo", "Stats")
                lv = int(d.get("local", 0)); vv = int(d.get("visita", 0))
                total = max(lv + vv, 1)
                pct_l = max(0.0, min(1.0, lv / total)); pct_v = 1.0 - pct_l

                overlay_html = f"""
      <div id="stats" class="panel panel-lg">
        <div class="stats-content">
            <div class="line" style="gap:18px; flex-wrap:wrap; align-items:center;">
              <span class="chip" style="background:#eee;">{titulo}</span>
            </div>
            <div class="stats-track">
              <div class="seg local" style="width:{pct_l*100:.2f}%">{lv}</div>
              <div class="seg visita" style="width:{pct_v*100:.2f}%">{vv}</div>
            </div>
        </div>
        <img class='stats-icon' src='{stats_png_rel}' alt='stats' onerror="this.style.display='none'"/>
      </div>"""
            elif self.overlay.get("type") == "goal":
                d = self.overlay.get("data", {})
                is_local = (d.get("equipo","local") == "local")
                bgc = color_local if is_local else color_visita
                tc = color_text_local if is_local else color_text_visita
                txt_team = self.equipo_local.currentText() if is_local else self.equipo_visita.currentText()
                score_l = d.get("local", self.marc_local.text())
                score_v = d.get("visita", self.marc_visita.text())
                jugador_raw = (d.get("jugador") or "").strip()
                jnum, jname = "", jugador_raw
                if jugador_raw:
                    parts = jugador_raw.split(" ", 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        jnum, jname = parts[0], parts[1]
                overlay_html = f"""
      <div id="goal" class="panel panel-lg">
        <div class="line">
          <span class="chip" style="background:{bgc};color:{tc}">GOL</span>
          <span class="team-long" style="background:{bgc};color:{tc}">{txt_team}</span>
          <span class="score-big">{score_l} : {score_v}</span>
          {f"<span class='player-big'>{('#'+jnum+' ') if jnum else ''}{jname}</span>" if jugador_raw else ""}
        </div>
      </div>"""
            elif self.overlay.get("type") == "card":
                d = self.overlay.get("data", {})
                is_local = (d.get("equipo","local") == "local")
                jugador = d.get("jugador","")
                tipo = d.get("tipo","amarilla")
                chip = "#FBC02D" if tipo == "amarilla" else "#D32F2F"
                txt_side = "LOCAL" if is_local else "VISITA"
                overlay_html = f"""
      <div id="card" class="panel panel-lg">
        <div class="line">
          <span class="chip" style="background:{chip};color:{'#000' if tipo=='amarilla' else '#fff'}">{tipo.upper()}</span>
          <span class="team-long">{txt_side}</span>
          <span class="player-big">{jugador}</span>
        </div>
      </div>"""
            elif self.overlay.get("type") == "sub":
                d = self.overlay.get("data", {})
                sale_txt = (d.get("sale","") or "").strip()
                entra_txt = (d.get("entra","") or "").strip()
                def split_player(s):
                    parts = s.split(" ", 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        return parts[0], parts[1]
                    return "", s
                num_in, name_in = split_player(entra_txt)
                num_out, name_out = split_player(sale_txt)
                overlay_html = f"""
      <div id="sub" class="panel panel-lg">
        <div class="line">
          <span class="chip" style="background:#00e676;">CAMBIO</span>
          <span class="tri tri-left"></span><span class="num-big">{num_in}</span><span class="pname-big">{name_in}</span>
          <span style="width:24px;"></span>
          <span class="tri tri-right"></span><span class="num-big out">{num_out}</span><span class="pname-big out">{name_out}</span>
        </div>
      </div>"""

            # -------- HTML (sin JS auto-refresh) --------
            expanded_class = "expanded" if overlay_html else ""
            expander_class = "open" if overlay_html else ""

            html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"/>
<meta http-equiv="Pragma" content="no-cache"/>
<meta http-equiv="Expires" content="0"/>
<link rel="preload" as="image" href="%%BRAND%%"/>
<link rel="preload" as="image" href="%%STATSPNG%%"/>
<title>Marcador</title>
<style>
:root{
  --bug-scale: 1.00;
  --mid-w: 950px;
  --mid-w-expanded: 1250px;
  --left-w: 300px;
  --right-w: 36px;
  --canvas-width: 1920px;
  --canvas-height: 1080px;
  --scorebug-top: 24px;
  --scorebug-left: 24px;
  --color-local: %%COLOR_LOCAL%%;
  --color-visita: %%COLOR_VISITA%%;
  --color-text-local: %%COLOR_TEXT_LOCAL%%;
  --color-text-visita: %%COLOR_TEXT_VISITA%%;
}
html,body{ margin:0; padding:0; width:var(--canvas-width); height:var(--canvas-height);
  background-color:rgba(0,0,0,0)!important; overflow:hidden; font-family:'Inter','SF Pro Display','Segoe UI',Arial,sans-serif; color:#111; }
.stage{ position:relative; width:var(--canvas-width); height:var(--canvas-height); }
#bug-wrap{ position:absolute; top:var(--scorebug-top); left:var(--scorebug-left); transform:scale(var(--bug-scale)); transform-origin:top left;
  filter:drop-shadow(0 12px 28px rgba(0,0,0,.35)); }
#ea-scorebug{ display:flex; align-items:stretch; transition:width .70s cubic-bezier(.2,.7,.2,1); }

/* IZQUIERDA */
.ea-left{ display:flex; flex-direction:column; width:var(--left-w); }
.ea-tri,.ea-comp,.ea-time,.time-extra{ width:var(--left-w); box-sizing:border-box; }
.ea-tri{ height:110px; background:#111; border-top-left-radius:10px; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.ea-tri img{ max-width: calc(var(--left-w) - 20px); max-height: 96px; width:auto; height:auto; object-fit:contain; }
.ea-comp{ background:#111; color:#fff; font-weight:900; font-size:28px; letter-spacing:.7px; padding:16px 18px; border-bottom:1px solid rgba(255,255,255,.08);}
.ea-time{ background:#2FE05B; color:#000; font-weight:900; font-size:64px; padding:18px 24px; line-height:1; display:flex; align-items:center; justify-content:center; }
.time-extra{ background:#2FE05B; color:#000; font-weight:900; font-size:56px; line-height:1; padding:0 18px; overflow:hidden; max-height:0; width:var(--left-w);
  transition:max-height .70s cubic-bezier(.2,.7,.2,1), padding .70s cubic-bezier(.2,.7,.2,1); border-bottom-left-radius:10px; }
.time-extra.show{ max-height:56px; padding:10px 18px; }

/* EXPANDER */
#bug-outer{ display:inline-block; width:auto; }
#expander{
  width:100%;
  background:#fff; color:#111;
  border-radius:0 0 10px 10px;
  overflow:hidden;
  box-shadow:0 10px 24px rgba(0,0,0,.20);
  max-height:0;
  transition:max-height .45s ease;
  will-change:max-height;
}
#expander.open{ max-height:460px; }
/* El panel usa el ancho del bug expandido */
.panel-lg{ width: calc(var(--left-w) + var(--mid-w-expanded) + var(--right-w)); max-width: calc(var(--left-w) + var(--mid-w-expanded) + var(--right-w)); padding: 22px 24px; } 
#expander .panel{ background:#fff; color:#111; }

/* CENTRO */
.ea-mid{ background:#fff; color:#111; display:flex; flex-direction:column; padding:20px 24px; row-gap:16px; 
  width:var(--mid-w); transition:width .70s cubic-bezier(.2,.7,.2,1); box-sizing:border-box; 
  border-top-right-radius: 0; border-bottom-right-radius: 0; } 

#ea-scorebug.expanded .ea-mid{ width:var(--mid-w-expanded); }
#ea-scorebug.expanded .ea-time{ font-size:74px; padding:22px 28px; }
#ea-scorebug.expanded .ea-mid .name{ font-size:72px; }
#ea-scorebug.expanded .ea-mid .score{ font-size:104px; }

.ea-mid .row{ 
    display:grid; 
    grid-template-columns: 180px 48px 1fr minmax(100px, auto); 
    align-items:center; 
    column-gap:22px; 
}
.ea-mid .name{ font-weight:900; font-size:64px; letter-spacing:.2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:300px; } 
.ea-mid .score{ font-weight:900; font-size:96px; text-align:right; min-width:100px; color:#111; }

.crest{ width:180px; height:180px; object-fit:contain; display:block; }
.reds{ display:flex; gap:8px; justify-content:flex-start; align-items: center; }
.rc{ width:40px; height:44px; background:#D32F2F; border-radius:6px; }

/* DERECHA */
.ea-right{ display:flex; flex-direction:column; width: var(--right-w); min-width: var(--right-w); border-top-right-radius:10px; border-bottom-right-radius:10px; overflow:hidden; }
.right-row{ flex:1 1 auto; }
.right-row.local{ background: var(--color-local); }
.right-row.visita{ background: var(--color-visita); }

/* Paneles grandes - Overlays */
.panel{ background:rgba(0,0,0,.92); border-radius:14px; padding:22px 24px; display:flex; align-items:center; gap:18px; box-shadow:0 10px 24px rgba(0,0,0,.35); margin:14px; font-size:22px; }
.panel .chip{ font-weight:900; padding:10px 16px; border-radius:10px; letter-spacing:.6px; text-transform:uppercase; }
.panel .line{ display:flex; align-items:center; gap:24px; flex-wrap:wrap; }
.team-long{ padding:6px 12px; border-radius:8px; font-weight:900; font-size:32px; }
.score-big{ font-weight:900; font-size:100px; }
.player-big{ font-weight:800; font-size:48px; }
.num-big{ font-weight:900; font-size:44px; min-width:48px; text-align:right; }
.pname-big{ font-weight:800; font-size:44px; }

/* STATS */
.stats-icon{ width:200px; height:200px; object-fit:contain; display:inline-block; margin-left: 24px; }
.stats-content{ flex-grow: 1; display:flex; flex-direction: column; }
#stats .stats-track{ flex:1 1 auto; height:44px; border-radius:12px; overflow:hidden; display:flex; margin:12px 0; background:#fff; border:1px solid rgba(0,0,0,.08); } 
#stats .seg{ display:flex; align-items:center; justify-content:center; font-weight:900; line-height:1; font-size:26px; } 
#stats .seg.local{ background: var(--color-local); color: var(--color-text-local); }
#stats .seg.visita{ background: var(--color-visita); color: var(--color-text-visita); }
.stats-wrap{ display:flex; align-items:center; gap:18px; flex-grow: 1; }

/* Triángulos cambio */
.tri{ width:0; height:0; }
.tri-left{ border-top:10px solid transparent; border-bottom:10px solid transparent; border-right:16px solid #00e676; }
.tri-right{ border-top:10px solid transparent; border-bottom:10px solid transparent; border-left:16px solid #ff5252; }
.num-big.out{ color:#ff5252; }
</style>
</head>
<body>
<div class="stage">
  <div id="bug-wrap">
    <div id="bug-outer">
      <div id="ea-scorebug" class="%%EXPANDED%%">
        <div class="ea-left">
          <div class="ea-tri"><img id="brand" src="%%BRAND%%" alt="Brand" onerror="this.style.display='none'"/></div>
          <div class="ea-comp">CONADEIP</div>
          <div class="ea-time"><span id="ea-clock">%%RELOJ%%</span></div>
          <div id="time-extra" class="time-extra%%EXTRA_CLASS%%">%%EXTRA_TXT%%</div>
        </div>
        <div class="ea-mid">
          <div class="row">
            %%CREST_MID_L%%
            <span class="reds" id="redsL">%%REDS_L%%</span>
            <span class="name" id="teamL">%%TEAM_L%%</span>
            <span class="score" id="scoreL">%%SCORE_L%%</span>
          </div>
          <div class="row">
            %%CREST_MID_R%%
            <span class="reds" id="redsR">%%REDS_R%%</span>
            <span class="name" id="teamR">%%TEAM_R%%</span>
            <span class="score" id="scoreR">%%SCORE_R%%</span>
          </div>
        </div>
        <div class="ea-right">
          <div class="right-row local"></div>
          <div class="right-row visita"></div>
        </div>
      </div>
      <div id="expander" class="%%EXPANDER_CLASS%%"><div id="expander-inner">%%OVERLAY_HTML%%</div></div>
    </div>
  </div>
</div>
</body>
</html>
"""
            # Armado de chips rojas y extra
            reds_l_html = "".join("<span class='rc'></span>" for _ in range(int(self.red_local)))
            reds_r_html = "".join("<span class='rc'></span>" for _ in range(int(self.red_visita)))
            extra_txt = f"+{int(self.tiempo_anadido_min)}'" if (self.mostrar_extra and self.tiempo_anadido_min>0) else ""
            extra_class = " show" if extra_txt else ""

            html = (html
                .replace("%%COLOR_LOCAL%%", color_local)
                .replace("%%COLOR_VISITA%%", color_visita)
                .replace("%%COLOR_TEXT_LOCAL%%", color_text_local)
                .replace("%%COLOR_TEXT_VISITA%%", color_text_visita)
                .replace("%%BRAND%%", brand_png_rel or "")
                .replace("%%STATSPNG%%", stats_png_rel or "stats.png")
                .replace("%%RELOJ%%", reloj_txt)
                .replace("%%EXTRA_TXT%%", extra_txt)
                .replace("%%EXTRA_CLASS%%", extra_class)
                .replace("%%CREST_MID_L%%", crestMidL_html)
                .replace("%%CREST_MID_R%%", crestMidR_html)
                .replace("%%REDS_L%%", reds_l_html)
                .replace("%%REDS_R%%", reds_r_html)
                .replace("%%TEAM_L%%", self.equipo_local.currentText())
                .replace("%%TEAM_R%%", self.equipo_visita.currentText())
                .replace("%%SCORE_L%%", self.marc_local.text())
                .replace("%%SCORE_R%%", self.marc_visita.text())
                .replace("%%OVERLAY_HTML%%", overlay_html)
                .replace("%%EXPANDED%%", expanded_class)
                .replace("%%EXPANDER_CLASS%%", expander_class)
            )

            # --- Añadir script de auto-actualización ---
            auto_script = """<script>
async function updateScorebug(){
  try {
    const resp = await fetch('estado.json', {cache: 'no-store'});
    if (!resp.ok) return;
    const data = await resp.json();
    // actualizar reloj
    const clockEl = document.getElementById('ea-clock');
    if (clockEl && data.clock !== undefined) clockEl.textContent = data.clock;
    // extra time
    const timeExtra = document.getElementById('time-extra');
    if (timeExtra) {
      if (data.extra && data.extra > 0) {
        timeExtra.classList.add('show');
        timeExtra.textContent = '+'+data.extra+"'";
      } else {
        timeExtra.classList.remove('show');
        timeExtra.textContent = '';
      }
    }
    // nombres y marcadores
    const teamL = document.getElementById('teamL');
    const teamR = document.getElementById('teamR');
    const scoreL = document.getElementById('scoreL');
    const scoreR = document.getElementById('scoreR');
    if (teamL && data.teamL !== undefined) teamL.textContent = data.teamL;
    if (teamR && data.teamR !== undefined) teamR.textContent = data.teamR;
    if (scoreL && data.scoreL !== undefined) scoreL.textContent = data.scoreL;
    if (scoreR && data.scoreR !== undefined) scoreR.textContent = data.scoreR;
    // colores
    if (data.colorL) {
      document.documentElement.style.setProperty('--color-local', data.colorL);
    }
    if (data.colorR) {
      document.documentElement.style.setProperty('--color-visita', data.colorR);
    }
    if (data.colorTextL) {
      document.documentElement.style.setProperty('--color-text-local', data.colorTextL);
    }
    if (data.colorTextR) {
      document.documentElement.style.setProperty('--color-text-visita', data.colorTextR);
    }
    // tarjetas rojas
    const redsL = document.getElementById('redsL');
    const redsR = document.getElementById('redsR');
    if (redsL) {
      redsL.innerHTML = '';
      const n = data.redL || 0;
      for (let i=0; i<n; i++) {
        const span = document.createElement('span');
        span.className = 'rc';
        redsL.appendChild(span);
      }
    }
    if (redsR) {
      redsR.innerHTML = '';
      const n = data.redR || 0;
      for (let i=0; i<n; i++) {
        const span = document.createElement('span');
        span.className = 'rc';
        redsR.appendChild(span);
      }
    }
    // Overlay
    const expander = document.getElementById('expander');
    const scorebug = document.getElementById('ea-scorebug');
    const expInner = document.getElementById('expander-inner');
    if (expander && scorebug && expInner) {
      if (data.overlay_html) {
        expander.classList.add('open');
        scorebug.classList.add('expanded');
        expInner.innerHTML = data.overlay_html;
      } else {
        expander.classList.remove('open');
        scorebug.classList.remove('expanded');
        expInner.innerHTML = '';
      }
    }
  } catch (err) {
    // error silencioso
  }
}
setInterval(updateScorebug, 500);
updateScorebug();
</script>"""
            if '</body>' in html:
                html = html.replace('</body>', auto_script + '\n</body>')

            if html != getattr(self,'html_prev',None):
                with open(OUTPUT_HTML,'w',encoding='utf-8') as f:
                    f.write(html)
                self.html_prev = html

            # Guardar estado JSON (por si lo quieres usar en otra herramienta)
            state = {
                "teamL": self.equipo_local.currentText(),
                "teamR": self.equipo_visita.currentText(),
                "colorL": color_local, "colorR": color_visita,
                "colorTextL": color_text_local, "colorTextR": color_text_visita,
                "scoreL": int(self.marc_local.text()), "scoreR": int(self.marc_visita.text()),
                "clock": reloj_txt,
                "extra": int(self.tiempo_anadido_min) if (self.mostrar_extra and self.tiempo_anadido_min>0) else 0,
                "overlay_html": overlay_html, "overlay_type": (self.overlay.get("type") or ""),
                "redL": int(self.red_local), "redR": int(self.red_visita), "flash": self.flash,
                "running": bool(self.running), "start_epoch_ms": int(self.start_epoch_ms), "elapsed_ms": int(self.elapsed_ms),
                "base_ms": int(self.base_minutos * 60 * 1000)
            }
            with open(OUTPUT_STATE,'w',encoding='utf-8') as sf:
                json.dump(state, sf, ensure_ascii=False)

        except Exception as e:
            print("[actualizar_html] error:", e)
            try: self.notificar(f"Error al renderizar: {e}", 4000)
            except Exception: pass

    def guardar_estado(self):
        try:
            self.config["equipo_local"] = self.equipo_local.currentText()
            self.config["equipo_visita"] = self.equipo_visita.currentText()
            self.config["marcador_local"] = int(self.marc_local.text())
            self.config["marcador_visita"] = int(self.marc_visita.text())
            guardar_config(self.config)
        except Exception:
            pass

    # ---------- Copiar HTML ----------
    def copy_html(self):
        """
        Copia el contenido HTML actual de salida.html al portapapeles.
        """
        try:
            with open(OUTPUT_HTML, 'r', encoding='utf-8') as f:
                html_text = f.read()
            QApplication.clipboard().setText(html_text)
            self.notificar("HTML copiado al portapapeles", 2000)
        except Exception as e:
            self.notificar(f"Error al copiar HTML: {e}", 3000)

    def copy_link(self):
        """
        Copia al portapapeles la URL actual del marcador (HTML servido) si el servidor está activo.
        """
        try:
            if self.http_port:
                url = f"http://localhost:{self.http_port}/TXT/salida.html"
                QApplication.clipboard().setText(url)
                self.notificar(f"URL copiada: {url}", 2500)
            else:
                self.notificar("Servidor HTTP no iniciado aún", 3000)
        except Exception as e:
            self.notificar(f"Error al copiar URL: {e}", 3000)

    # ---------- Cierre seguro ----------
    def _enable_close(self):
        self._allow_close = True
        self.notificar("Cierre habilitado por 5 segundos (Ctrl+Shift+Q)", 2500)
        QTimer.singleShot(5000, lambda: setattr(self, "_allow_close", False))

    def closeEvent(self, event):
        if not getattr(self, "_allow_close", False):
            self.notificar("Para cerrar: Ctrl+Shift+Q (se habilita por 5s)", 3000)
            event.ignore()
            return

        try: self.overlay_timer.stop()
        except Exception: pass
        try:
            if getattr(self, 'http_proc', None): self.http_proc.terminate()
        except Exception: pass

        # Persistir el reloj antes de salir
        if self.running and self.start_epoch_ms:
            now_ms = int(time.time() * 1000)
            self.elapsed_ms += max(0, now_ms - self.start_epoch_ms)
            self.start_epoch_ms = 0
            self.running = False
        self.config.update({
            "running": self.running,
            "start_epoch_ms": self.start_epoch_ms,
            "elapsed_ms": self.elapsed_ms
        })
        guardar_config(self.config)
        self.guardar_estado()
        return super().closeEvent(event)

# ------------------ Main ------------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    ventana = Marcador()
    ventana.show()
    sys.exit(app.exec())