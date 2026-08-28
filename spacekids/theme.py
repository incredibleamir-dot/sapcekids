"""Theming: several kid-friendly palettes plus the global stylesheet.

Palettes are plain dicts; the module forwards unknown attributes (``theme.BG``,
``theme.C_SAT``, ...) to the currently active palette, so every component that
reads ``theme.<COLOR>`` at paint time follows a theme switch instantly.  Use
:func:`set_active` from anywhere (e.g. the settings page) - registered
listeners re-apply the app stylesheet afterwards.
"""

from PySide6.QtGui import QColor, QFont

# -------------------------------------------------------------------- palettes
# Every palette carries the same keys so any code can ask for any colour.
_KEYS = ("BG PANEL PANEL_ALT BORDER BORDER_SOFT GRID TEXT TEXT_MUT TEXT_DIM "
         "ACCENT ACCENT_DARK ACCENT_TEXT ACCENT_BG LINK "
         "OK OK_BG WARN WARN_BG ERR ERR_BG INFO INFO_BG CARD_EDGE "
         "C_EARTH C_MARS C_SUN C_ASTEROID C_SAT C_PROBE C_TRANSFER C_TRAIL "
         "C_GPS C_GLONASS C_BEIDOU C_PLACE_OFF").split()

SPACE_NIGHT = {
    "BG": "#0f1b2d", "PANEL": "#17253a", "PANEL_ALT": "#1d2e46",
    "BORDER": "#2b4060", "BORDER_SOFT": "#223450", "GRID": "#1d2c44",
    "TEXT": "#e8eef7", "TEXT_MUT": "#9fb2c9", "TEXT_DIM": "#6d81a0",
    "ACCENT": "#37b6ff", "ACCENT_DARK": "#1f8fd6", "ACCENT_TEXT": "#06131f",
    "ACCENT_BG": "#16334f", "LINK": "#6fd0ff",
    "OK": "#4cd487", "OK_BG": "#123a28", "WARN": "#ffc24b", "WARN_BG": "#3a2c12",
    "ERR": "#ff6b6b", "ERR_BG": "#3a151f", "INFO": "#6fb6ff", "INFO_BG": "#122b4a",
    "CARD_EDGE": "#2b4060",
    "C_EARTH": "#3f86e0", "C_MARS": "#e2623a", "C_SUN": "#ffd25e",
    "C_ASTEROID": "#c98aff", "C_SAT": "#5be0a0", "C_PROBE": "#37b6ff",
    "C_TRANSFER": "#ff9a4d", "C_TRAIL": "#6fd0ff",
    "C_GPS": "#5be0a0", "C_GLONASS": "#ff9a8a", "C_BEIDOU": "#8fb0ff",
    "C_PLACE_OFF": "#4a5a75",
}

RAINBOW_KIDS = {
    "BG": "#f2f7ff", "PANEL": "#ffffff", "PANEL_ALT": "#edf3fb",
    "BORDER": "#d4e1f0", "BORDER_SOFT": "#e3ecf6", "GRID": "#e0e9f4",
    "TEXT": "#24324a", "TEXT_MUT": "#5b6b85", "TEXT_DIM": "#94a2b8",
    "ACCENT": "#ff5da2", "ACCENT_DARK": "#e23f86", "ACCENT_TEXT": "#ffffff",
    "ACCENT_BG": "#ffe0ee", "LINK": "#3fa7ff",
    "OK": "#17b45a", "OK_BG": "#d7f4e1", "WARN": "#e8a000", "WARN_BG": "#fdeecb",
    "ERR": "#e5484d", "ERR_BG": "#fbdcdc", "INFO": "#2f8de8", "INFO_BG": "#d9eaff",
    "CARD_EDGE": "#d4e1f0",
    "C_EARTH": "#2f86e0", "C_MARS": "#f0712a", "C_SUN": "#ffb300",
    "C_ASTEROID": "#a04ff0", "C_SAT": "#12b886", "C_PROBE": "#ff5da2",
    "C_TRANSFER": "#f0852a", "C_TRAIL": "#3fa7ff",
    "C_GPS": "#12b886", "C_GLONASS": "#f0716d", "C_BEIDOU": "#5b8def",
    "C_PLACE_OFF": "#9aabc2",
}

SUNNY_DAY = {
    "BG": "#fff6e5", "PANEL": "#ffffff", "PANEL_ALT": "#fdf0d6",
    "BORDER": "#f0d8a4", "BORDER_SOFT": "#f7e6c2", "GRID": "#f6ead0",
    "TEXT": "#46311a", "TEXT_MUT": "#8a6d43", "TEXT_DIM": "#b89a6e",
    "ACCENT": "#ff8a00", "ACCENT_DARK": "#dd6f00", "ACCENT_TEXT": "#ffffff",
    "ACCENT_BG": "#ffe9bf", "LINK": "#2f9de0",
    "OK": "#2fb35a", "OK_BG": "#dcf5e4", "WARN": "#d9a514", "WARN_BG": "#fbebb0",
    "ERR": "#e5484d", "ERR_BG": "#fbdddc", "INFO": "#2f8de0", "INFO_BG": "#dbeaff",
    "CARD_EDGE": "#f0d8a4",
    "C_EARTH": "#3f86e0", "C_MARS": "#e2623a", "C_SUN": "#ffb300",
    "C_ASTEROID": "#a04ff0", "C_SAT": "#1f9d63", "C_PROBE": "#ff8a00",
    "C_TRANSFER": "#f0641a", "C_TRAIL": "#2f9de0",
    "C_GPS": "#1f9d63", "C_GLONASS": "#e2623a", "C_BEIDOU": "#5168c8",
    "C_PLACE_OFF": "#a8936b",
}

MOONLIGHT = {
    "BG": "#141028", "PANEL": "#201b3d", "PANEL_ALT": "#2a244d",
    "BORDER": "#403873", "BORDER_SOFT": "#332c5b", "GRID": "#2a244a",
    "TEXT": "#eef0ff", "TEXT_MUT": "#a9a7d8", "TEXT_DIM": "#746f9f",
    "ACCENT": "#c27fff", "ACCENT_DARK": "#a55bf0", "ACCENT_TEXT": "#140826",
    "ACCENT_BG": "#33265c", "LINK": "#9ad0ff",
    "OK": "#4cd487", "OK_BG": "#123a28", "WARN": "#ffc24b", "WARN_BG": "#3a2c12",
    "ERR": "#ff6b6b", "ERR_BG": "#3a151f", "INFO": "#8fb8ff", "INFO_BG": "#1d2a4a",
    "CARD_EDGE": "#403873",
    "C_EARTH": "#4a8ef0", "C_MARS": "#f0805a", "C_SUN": "#ffd25e",
    "C_ASTEROID": "#e0a0ff", "C_SAT": "#5be0a0", "C_PROBE": "#c27fff",
    "C_TRANSFER": "#ff9a4d", "C_TRAIL": "#9ad0ff",
    "C_GPS": "#5be0a0", "C_GLONASS": "#ff9a8a", "C_BEIDOU": "#8fb0ff",
    "C_PLACE_OFF": "#5f5a88",
}

AURORA = {
    "BG": "#071a1e", "PANEL": "#0d2b2e", "PANEL_ALT": "#13393b",
    "BORDER": "#1f4a4b", "BORDER_SOFT": "#15383a", "GRID": "#122f33",
    "TEXT": "#e8fbf7", "TEXT_MUT": "#9fd0c9", "TEXT_DIM": "#5f938d",
    "ACCENT": "#5ff0d0", "ACCENT_DARK": "#33cfae", "ACCENT_TEXT": "#05211a",
    "ACCENT_BG": "#123f38", "LINK": "#8fdcff",
    "OK": "#7be08a", "OK_BG": "#123a24", "WARN": "#ffcf5e", "WARN_BG": "#3a2c10",
    "ERR": "#ff7b7b", "ERR_BG": "#3a1518", "INFO": "#8fdcff", "INFO_BG": "#102b3a",
    "CARD_EDGE": "#1f4a4b",
    "C_EARTH": "#3f9ff0", "C_MARS": "#f0805a", "C_SUN": "#ffe08a",
    "C_ASTEROID": "#b09fff", "C_SAT": "#7be08a", "C_PROBE": "#5ff0d0",
    "C_TRANSFER": "#ffb347", "C_TRAIL": "#8fdcff",
    "C_GPS": "#7be08a", "C_GLONASS": "#ff9a8a", "C_BEIDOU": "#8fb0ff",
    "C_PLACE_OFF": "#3f6a66",
}

_PALETTES = {
    "Space Night": SPACE_NIGHT,
    "Rainbow Kids": RAINBOW_KIDS,
    "Sunny Day": SUNNY_DAY,
    "Moonlight": MOONLIGHT,
    "Aurora": AURORA,
}
_BLURBS = {
    "Space Night": "Deep-space navy with sky-blue accents (default).",
    "Rainbow Kids": "Bright and light with a candy-pink accent - very playful.",
    "Sunny Day": "Warm cream and sunshine orange.",
    "Moonlight": "Deep indigo night with a violet glow.",
    "Aurora": "Dark polar night with aurora-green light.",
}

DEFAULT_THEME = "Space Night"

_name = DEFAULT_THEME
_active = dict(_PALETTES[DEFAULT_THEME])
_listeners = []


def themes():
    """Ordered list of theme names, in menu order."""
    return list(_PALETTES)


def active_name():
    return _name


def blurb(name):
    return _BLURBS.get(name, "")


def on_change(fn):
    """Register ``fn()``; called after the active palette has switched."""
    _listeners.append(fn)


def set_active(name, persist=True):
    """Switch the active palette and notify listeners.  Unknown names are
    ignored (keeps the current theme rather than crashing)."""
    global _active, _name
    if name not in _PALETTES:
        return
    if name == _name:
        return
    _name = name
    _active = _PALETTES[name]
    if persist:
        try:
            from . import settings
            settings.set("theme", name)
        except Exception:
            pass
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            pass


def __getattr__(name):
    """Forward ``theme.COLOR`` to the currently active palette."""
    if name in _active:
        return _active[name]
    raise AttributeError(name)


# --------------------------------------------------------------------------- fonts
FAMILY = "Segoe UI"
MONO = "Consolas"


def font(size=10, bold=False, mono=False, family=None):
    f = QFont(mono and MONO or (family or FAMILY), size)
    f.setBold(bold)
    return f


def chip_color(kind):
    hexcol = {"ok": _active["OK"], "warn": _active["WARN"],
              "err": _active["ERR"], "error": _active["ERR"],
              "info": _active["INFO"], "no": _active["ERR"]}.get(
                  kind, _active["TEXT_MUT"])
    return QColor(hexcol)


def css_for(role="muted"):
    """A tiny inline stylesheet for labelled text, rebuilt per theme.

    Roles: ``text``, ``muted``, ``dim``, ``accent``, ``fact``.
    """
    if role == "fact":
        return ("color: %s; border-left: 3px solid %s; padding: 4px 8px;"
                % (_active["TEXT_MUT"], _active["ACCENT"]))
    key = {"text": "TEXT", "muted": "TEXT_MUT", "dim": "TEXT_DIM",
           "accent": "ACCENT"}.get(role, "TEXT_MUT")
    return "color: %s;" % _active[key]


# --------------------------------------------------------------------------- stylesheet
_STYLE_TPL = """
QWidget {
    background: %(bg)s;
    color: %(text)s;
    font-family: "Segoe UI";
    font-size: 13px;
    selection-background-color: %(accent)s;
    selection-color: %(accent_text)s;
}

QMainWindow, QDialog { background: %(bg)s; }

QMenuBar {
    background: %(panel)s;
    border-bottom: 1px solid %(border)s;
    padding: 2px 4px;
}
QMenuBar::item { padding: 4px 10px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: %(accent_bg)s; color: %(accent)s; }

QMenu {
    background: %(panel)s;
    border: 1px solid %(border)s;
    padding: 4px;
}
QMenu::item { padding: 5px 22px 5px 14px; border-radius: 4px; }
QMenu::item:selected { background: %(accent_bg)s; color: %(accent)s; }
QMenu::separator { height: 1px; background: %(border_soft)s; margin: 4px 8px; }

QToolBar {
    background: %(panel)s;
    border: none;
    border-bottom: 1px solid %(border)s;
    padding: 4px 6px;
    spacing: 4px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 10px;
    color: %(text_mut)s;
}
QToolBar QToolButton:hover { background: %(accent_bg)s; color: %(text)s; }
QToolBar QToolButton:checked {
    background: %(accent)s;
    color: %(accent_text)s;
    border-color: %(accent)s;
}
QToolBar QToolButton:pressed { background: %(accent_dark)s; }

QTabWidget::pane {
    border: 1px solid %(border)s;
    background: %(panel)s;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: %(text_mut)s;
    padding: 9px 16px;
    border: 1px solid transparent;
    border-bottom: 3px solid transparent;
    margin-right: 3px;
    font-size: 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    color: %(accent)s;
    border-bottom-color: %(accent)s;
    background: %(panel)s;
}
QTabBar::tab:hover:!selected { color: %(link)s; }

QGroupBox {
    background: %(panel)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 12px 10px 12px;
    font-weight: 600;
    color: %(text)s;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background: %(panel)s;
    color: %(accent)s;
    font-size: 11px;
    letter-spacing: 1px;
}

QPushButton {
    background: %(panel_alt)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 6px 16px;
    color: %(text)s;
}
QPushButton:hover { border-color: %(accent)s; color: %(accent)s; }
QPushButton:pressed { background: %(accent_bg)s; }
QPushButton:default, QPushButton[primary="true"] {
    background: %(accent)s;
    border: 1px solid %(accent)s;
    color: %(accent_text)s;
    font-weight: 600;
}
QPushButton:default:hover, QPushButton[primary="true"]:hover {
    background: %(accent_dark)s; border-color: %(accent_dark)s; color: %(accent_text)s;
}
QPushButton:disabled { color: %(text_dim)s; border-color: %(border_soft)s; background: %(panel_alt)s; }

QLineEdit, QDoubleSpinBox, QSpinBox, QDateEdit, QTimeEdit, QComboBox {
    background: %(panel_alt)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 5px 9px;
    min-height: 24px;
    color: %(text)s;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus {
    border-color: %(accent)s;
}
QDateEdit, QTimeEdit { selection-background-color: %(accent_bg)s; }

QSlider::groove:horizontal {
    height: 6px;
    background: %(border)s;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: %(accent)s;
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:hover { background: %(link)s; }
QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 3px; }
QSlider::groove:vertical {
    width: 6px;
    background: %(border)s;
    border-radius: 3px;
}
QSlider::handle:vertical {
    background: %(accent)s;
    width: 18px;
    height: 18px;
    margin: 0 -6px;
    border-radius: 9px;
}
QSlider::sub-page:vertical { background: %(accent)s; border-radius: 3px; }

QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: %(panel)s;
    border: 1px solid %(border)s;
    selection-background-color: %(accent_bg)s;
    selection-color: %(accent)s;
    outline: none;
}
QDateEdit::drop-down, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button { width: 20px; border: none; background: transparent; }

QTableView, QTableWidget {
    background: %(panel_alt)s;
    alternate-background-color: %(panel)s;
    gridline-color: %(border_soft)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    selection-background-color: %(accent_bg)s;
    selection-color: %(accent)s;
    color: %(text)s;
}
QTableView QHeaderView::section {
    background: %(panel)s;
    color: %(text_mut)s;
    border: none;
    border-bottom: 1px solid %(border)s;
    border-right: 1px solid %(border_soft)s;
    padding: 6px 8px;
    font-weight: 600;
}
QTableView QTableCornerButton::section {
    background: %(panel)s;
    border: none;
    border-bottom: 1px solid %(border)s;
}

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 5px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: %(accent)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(border)s; border-radius: 5px; min-width: 26px; }

QStatusBar {
    background: %(panel)s;
    border-top: 1px solid %(border)s;
    color: %(text_mut)s;
}
QStatusBar QLabel { color: %(text_mut)s; padding: 0 6px; }
QStatusBar QLabel[chip="ok"] { color: %(ok)s; }
QStatusBar QLabel[chip="warn"] { color: %(warn)s; }
QStatusBar QLabel[chip="err"] { color: %(err)s; }

QToolTip {
    background: %(panel)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    padding: 5px 9px;
}

QSplitter::handle { background: transparent; width: 8px; }

QLabel[section="true"] { color: %(accent)s; font-weight: 600; letter-spacing: 1px; }
"""


def build_stylesheet():
    """The full app stylesheet, formatted from the active palette."""
    a = _active
    return _STYLE_TPL % {
        "bg": a["BG"], "panel": a["PANEL"], "panel_alt": a["PANEL_ALT"],
        "border": a["BORDER"], "border_soft": a["BORDER_SOFT"],
        "text": a["TEXT"], "text_mut": a["TEXT_MUT"],
        "text_dim": a["TEXT_DIM"], "accent": a["ACCENT"],
        "accent_dark": a["ACCENT_DARK"], "accent_text": a["ACCENT_TEXT"],
        "accent_bg": a["ACCENT_BG"], "link": a["LINK"],
        "ok": a["OK"], "warn": a["WARN"], "err": a["ERR"], "info": a["INFO"],
    }