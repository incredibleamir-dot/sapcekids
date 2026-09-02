"""Tab 8 - Transfer Study.

Compare Hohmann vs Lambert transfer costs: see how delta-v changes with
flight time, and watch the actual orbit geometry in 3D.  A cost-curve
chart sits below the PyVista view so the kid can match the numbers with
the shape of the trajectory.
"""

import datetime

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QLabel, QPushButton, QSlider)

from .. import theme
from ..astro import bodies, transfer
from ..astro.core import fmt_date, julian_date
from ..views.orbital3d import Body, make_orbital_view
from ..views.mplchart import MplChart
from ..widgets import DatePicker, Panel, PlayBar, SliderRow, StatBox
from .base import PageBase


def _qdate_to_dt(qdate):
    py = qdate.toPython()
    return datetime.datetime(py.year, py.month, py.day)


class TransferStudyPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Transfer Study",
            "How much fuel does it cost to fly to another planet?  Compare "
            "the textbook Hohmann transfer with real Lambert solutions and "
            "see how the numbers and the orbit shape change together.",
            parent)
        self._hoh = None
        self._plan = None
        self._tof_s = 0.0
        self._base_dt = 60.0
        self._dv_data = None

        self._build_controls()
        self._build_canvas()

        self._movie = QTimer(self)
        self._movie.setInterval(120)
        self._movie.timeout.connect(self._on_tick)
        self._movie.start()

    # ----------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Transfer setup")

        lay.addWidget(QLabel("Target body"))
        self.planet = QComboBox()
        self.planet.addItems(bodies.target_bodies())
        self.planet.currentTextChanged.connect(self._recompute)
        lay.addWidget(self.planet)

        lay.addWidget(QLabel("Launch day"))
        self.date = DatePicker()
        self.date.setDate(datetime.date(2026, 7, 1))
        self.date.dateChanged.connect(lambda _d: self._recompute())
        lay.addWidget(self.date)

        self.btn = QPushButton("Compute transfer")
        self.btn.setProperty("primary", True)
        self.btn.clicked.connect(self._recompute)
        lay.addWidget(self.btn)

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay.addWidget(self.playbar)

        lay.addWidget(QLabel("Flight progress"))
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.valueChanged.connect(self._seek)
        lay.addWidget(self.progress)

        stats = Panel(title="Hohmann baseline")
        self.st_hoh_tof = StatBox("Hohmann TOF")
        self.st_hoh_dv = StatBox("Hohmann dv")
        self.st_lam_dv = StatBox("Lambert dv")
        self.st_c3 = StatBox("C3")
        for w in (self.st_hoh_tof, self.st_hoh_dv, self.st_lam_dv, self.st_c3):
            stats.layout_box.addWidget(w)
        self.controls.addWidget(stats)

        exp = Panel(title="Experiment lab")
        self.s_tof = SliderRow("Days in flight", 120, 400, 260, step=10,
                               suffix=" d")
        self.s_tof.valueChanged.connect(self._on_tof_change)
        exp.layout_box.addWidget(self.s_tof)
        self.controls.addWidget(exp)

        self.fact = self.fact_label(
            "Hohmann transfers are the cheapest path between circular orbits, "
            "but real planets aren't on perfect circles - Lambert's math "
            "finds the true cost!")
        self.controls.addWidget(self.fact)

    def _build_canvas(self):
        self.view = make_orbital_view()
        self.view.dt = self._base_dt
        self.add_canvas(self.view)

        self.chart = MplChart(figsize=(6, 2.6))
        self.chart.axes.set_title("delta-v vs flight time")
        self.chart.refresh()
        self.add_chart(self.chart)

    # ----------------------------------------------------------------- math
    def _recompute(self):
        planet = self.planet.currentText()
        jd_launch = julian_date(_qdate_to_dt(self.date.date()))
        is_moon = planet == "Moon"

        if is_moon:
            hoh = transfer.moon_hohmann()
        else:
            hoh = transfer.hohmann_circular(bodies.MU_SUN, bodies.AU,
                                            bodies.planet(planet)["a_au"] * bodies.AU)
        self._hoh = hoh
        self.st_hoh_tof.set_value("%.0f d" % hoh.tof_days)
        self.st_hoh_dv.set_value("%.2f km/s" % hoh.dv_total)

        gap = (0.5 if is_moon else 8.0)
        tmin = (1.0 if is_moon else 120.0)
        tmax = (10.0 if is_moon else 360.0)
        self._dv_data = transfer.dv_vs_tof(planet, jd_launch, tmin, tmax, gap)
        self._draw_cost_curve()
        self.s_tof.set_range(tmin, tmax, step=max(0.5, gap), suffix=" d")

        tof = self.s_tof.value()
        self._compute_transfer(planet, jd_launch, tof)

    def _compute_transfer(self, planet, jd_launch, tof_days):
        jd0 = jd_launch
        is_moon = planet == "Moon"
        mu = bodies.MU_EARTH if is_moon else bodies.MU_SUN

        if is_moon:
            r_leo = bodies.planet("Earth")["radius_km"] + 200.0
            v_circ = np.sqrt(bodies.MU_EARTH / r_leo)
            r0 = np.array([r_leo, 0.0, 0.0], float)
            v_e = np.array([0.0, v_circ, 0.0], float)
        else:
            r0, v_e = bodies.state("Earth", jd0)
            r0 = np.asarray(r0, float)
            v_e = np.asarray(v_e, float)
        tof_s = float(tof_days) * 86400.0

        from ..astro.core import best_lambert
        jd_arr = jd0 + tof_days
        if is_moon:
            r1, v_m = bodies.moon_geo_state(jd_arr)
        else:
            r1, v_m = bodies.state(planet, jd_arr)
        r1 = np.asarray(r1, float)
        v_m = np.asarray(v_m, float)

        pair = best_lambert(mu, r0, r1, tof_s,
                            v_depart=v_e, v_arrival=v_m)
        if pair is None:
            self.status("no Lambert solution for that flight time", "warn")
            return
        v0, v1 = pair
        dv_dep = float(np.linalg.norm(v0 - v_e))
        dv_arr = float(np.linalg.norm(v_m - v1))
        c3 = dv_dep ** 2

        self.st_lam_dv.set_value("%.2f km/s" % (dv_dep + dv_arr))
        self.st_c3.set_value("%.1f km2/s2" % c3)

        from ..astro.kepler import elements_from_state
        el = elements_from_state(mu, r0, v0)

        class _Plan:
            pass
        p = _Plan()
        p.ok = True
        p.launch_jd = jd0
        p.tof_days = tof_days
        p.r0 = r0
        p.v_transfer0 = v0
        p.elements = el
        p.mu = mu
        self._plan = p
        self._tof_s = tof_s
        self._base_dt = tof_s / 1500.0
        self.view.dt = self._base_dt * self.playbar.speed.currentData()
        self._build_scene()
        self.status("press Play to animate the transfer", "ok")

    def _on_tof_change(self, _v):
        planet = self.planet.currentText()
        jd_launch = julian_date(_qdate_to_dt(self.date.date()))
        self._compute_transfer(planet, jd_launch, self.s_tof.value())

    # ---------------------------------------------------------------- chart
    def _draw_cost_curve(self):
        if self._dv_data is None:
            return
        d = self._dv_data
        chart = self.chart
        chart.clear_plot()
        ax = chart.axes

        valid = np.isfinite(d["dv_total"])
        ax.plot(d["tof_days"][valid], d["dv_total"][valid],
                color=chart.color("accent"), linewidth=1.8, label="dv total")
        ax.plot(d["tof_days"][valid], d["dv_depart"][valid],
                color=chart.color("ok"), linewidth=1.2, linestyle="--",
                label="dv depart")
        ax.plot(d["tof_days"][valid], d["dv_arrive"][valid],
                color=chart.color("warn"), linewidth=1.2, linestyle=":",
                label="dv arrive")

        if self._hoh:
            ax.axhline(self._hoh.dv_total, color=chart.color("err"),
                        linewidth=1.0, linestyle="--", alpha=0.7,
                        label="Hohmann baseline")

        ax.set_xlabel("Time of flight (days)")
        ax.set_ylabel("delta-v (km/s)")
        ax.set_title("Earth -> %s  -  delta-v vs flight time"
                      % self.planet.currentText())
        ax.legend(fontsize=7, framealpha=0.7,
                  facecolor=chart.color_hex("panel"),
                  edgecolor=chart.color_hex("border"),
                  labelcolor=chart.color_hex("text"))
        chart.refresh()

    # ----------------------------------------------------------------- scene
    def _build_scene(self):
        if not self._plan or not self._plan.ok:
            return
        jd0 = self._plan.launch_jd
        planet = self.planet.currentText()
        is_moon = planet == "Moon"
        mu = self._plan.mu
        n = 300

        path_pts, earth_pts, target_pts, info = transfer.transfer_orbit_path(
            planet, datetime.datetime(1858, 11, 17) + datetime.timedelta(
                days=jd0 - 2400000.5), self._plan.tof_days, n)

        if is_moon:
            rec = bodies.MOON
            color = bodies.MOON["color"]
        else:
            rec = bodies.planet(planet)
            color = rec["color"]

        paths = [
            dict(points=earth_pts, color=theme.C_EARTH, width=1.2),
            dict(points=target_pts, color=color, width=1.2),
            dict(points=path_pts, color=theme.C_TRANSFER, width=2.2),
        ]

        def sun_pos(_t):
            return (0.0, 0.0, 0.0)

        def earth_pos(t):
            jd = jd0 + t / 86400.0
            return tuple(bodies.position("Earth", jd))

        def target_pos(t):
            jd = jd0 + t / 86400.0
            if is_moon:
                return tuple(bodies.moon_geo_position(jd))
            return tuple(bodies.position(planet, jd))

        def probe_pos(t):
            if t > self._tof_s:
                t = self._tof_s
            from ..astro.kepler import integrate_state
            return tuple(integrate_state(
                mu,
                np.asarray(self._plan.r0, dtype=float),
                np.asarray(self._plan.v_transfer0, dtype=float),
                np.array([t]))[0])

        bodies_ = [
            Body(sun_pos, 696340.0, theme.C_SUN, "Sun", glow=1.4),
            Body(earth_pos, 6371.0, theme.C_EARTH, "Earth"),
            Body(target_pos, rec["radius_km"], color, planet),
            Body(probe_pos, 2400.0, theme.C_PROBE, "Probe", line=True),
        ]

        self.view.set_scene(
            paths, bodies_, center=(0.0, 0.0),
            title="Transfer orbit to %s" % planet,
            subtitle="%d-day Lambert transfer" % round(self._plan.tof_days),
            min_radius_km=(1.2 * 384400.0) if is_moon else 1.9 * bodies.AU)
        self.view.dt = self._base_dt * self.playbar.speed.currentData()

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
        if self._plan is not None and self._plan.ok:
            self._build_scene()
        self.chart.refresh_theme()
        if self._dv_data is not None:
            self._draw_cost_curve()
        self.view.update()
