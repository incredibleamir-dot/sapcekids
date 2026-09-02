"""Tab 3 - Catch the Asteroid.

Choose a real near-Earth asteroid, pick a launch day, and let poliastro's
Izzo Lambert solver design the interception.  Watch the probe swing out,
meet the rock, and (hopefully) arrive with enough rocket power to spare -
a tiny taste of what the DART mission did for real.
"""

import datetime

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QSlider

from .. import theme
from ..astro import asteroids, bodies
from ..astro.core import fmt_date, julian_date
from ..views.orbital3d import Body, make_orbital_view
from ..widgets import DatePicker, Panel, PlayBar, SliderRow, StatBox
from .base import PageBase


class AsteroidPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Catch the Asteroid",
            "A real space rock is on its way past Earth. Plan a rocket's "
            "flight so it meets the asteroid head-on - just like NASA's DART "
            "mission.",
            parent)
        self._plan = None
        self._tof_s = 0.0
        self._base_dt = 60.0
        self._name = asteroids.asteroid_names()[1]

        self._build_controls()
        self._build_canvas()
        self.replan()

        self._movie = QTimer(self)
        self._movie.setInterval(120)
        self._movie.timeout.connect(self._on_movie_tick)
        self._movie.start()

        self._exp_timer = QTimer(self)
        self._exp_timer.setSingleShot(True)
        self._exp_timer.setInterval(220)
        self._exp_timer.timeout.connect(self._run_experiment)

        self._date_timer = QTimer(self)
        self._date_timer.setSingleShot(True)
        self._date_timer.setInterval(400)
        self._date_timer.timeout.connect(self.replan)
        self.date.dateChanged.connect(lambda _d: self._date_timer.start())

    # ----------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Mission control")

        lay.addWidget(QLabel("Which asteroid?"))
        self.combo = QComboBox()
        self.combo.addItems(asteroids.asteroid_names())
        self.combo.setCurrentText(self._name)
        self.combo.currentTextChanged.connect(self._on_asteroid)
        lay.addWidget(self.combo)

        lay.addWidget(QLabel("Launch day"))
        self.date = DatePicker()
        self.date.setDateRange(datetime.date.today().replace(year=2006),
                               datetime.date.today().replace(year=2032))
        self.date.setDate(datetime.date.today())
        lay.addWidget(self.date)

        self.btn = QPushButton("Plan the interception")
        self.btn.setProperty("primary", True)
        self.btn.clicked.connect(self.replan)
        lay.addWidget(self.btn)

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay.addWidget(self.playbar)

        lay.addWidget(QLabel("Flight progress"))
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.valueChanged.connect(self._seek)
        lay.addWidget(self.progress)

        stats = Panel(title="Defence brief")
        self.st_tof = StatBox("TOF (days)")
        self.st_dv = StatBox("delta-v \u0394v (km/s)")
        self.st_arr = StatBox("intercepted on")
        self.st_dia = StatBox("asteroid size")
        for w in (self.st_tof, self.st_dv, self.st_arr, self.st_dia):
            stats.layout_box.addWidget(w)
        self.controls.addWidget(stats)

        exp = Panel(title="Experiment lab")
        self.s_exp = SliderRow("Time of flight (TOF)", 40, 400, 220, step=10,
                               suffix=" d")
        self.s_exp.valueChanged.connect(self._on_exp)
        b_exp = QPushButton("Best plan")
        b_exp.clicked.connect(self.replan)
        exp.layout_box.addWidget(self.s_exp)
        exp.layout_box.addWidget(b_exp)
        self.controls.addWidget(exp)

        self.fact = self.fact_label("")
        self.controls.addWidget(self.fact)
        self._refresh_fact()

    def _build_canvas(self):
        self.view = make_orbital_view()
        self.view.dt = self._base_dt
        self.add_canvas(self.view)

    # ----------------------------------------------------------------- plans
    def _on_asteroid(self, name):
        self._name = name
        self._refresh_fact()
        self.replan()

    def _refresh_fact(self):
        self.fact.setText("Fact: " + asteroids.asteroid_fact(self._name))

    def _launch_dt(self):
        launch = self.date.date().toPython()
        return datetime.datetime(launch.year, launch.month, launch.day)

    def replan(self):
        launch = self._launch_dt()
        jd0 = julian_date(launch)
        plan = asteroids.best_intercept(self._name, jd0)
        if (hasattr(self, "s_exp") and plan is not None
                and plan.ok and plan.tof_days > 0):
            self.s_exp.blockSignals(True)
            self.s_exp.set_value(plan.tof_days)
            self.s_exp.blockSignals(False)
        self._apply_plan(plan)

    def _apply_plan(self, plan, mode="best"):
        self._plan = plan
        self.view.play(False)
        self.playbar.set_playing(False)
        self.view.t = 0.0
        self.progress.blockSignals(True)
        self.progress.setValue(0)
        self.progress.blockSignals(False)

        if plan is None or not plan.ok:
            self.status("no sane transfer for that flight time", "err")
            for w in (self.st_tof, self.st_dv, self.st_arr, self.st_dia):
                w.set_value("--")
            return
        rec = asteroids._ASTEROIDS[self._name]
        self.st_dia.set_value("%.2f km" % rec["diameter_km"])

        self._tof_s = plan.tof_days * 86400.0
        self._base_dt = self._tof_s / 1400.0
        self._build_scene()

        self.st_tof.set_value("%.f" % round(plan.tof_days))
        self.st_dv.set_value("%.2f" % plan.dv_total)
        self.st_arr.set_value(fmt_date(plan.arrival_jd))

        kind = "err" if plan.dv_total > 18.0 else \
            ("warn" if plan.dv_total >= 9.0 else "ok")
        if mode == "exp":
            self.status(
                "experiment: %d days TOF needs %.1f km/s \u0394v (%s)"
                % (round(plan.tof_days), plan.dv_total, plan.result_word()),
                kind)
        else:
            self.status(plan.result_word(), kind)
        self.view.play(True)
        self.playbar.set_playing(True)

    def _on_exp(self, _value):
        self._exp_timer.start()

    def _run_experiment(self):
        plan = asteroids.intercept_at(
            self._name, julian_date(self._launch_dt()), self.s_exp.value())
        self._apply_plan(plan, mode="exp")

    def _build_scene(self):
        plan = self._plan
        jd0 = plan.launch_jd

        n = 260
        transfer = asteroids.intercept_trajectory_path(
            plan.elements["k"], plan.r0, plan.v0, n, self._tof_s)

        paths = [
            dict(points=bodies.path("Earth", jd0 - 120.0, 260.0, n=220),
                 color=theme.C_EARTH, width=1.2),
            dict(points=asteroids.asteroid_path(
                self._name, jd0 - 150.0, 640.0, n=320),
                 color=theme.C_ASTEROID, width=1.4, style=1),
            dict(points=transfer, color=theme.C_TRANSFER, width=2.2, style=1),
        ]

        def probe_pos(t):
            if t > self._tof_s:
                t = self._tof_s
            return asteroids.intercept_trajectory_position(
                plan.elements["k"], plan.r0, plan.v0, t)

        blobs = [
            Body(lambda _t: (0.0, 0.0, 0.0), 696340.0, theme.C_SUN, "Sun",
                 glow=1.2),
            Body(lambda t: bodies.position("Earth", jd0 + t / 86400.0),
                 6371.0, theme.C_EARTH, "Earth"),
            Body(lambda t: asteroids.asteroid_position(
                self._name, jd0 + t / 86400.0),
                700.0, theme.C_ASTEROID, self._name),
            Body(probe_pos, 1500.0, theme.C_PROBE, "Probe", line=True),
        ]

        self.view.set_scene(
            paths, blobs, center=(0.0, 0.0),
            title="Interceptor vs %s" % self._name,
            subtitle="Sun-centred view; dashed line is the rocket's path",
            min_radius_km=1.7 * bodies.AU)
        self.view.dt = self._base_dt * self.playbar.speed.currentData()

    # ---------------------------------------------------------------- motion
    def _toggle_play(self, on):
        if on and self._plan and self._plan.ok:
            self.view.play(True)
        else:
            self.playbar.set_playing(False)

    def _seek(self, value):
        if self._plan and self._plan.ok:
            t = self._tof_s * value / 1000.0
            self.view.seek(t)
            self._refresh_trail(t)

    # ------------------------------------------------------------ movie
    def _refresh_trail(self, t):
        """Rebuild the travelled arc as a dense curve so it never looks
        like a straight slingshot between probe samples."""
        keep = [p for p in self.view.paths if p.get("name") != "trail"]
        if t > 0 and self._plan and self._plan.ok:
            from ..astro.kepler import integrate_state
            k = self._plan.elements["k"]
            ts = np.linspace(0.0, min(t, self._tof_s), 90)
            pts = integrate_state(k, np.asarray(self._plan.r0, dtype=float),
                                  np.asarray(self._plan.v0, dtype=float), ts)
            keep.append(dict(points=pts, color=theme.C_TRAIL, width=1.4,
                             name="trail"))
        self.view.set_paths(keep)

    def _on_movie_tick(self):
        if not self._plan or not self._plan.ok:
            return
        t = self.view.t
        if t >= self._tof_s:
            self.view.play(False)
            self.playbar.set_playing(False)
            self.view.t = self._tof_s
            t = self._tof_s
            self.status("Direct hit! You caught %s!" % self._name, "ok")
        else:
            pct = int(100.0 * t / self._tof_s)
            self.status("%d%% of the way to %s" % (pct, self._name), "info")
            self.progress.blockSignals(True)
            self.progress.setValue(int(1000.0 * t / self._tof_s))
            self.progress.blockSignals(False)

        self._refresh_trail(t)
        self.view.update()

    def _on_shown(self):
        self.view.update()

    def refresh_theme(self):
        super().refresh_theme()
        if self._plan is not None:
            self._build_scene()
            self._refresh_trail(self.view.t)
        else:
            self.view.update()