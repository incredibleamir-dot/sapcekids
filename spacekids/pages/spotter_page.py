"""Tab 4 - ISS Spotter.

Where is the space station right now, and when will it fly over my town?
Searches real satellite elements (catalog + a background CelesTrak refresh
when online), draws the ground track on a world map and lists the next
visible passes for the selected city, like the apps mission-controls use.
"""

import datetime

import numpy as np
from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem)

from .. import theme
from ..astro import satellites
from ..astro.core import julian_date
from ..geo import locations
from ..geo.earth import subpoint
from ..geo.mapview import MapView
from ..widgets import Panel, PlayBar, SliderRow
from .base import PageBase


class _Bridge(QObject):
    tle_ready = Signal(object, str)


class SpotterPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "ISS Spotter",
            "Watch the ground track of a spacecraft over the whole planet, "
            "then find out exactly when it passes above your town.",
            parent)
        self._bridge = _Bridge(self)
        self._bridge.tle_ready.connect(self._on_tle)
        self._live = None          # dict: name, prop, source
        self._off_s = 0.0
        self._track_start = 0.0    # sim-offset where the drawn track begins
        self._playing = False
        self._period = satellites.CATALOG[0].period_s
        self._jd_now = julian_date(datetime.datetime.utcnow())

        self._build_controls()
        self._build_canvas()
        self._fill_satellites()
        self._refresh_all()

        self._movie = QTimer(self)
        self._movie.setInterval(150)
        self._movie.timeout.connect(self._live_tick)
        self._movie.start()

        satellites.refresh_iss(self._bridge.tle_ready.emit)

    # ----------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Tracker")

        lay.addWidget(QLabel("Satellite"))
        self.sat = QComboBox()
        self.sat.currentIndexChanged.connect(self._refresh_all)
        lay.addWidget(self.sat)

        lay.addWidget(QLabel("My town"))
        self.city = QComboBox()
        self._fill_cities()
        self.city.currentIndexChanged.connect(self._refresh_all)
        lay.addWidget(self.city)

        self.s_horizon = SliderRow("See it above", 5, 30, 10, step=1,
                                   suffix=" deg")
        self.s_horizon.valueChanged.connect(self._refresh_all)
        lay.addWidget(self.s_horizon)

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay.addWidget(self.playbar)

        self.lbl_now = QLabel()
        self.lbl_now.setWordWrap(True)
        self._register_styled(self.lbl_now, "muted")
        lay.addWidget(self.lbl_now)

        passes = Panel(title="Next passes over my town")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Starts", "Greatest height", "Ends", "Minutes"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        passes.layout_box.addWidget(self.table)
        self.controls.addWidget(passes)

        self.fact = self.fact_label(
            "The ISS flies about 400 km above your head at nearly 8 km every "
            "second - a full lap of Earth every 93 minutes!")
        self.controls.addWidget(self.fact)

    def _build_canvas(self):
        self.map = MapView()
        self.map.set_title("Ground track - now and the next lap")
        self.add_canvas(self.map)

    # ---------------------------------------------------------------- sources
    def _fill_satellites(self):
        for d in satellites.CATALOG:
            self.sat.addItem(d.name, ("cat", d))

    def _current(self):
        data = self.sat.currentData()
        if data is None:
            return ("cat", satellites.CATALOG[0])
        return data

    def _is_tle(self, kind):
        return kind == "tle"

    def _fill_cities(self):
        self.city.blockSignals(True)
        self.city.clear()
        for rec in locations.all_locations():
            self.city.addItem(rec["name"], rec)
        if self.city.count():
            self.city.setCurrentIndex(0)
        self.city.blockSignals(False)

    def _city(self):
        data = self.city.currentData()
        if data is None:
            allp = locations.all_locations()
            return dict(allp[0]) if allp else None
        return dict(data)

    # ---------------------------------------------------------------- live TLE
    def _on_tle(self, prop, source):
        if prop is None:
            return
        if self._live is None:
            self._live = dict(name="ISS (live)", prop=prop, source=source)
            self.sat.addItem(self._live["name"], ("tle", prop))
            age_d = abs(prop.epoch_jd - self._jd_now)
            self.status("live TLE loaded (%.0f days old)" % age_d,
                        "info" if age_d < 15 else "warn")
            self._refresh_all()

    # ---------------------------------------------------------------- compute
    def _track_pts(self, src, is_tle, dur, start_s):
        """ECI positions of the ground-track window that begins ``start_s``
        seconds after page start (0 for the fresh track, ``_track_start``
        when a finished lap rolls the window forward)."""
        n = 400
        if is_tle:
            return satellites.track_positions_sgp4(
                src, self._jd_now + start_s / 86400.0, dur, n)
        step = dur / (n - 1)
        pts = np.empty((n, 3))
        for i in range(n):
            pts[i] = src.state_at(start_s + step * i)[0]
        return pts

    def _refresh_all(self):
        self._off_s = 0.0
        self._track_start = 0.0
        self._playing = False
        self.playbar.set_playing(False)
        kind, src = self._current()
        is_tle = self._is_tle(kind)

        dur = 200 * 60.0 if is_tle else src.period_s * 1.5
        self._period = dur
        pts = self._track_pts(src, is_tle, dur, 0.0)
        self._draw_track(pts, dur)
        self._refresh_passes()

    def _redraw_track(self, src, is_tle):
        """Recompute the ground track for the window starting right at the
        current marker position and repaint the map (used each finished lap)."""
        dur = self._period
        pts = self._track_pts(src, is_tle, dur, self._track_start)
        self._draw_track(pts, dur)

    def refresh_theme(self):
        super().refresh_theme()
        try:
            self._refresh_all()
        except Exception:
            pass

    def _draw_track(self, pts, dur):
        n = len(pts)
        lats = np.zeros(n)
        lons = np.zeros(n)
        for i in range(n):
            jd = self._jd_now + (self._track_start + dur * i /
                                 max(1, n - 1)) / 86400.0
            la, lo = subpoint(pts[i], jd)
            lats[i], lons[i] = la, lo
        self.map.clear()
        self.map.set_title("Ground track - now and the next lap")
        self.map.add_track(lats, lons, color=theme.C_SAT, width=2.4)
        self._draw_place_markers(label_sel=True)
        self._last_table_jd = None

    def _draw_place_markers(self, label_sel=True):
        """Saved places (Settings tab) get accent dots; the chosen town is the
        earth-coloured 'my town' marker so it stands out from the fleet."""
        place = self._city()
        for rec in locations.all_locations():
            if rec.get("user") is True:
                if place is None or rec["name"] != place["name"]:
                    self.map.add_point(rec["lat"], rec["lon"],
                                       color=theme.ACCENT, radius=4.2,
                                       glow=True)
        if place is not None:
            self.map.add_point(place["lat"], place["lon"],
                               color=theme.C_EARTH,
                               label="my town" if label_sel else None,
                               radius=4.0)

    def _refresh_passes(self):
        kind, src = self._current()
        is_tle = self._is_tle(kind)
        place = self._city()
        lat = place["lat"] if place else 0.0
        lon = place["lon"] if place else 0.0
        passes = satellites.find_passes(
            src, self._jd_now, lat, lon,
            horizon_deg=self.s_horizon.value(),
            span_hours=48.0, is_tle=is_tle)
        self.table.setRowCount(0)
        for p in passes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            mins = int(round((p["set_jd"] - p["rise_jd"]) * 1440.0))
            cells = [satellites.format_pass_time(p["rise_jd"]),
                     "%.0f deg" % p["max_elev"],
                     satellites.format_pass_time(p["set_jd"]),
                     "%d min" % mins]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 1:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
        if not passes:
            self.table.setRowCount(1)
            item = QTableWidgetItem(
                "No passes above %d deg in the next 48 hours"
                % self.s_horizon.value())
            item.setForeground(QColor(theme.WARN))
            self.table.setItem(0, 0, item)

    # ---------------------------------------------------------------- motion
    def _toggle_play(self, on):
        self._playing = bool(on)

    def _live_tick(self):
        if self._playing:
            self._off_s += (self.playbar.speed.currentData()
                            * self._period / 900.0)
            kind, src = self._current()
            is_tle = self._is_tle(kind)
            # once the marker has travelled the whole drawn ground track
            # (end of the line on the map), recompute the track from there
            # and redraw, keeping the line advancing start-to-end.
            while self._off_s - self._track_start >= self._period:
                self._track_start += self._period
                self._redraw_track(src, is_tle)

        kind, src = self._current()
        is_tle = self._is_tle(kind)
        if is_tle:
            r = src.eci(self._jd_now + self._off_s / 86400.0)
            r = r if r is not None else np.zeros(3)
        else:
            r = src.state_at(self._off_s)[0]
        jd = self._jd_now + self._off_s / 86400.0
        la, lo = subpoint(r, jd)

        self.map.clear_points()
        self._draw_place_markers(label_sel=False)
        self.map.add_point(la, lo, color=theme.C_SAT,
                           label=self.sat.currentText(), radius=5.0,
                           glow=True)

        srcname = (self._live["name"] if (self._live and
                                          self._live["prop"] is src)
                   else self.sat.currentText())
        self.lbl_now.setText(
            "%s is flying over  %.1f°N, %.1f°E  right now" %
            (srcname, la, lo))

        last = getattr(self, "_last_table_jd", None)
        now = self._jd_now
        if last is None or (now - last) * 86400.0 > 600.0:
            self._last_table_jd = now
            self._refresh_passes()

    def _on_shown(self):
        self._fill_cities()
        self._live_tick()