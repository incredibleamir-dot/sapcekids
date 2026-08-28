#!/usr/bin/env python3
"""Space Kids - a playful orbital-mechanics playground (PySide6 + poliastro).

Run from this directory:  python3.13 main.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE = HERE
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "vendor"))

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    if getattr(sys, "frozen", False):
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")

    from PySide6.QtWidgets import QApplication

    from spacekids import APP_NAME, ORGANIZATION, settings, theme
    from spacekids.controller import app_logo
    from spacekids.app_window import MainWindow

    theme.set_active(settings.get("theme", theme.DEFAULT_THEME), persist=False)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.build_stylesheet())
    app.setWindowIcon(app_logo())
    font = app.font()
    font.setFamily(theme.FAMILY)
    font.setPointSize(10)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())