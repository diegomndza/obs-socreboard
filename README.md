# obs-socreboard
This extensive Python script defines a PyQt6 application for controlling a **football (soccer) scoreboard overlay**, typically used for live broadcasts or streaming (often called a "bug" or "lower third"). It manages team data, scores, a match clock, and various on-screen event overlays (goals, substitutions, cards, and statistics).

Here is an explanation of the program's purpose and functionality, structured as a documentation overview, suitable for a GitHub repository in English:

***

## Soccer Scoreboard Controller (PyQt6/HTML)

This application serves as a **graphical user interface (GUI) controller** for a live, data-driven soccer scoreboard overlay (often referred to as a "bug" or "lower third"). The program manages match state—including time, scores, and event data—and outputs an **HTML file** (`TXT/salida.html`) and a **JSON state file** (`TXT/estado.json`). These files are intended to be read by external tools (such as OBS Studio, vMix, or a web browser) via a simple HTTP server to display the dynamic, real-time scoreboard in a broadcast environment.

### ⚽ Main Purpose

The core function is to provide an easy-to-use desktop application for a match operator to control the visual scoreboard displayed over live video.

### ✨ Key Features and Functionality

| Feature | Description |
| :--- | :--- |
| **Persistent Match Clock** | Manages a running match clock with start, pause, and reset functionality. The time state (`running`, `start_epoch_ms`, `elapsed_ms`) is saved in `config.json` to persist across restarts. |
| **Score Management** | Buttons for incrementing home/away scores and updating the display. |
| **Team Data Loading** | Reads team names, colors (HEX codes), and logo paths from an **Excel file** (`equipos.xlsx`). |
| **Player Data Loading** | Reads player lists (for goal scorers and substitutions) from a separate **Excel file** (`jugadores.xlsx`). |
| **Event Overlays (Lower Thirds)** | Specialized pop-up windows to trigger dynamic, time-limited graphic overlays for key match events: **Goal**, **Substitution** (`Cambio`), and **Card** (`Tarjeta`). |
| **Statistics Overlay** | Allows the operator to input and display match statistics (e.g., Shots on Goal, Possession) with a progress bar visualization. Includes an option for a random-delay programmed display. |
| **Background Control** | The HTML output changes the background image of the bug based on the current active event (e.g., `gol_local`, `stats`). |
| **Visibility Control** | Buttons to show (`Mostrar Marcador`) and hide (`Ocultar Marcador`) the entire scoreboard with CSS-based animations, controlling the `visible` state in the output JSON. |
| **Configuration Saving** | Saves match settings (current teams, scores, clock state, logo paths) to a `config.json` file. |
| **Local HTTP Server** | Automatically starts a lightweight Python HTTP server to make the output HTML easily accessible over the network (default `http://localhost:3333/TXT/salida.html`). |

---

### 💻 Program Structure Overview

The Python script is organized into several logical sections:

#### 1. Configuration and Utility Functions (`cargar_config`, `guardar_config`, `_normalize_hex_color`, `_contrast_text`, `rel_from_html`)

* Handles loading and saving of the application state and persistent settings to `config.json`.
* Includes utility functions for validating and normalizing **HEX colors** and determining a suitable **contrast text color** (black or white) for team colors.
* The `rel_from_html` function calculates file paths relative to the HTML output directory, crucial for proper asset loading in the browser.

#### 2. Excel Data Handlers (`leer_equipos`, `leer_jugadores`)

* **`leer_equipos()`**: Reads the `equipos.xlsx` file to get team names, their primary HEX colors, and paths to their crest/logo images.
* **`leer_jugadores()`**: Reads the `jugadores.xlsx` file to get player lists (name and number) based on the current team selected in the GUI.

#### 3. Main Application Class (`class Marcador`)

This is the PyQt6 GUI where all control logic resides.

* **`__init__`**: Initializes the GUI layout, loads the configuration, and sets up timers for the clock and event overlays. It also attempts to start the local HTTP server.
* **Clock Methods (`toggle_reloj`, `reset_reloj`, `actualizar_reloj`, `set_periodo`)**: Implements the core match timing logic, managing the running state and calculating the current time (`MM:SS`) based on persisted `elapsed_ms` and live run time.
* **Event Handlers (`gol`, `cambio_popup`, `tarjeta_popup`, `stats_popup`)**: Methods that respond to user button clicks by updating scores, showing dialogs to collect event-specific data (e.g., player name for a goal), and triggering the display of the corresponding graphic overlay.
* **Overlay Control (`mostrar_overlay`, `_ocultar_overlay`)**: Manages the content and display duration of event graphics.
* **Visibility Control (`mostrar_marcador`, `ocultar_marcador`)**: Toggles the overall visibility of the scoreboard, controlling the initial animation on the HTML output.
* **`actualizar_html`**: The critical function that gathers the entire current state of the match, generates the final **HTML/CSS content**, and writes it to `TXT/salida.html` and the structured state to `TXT/estado.json`. It embeds all dynamic data (scores, time, colors, logos, overlay HTML) into these output files for the broadcast graphics system to read.
