"""Tab 5 - Constellation Lab.

Pick the GPS, GLONASS or BeiDou satellite fleet and watch which places have a
navigation satellite high enough to see at any moment - the job every phone
does when it figures out where you are.  Your own saved places (added in the
app's Settings tab) show up here and in the ISS Spotter.
"""

import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem)

from .. import theme
from ..astro import constellations
from ..astro.core import julian_date
from ..astro.satellites import format_pass_time
from ..geo import locations
from ..geo.earth import ring_points
from ..geo.mapview import MapView
from ..widgets import Panel, PlayBar, SliderRow
from .base import PageBase

_SID_DAY_S = 86164.0  # one turn of the whole fleet over the map


def _now_jd():
    return julian_date(datetime.datetime.utcnow())


class GnssPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Constellation Lab",
            "Pick a sat-nav fleet, mark your own places, and see which ones "
            "have a satellite overhead at this very moment.",
            parent)
        self._base_jd = _now_jd()
        self._off_s = 0.0
        self._playing = False
        self._last_table_jd = None

        self._build_controls()
        self._build_canvas()
        self._fill_places()
        self._refresh_all()

        self._movie = QTimer(self)
        self._movie.setInterval(150)
        self._movie.timeout.connect(self._tick)
        self._movie.start()

    # ------------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Satellite fleet")

        lay.addWidget(QLabel("Constellation"))
        self.fleet = QComboBox()
        for name in constellations.constellation_names():
            self.fleet.addItem(name)
        self.fleet.currentIndexChanged.connect(self._refresh_all)
        lay.addWidget(self.fleet)

        self.fleet_fact = QLabel()
        self.fleet_fact.setWordWrap(True)
        self.fleet_fact.setStyleSheet(
            "color: %s; border-left: 3px solid %s; padding: 2px 8px;"
            % (theme.TEXT_MUT, constellations.color(
                constellations.constellation_names()[0])))
        lay.addWidget(self.fleet_fact)
        self._update_fleet_fact()

        box2, lay2 = self.add_group("My places")
        self.place = QComboBox()
        self.place.currentIndexChanged.connect(self._refresh_all)
        lay2.addWidget(self.place)

        self.s_mask = SliderRow("See it above", 5, 30, 10, step=1,
                                suffix=" deg")
        self.s_mask.valueChanged.connect(self._refresh_all)
        lay2.addWidget(self.s_mask)

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay2.addWidget(self.playbar)

        self.lbl_now = QLabel()
        self.lbl_now.setWordWrap(True)
        self._register_styled(self.lbl_now, "muted")
        lay2.addWidget(self.lbl_now)

        seen = Panel(title="Places with a satellite in view")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Place", "In view", "Highest"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        seen.layout_box.addWidget(self.table)
        self.controls.addWidget(seen)

        self.fact = self.fact_label(
            "GPS, GLONASS and BeiDou together paint a net of moving beacons "
            "around Earth - your phone needs at least four to find you!")
        self.controls.addWidget(self.fact)

    def _build_canvas(self):
        self.map = MapView()
        self.map.set_title("Fleet over the world - now")
        self.map.setMinimumSize(520, 300)
        self.add_canvas(self.map)

    # ------------------------------------------------------------ internals
    def _fleet_name(self):
        return self.fleet.currentText()

    def _fleet_color(self):
        return constellations.color(self._fleet_name())

    def _update_fleet_fact(self):
        self.fleet_fact.setText(
            "Fact: " + constellations.constellation_fact(self._fleet_name()))
        self.fleet_fact.setStyleSheet(
            "color: %s; border-left: 3px solid %s; padding: 2px 8px;"
            % (theme.TEXT_MUT, self._fleet_color()))

    def _fill_places(self):
        self.place.blockSignals(True)
        self.place.clear()
        for rec in locations.all_locations():
            self.place.addItem(rec["name"], rec)
        if self.place.count():
            self.place.setCurrentIndex(0)
        self.place.blockSignals(False)

    def _place_rec(self):
        data = self.place.currentData()
        if data is None:
            allp = locations.all_locations()
            return dict(allp[0]) if allp else None
        return dict(data)

    # ---------------------------------------------------------------- compute
    def _now_jd(self):
        return self._base_jd + self._off_s / 86400.0

    def _refresh_all(self):
        self._off_s = 0.0
        self._playing = False
        self.playbar.set_playing(False)
        self._update_fleet_fact()
        self._redraw()
        self._refresh_table()

    def _redraw(self):
        name = self._fleet_name()
        fleet = constellations.satellites(name)
        col = self._fleet_color()
        mask = self.s_mask.value()
        jd = self._now_jd()
        place = self._place_rec()

        self.map.clear()
        self.map.set_title("%s over the world - now" % name)

        if place is not None:
            # approximate footprint circle (whole fleet's altitude)
            alt = max(20000.0, fleet[0].a_km - 6371.0)
            rr = constellations.footprint_radius_deg(alt, mask)
            lats, lons = ring_points(place["lat"], place["lon"], rr)
            self.map.add_track(lats, lons, color=col + "66", width=1.2)

            seen_at_home = constellations.visible(fleet, jd, place["lat"],
                                                  place["lon"], mask)
            home_radius = 5.5
        else:
            seen_at_home = []

        # every place: green when covered, grey otherwise
        for rec in locations.all_locations():
            hits = constellations.visible(fleet, jd, rec["lat"], rec["lon"],
                                          mask)
            is_home = place is not None and rec["name"] == place["name"]
            color = theme.OK if hits else theme.GRID
            r = home_radius if is_home else 3.4
            self.map.add_point(rec["lat"], rec["lon"], color=color,
                               label=rec["name"] if is_home else None,
                               radius=r,
                               glow=(is_home and bool(hits)))

        # the fleet dots right now; brighter = the ones your place can see
        for d in fleet:
            s = constellations.sub(d, jd)
            vis = any(d is h[0] for h in seen_at_home)
            self.map.add_point(s[0], s[1], color=(col if vis else col + "66"),
                               radius=(2.6 if vis else 1.9),
                               glow=vis)

        # short arcs of the visible satellites' tracks (where they came from)
        for d, _el in seen_at_home:
            lats, lons = [], []
            for i in range(26):
                t_s = -30.0 * 60.0 + (i / 25.0) * 90.0 * 60.0
                la, lo = constellations.sub(d, jd + t_s / 86400.0)
                lats.append(la)
                lons.append(lo)
            self.map.add_track(lats, lons, color=col + "88", width=1.4)

        self.lbl_now.setText(
            "Simulated now: %s UT\n%s satellites of %s are above your place %s"
            % (format_pass_time(jd), len(seen_at_home), name,
               place["name"] if place else "(-)"))
        self.map.update()

    def _refresh_table(self):
        mask = self.s_mask.value()
        fleet = constellations.satellites(self._fleet_name())
        jd = self._now_jd()
        rows = constellations.visible_places(fleet, jd,
                                             locations.all_locations(), mask)
        self.table.setRowCount(0)
        ia = self.place.currentIndex()
        for i, row in enumerate(rows):
            r = self.table.rowCount()
            self.table.insertRow(r)
            cells = [row["name"],
                     "%d" % row["count"] if row["count"] else "\u2013",
                     "%s   %0.f\u00b0" % (row["best"], row["elev"])
                     if row["count"] else "none visible"]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 0 and i == ia:
                    item.setForeground(QColor(theme.ACCENT))
                elif c == 2 and row["count"] == 0:
                    item.setForeground(QColor(theme.TEXT_DIM))
                self.table.setItem(r, c, item)

    # ---------------------------------------------------------------- motion
    def _toggle_play(self, on):
        self._playing = bool(on)

    def _tick(self):
        if self._playing:
            self._off_s += (self.playbar.speed.currentData()
                            * _SID_DAY_S / 900.0)
            if self._off_s > _SID_DAY_S:
                self._off_s -= _SID_DAY_S
        self._redraw()
        last = getattr(self, "_last_table_jd", None)
        now = self._now_jd()
        if last is None or (now - last) * 86400.0 > 600.0:
            self._last_table_jd = now
            self._refresh_table()

    def _on_shown(self):
        self._fill_places()
        self._tick()

    def refresh_theme(self):
        super().refresh_theme()
        self._update_fleet_fact()
        self._redraw()
        self._refresh_table()