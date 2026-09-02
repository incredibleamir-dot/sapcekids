"""Main window: toolbar, mission tabs and a status bar."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QMainWindow,
                               QTabWidget, QTextBrowser, QToolBar, QVBoxLayout,
                               QWidget)

from . import APP_NAME, __version__, theme
from .controller import about_html, app_logo, toolbar_icon
from .pages.asteroid_page import AsteroidPage
from .pages.gnss_page import GnssPage
from .pages.mission_page import MissionPage
from .pages.orbitlab_page import OrbitLabPage
from .pages.porkchop_page import PorkchopPage
from .pages.settings_page import SettingsPage
from .pages.spotter_page import SpotterPage
from .pages.transfer_page import TransferStudyPage

TABS = [
    ("mission", "Rocket to Mars", "plan a Hohmann transfer to the Red Planet"),
    ("orbit", "Build My Satellite", "design an orbit and fly it"),
    ("asteroid", "Catch the Asteroid", "intercept a real NEO"),
    ("spotter", "ISS Spotter", "track satellites and find passes over town"),
    ("gnss", "Constellation Lab", "GPS, GLONASS & BeiDou over your places"),
    ("porkchop", "Porkchop Plot", "launch window contours of C3 and delta-v"),
    ("transfer", "Transfer Study", "compare Hohmann & Lambert transfer costs"),
    ("settings", "Settings", "themes, my places and scene tuning"),
]


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("%s - %s" % (APP_NAME, __version__))
        self.setWindowIcon(app_logo())
        self.resize(1280, 820)
        self.setMinimumSize(1040, 680)

        self.pages = {}

        self._build_actions()
        self._build_toolbar()
        self._build_tabs()
        theme.on_change(self._theme_updated)

    def _build_actions(self):
        self.act_about = QAction("About %s" % APP_NAME, self)
        self.act_about.setShortcut(Qt.Key_F1)
        self.act_about.triggered.connect(self.show_about)

        self.act_full = QAction("Toggle fullscreen", self)
        self.act_full.setShortcut(Qt.Key_F11)
        self.act_full.triggered.connect(self._toggle_fullscreen)

        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        self._tb_actions = []
        for _i, (key, label, _tip) in enumerate(TABS, start=1):
            act = QAction(toolbar_icon(), "%s  (Alt+%d)" % (label, _i), self)
            act.setShortcut("Alt+%d" % _i)
            act.triggered.connect(lambda _c, k=key: self._show_tab(k))
            tb.addAction(act)
            self._tb_actions.append(act)
        tb.addSeparator()
        tb.addAction(self.act_about)

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.pages = {
            "mission": MissionPage(),
            "orbit": OrbitLabPage(),
            "asteroid": AsteroidPage(),
            "spotter": SpotterPage(),
            "gnss": GnssPage(),
            "porkchop": PorkchopPage(),
            "transfer": TransferStudyPage(),
            "settings": SettingsPage(),
        }
        for key, label, tip in TABS:
            self.tabs.addTab(self.pages[key], label)
            self.tabs.setTabToolTip(self.tabs.count() - 1, tip)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)

        sb = self.statusBar()
        lbl = QLabel()
        sb.addWidget(lbl)
        lbl2 = QLabel("drag the sliders and press Play - physics does the rest")
        sb.addPermanentWidget(lbl2)

    def _show_tab(self, key):
        index = [t[0] for t in TABS].index(key)
        self.tabs.setCurrentIndex(index)

    def _tab_changed(self, index):
        key = TABS[index][0]
        page = self.pages.get(key)
        if page is not None:
            fn = getattr(page, "_on_shown", None)
            if fn:
                fn()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("About %s" % APP_NAME)
        out = QVBoxLayout(dlg)
        text = QTextBrowser()
        text.setHtml(about_html())
        text.setOpenExternalLinks(True)
        out.addWidget(text)
        dlg.resize(560, 380)
        dlg.exec()

    # ------------------------------------------------------------- theming
    def _theme_updated(self):
        """The active palette just changed: restyle everything instantly."""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.build_stylesheet())
        self.setWindowIcon(app_logo())
        for act in getattr(self, "_tb_actions", ()):
            act.setIcon(toolbar_icon())
        for page in self.pages.values():
            fn = getattr(page, "refresh_theme", None)
            if fn is not None:
                fn()
            for w in (getattr(page, "view", None), getattr(page, "map", None)):
                if w is not None and hasattr(w, "update"):
                    w.update()
        for w in self.findChildren(QWidget):
            if w is self:
                continue
            fn = getattr(w, "refresh_theme", None)
            if fn is not None:
                fn()