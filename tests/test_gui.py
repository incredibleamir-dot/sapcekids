"""GUI / widget edge cases: reusable controls, the two canvas views' zoom +
pan invariants, the six pages, and the main window (theme switching, places).

Runs entirely on Qt's offscreen platform; the live ISS TLE fetch is stubbed.
"""

import datetime
import os
import sys
import unittest
from unittest import mock

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    from tests.helpers import (get_app, isolated_env, no_network, pump,
                               shut_window, make_mouse)
except ImportError:
    from helpers import (get_app, isolated_env, no_network, pump,
                         shut_window, make_mouse)

from PySide6.QtCore import QDate, QEvent, QPointF, QPoint, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent  # noqa: F401
from PySide6.QtWidgets import QDialog, QVBoxLayout

from spacekids import theme
from spacekids import settings as settings_store
from spacekids.geo import locations
from spacekids.views.spaceview import SpaceView, Body
from spacekids.geo.mapview import MapView
from spacekids.widgets import (DatePicker, HLine, Panel, PlayBar, SliderRow,
                               StatBox, pill, section_label, prompt_add_place)


class TestWidgets(unittest.TestCase):
    def setUp(self):
        get_app()

    # ---------------------------------------------------------- SliderRow
    def test_slider_row_value_and_clamp(self):
        row = SliderRow("Fuel", 0.0, 100.0, 50.0, step=1.0, suffix=" %")
        seen = []
        row.valueChanged.connect(seen.append)
        self.assertEqual(row.value(), 50.0)
        row.set_value(120.0)          # above max
        self.assertEqual(row.value(), 100.0)
        row.set_value(-20.0)          # below min
        self.assertEqual(row.value(), 0.0)
        self.assertTrue(seen)

    def test_slider_row_steps(self):
        row = SliderRow("x", 0.0, 1.0, 0.5, step=0.25)
        self.assertEqual(row.value(), 0.5)
        row.set_value(0.62)            # rounds to nearest step (0.5 or 0.75)
        self.assertIn(row.value(), (0.5, 0.75))

    def test_slider_row_decimals_and_fmt(self):
        row = SliderRow("x", 0.0, 10.0, 2.5, step=0.5, decimals=1, suffix=" k")
        self.assertEqual(row._val.text()[-2:], " k")  # value renders with suffix
        fmt = SliderRow("y", 0.0, 10.0, 1.0, step=1.0,
                        fmt=lambda v: "=%.0f!" % v)
        self.assertEqual(fmt._val.text(), "=1!")

    def test_slider_row_refresh_theme(self):
        row = SliderRow("t", 0, 10, 5)
        old = row._val.styleSheet()
        theme.set_active("Moonlight", persist=False)
        row.refresh_theme()
        self.assertIn(theme.MONO, row._val.styleSheet())
        theme.set_active("Space Night", persist=False)
        self.assertNotEqual(old, row._val.styleSheet())

    # ---------------------------------------------------------- PlayBar
    def test_playbar_speeds(self):
        bar = PlayBar()
        self.assertEqual(bar.speed.count(), 5)
        self.assertEqual([bar.speed.itemData(i) for i in range(5)],
                         [1.0, 2.0, 5.0, 10.0, 30.0])
        bar.set_playing(True)
        self.assertTrue(bar._play_btn.isChecked())
        bar.set_playing(False)
        self.assertFalse(bar._play_btn.isChecked())

    def test_playbar_default_from_settings(self):
        with isolated_env():
            settings_store.set("playback", 3)
            bar = PlayBar()
            self.assertEqual(bar.speed.currentIndex(), 3)

    # ---------------------------------------------------------- DatePicker
    def test_datepicker_initial_and_signal(self):
        dp = DatePicker(initial=datetime.date(2026, 1, 5))
        self.assertEqual(dp.date(), QDate(2026, 1, 5))
        seen = []
        dp.dateChanged.connect(seen.append)
        dp.setDate(QDate(2026, 2, 1))
        self.assertEqual(dp.date(), QDate(2026, 2, 1))
        self.assertTrue(seen)

    def test_datepicker_clamps(self):
        today = QDate.currentDate()
        lo = today.addDays(-3)
        hi = today.addDays(+3)
        dp = DatePicker(minimum=lo, maximum=hi)
        dp.setDate(today.addDays(-99))      # below range
        self.assertEqual(dp.date(), lo)
        dp.setDate(today.addDays(+99))      # above range
        self.assertEqual(dp.date(), hi)

    def test_datepicker_set_range_clamps_current(self):
        today = QDate.currentDate()
        dp = DatePicker(initial=today.addDays(-10))
        dp.setDateRange(today, today.addDays(10))
        self.assertEqual(dp.date(), today)

    def test_datepicker_today_clamped(self):
        today = QDate.currentDate()
        future = today.addDays(5)
        dp = DatePicker(minimum=future, maximum=future.addDays(10))
        dp._go_today()
        self.assertEqual(dp.date(), future)

    def test_datepicker_config(self):
        dp = DatePicker()
        self.assertTrue(112 <= dp._field.width() <= 150)
        self.assertTrue(dp.width() <= 280)

    # ---------------------------------------------------------- misc widgets
    def test_panel_hline_statbox(self):
        p = Panel(title="Stats")
        self.assertIsInstance(p.layout_box, QVBoxLayout)
        sb = StatBox("speed")
        sb.set_value("7.6 km/s")
        self.assertEqual(sb._val.text(), "7.6 km/s")
        HLine().refresh_theme()   # must not raise
        p.refresh_theme()         # must not raise
        pill("ready", "ok")
        lbl = section_label("ABOUT")
        self.assertTrue(lbl.property("section"))

    def test_prompt_add_place_cancel(self):
        with mock.patch.object(QDialog, "exec", return_value=QDialog.Rejected):
            self.assertIsNone(prompt_add_place())

    def test_prompt_add_place_empty_accept(self):
        with mock.patch.object(QDialog, "exec", return_value=QDialog.Accepted):
            self.assertIsNone(prompt_add_place())


class TestMapView(unittest.TestCase):
    SPACE_AFTER = None

    def setUp(self):
        a = get_app()
        self.m = MapView()
        self.m.resize(500, 300)

    def tearDown(self):
        self.m.deleteLater()

    def test_zoom_anchor_preserves_point(self):
        box = self.m._inner_rect(500, 300)
        anchor = QPointF(120.0, 80.0)
        lon = (anchor.x() - box.x()) / box.width() * 360.0 - 180.0
        lat = 90.0 - (anchor.y() - box.y()) / box.height() * 180.0
        self.m._set_zoom(2.0, anchor=anchor)
        self.assertAlmostEqual(self.m._zoom, 2.0, places=6)
        new = self.m._inner_rect(500, 300)
        x, y = self.m._geo(lat, lon, new)
        self.assertAlmostEqual(x, anchor.x(), places=4)
        self.assertAlmostEqual(y, anchor.y(), places=4)

    def test_zoom_bounds_and_reset(self):
        self.m._set_zoom(1e9)
        self.assertEqual(self.m._zoom, self.m._zoom_bounds[1])
        self.m._set_zoom(1e-9)
        self.assertEqual(self.m._zoom, self.m._zoom_bounds[0])
        self.m.zoom_reset()
        self.assertEqual(self.m._zoom, 1.0)
        self.assertEqual(self.m._pan.x(), 0.0)
        self.assertEqual(self.m._pan.y(), 0.0)

    def test_wheel_zoom(self):
        before = self.m._zoom
        ev = QWheelEvent(QPointF(250, 150), QPointF(250, 150), QPoint(0, 0),
                         QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                         Qt.NoScrollPhase, False)
        self.m.wheelEvent(ev)
        self.assertTrue(ev.isAccepted())
        self.assertGreater(self.m._zoom, before)

    def test_wheel_horizontal_ignored(self):
        ev = QWheelEvent(QPointF(250, 150), QPointF(250, 150), QPoint(120, 0),
                         QPoint(120, 0), Qt.NoButton, Qt.NoModifier,
                         Qt.NoScrollPhase, False)
        self.m.wheelEvent(ev)
        self.assertFalse(ev.isAccepted())

    def test_key_zoom(self):
        self.m.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Plus,
                                       Qt.NoModifier))
        self.assertGreater(self.m._zoom, 1.0)
        self.m.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_0,
                                       Qt.NoModifier))
        self.assertEqual(self.m._zoom, 1.0)

    def test_drag_pan(self):
        self.m.mousePressEvent(make_mouse("MouseButtonPress", (100, 100),
                                          button=Qt.LeftButton,
                                          buttons=Qt.LeftButton))
        self.m.mouseMoveEvent(make_mouse("MouseMove", (130, 120),
                                         buttons=Qt.LeftButton))
        self.assertAlmostEqual(self.m._pan.x(), 30.0, places=4)
        self.assertAlmostEqual(self.m._pan.y(), 20.0, places=4)
        self.m.mouseReleaseEvent(make_mouse("MouseButtonRelease", (130, 120),
                                            button=Qt.LeftButton,
                                            buttons=Qt.LeftButton))
        self.assertIsNone(self.m._drag_pos)

    def test_double_click_reset(self):
        self.m._set_zoom(3.0)
        self.m._pan = QPointF(40.0, 25.0)
        self.m.mouseDoubleClickEvent(make_mouse("MouseButtonDblClick",
                                                (10, 10),
                                                button=Qt.LeftButton,
                                                buttons=Qt.LeftButton))
        self.assertEqual(self.m._zoom, 1.0)
        self.assertEqual(self.m._pan.x(), 0.0)

    def test_model_ops(self):
        self.m.add_track([0, 10, 20], [-50, 0, 50], color="#00ff00")
        self.m.add_point(51.5, -0.13, label="London")
        self.m.add_highlight(0, 0, "#ff0000")
        self.assertEqual(len(self.m.tracks), 1)
        self.assertEqual(len(self.m.points), 1)
        self.assertEqual(len(self.m.highlights), 1)
        self.m.clear_points()
        self.assertEqual(self.m.points, [])
        self.m.clear()
        self.assertEqual(self.m.tracks, [])


class TestSpaceView(unittest.TestCase):
    def setUp(self):
        get_app()
        self.v = SpaceView()
        self.v.resize(500, 400)
        self.v.set_scene(
            [dict(points=np.array([[0.0, 0.0, 0.0], [1e8, 0.0, 0.0]]),
                  color="#ffffff")],
            [Body(lambda t: (0.0, 0.0, 0.0), 100.0, "#ffffff", "Sun")],
            center=(0.0, 0.0))

    def tearDown(self):
        self.v.deleteLater()

    def test_anchor_zoom(self):
        s0 = self.v._scale(500, 400)
        A = QPointF(120.0, 90.0)
        wx = self.v.center[0] + (A.x() - 250.0) / s0
        wy = self.v.center[1] + (200.0 - A.y()) / s0
        self.v._set_zoom(2.0, anchor=A)
        x, y = self.v.scene_point_to_px((wx, wy, 0.0), 500, 400)
        self.assertAlmostEqual(x, A.x(), places=3)
        self.assertAlmostEqual(y, A.y(), places=3)

    def test_zoom_bounds(self):
        self.v._set_zoom(1e6)
        self.assertEqual(self.v._zoom, self.v._zoom_bounds[1])
        self.v._set_zoom(1e-9)
        self.assertEqual(self.v._zoom, self.v._zoom_bounds[0])
        self.v.zoom_reset()
        self.assertEqual(self.v._zoom, 1.0)

    def test_scale_uses_extent(self):
        self.assertGreater(self.v._scale(500, 400), 0.0)
        r = self.v.world_radius()
        self.assertGreaterEqual(r, 1e5)

    def test_stars_deterministic(self):
        self.v.set_stars(90)
        first = list(self.v._stars)
        self.assertTrue(40 <= len(first) <= 90, len(first))
        self.v.set_stars(90)
        self.assertEqual(first, list(self.v._stars))

    def test_stars_min_clamp(self):
        self.v.set_stars(3)
        self.assertGreaterEqual(len(self.v._stars), 40)

    def test_body_position_cache(self):
        b = Body(lambda t: (float(t), 0.0, 0.0), 10.0, "#ffffff")
        self.assertIsNone(b._last)
        self.assertEqual(b.position(5.0), (5.0, 0.0, 0.0))
        self.assertEqual(b._last[:2], (5.0, 0.0))

    def test_playback_state(self):
        self.v.dt = 10.0
        self.v.play(True)
        self.assertTrue(self.v.playing)
        self.v.play(False)
        self.assertFalse(self.v.playing)

    def test_paint_does_not_crash(self):
        self.v.show()
        pump()
        pm = self.v.grab()
        self.assertFalse(pm.isNull())
        self.assertGreater(pm.width(), 0)
        self.v.hide()


class TestPages(unittest.TestCase):
    def setUp(self):
        get_app()

    def test_mission_experiment_and_completion(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            page = win.pages["mission"]
            page.replan()
            self.assertTrue(page._plan is not None and page._plan.ok)
            self.assertTrue(page.view.paths)
            page.s_exp.set_value(200.0)
            page._run_experiment()
            self.assertTrue(page._plan.ok)

            page.view.t = page._tof_s - 1.0
            page._on_movie_tick()
            self.assertIn("mars", page._status_word.lower())

            shut_window(win)

    def test_asteroid_intercept_page(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            page = win.pages["asteroid"]
            page.replan()
            self.assertTrue(page._plan is not None and page._plan.ok)
            page.s_exp.set_value(120.0)
            page._run_experiment()
            self.assertTrue(page._plan.ok)
            shut_window(win)

    def test_orbit_rebuild(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            page = win.pages["orbit"]
            page.rebuild()
            self.assertTrue(page.view.paths or page.map.tracks)
            shut_window(win)


# --------------------------------------------------------------------------- window
class TestMainWindow(unittest.TestCase):
    def setUp(self):
        get_app()

    def test_window_builds_all_tabs(self):
        with isolated_env(), no_network():
            from spacekids.app_window import APP_NAME, MainWindow, TABS
            win = MainWindow()
            self.assertEqual(win.tabs.count(), 8)
            self.assertEqual(list(win.pages), [t[0] for t in TABS])
            self.assertIn(APP_NAME, win.windowTitle())
            self.assertEqual(len(win._tb_actions), 8)
            for i in range(win.tabs.count()):
                win.tabs.setCurrentIndex(i)
                pump()
            shut_window(win)

    def test_theme_switch_persists_and_styles(self):
        with isolated_env(), no_network():
            from PySide6.QtWidgets import QApplication
            from spacekids.app_window import MainWindow
            win = MainWindow()
            settings_page = win.pages["settings"]
            target = settings_page.theme_box.findText("Aurora")
            settings_page.theme_box.setCurrentIndex(target)
            pump()
            self.assertEqual(theme.active_name(), "Aurora")
            self.assertEqual(settings_store.get("theme"), "Aurora")
            css = QApplication.instance().styleSheet()
            self.assertIn(theme._PALETTES["Aurora"]["ACCENT"].upper(),
                          css.upper())
            self.assertEqual(
                settings_page.theme_box.currentText(), "Aurora")
            shut_window(win)

    def test_reset_all_restores_defaults(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            page = win.pages["settings"]
            page.s_stars.set_value(400)
            page._change_stars(400)
            page.theme_box.setCurrentIndex(
                page.theme_box.findText("Moonlight"))
            page.speed_box.setCurrentIndex(4)
            pump()
            self.assertNotEqual(settings_store.get("stars"), 200)
            page._reset_all()
            pump()
            self.assertEqual(theme.active_name(), theme.DEFAULT_THEME)
            self.assertEqual(settings_store.get("stars"), 200)
            self.assertEqual(settings_store.get("playback"), 1)
            self.assertEqual(page.s_stars.value(), 200)
            self.assertEqual(page.speed_box.currentIndex(), 1)
            shut_window(win)

    def test_add_and_remove_place(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            page = win.pages["settings"]
            base_rows = page.table.rowCount()
            self.assertEqual(base_rows, len(locations.BUILTIN))

            with mock.patch(
                    "spacekids.pages.settings_page.prompt_add_place",
                    return_value={"name": "Grandma's",
                                  "lat": 34.05, "lon": -118.24}):
                page._add_place()
            self.assertEqual(page.table.rowCount(), base_rows + 1)
            self.assertIsNotNone(locations.find("Grandma's"))
            self.assertIn("ok", page._status_kind)

            # a built-in cannot be removed
            page.table.selectRow(page._records.index(
                next(r for r in locations.all_locations() if not r["user"])))
            page._remove_place()
            self.assertIn("warn", page._status_kind)
            self.assertEqual(page.table.rowCount(), base_rows + 1)

            # the saved one can
            page._fill_table(select_name="Grandma's")
            page._remove_place()
            self.assertEqual(page.table.rowCount(), base_rows)
            self.assertIsNone(locations.find("Grandma's"))
            shut_window(win)

    def test_add_place_bad_input(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            page = win.pages["settings"]
            with mock.patch(
                    "spacekids.pages.settings_page.prompt_add_place",
                    return_value={"name": "Bad", "lat": 200.0, "lon": 0.0}):
                page._add_place()
            self.assertIn("err", page._status_kind)
            self.assertIsNone(locations.find("Bad"))
            shut_window(win)

    def test_spotter_markers_and_cities(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            locations.add_location("Grandma's", 34.05, -118.24)
            page = win.pages["spotter"]
            page._fill_cities()
            page._refresh_all()
            colors = {pt["color"] for pt in page.map.points}
            self.assertIn(theme.ACCENT, colors)      # saved place dot
            self.assertIn(theme.C_EARTH, colors)     # selected town
            # pick the saved place as "my town"
            idx = page.city.findText("Grandma's")
            self.assertGreaterEqual(idx, 0)
            page.city.setCurrentIndex(idx)
            page._refresh_all()
            colors2 = {pt["color"] for pt in page.map.points}
            self.assertNotIn(theme.ACCENT, colors2)  # no duplicate once named
            self.assertIn(theme.C_EARTH, colors2)
            # live tick adds the glow dot for the spacecraft itself
            page._live_tick()
            total = len(page.map.points)
            self.assertGreaterEqual(total, 2)
            shut_window(win)

    def test_gnss_places_respect_user_locations(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            locations.add_location("Grandma's", 34.05, -118.24)
            page = win.pages["gnss"]
            page._fill_places()
            self.assertGreaterEqual(page.place.findText("Grandma's"), 0)
            page._refresh_all()
            self.assertTrue(page.map.tracks)
            self.assertGreaterEqual(page.table.rowCount(),
                                    len(locations.BUILTIN))
            pump()
            page._tick()
            shut_window(win)

    def test_playbar_defaults_in_pages(self):
        with isolated_env(), no_network():
            settings_store.set("playback", 3)
            from spacekids.app_window import MainWindow
            win = MainWindow()
            for key in ("mission", "orbit", "asteroid", "spotter", "gnss"):
                self.assertEqual(win.pages[key].playbar.speed.currentIndex(),
                                 3, key)
            shut_window(win)

    def test_theme_change_updates_pages(self):
        with isolated_env(), no_network():
            from spacekids.app_window import MainWindow
            win = MainWindow()
            win.pages["mission"].replan()
            win.pages["asteroid"].replan()
            theme.set_active("Rainbow Kids")   # drives every page's restyle
            pump()
            self.assertEqual(theme.active_name(), "Rainbow Kids")
            for page in win.pages.values():
                fn = getattr(page, "refresh_theme", None)
                if fn is not None:
                    fn()
            pump()
            shut_window(win)


if __name__ == "__main__":
    unittest.main(verbosity=2)