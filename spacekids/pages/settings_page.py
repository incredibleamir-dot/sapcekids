"""Tab 6 - Settings: themes, my places, and how the scenes feel.

Theme picker (several kid-friendly palettes), the shared "my places" list
(also shown on the ISS Spotter and Constellation Lab maps), how many stars the
space scenes draw, and the default movie speed.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QSizePolicy, QTableWidget,
                               QTableWidgetItem)

from .. import settings, theme
from ..geo import locations
from ..widgets import Panel, SliderRow, prompt_add_place
from .base import PageBase


class SettingsPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Settings",
            "Pick a look, save your own places, and tune how the scenes feel.",
            parent)
        self._build_controls()
        self._fill_table()

    # ------------------------------------------------------------------- ui
    def _fit_group(self, box):
        box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def _build_controls(self):
        box, lay = self.add_group("Appearance")
        self._fit_group(box)

        lay.addWidget(QLabel("Colour theme"))
        self.theme_box = QComboBox()
        for name in theme.themes():
            self.theme_box.addItem(name)
        self.theme_box.setCurrentIndex(
            self.theme_box.findText(theme.active_name()))
        self.theme_box.currentIndexChanged.connect(self._change_theme)
        lay.addWidget(self.theme_box)

        self.prev = QLabel()
        self.blurb = QLabel()
        self.blurb.setWordWrap(True)
        self._register_styled(self.blurb, "muted")
        for lbl in (self.prev, self.blurb):
            lbl.setMinimumWidth(1)
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        lay.addWidget(self.prev)
        lay.addWidget(self.blurb)
        self._update_preview()

        self.s_stars = SliderRow("Stars in space scenes",
                                 40, 420, int(settings.get("stars", 200)),
                                 step=10, suffix=" stars")
        self.s_stars.valueChanged.connect(self._change_stars)
        lay.addWidget(self.s_stars)

        lay.addWidget(QLabel("Default movie speed"))
        self.speed_box = QComboBox()
        for i, (label, _mult) in enumerate(
                (("1x", 1.0), ("2x", 2.0), ("5x", 5.0),
                 ("10x", 10.0), ("30x", 30.0))):
            self.speed_box.addItem(label, i)
        self.speed_box.setCurrentIndex(int(settings.get("playback", 1)))
        self.speed_box.currentIndexChanged.connect(self._change_speed)
        lay.addWidget(self.speed_box)

        box2, lay2 = self.add_group("My places")
        self._fit_group(box2)
        note = QLabel("Places you add are saved for good and appear here, on "
                      "the Constellation Lab map, and on the ISS Spotter map "
                      "as extra 'my town' choices.")
        note.setWordWrap(True)
        note.setMinimumWidth(1)
        note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._register_styled(note, "muted")
        lay2.addWidget(note)

        self.places = Panel(title="Saved places")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Latitude", "Longitude", "Kind"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.places.layout_box.addWidget(self.table)
        self.controls.addWidget(self.places)

        btns = self._make_place_buttons()
        lay2.addLayout(btns)

        box3, lay3 = self.add_group("Extras")
        self._fit_group(box3)
        reset = QPushButton("Reset all settings to defaults")
        reset.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        reset.clicked.connect(self._reset_all)
        lay3.addWidget(reset)
        about = QLabel("Need help? Press F1 for the About box.")
        about.setWordWrap(True)
        about.setMinimumWidth(1)
        about.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._register_styled(about, "muted")
        lay3.addWidget(about)

        self.fact = self.fact_label(
            "Themes restyle the whole app instantly - try Rainbow Kids, then "
            "Sunny Day, then Moonlight and pick your favourite!")
        self.controls.addWidget(self.fact)

    def _make_place_buttons(self):
        btns = QHBoxLayout()
        self.btn_add = QPushButton("Add place")
        self.btn_add.setProperty("primary", True)
        self.btn_add.setToolTip("Add a new place to the shared my-places list")
        self.btn_add.clicked.connect(self._add_place)
        self.btn_del = QPushButton("Remove selected")
        self.btn_del.clicked.connect(self._remove_place)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        return btns

    # ------------------------------------------------------------- appearance
    def _update_preview(self):
        name = self.theme_box.currentText()
        a = theme._PALETTES.get(name, {})
        dots = "  ".join(
            "<span style='font-size:17px; color:%s;'>&#9679;</span><span "
            "style='color:%s;'>&#160;%s</span>"
            % (a.get(key, "#888"), QColor(a.get(key, "#ddd")).name(),
               label)
            for key, label in (("BG", "background"),
                               ("ACCENT", "accent"),
                               ("TEXT", "text")))
        self.prev.setText(dots)
        self.blurb.setText(theme.blurb(name))

    def _change_theme(self, _index):
        theme.set_active(self.theme_box.currentText())
        self._update_preview()

    def _change_stars(self, value):
        settings.set("stars", int(value))
        win = self.window()
        if win is not None and hasattr(win, "pages"):
            for page in win.pages.values():
                view = getattr(page, "view", None)
                if view is not None and hasattr(view, "set_stars"):
                    view.set_stars(int(value))

    def _change_speed(self, index):
        settings.set("playback", int(index))
        win = self.window()
        if win is not None and hasattr(win, "pages"):
            for page in win.pages.values():
                bar = getattr(page, "playbar", None)
                if bar is not None and hasattr(bar, "speed"):
                    bar.speed.setCurrentIndex(int(index))

    # ----------------------------------------------------------------- places
    def _fill_table(self, select_name=None):
        self._records = locations.all_locations()
        self.table.setRowCount(0)
        for i, rec in enumerate(self._records):
            r = self.table.rowCount()
            self.table.insertRow(r)
            cells = [rec["name"], "%.2f" % rec["lat"], "%.2f" % rec["lon"],
                     "mine" if rec.get("user") else "built-in"]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 3 and rec.get("user"):
                    item.setForeground(QColor(theme.ACCENT))
                self.table.setItem(r, c, item)
        if select_name:
            for i, rec in enumerate(self._records):
                if rec["name"] == select_name:
                    self.table.selectRow(i)
                    break

    def _selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def _add_place(self):
        rec = prompt_add_place(self)
        if rec is None:
            self.status("please type a name and real latitude/longitude", "err")
            return
        try:
            locations.add_location(rec["name"], rec["lat"], rec["lon"])
        except ValueError:
            self.status("latitude must be -90..90, longitude -180..180", "err")
            return
        self._fill_table(select_name=rec["name"])
        self.status("saved my place: %s" % rec["name"], "ok")

    def _remove_place(self):
        rec = self._selected()
        if rec is None:
            self.status("pick a place in the table first", "warn")
            return
        if not rec.get("user"):
            self.status("%s is a built-in city - only remove your own places"
                        % rec["name"], "warn")
            return
        locations.remove_location(rec["name"])
        self._fill_table()
        self.status("removed my place: %s" % rec["name"], "ok")

    # ------------------------------------------------------------------- misc
    def _reset_all(self):
        settings.reset()
        theme.set_active(settings.get("theme", theme.DEFAULT_THEME))
        stars = int(settings.get("stars", 200))
        speed = int(settings.get("playback", 1))
        self.s_stars.set_value(stars)
        self.speed_box.setCurrentIndex(speed)
        self.theme_box.setCurrentIndex(
            self.theme_box.findText(theme.active_name()))
        self._change_stars(stars)
        self._change_speed(speed)
        self._update_preview()
        self.status("settings back to defaults", "ok")

    def _on_shown(self):
        self._fill_table()
        self._update_preview()

    def refresh_theme(self):
        super().refresh_theme()
        self._fill_table()