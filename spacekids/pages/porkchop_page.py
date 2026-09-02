"""Tab 7 - Porkchop Plot.

A classic JPL porkchop chart: launch-date vs time-of-flight contours of
characteristic energy (C3) and total delta-v for an Earth -> Mars transfer.
Pick a date window, see the cost landscape, click a sweet spot, and watch
the 3-D transfer orbit unfold.
"""

import datetime

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QLabel, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from .. import theme
from ..astro import bodies, porkchop, mission
from ..astro.core import fmt_date, julian_date
from ..views.orbital3d import Body, make_orbital_view
from ..views.mplchart import MplChart
from ..widgets import DatePicker, Panel, PlayBar, SliderRow, StatBox
from .base import PageBase


def _qdate_to_dt(qdate):
    py = qdate.toPython()
    return datetime.datetime(py.year, py.month, py.day)


class PorkchopPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Porkchop Plot",
            "The classic mission-planner's chart: which launch day and "
            "flight time cost the least rocket fuel?  Pick a window and "
            "read the contour map.",
            parent)
        self._plan = None
        self._tof_s = 0.0
        self._base_dt = 60.0
        self._grid = None

        self._build_controls()
        self._build_canvas()

        self._movie = QTimer(self)
        self._movie.setInterval(120)
        self._movie.timeout.connect(self._on_tick)
        self._movie.start()

    # ----------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Launch window")

        lay.addWidget(QLabel("Target body"))
        self.planet = QComboBox()
        self.planet.addItems(bodies.target_bodies())
        self.planet.currentTextChanged.connect(self._compute)
        lay.addWidget(self.planet)

        lay.addWidget(QLabel("Window start"))
        self.date_start = DatePicker()
        self.date_start.setDate(datetime.date(2026, 1, 1))
        lay.addWidget(self.date_start)

        lay.addWidget(QLabel("Window end"))
        self.date_end = DatePicker()
        self.date_end.setDate(datetime.date(2028, 1, 1))
        lay.addWidget(self.date_end)

        self.btn_compute = QPushButton("Compute porkchop")
        self.btn_compute.setProperty("primary", True)
        self.btn_compute.clicked.connect(self._compute)
        lay.addWidget(self.btn_compute)

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay.addWidget(self.playbar)

        lay.addWidget(QLabel("Flight progress"))
        from PySide6.QtWidgets import QSlider
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.valueChanged.connect(self._seek)
        lay.addWidget(self.progress)

        stats = Panel(title="Best window")
        self.st_c3 = StatBox("C3 (km2/s2)")
        self.st_dv = StatBox("delta-v (km/s)")
        self.st_tof = StatBox("TOF (days)")
        self.st_date = StatBox("optimal launch")
        for w in (self.st_c3, self.st_dv, self.st_tof, self.st_date):
            stats.layout_box.addWidget(w)
        self.controls.addWidget(stats)

        self.fact = self.fact_label(
            "A porkchop plot is how NASA chooses launch windows.  The "
            "colours show how much energy is needed - blue valleys are "
            "the cheap paths!")
        self.controls.addWidget(self.fact)

    def _build_canvas(self):
        self.view = make_orbital_view()
        self.view.dt = self._base_dt
        self.add_canvas(self.view)

        self.chart = MplChart(figsize=(6, 2.6))
        self.chart.axes.set_title("C3 contour (km2/s2)")
        self.chart.refresh()
        self.add_chart(self.chart)

    # ----------------------------------------------------------------- compute
    def _compute(self):
        jd0 = julian_date(_qdate_to_dt(self.date_start.date()))
        jd1 = julian_date(_qdate_to_dt(self.date_end.date()))
        planet = self.planet.currentText()

        self.status("computing porkchop grid...", "info")

        self._grid = porkchop.porkchop_grid(
            planet, jd0, jd1, 8.0, 120, 360, 8.0)

        bw = porkchop.best_window(self._grid)
        if bw is not None:
            jd_best, tof_best, c3, dv = bw
            self.st_c3.set_value("%.1f" % c3)
            self.st_dv.set_value("%.2f" % dv)
            self.st_tof.set_value("%d" % round(tof_best))
            self.st_date.set_value(fmt_date(jd_best))

            self._launch_plan(planet, jd_best, tof_best)

        self._draw_contour()

    def _launch_plan(self, planet, jd_launch, tof_days):
        import numpy as _np
        from ..astro.core import best_lambert
        from ..astro import transfer as _tr
        is_moon = planet == "Moon"
        mu = bodies.MU_EARTH if is_moon else bodies.MU_SUN

        if is_moon:
            r0 = _np.array([bodies.planet("Earth")["radius_km"] + 200.0,
                            0.0, 0.0], float)
            v_circ = _np.sqrt(bodies.MU_EARTH / _np.linalg.norm(r0))
            v_e = _np.array([0.0, v_circ, 0.0], float)
            jd_arr = jd_launch + tof_days
            r1, v_tgt = bodies.moon_geo_state(jd_arr)
        else:
            r0, v_e = bodies.state("Earth", jd_launch)
            r0 = _np.asarray(r0, float)
            v_e = _np.asarray(v_e, float)
            jd_arr = jd_launch + tof_days
            r1, v_tgt = bodies.state(planet, jd_arr)
        r1 = _np.asarray(r1, float)

        pair = best_lambert(mu, r0, r1, tof_days * 86400.0,
                            v_depart=v_e, v_arrival=v_tgt)
        if pair is None:
            self.status("no valid transfer for that point", "warn")
            self._plan = None
            return
        v0, v1 = pair

        from ..astro.kepler import elements_from_state
        el = elements_from_state(mu, r0, v0)

        class _Plan:
            pass
        p = _Plan()
        p.ok = True
        p.launch_jd = jd_launch
        p.tof_days = tof_days
        p.r0 = r0
        p.v_transfer0 = v0
        p.elements = el
        p.mu = mu
        self._plan = p
        self._tof_s = tof_days * 86400.0
        self._base_dt = self._tof_s / 1500.0
        self.view.dt = self._base_dt * self.playbar.speed.currentData()
        self._build_scene()
        self.status("transfer computed - press Play", "ok")

    def _draw_contour(self):
        if self._grid is None:
            return
        g = self._grid
        chart = self.chart
        chart.clear_plot()
        ax = chart.axes

        launch_dates = g["launch_jds"]
        tofs = g["tof_days"]
        X, Y = np.meshgrid(range(len(launch_dates)), tofs, indexing="ij")
        c3 = g["c3"]
        mask = g["valid"]

        c3_masked = np.where(mask, c3, np.nan)
        levels = np.nanpercentile(c3_masked[mask], [10, 25, 40, 55, 70, 85, 95]) if mask.any() else np.arange(5, 80, 8)
        cf = ax.contourf(X, Y, c3_masked, levels=levels, cmap="viridis",
                         alpha=0.85)
        cb = chart._fig.colorbar(cf, ax=ax, label="C3 (km2/s2)", shrink=0.9)
        cb.ax.tick_params(colors=chart.color_hex("text_mut"), labelsize=7)
        cb.set_label("C3 (km2/s2)", color=chart.color_hex("text_mut"),
                     fontsize=8)

        tick_pos = np.linspace(0, len(launch_dates) - 1, min(8, len(launch_dates))).astype(int)
        tick_labels = [fmt_date(launch_dates[i]) for i in tick_pos]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=7)
        ax.set_ylabel("Time of flight (days)")
        ax.set_title("C3 contour - Earth -> %s" % self.planet.currentText())
        chart.refresh()

    # ----------------------------------------------------------------- scene
    def _build_scene(self):
        if not self._plan or not self._plan.ok:
            return
        jd0 = self._plan.launch_jd
        planet = self.planet.currentText()
        is_moon = planet == "Moon"
        mu = self._plan.mu

        rec = bodies.planet(planet) if not is_moon else bodies.MOON
        radius = rec["radius_km"]
        color = bodies.planet(planet)["color"] if not is_moon else bodies.MOON["color"]

        paths = [
            dict(points=bodies.path("Earth", jd0 - 90.0, 320.0, n=240),
                 color=theme.C_EARTH, width=1.2),
        ]
        if not is_moon:
            paths.append(dict(points=bodies.path(planet, jd0 - 300.0, 760.0, n=320),
                              color=color, width=1.2))
        if self._plan.ok:
            n = 240
            pts = mission.trajectory_path(mu, self._plan.r0,
                                          self._plan.v_transfer0,
                                          n, self._tof_s)
            paths.append(dict(points=pts, color=theme.C_TRANSFER, width=2.2))

        def sun_pos(_t):
            return (0.0, 0.0, 0.0)

        bodies_ = [
            Body(sun_pos, 696340.0, theme.C_SUN, "Sun", glow=1.4),
            Body(lambda t: bodies.position("Earth", jd0 + t / 86400.0),
                 6371.0, theme.C_EARTH, "Earth"),
        ]
        if not is_moon:
            bodies_.append(Body(
                lambda t: bodies.position(planet, jd0 + t / 86400.0),
                radius, color, planet))
        else:
            bodies_.append(Body(
                lambda t: bodies.moon_geo_position(jd0 + t / 86400.0),
                radius, color, "Moon"))
        if self._plan.ok:
            bodies_.append(Body(self._probe_pos, 2400.0, theme.C_PROBE,
                                "Probe", line=True))

        self.view.set_scene(
            paths, bodies_, center=(0.0, 0.0),
            title="Earth -> %s transfer" % planet,
            subtitle="Porkchop-optimal trajectory",
            min_radius_km=(1.2 * 384400.0) if is_moon else 1.9 * bodies.AU)
        self.view.dt = self._base_dt * self.playbar.speed.currentData()

    def _probe_pos(self, t):
        if not self._plan or not self._plan.ok:
            return (0.0, 0.0, 0.0)
        if t > self._tof_s:
            t = self._tof_s
        return mission.trajectory_position(self._plan.mu,
                                           self._plan.r0,
                                           self._plan.v_transfer0, t)

    # ----------------------------------------------------------------- motion
    def _toggle_play(self, on):
        if on and self._plan and self._plan.ok:
            self.view.play(True)
        elif on:
            self.playbar.set_playing(False)

    def _seek(self, value):
        if self._plan and self._plan.ok:
            t = self._tof_s * value / 1000.0
            self.view.seek(t)

    def _on_tick(self):
        if not self._plan or not self._plan.ok:
            return
        t = self.view.t
        if t >= self._tof_s:
            self.view.play(False)
            self.playbar.set_playing(False)
            self.view.t = self._tof_s
            self.status("Transfer complete!", "ok")
        else:
            pct = int(100.0 * t / self._tof_s)
            self.status("%d%% of the way" % pct, "info")
            self.progress.blockSignals(True)
            self.progress.setValue(int(1000.0 * t / self._tof_s))
            self.progress.blockSignals(False)

    def _on_shown(self):
        self.view.update()

    def refresh_theme(self):
        super().refresh_theme()
        if self._plan is not None:
            self._build_scene()
        self.chart.refresh_theme()
        if self._grid is not None:
            self._draw_contour()
        self.view.update()
