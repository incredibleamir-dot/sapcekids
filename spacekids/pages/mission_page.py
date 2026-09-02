"""Tab 1 - Rocket to Mars.

The kid picks a launch day.  poliastro (Izzo Lambert) figures out the rocket
burns needed to reach Mars on a Hohmann-style transfer, and the scene plays
the flight.  Some days are wildly expensive (Mars is on the wrong side of the
Sun), which is the whole point: real launch windows!
"""

import datetime

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QSlider

from .. import theme
from ..astro import bodies, mission
from ..astro.core import fmt_date
from ..views.orbital3d import Body, make_orbital_view
from ..widgets import DatePicker, Panel, PlayBar, SliderRow, StatBox
from .base import PageBase


class MissionPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Rocket to Mars",
            "Pick a launch day and light the engines. Watch the probe coast "
            "along a Hohmann transfer to the Red Planet.",
            parent)
        self._plan = None
        self._best = None
        self._tof_s = 0.0
        self._base_dt = 60.0

        self._build_controls()
        self._build_canvas()

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

    # --------------------------------------------------------------- ui
    def _build_controls(self):
        box, lay = self.add_group("Launch pad")

        lay.addWidget(QLabel("Launch day"))
        self.date = DatePicker()
        self.date.setDateRange(datetime.date.today().replace(year=2006),
                               datetime.date.today().replace(year=2032))
        self.date.setDate(datetime.date.today())
        lay.addWidget(self.date)

        self.btn_plan = QPushButton("Plan the mission")
        self.btn_plan.setProperty("primary", True)
        self.btn_plan.clicked.connect(self.replan)
        lay.addWidget(self.btn_plan)

        self.playbar = PlayBar()
        self.playbar.playToggled.connect(self._toggle_play)
        lay.addWidget(self.playbar)

        lay.addWidget(QLabel("Flight progress"))
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.valueChanged.connect(self._seek)
        lay.addWidget(self.progress)

        exp = Panel(title="Experiment lab")
        self.s_exp = SliderRow("Time of flight (TOF)", 160, 351, 260, step=8,
                               suffix=" d")
        self.s_exp.valueChanged.connect(self._on_exp)
        b_exp = QPushButton("Best window")
        b_exp.clicked.connect(self.replan)
        exp.layout_box.addWidget(self.s_exp)
        exp.layout_box.addWidget(b_exp)
        self.controls.addWidget(exp)

        stats = Panel(title="Mission report")
        self.st_days = StatBox("TOF (days)")
        self.st_dv = StatBox("delta-v \u0394v (km/s)")
        self.st_arr = StatBox("arrival")
        self.st_best = StatBox("best launch day in this window")
        for w in (self.st_days, self.st_dv, self.st_arr, self.st_best):
            stats.layout_box.addWidget(w)
        self.controls.addWidget(stats)

        self.fact = self.fact_label(
            "Fact: returning from Mars needs a heavy, fancy rocket. That is "
            "why sample-return missions are so hard!")
        self.controls.addWidget(self.fact)

    def _build_canvas(self):
        self.view = make_orbital_view()
        self.view.dt = self._base_dt
        self.add_canvas(self.view)

    # --------------------------------------------------------------- actions
    def _toggle_play(self, on):
        if on and self._plan and self._plan.ok:
            self.view.play(True)
        elif on:
            self.playbar.set_playing(False)

    def _launch_dt(self):
        launch = self.date.date().toPython()
        return datetime.datetime(launch.year, launch.month, launch.day)

    def replan(self):
        chosen, best = mission.plan_mission(self._launch_dt())
        self._best = best
        if chosen.ok and chosen.tof_days > 0:
            self.s_exp.blockSignals(True)
            self.s_exp.set_value(chosen.tof_days)
            self.s_exp.blockSignals(False)
        self._apply_plan(chosen)

    def _apply_plan(self, plan, mode="best"):
        self._plan = plan
        self.view.play(False)
        self.playbar.set_playing(False)
        self.view.t = 0.0
        self.progress.blockSignals(True)
        self.progress.setValue(0)
        self.progress.blockSignals(False)

        if not plan.ok:
            self.status("geometry trouble - try another launch day", "err")
            for w in (self.st_days, self.st_dv, self.st_arr, self.st_best):
                w.set_value("--")
            return

        self._tof_s = plan.tof_days * 86400.0
        self._base_dt = self._tof_s / 1500.0
        self.view.dt = self._base_dt * self.playbar.speed.currentData()
        self._build_scene()

        self.st_days.set_value("%d" % round(plan.tof_days))
        self.st_dv.set_value("%.2f" % plan.dv_total)
        self.st_arr.set_value(fmt_date(plan.arrival_jd))
        if self._best and self._best.ok:
            self.st_best.set_value(fmt_date(self._best.launch_jd))

        if plan.dv_total < 7.0:
            word, kind = "Good window - low \u0394v. Mars is close!", "ok"
        elif plan.dv_total < 13.0:
            word, kind = "High \u0394v - it will take a big rocket!", "warn"
        else:
            word = "Mars is far away today"
            if self._best and self._best.ok \
                    and self._best.dv_total < plan.dv_total:
                word += " - the window near %s is easier (%.1f km/s)" % (
                    fmt_date(self._best.launch_jd), self._best.dv_total)
            kind = "err"

        if mode == "exp":
            self.status(
                "experiment: %d days TOF needs %.1f km/s \u0394v"
                % (round(plan.tof_days), plan.dv_total), kind)
        else:
            self.status(word, kind)
        self.view.play(True)
        self.playbar.set_playing(True)

    def _on_exp(self, _value):
        self._exp_timer.start()

    def _run_experiment(self):
        plan = mission.plan_at_tof(self._launch_dt(), self.s_exp.value())
        self._apply_plan(plan, mode="exp")

    def _build_scene(self):
        jd0 = self._plan.launch_jd

        paths = [
            dict(points=bodies.path("Earth", jd0 - 90.0, 320.0, n=240),
                 color=theme.C_EARTH, width=1.2),
            dict(points=bodies.path("Mars", jd0 - 300.0, 760.0, n=320),
                 color=theme.C_MARS, width=1.2),
        ]
        if self._plan.ok:
            n = 240
            pts = mission.trajectory_path(self._plan.elements["k"],
                                          self._plan.r0, self._plan.v_transfer0,
                                          n, self._tof_s)
            paths.append(dict(points=pts, color=theme.C_TRANSFER, width=2.2,
                              style=1))

        def sun_pos(_t):
            return (0.0, 0.0, 0.0)

        bodies_ = [
            Body(sun_pos, 696340.0, theme.C_SUN, "Sun", glow=1.4),
            Body(lambda t: bodies.position("Earth", jd0 + t / 86400.0),
                 6371.0, theme.C_EARTH, "Earth"),
            Body(lambda t: bodies.position("Mars", jd0 + t / 86400.0),
                 3390.0, theme.C_MARS, "Mars"),
        ]
        if self._plan.ok:
            bodies_.append(Body(self._probe_pos, 2400.0, theme.C_PROBE,
                                "Probe", line=True))

        self.view.set_scene(
            paths, bodies_, center=(0.0, 0.0),
            title="Earth -> Mars transfer",
            subtitle="shown from above the solar system (not to scale)",
            min_radius_km=1.9 * bodies.AU)
        self.view.dt = self._base_dt * self.playbar.speed.currentData()

    def _probe_pos(self, t):
        if not self._plan or not self._plan.ok:
            return (0.0, 0.0, 0.0)
        if t > self._tof_s:
            t = self._tof_s
        return mission.trajectory_position(self._plan.elements["k"],
                                           self._plan.r0, self._plan.v_transfer0,
                                           t)

    def _seek(self, value):
        if self._plan and self._plan.ok:
            t = self._tof_s * value / 1000.0
            self.view.seek(t)
            self._refresh_trail(t)

    # --------------------------------------------------------------- movie
    def _refresh_trail(self, t):
        """Rebuild the travelled arc as a dense curve so it never looks
        like a straight slingshot between probe samples."""
        keep = [p for p in self.view.paths if p.get("name") != "trail"]
        if t > 0 and self._plan and self._plan.ok:
            from ..astro.kepler import integrate_state
            k = self._plan.elements["k"]
            ts = np.linspace(0.0, min(t, self._tof_s), 90)
            pts = integrate_state(k, np.asarray(self._plan.r0, dtype=float),
                                  np.asarray(self._plan.v_transfer0, dtype=float),
                                  ts)
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
            self.status("Congratulations - you reached Mars!", "ok")
        else:
            pct = int(100.0 * t / self._tof_s)
            self.status("%d%% of the way to Mars" % pct, "info")
            self.progress.blockSignals(True)
            self.progress.setValue(int(1000.0 * t / self._tof_s))
            self.progress.blockSignals(False)

        self._refresh_trail(t)
        self.view.update()

    def _shut(self):
        self._movie.stop()

    def _on_shown(self):
        self.view.update()

    def refresh_theme(self):
        super().refresh_theme()
        if self._plan is not None:
            self._build_scene()
            self._refresh_trail(self.view.t)
        else:
            self.view.update()