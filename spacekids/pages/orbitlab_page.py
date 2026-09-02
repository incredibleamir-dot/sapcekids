"""Tab 2 - Build My Satellite.

Sliders for how close/high/tilted the orbit is, a flying scene around the
Earth, live numbers (period, speeds, orbit family) and a ground-track map.
"""

import datetime

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QLabel

from .. import theme
from ..astro import orbitlab
from ..astro.core import julian_date
from ..geo.earth import subpoint
from ..geo.mapview import MapView
from ..views.orbital3d import Body, make_orbital_view
from ..widgets import Panel, PlayBar, SliderRow, StatBox
from .base import PageBase


class OrbitLabPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Build My Satellite",
            "How low? How high? How tilted? Design an orbit and fly it. "
            "Real numbers, promise - this is the same math NASA uses.",
            parent)
        self._design = orbitlab.PRESETS["ISS (Low Orbit)"]
        self._jd_now = julian_date(datetime.datetime.utcnow())

        self._build_controls()
        self._build_canvas()
        self.rebuild()

        self._movie = QTimer(self)
        self._movie.setInterval(120)
        self._movie.timeout.connect(self._live_updates)
        self._movie.start()

    # ----------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Orbit workshop")

        lay.addWidget(QLabel("Start from a famous orbit:"))
        self.preset = QComboBox()
        self.preset.addItems(list(orbitlab.PRESETS.keys()))
        self.preset.currentTextChanged.connect(self._apply_preset)
        lay.addWidget(self.preset)

        self.s_peri = SliderRow("Periapsis altitude", 100, 35790, 407, step=10,
                                suffix=" km")
        self.s_apo = SliderRow("Apoapsis altitude", 400, 60000, 417, step=50,
                               suffix=" km")
        self.s_inc = SliderRow("Inclination (INC)", 0, 90, 51.6, step=0.5,
                               suffix=" deg", decimals=1)
        self.s_raan = SliderRow("RAAN", 0, 360, 0, step=1, suffix=" deg")
        for s in (self.s_peri, self.s_apo, self.s_inc, self.s_raan):
            lay.addWidget(s)
            s.valueChanged.connect(lambda _v: self.rebuild())

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay.addWidget(self.playbar)

        stats = Panel(title="Orbit report")
        self.st_period = StatBox("orbital period (min)")
        self.st_low = StatBox("velocity @ periapsis (km/s)")
        self.st_high = StatBox("velocity @ apoapsis (km/s)")
        self.st_type = StatBox("orbit classification")
        for w in (self.st_period, self.st_low, self.st_high, self.st_type):
            stats.layout_box.addWidget(w)
        self.controls.addWidget(stats)

        self.fact = self.fact_label(
            "Speed changes a lot: satellites fly like a bicycle over a hill - "
            "fast at the bottom, slow at the top.")
        self.controls.addWidget(self.fact)

    def _build_canvas(self):
        self.view = make_orbital_view()
        self.add_canvas(self.view)
        self.view.dt = 60.0
        self.map = MapView()
        self.map.setMinimumHeight(260)
        self.add_static(self.map)

    # ----------------------------------------------------------------- math
    def rebuild(self):
        peri = self.s_peri.value()
        apo = self.s_apo.value()
        if apo <= peri:
            apo = peri + 50.0
        rp = orbitlab.RE + peri
        ra = orbitlab.RE + apo
        a = (rp + ra) / 2.0
        e = (ra - rp) / (ra + rp)
        self._design = orbitlab.OrbitDesign(
            "Custom", a, e,
            self.s_inc.value(), self.s_raan.value(), 0.0, 0.0)

        self._refresh_scene()
        self._refresh_report()
        self._refresh_map()

    def _apply_preset(self, name):
        d = orbitlab.PRESETS.get(name)
        if d is None:
            return
        self.s_peri.set_value(d.alt_peri)
        self.s_apo.set_value(d.alt_apo)
        self.s_inc.set_value(d.inc_deg)
        self.s_raan.set_value(d.raan_deg)
        self.rebuild()

    def _refresh_scene(self):
        d = self._design
        from ..astro.kepler import sample_elements
        pts = sample_elements(d.k, d.a_km, d.e, d.inc_deg, d.raan_deg,
                              d.argp_deg, n=400)

        # Kid-friendly exaggeration: draw the planet well *inside* the orbit
        # so the fly ring reads as a clean circle instead of hugging a giant
        # sphere.  The orbit itself is still drawn at true scale.
        rp = d.rp_km
        earth_visual = min(0.55 * rp, orbitlab.RE)

        # Look straight down the orbit's angular-momentum axis so a circular
        # orbit renders as a clean circle (not a foreshortened ellipse).
        p0 = d.state_at(0.0)[0]
        p1 = d.state_at(d.period_s / 4.0)[0]
        p2 = d.state_at(d.period_s / 2.0)[0]
        normal = np.cross(np.asarray(p1) - np.asarray(p0),
                          np.asarray(p2) - np.asarray(p0))

        self.view.set_scene(
            [dict(points=pts, color=theme.C_SAT, width=1.8)],
            [Body(self._sat_position, 60.0, theme.C_SAT, "My satellite",
                  glow=0.6),
             Body(lambda _t: (0.0, 0.0, 0.0), earth_visual, theme.C_EARTH,
                  "Earth", glow=0.8)],
            center=(0.0, 0.0),
            title="My orbit around Earth",
            subtitle="top-down view (Earth at the centre)",
            min_radius_km=d.a_km * (1.0 + d.e) * 1.08,
            view_axis=normal)
        self.view.dt = d.period_s / 900.0 * self.playbar.speed.currentData()

    def _sat_position(self, t):
        return self._design.state_at(t)[0]

    def _refresh_report(self):
        d = self._design
        self.st_period.set_value("%.1f min" % d.period_min)
        self.st_low.set_value("%.2f km/s" % d.speed_peri)
        self.st_high.set_value("%.2f km/s" % d.speed_apo)
        self.st_type.set_value(d.classification())
        if d.e > 0.75:
            self.status("very stretchy orbit!", "warn")
        else:
            self.status(d.classification().split(" - ")[0], "info")

    def _refresh_map(self):
        d = self._design
        lats, lons = d.ground_track(n=720, start_jd=self._jd_now)
        self.map.clear()
        self.map.set_title("Ground track - where my satellite is over Earth")
        self.map.add_track(lats, lons, color=theme.C_SAT, width=2.2)
        self._live_updates()

    # ----------------------------------------------------------------- motion
    def _toggle_play(self, on):
        if on:
            self.view.play(True)
        else:
            self.view.play(False)

    def _live_updates(self):
        if not self._design:
            return
        t = self.view.t
        if self.view.playing and t >= self._design.period_s:
            self.view.t = 0.0
            t = 0.0
        r = self._design.state_at(t)[0]
        jd = self._jd_now + t / 86400.0
        la, lo = subpoint(r, jd)
        self.map.clear_points()
        self.map.add_point(la, lo, color=theme.C_SAT, label="my satellite",
                           radius=5.0)
        self.status("flying - matching the white chalk line", "info")

    def _on_shown(self):
        self.view.update()

    def refresh_theme(self):
        super().refresh_theme()
        self._refresh_scene()
        self._refresh_map()
        self._live_updates()