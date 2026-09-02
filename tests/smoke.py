"""Headless smoke tests:  python -m pytest tests  (or run directly).

Verifies the math and that every page builds and replan()s without touching
the network or blocking threads.  Runs with the offscreen Qt platform so it
works on any machine without a display.
"""

import math
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

# --------------------------------------------------------------------------- 1. orbit math
def test_hohmann_baseline():
    from spacekids.astro.mission import hohmann_baseline
    base = hohmann_baseline()
    assert 240 < base["tof_days"] < 280, base["tof_days"]   # textbook ~259 days
    assert 5.0 < base["dv_total"] < 6.2, base["dv_total"]   # 5.6 km/s heliocentric


def test_kepler_propagation_consistency():
    from spacekids.astro import bodies
    from spacekids.astro.kepler import propagate_elements, period_s
    from spacekids.astro.core import mu_km3s2
    k = mu_km3s2("earth")
    a = 7000.0
    r0, _v0 = propagate_elements(k, a, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    r_after, _v = propagate_elements(k, a, 0.0, 0.0, 0.0, 0.0, 0.0,
                                     period_s(k, a))
    assert np.allclose(np.asarray(r0), np.asarray(r_after), atol=1e-6)


def test_planet_positions_finite():
    from spacekids.astro import bodies
    from spacekids.astro.core import julian_date
    import datetime
    jd = julian_date(datetime.datetime(2026, 8, 28))
    for name in ("Earth", "Mars", "Venus", "Mercury"):
        r, v = bodies.state(name, jd)
        assert np.all(np.isfinite(r)) and np.linalg.norm(r) > 3e7


def test_lambert_via_poliastro():
    from spacekids.astro.core import best_lambert, mu_km3s2
    k = mu_km3s2("sun")
    pair = best_lambert(k, [149.6e6, 0.0, 0.0], [227.9e6, 10e6, 0.0],
                        250 * 86400.0)
    assert pair is not None
    v0, v1 = pair
    assert abs(29.57 - v0[0]) < 0.05 and abs(-16.26 - v1[0]) < 0.05


def test_planetvelocities_between():
    from spacekids.astro.mission import plan_mission
    import datetime
    chosen, best = plan_mission(datetime.datetime(2026, 5, 1))
    assert chosen.ok
    assert 200 < chosen.tof_days < 300
    # bad windows can demand a LOT of delta-v; that is the whole lesson
    assert 0 < chosen.dv_total < 80
    if best:
        assert best.dv_total <= chosen.dv_total + 1e-9


# --------------------------------------------------------------------------- 2. orbit lab
def test_orbit_design_numbers():
    from spacekids.astro import orbitlab
    d = orbitlab.PRESETS["GPS (Medium)"]
    assert 700 < d.period_min < 1200          # GPS ~ 11h58m
    assert 3.8 < d.speed_peri < 4.0           # ~3.87 km/s circular-ish
    assert "MEO" in d.classification()
    lats, lons = d.ground_track(n=120)
    assert len(lats) == 120 and np.all(np.abs(lats) <= 90)
    assert np.all(np.abs(lons) <= 180)


# --------------------------------------------------------------------------- 3. asteroid
def test_asteroid_intercept():
    from spacekids.astro import asteroids
    from spacekids.astro.core import julian_date
    import datetime
    jd0 = julian_date(datetime.datetime(2027, 3, 15))
    plan = asteroids.best_intercept("Bennu", jd0)
    assert plan is not None and plan.ok
    assert plan.tof_days > 0 and plan.dv_total > 0


# --------------------------------------------------------------------------- 4. satellites
def test_pass_finding():
    from spacekids.astro import satellites
    d = satellites.CATALOG[0]  # ISS-like low orbit
    passes = satellites.find_passes(d, 2461000.0, 51.51, -0.13,
                                    horizon_deg=10.0, span_hours=36.0)
    assert len(passes) >= 1, "ISS flies over London daily at 10deg horizon"
    p = passes[0]
    assert p["set_jd"] > p["rise_jd"]
    assert 10.0 <= p["max_elev"] <= 90.0


def test_sgp4():
    from spacekids.astro.satellites import parse_tle
    l1 = "1 25544U 98067A   24172.56859098  .00022029  00000-0  39874-3 0  9991"
    l2 = "2 25544  51.6416 195.8944 0001839 101.5135 158.7405 15.50066165447066"
    prop = parse_tle(l1, l2)
    assert prop is not None
    r = prop.eci(prop.epoch_jd + 0.25)
    assert r is not None and np.linalg.norm(r) > 6000.0


# --------------------------------------------------------------------------- 5. GUI builds
def test_gui_pages_build():
    from PySide6.QtWidgets import QApplication
    from spacekids.app_window import MainWindow

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    assert win.tabs.count() == 8, win.tabs.count()
    win.pages["mission"].replan()
    win.pages["asteroid"].replan()
    win.pages["orbit"].rebuild()
    win.pages["gnss"]._refresh_all()
    win.pages["settings"]._fill_table()
    app.processEvents()
    # drag the experiment sliders; the debounced recompute runs by hand
    win.pages["mission"].s_exp.set_value(200.0)
    win.pages["mission"]._run_experiment()
    assert win.pages["mission"]._plan is not None and \
        win.pages["mission"]._plan.ok
    win.pages["asteroid"].s_exp.set_value(120.0)
    win.pages["asteroid"]._run_experiment()
    assert win.pages["asteroid"]._plan is not None and \
        win.pages["asteroid"]._plan.ok
    win.pages["gnss"]._tick()
    app.processEvents()
    win.close()
    app.processEvents()


# --------------------------------------------------------------------------- 6. constellation lab
def test_constellations_sanity():
    from spacekids.astro import constellations
    import datetime
    from spacekids.astro.core import julian_date

    jd = julian_date(datetime.datetime(2026, 8, 28))
    assert len(constellations.satellites("GPS")) == 24
    assert len(constellations.satellites("GLONASS")) == 24
    assert len(constellations.satellites("BeiDou")) == 27 + 5
    for name in constellations.constellation_names():
        for d in constellations.satellites(name)[:8]:
            r = constellations.stat(d, jd)
            assert np.all(np.isfinite(r)) and np.linalg.norm(r) > 6000.0
    # a BeiDou GEO bird stays over its slot longitude (near-Earth toy model)
    geo = constellations.satellites("BeiDou")[-1]
    lon1 = constellations.sub(geo, jd)[1]
    lon2 = constellations.sub(geo, jd + 0.5)[1]
    assert abs(lon1 - lon2) < 1.0
    # visibility: a mid-latitude fleet is never empty over town
    hits = constellations.visible(constellations.satellites("GPS"),
                                  jd, 40.71, -74.01, mask_deg=10.0)
    assert len(hits) >= 2


def test_experiment_plan_at_tof():
    from spacekids.astro import mission
    import datetime
    plan = mission.plan_at_tof(datetime.datetime(2026, 5, 1), 260.0)
    assert plan.ok and 250 < plan.tof_days < 270
    assert plan.dv_total > 0


def test_locations_persistence():
    import tempfile
    from spacekids.geo import locations
    saved = os.environ.get("SPACEKIDS_LOCATIONS")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SPACEKIDS_LOCATIONS"] = os.path.join(
                tmp, "locs.json")
            locations.add_location("Grandma", 34.05, -118.24)
            rec = locations.find("Grandma")
            assert rec is not None and rec["user"]
            assert abs(rec["lat"] - 34.05) < 1e-3
            locations.remove_location("Grandma")
            assert locations.find("Grandma") is None
    finally:
        if saved is None:
            os.environ.pop("SPACEKIDS_LOCATIONS", None)
        else:
            os.environ["SPACEKIDS_LOCATIONS"] = saved


def test_mapview_builds():
    from PySide6.QtWidgets import QApplication
    from spacekids.geo.mapview import MapView
    import datetime
    from spacekids.astro import orbitlab
    from spacekids.astro.core import julian_date

    app = QApplication.instance() or QApplication([])
    m = MapView()
    d = orbitlab.PRESETS["ISS (Low Orbit)"]
    lats, lons = d.ground_track(n=300, start_jd=julian_date(
        datetime.datetime.utcnow()))
    m.resize(500, 280)
    m.add_track(lats, lons)
    m.add_point(51.5, -0.13, color="#3f86e0", label="London")
    m.show()
    app.processEvents()


def test_theme_switch():
    import tempfile
    from spacekids import theme
    saved = os.environ.get("SPACEKIDS_SETTINGS")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SPACEKIDS_SETTINGS"] = os.path.join(tmp, "s.json")
            before = theme.active_name()
            assert before in theme.themes()
            old_bg = theme.BG
            for name in theme.themes():
                theme.set_active(name)
                assert theme.active_name() == name
                assert theme.BG and theme.ACCENT and theme.C_SAT
                assert theme.build_stylesheet().find(
                    "background:") >= 0
                assert theme.css_for("muted").startswith("color: #")
            theme.set_active(before)
            assert theme.active_name() == before
            assert theme.BG == old_bg
    finally:
        if saved is None:
            os.environ.pop("SPACEKIDS_SETTINGS", None)
        else:
            os.environ["SPACEKIDS_SETTINGS"] = saved


def test_settings_persistence():
    import tempfile
    from spacekids import settings
    saved = os.environ.get("SPACEKIDS_SETTINGS")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SPACEKIDS_SETTINGS"] = os.path.join(tmp, "s.json")
            settings.set("stars", 333)
            settings.set("playback", 3)
            assert settings.get("stars") == 333
            assert settings.get("playback") == 3
            assert settings.get("theme") == "Space Night"
            settings.reset()
            assert settings.get("stars") == 200
            assert settings.get("playback") == 1
    finally:
        if saved is None:
            os.environ.pop("SPACEKIDS_SETTINGS", None)
        else:
            os.environ["SPACEKIDS_SETTINGS"] = saved


if __name__ == "__main__":
    names = [n for n in dir() if n.startswith("test_")]
    failed = 0
    for name in names:
        try:
            globals()[name]()
            print("ok   ", name)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("FAIL ", name, "->", repr(exc))
    sys.exit(1 if failed else 0)