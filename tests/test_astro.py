"""Full physics edge-case suite: astro.core, kepler, bodies, mission,
orbitlab, asteroids, constellations, satellites.

No GUI, no network (network functions are patched).  Uses unittest so it runs
with the standard library:

    python -m unittest discover -s tests -v
"""

import datetime
import math
import os
import sys
import unittest

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    from tests.helpers import isolated_env, no_network
except ImportError:  # discovered flat from inside tests/
    from helpers import isolated_env, no_network

from spacekids.astro import core as core
from spacekids.astro import kepler
from spacekids.astro import bodies, mission, orbitlab, asteroids
from spacekids.astro import constellations, satellites


# --------------------------------------------------------------------------- core
@unittest.skipUnless(core.PO_FOUND, "poliastro is not installed")
class TestCorePoliastro(unittest.TestCase):
    def test_mu_known(self):
        self.assertAlmostEqual(core.mu_km3s2("earth"), 3.986004418e5, delta=1e-2)
        self.assertTrue(1.32712e11 < core.mu_km3s2("sun") < 1.32714e11)
        self.assertTrue(4.2e4 < core.mu_km3s2("mars") < 4.4e4)

    def test_mu_unknown_defaults_to_earth(self):
        self.assertEqual(core.mu_km3s2("pluto"), core.mu_km3s2("Earth"))

    def test_julian_date_j2000_noon(self):
        self.assertAlmostEqual(
            core.julian_date(datetime.datetime(2000, 1, 1, 12)), 2451545.0)
        self.assertEqual(core.julian_date(2451545.0), 2451545.0)

    def test_julian_date_timezone_aware(self):
        # the same instant expressed in two time zones must give the same JD
        utc = datetime.timezone.utc
        east = datetime.timezone(datetime.timedelta(hours=-4))
        same = datetime.datetime(2020, 6, 1, 4, 0, tzinfo=utc)
        local = datetime.datetime(2020, 6, 1, 0, 0, tzinfo=east)
        self.assertEqual(core.julian_date(same), core.julian_date(local))

    def test_jd_roundtrip(self):
        jd = core.julian_date(datetime.datetime(2026, 8, 28, 12))
        dt = core.jd_to_datetime(jd)
        self.assertAlmostEqual(core.julian_date(dt), jd, places=6)

    def test_fmt_date(self):
        self.assertEqual(core.fmt_date(2451545.0), "01 Jan 2000")

    def test_gmst_at_j2000(self):
        self.assertAlmostEqual(core.gmst_deg(2451545.0), 280.46061837, places=5)

    def test_gmst_wrapped_and_rate(self):
        self.assertTrue(0.0 <= core.gmst_deg(2451545.0) < 360.0)
        d1 = core.gmst_deg(2451545.0)
        d2 = core.gmst_deg(2451546.0)
        self.assertAlmostEqual((d2 - d1) % 360.0, 360.98564736629 % 360.0,
                               places=3)

    def test_build_orbit_roundtrip(self):
        po = core.build_orbit("earth", 7000.0, 0.001, 51.6, 120.0, 30.0, 0.0)
        el = core.po_elements(po)
        self.assertAlmostEqual(el["a"], 7000.0, delta=1e-6)
        self.assertAlmostEqual(el["e"], 0.001, places=6)
        self.assertAlmostEqual(el["i"], 51.6, places=4)

    def test_po_propagate_period(self):
        po = core.build_orbit("earth", 7000.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        t = 2.0 * math.pi * math.sqrt(7000.0 ** 3 / core.mu_km3s2("earth"))
        r1, _ = core.po_propagate(po, t)
        r0, _ = core.po_propagate(po, 0.0)
        self.assertTrue(np.allclose(r0, r1, atol=1e-4))

    def test_lambert_hohmann_smoke(self):
        pair = core.best_lambert(core.mu_km3s2("sun"),
                                 [149.6e6, 0, 0], [227.9e6, 10e6, 0],
                                 250 * 86400.0)
        self.assertIsNotNone(pair)
        v0, v1 = pair
        self.assertAlmostEqual(v0[0], 29.57, delta=0.05)
        self.assertAlmostEqual(v1[0], -16.26, delta=0.05)

    def test_best_lambert_costs_choices(self):
        r0 = np.array([149.6e6, 0.0, 0.0])
        r1 = np.array([227.9e6, 10e6, 0.0])
        tof = 250 * 86400.0
        cheap = core.best_lambert(core.mu_km3s2("sun"), r0, r1, tof,
                                  v_depart=core.lambert_solutions(
                                      core.mu_km3s2("sun"), r0, r1, tof)[0][0],
                                  v_arrival=core.lambert_solutions(
                                      core.mu_km3s2("sun"), r0, r1, tof)[0][1])
        self.assertIsNotNone(cheap)
        for v in cheap:
            self.assertEqual(len(v), 3)
            self.assertTrue(np.all(np.isfinite(v)))

    def test_lambert_empty_on_bad_tof(self):
        self.assertEqual(core.lambert_solutions(core.mu_km3s2("sun"),
                                                [1e8, 0, 0], [2e8, 0, 0], 0.0),
                         [])
        self.assertEqual(core.lambert_solutions(core.mu_km3s2("sun"),
                                                [1e8, 0, 0], [2e8, 0, 0], -5),
                         [])

    def test_lambert_nan_input_safe(self):
        out = core.lambert_solutions(core.mu_km3s2("sun"),
                                     [float("nan"), 0, 0], [2e8, 0, 0], 100.0)
        self.assertIsInstance(out, list)

    def test_poliastro_status_text(self):
        text = core.poliastro_status()
        self.assertTrue(text)


class TestCoreWithoutPoliastro(unittest.TestCase):
    def test_julian_date_scalar(self):
        self.assertTrue(math.isfinite(core.julian_date(2460000.5)))


# --------------------------------------------------------------------------- kepler
class TestKepler(unittest.TestCase):
    K = core.mu_km3s2("earth")

    def test_nu_m_roundtrip(self):
        for ecc in (0.0, 0.2, 0.7, 0.95):
            for M in (0.0, 40.0, 180.0, 300.0):
                nu = kepler.nu_from_M(M, ecc)
                M2 = kepler.M_from_nu(nu, ecc)
                self.assertAlmostEqual(M2 % 360.0, M % 360.0, places=4)

    def test_nu_endpoints(self):
        for ecc in (0.0, 0.4, 0.9):
            self.assertAlmostEqual(kepler.nu_from_M(0.0, ecc), 0.0, places=6)
            self.assertAlmostEqual(kepler.nu_from_M(180.0, ecc), 180.0,
                                   places=4)

    def test_kepler_E_high_eccentricity(self):
        E = kepler.kepler_E(math.pi, 0.999)
        self.assertTrue(math.isfinite(E))
        residual = (E - 0.999 * math.sin(E)) - math.pi
        self.assertLess(abs(residual), 1e-9)

    def test_kepler_E_negative_M(self):
        E = kepler.kepler_E(-1.0, 0.5)
        self.assertTrue(math.isfinite(E))

    def test_period_circular(self):
        t = kepler.period_s(self.K, 7000.0)
        self.assertTrue(5700 < t < 6000, t)
        # matched against Kepler's third law
        expect = 2 * math.pi * math.sqrt(7000.0 ** 3 / self.K)
        self.assertAlmostEqual(t, expect, places=6)

    def test_period_keeps_eccentricity_value(self):
        self.assertAlmostEqual(kepler.period_s(self.K, 42164.0),
                               2 * math.pi * math.sqrt(42164 ** 3 / self.K),
                               places=6)

    def test_propagate_circular_period_returns(self):
        r0, v0 = kepler.propagate_elements(self.K, 7000.0, 0.0, 0.0, 0.0, 0.0,
                                           0.0, 0.0)
        r1, v1 = kepler.propagate_elements(self.K, 7000.0, 0.0, 0.0, 0.0, 0.0,
                                           0.0, kepler.period_s(self.K, 7000.0))
        self.assertTrue(np.allclose(r0, r1, atol=1e-6))
        self.assertTrue(np.allclose(v0, v1, atol=1e-6))

    def test_propagate_eccentric_period_returns(self):
        s = dict(a=20000.0, e=0.65, i=45.0, raan=30.0, argp=40.0)
        r0, v0 = kepler.propagate_elements(self.K, s["a"], s["e"], s["i"],
                                           s["raan"], s["argp"], 0.0, 0.0)
        t = kepler.period_s(self.K, s["a"])
        r1, v1 = kepler.propagate_elements(self.K, s["a"], s["e"], s["i"],
                                           s["raan"], s["argp"], 0.0, t)
        self.assertTrue(np.allclose(r0, r1, atol=1e-3))
        self.assertTrue(np.allclose(v0, v1, atol=1e-3))

    def test_propagate_rejects_open_orbits(self):
        for bad_e in (1.0, 1.2):
            with self.assertRaises(ValueError):
                kepler.propagate_elements(self.K, 20000.0, bad_e, 0, 0, 0, 0, 0)

    def test_energy_conserved(self):
        r0, v0 = kepler.propagate_elements(self.K, 20000.0, 0.5, 40.0, 120.0,
                                           30.0, 60.0, 0.0)
        r1, v1 = kepler.propagate_elements(self.K, 20000.0, 0.5, 40.0, 120.0,
                                           30.0, 60.0, 10000.0)
        spec = lambda r, v: np.dot(v, v) / 2.0 - self.K / float(np.linalg.norm(r))
        self.assertAlmostEqual(spec(r0, v0), spec(r1, v1), delta=1e-9)

    def test_sample_elements_bounds(self):
        pts = kepler.sample_elements(self.K, 20000.0, 0.65, 45.0, 30.0, 40.0,
                                     n=360)
        self.assertEqual(pts.shape, (360, 3))
        self.assertTrue(np.all(np.isfinite(pts)))
        rp = 20000.0 * (1 - 0.65)
        ra = 20000.0 * (1 + 0.65)
        r = np.linalg.norm(pts, axis=1)
        self.assertTrue(np.all((r >= rp - 1e-6) & (r <= ra + 1e-6)))

    def test_integrate_state_vs_analytic(self):
        a, k = 7000.0, self.K
        v = math.sqrt(k / a)
        r0, v0 = np.array([a, 0.0, 0.0]), np.array([0.0, v, 0.0])
        def want(dt):
            return kepler.propagate_elements(k, a, 0.0, 0.0, 0.0, 0.0,
                                             0.0, dt)[0]
        # short single-step advances match the closed form to ~100 m
        for dt in (1.0, 60.0):
            with self.subTest(dt=dt):
                got = kepler.integrate_state(k, r0, v0, np.array([dt]))[0]
                self.assertLess(float(np.linalg.norm(got - want(dt))), 0.5, dt)
        # long advances need sub-stepping in RK4; with a fine max_step the
        # integrated state still lands on the analytic position
        for dt, step in ((600.0, 30.0), (3600.0, 90.0)):
            with self.subTest(dt=dt, step=step):
                got = kepler.integrate_state(k, r0, v0, np.array([dt]),
                                             max_step_s=step)[0]
                self.assertLess(float(np.linalg.norm(got - want(dt))), 1.0)

    def test_integrate_state_empty_and_single(self):
        self.assertEqual(kepler.integrate_state(self.K, [7000, 0, 0],
                                                [0, 7.5, 0], []).shape, (0, 3))
        one = kepler.integrate_state(self.K, [7000, 0, 0], [0, 7.5, 0],
                                     [0.0])
        self.assertEqual(one.shape, (1, 3))
        self.assertTrue(np.allclose(one[0], [7000, 0, 0], atol=1e-9))

    def test_integrate_state_hyperbolic_finite(self):
        k, a = self.K, 7000.0
        v_esc = math.sqrt(2.0 * k / a) * 1.5  # clearly hyperbolic
        pts = kepler.integrate_state(k, [a, 0, 0], [0, v_esc, 0],
                                     np.linspace(0, 400 * 86400.0, 50))
        self.assertTrue(np.all(np.isfinite(pts)))

    def test_two_body_accel_center_guard(self):
        self.assertTrue(np.allclose(
            kepler.two_body_accel(self.K, [1e-12, 1e-12, 1e-12]), [0, 0, 0]))

    def test_angle_wrap(self):
        arr = kepler.angle_wrap(np.array([-190.0, 720.0, 350.0, 0.0]))
        self.assertTrue(np.allclose(arr, [170.0, 0.0, 350.0, 0.0]))
        self.assertEqual(kepler.angle_wrap(190.0), 190.0)

    def test_elements_from_state_roundtrip(self):
        r, v = kepler.propagate_elements(self.K, 20000.0, 0.5, 55.0, 200.0,
                                         110.0, 90.0, 0.0)
        el = kepler.elements_from_state(self.K, r, v)
        self.assertAlmostEqual(el["a"], 20000.0, places=3)
        self.assertAlmostEqual(el["e"], 0.5, places=9)
        self.assertAlmostEqual(el["i"], 55.0, places=5)
        self.assertAlmostEqual(el["raan"], 200.0, places=4)
        self.assertAlmostEqual(el["argp"], 110.0, places=4)
        self.assertAlmostEqual(el["nu"], 90.0, places=4)

    def test_elements_from_state_circular(self):
        r, v = kepler.propagate_elements(self.K, 7000.0, 0.0, 0.0, 0.0, 0.0,
                                         0.0, 0.0)
        el = kepler.elements_from_state(self.K, r, v)
        self.assertAlmostEqual(el["e"], 0.0, places=9)
        self.assertAlmostEqual(el["a"], 7000.0, places=3)

    def test_checksum(self):
        self.assertEqual(kepler.checksum("209"), 1)  # 2+0+9 = 11 -> 1
        self.assertEqual(kepler.checksum("12345"), 5)

    def test_mean_motion_scaling(self):
        n = kepler.mean_motion(self.K, 10000.0)
        self.assertAlmostEqual(n, math.sqrt(self.K / 10000.0 ** 3))


# --------------------------------------------------------------------------- bodies
class TestBodies(unittest.TestCase):
    def test_planet_list(self):
        self.assertEqual(bodies.planets(),
                         ["Mercury", "Venus", "Earth", "Mars"])

    def test_positions_finite_and_in_range(self):
        for jd in (2451545.0, 2460000.5, 2470000.0):
            for name in bodies.planets():
                r, v = bodies.state(name, jd)
                self.assertTrue(np.all(np.isfinite(r)) and
                                np.all(np.isfinite(v)), (name, jd))
                rec = bodies.planet(name)
                rp = rec["a"] * (1 - rec["e"])
                ra = rec["a"] * (1 + rec["e"])
                self.assertTrue(rp - 1e-3 <= np.linalg.norm(r) <= ra + 1e-3,
                                name)

    def test_vis_viva_consistent(self):
        jd = 2460000.5
        for name in bodies.planets():
            r, v = bodies.state(name, jd)
            rec = bodies.planet(name)
            en = float(np.dot(v, v)) / 2.0 - bodies.MU_SUN / np.linalg.norm(r)
            expect = -bodies.MU_SUN / (2.0 * rec["a"])
            self.assertAlmostEqual(en, expect, places=6)

    def test_periodic_in_state(self):
        jd = 2460000.5
        for name in ("Earth", "Mars"):
            rec = bodies.planet(name)
            r0, v0 = bodies.state(name, jd)
            r1, v1 = bodies.state(name, jd + rec["period_days"])
            self.assertTrue(np.allclose(r0, r1, atol=1e-6))
            self.assertTrue(np.allclose(v0, v1, atol=1e-6))

    def test_path_shape_and_bounds(self):
        jd = 2460000.5
        for name in ("Earth", "Mars"):
            pts = bodies.path(name, jd, 400.0, n=200)
            self.assertEqual(pts.shape, (200, 3))
            self.assertTrue(np.all(np.isfinite(pts)))
            rec = bodies.planet(name)
            r = np.linalg.norm(pts, axis=1)
            self.assertTrue(np.all(r >= rec["a"] * (1 - rec["e"]) - 1))
            self.assertTrue(np.all(r <= rec["a"] * (1 + rec["e"]) + 1))

    def test_au_constant(self):
        self.assertAlmostEqual(bodies.AU, 149597870.691, places=3)


# --------------------------------------------------------------------------- mission
class TestMission(unittest.TestCase):
    def test_hohmann_baseline(self):
        b = mission.hohmann_baseline()
        self.assertTrue(240 < b["tof_days"] < 280, b["tof_days"])
        self.assertTrue(5.0 < b["dv_total"] < 6.2, b["dv_total"])
        self.assertTrue(b["dv1"] > 0 and b["dv2"] > 0)
        self.assertTrue(0 < b["e_t"] < 1)

    def test_plan_at_tof_orchestration(self):
        plan = mission.plan_at_tof(datetime.datetime(2026, 5, 1), 260.0)
        self.assertTrue(plan.ok)
        self.assertTrue(250 < plan.tof_days < 270)
        self.assertTrue(plan.dv_total > 0)
        self.assertEqual(plan.r0.shape, (3,))
        self.assertEqual(plan.v_transfer0.shape, (3,))
        self.assertIn("k", plan.elements)

    def test_dv_decreases_toward_hohmann(self):
        fast = mission.plan_at_tof(datetime.datetime(2026, 5, 1), 100.0)
        slow = mission.plan_at_tof(datetime.datetime(2026, 5, 1), 260.0)
        if fast.ok and slow.ok:
            self.assertTrue(slow.dv_total <= fast.dv_total,
                            (slow.dv_total, fast.dv_total))

    def test_window_scan(self):
        chosen, best = mission.plan_mission(datetime.datetime(2026, 5, 1))
        self.assertTrue(chosen.ok)
        self.assertTrue(200 < chosen.tof_days < 300)
        self.assertTrue(0 < chosen.dv_total < 80)
        if best is not None:
            self.assertTrue(best.dv_total <= chosen.dv_total + 1e-9)

    def test_phase_angle_range(self):
        for jd in (2451545.0, 2460000.5, 2461000.0):
            a = mission.phase_angle_deg(jd)
            self.assertTrue(0.0 <= a <= 180.0, a)

    def test_trajectory_helpers(self):
        plan = mission.plan_at_tof(datetime.datetime(2026, 5, 1), 260.0)
        k = plan.elements["k"]
        p0 = mission.trajectory_position(k, plan.r0, plan.v_transfer0, 0.0)
        self.assertTrue(np.allclose(p0, plan.r0, atol=1e-6))
        path = mission.trajectory_path(k, plan.r0, plan.v_transfer0, 90,
                                       plan.tof_days * 86400.0)
        self.assertEqual(path.shape, (90, 3))
        self.assertTrue(np.all(np.isfinite(path)))

    def test_trajectory_none_safe(self):
        self.assertTrue(np.allclose(
            mission.trajectory_position(1.0, None, None, 0.0), [0, 0, 0]))
        self.assertEqual(mission.trajectory_path(1.0, None, None, 12, 100.0)
                         .shape, (12, 3))


# --------------------------------------------------------------------------- orbitlab
class TestOrbitDesign(unittest.TestCase):
    def test_presets_present(self):
        for name in ("ISS (Low Orbit)", "Hubble (Low, tilted)",
                     "GPS (Medium)", "TV satellite (GEO)", "Egg (Elliptical)"):
            self.assertIn(name, orbitlab.PRESETS)

    def test_classifications(self):
        folded = {"ISS (Low Orbit)": "LEO",
                  "Hubble (Low, tilted)": "LEO",
                  "GPS (Medium)": "MEO",
                  "TV satellite (GEO)": "GEO",
                  "Egg (Elliptical)": "MEO"}   # apogee 26,629 km - a MEO egg
        for name, word in folded.items():
            with self.subTest(name=name):
                self.assertIn(word, orbitlab.PRESETS[name].classification(),
                              orbitlab.PRESETS[name].classification())
        # a real HEO: e>0.30 and apogee above 35,786 km
        heo = orbitlab.OrbitDesign("HEO", 30000.0, 0.7, 33.0)
        self.assertIn("HEO", heo.classification())
        self.assertGreater(heo.alt_apo, 35786.0)
        # exact boundaries
        leo = orbitlab.OrbitDesign("ley", 2000.0 + 6371.0, 0.0, 0.0)
        self.assertIn("LEO", leo.classification())
        geo = orbitlab.OrbitDesign("geo", 35786.0 + 6371.0, 0.0, 0.1)
        self.assertIn("GEO", geo.classification())

    def test_geostationary_period(self):
        d = orbitlab.PRESETS["TV satellite (GEO)"]
        self.assertTrue(1420 < d.period_min < 1450, d.period_min)
        self.assertAlmostEqual(d.alt_apo, d.alt_peri, places=3)

    def test_iss_period_and_altitudes(self):
        d = orbitlab.PRESETS["ISS (Low Orbit)"]
        self.assertTrue(90 < d.period_min < 95)
        self.assertTrue(380 < d.alt_peri < 430)
        self.assertTrue(380 < d.alt_apo < 430)

    def test_speeds_match_vis_viva(self):
        d = orbitlab.PRESETS["GPS (Medium)"]
        for r, s in ((d.rp_km, d.speed_peri), (d.ra_km, d.speed_apo)):
            self.assertAlmostEqual(
                s, math.sqrt(d.k * (2.0 / r - 1.0 / d.a_km)), places=9)

    def test_apogee_slower_than_perigee(self):
        for d in orbitlab.PRESETS.values():
            with self.subTest(name=d.name):
                self.assertLessEqual(d.speed_apo, d.speed_peri)
                if d.e > 0.0:
                    self.assertLess(d.speed_apo, d.speed_peri)
                self.assertTrue(0.0 < d.speed_peri and 0.0 < d.speed_apo)

    def test_validity(self):
        good = orbitlab.OrbitDesign("x", 8000.0, 0.5, 60.0)
        self.assertTrue(good.is_valid())
        self.assertFalse(orbitlab.OrbitDesign("x", 6371.0, 0.0, 0.0).is_valid())
        self.assertFalse(orbitlab.OrbitDesign("x", 8000.0, 1.0, 0.0).is_valid())
        self.assertFalse(orbitlab.OrbitDesign("x", 8000.0, 1.5, 0.0).is_valid())

    def test_design_from_sliders(self):
        d = orbitlab.design_from_sliders(400.0, 0.0, 51.6, 0.0, 0.0)
        self.assertEqual(d.name, "Custom")
        self.assertAlmostEqual(d.a_km, 6371.0 + 400.0)
        self.assertEqual(d.nu0_deg, 0.0)

    def test_state_at_time_zero_is_perigee(self):
        d = orbitlab.OrbitDesign("x", 20000.0, 0.65, 45.0, 0.0, 0.0, 0.0)
        r, v = d.state_at(0.0)
        self.assertAlmostEqual(float(np.linalg.norm(r)), d.rp_km, places=6)

    def test_state_at_period_returns(self):
        d = orbitlab.OrbitDesign("x", 20000.0, 0.3, 60.0, 40.0, 20.0)
        r0, _ = d.state_at(0.0)
        r1, _ = d.state_at(d.period_s)
        self.assertTrue(np.allclose(r0, r1, atol=1e-3))

    def test_equatorial_ground_track(self):
        d = orbitlab.OrbitDesign("eq", 7000.0, 0.0, 0.0)
        lats, lons = d.ground_track(n=240)
        self.assertEqual(len(lats), 240)
        self.assertTrue(np.all(np.abs(lats) < 1e-6))
        self.assertTrue(np.all(np.abs(lons) <= 180.0))

    def test_ground_track_bounds_custom_length(self):
        d = orbitlab.PRESETS["ISS (Low Orbit)"]
        lats, lons = d.ground_track(n=97)
        self.assertEqual(len(lats), 97)
        self.assertTrue(np.all(np.abs(lats) <= 90))
        self.assertTrue(np.all(np.abs(lons) <= 180))


# --------------------------------------------------------------------------- asteroids
class TestAsteroids(unittest.TestCase):
    def test_names_and_facts(self):
        names = asteroids.asteroid_names()
        self.assertIn("Eros", names)
        self.assertIn("Bennu", names)
        for n in names:
            self.assertTrue(asteroids.asteroid_fact(n))

    def test_position_radius_in_orbit(self):
        jd = 2460000.5
        for name in asteroids.asteroid_names():
            rec = asteroids._ASTEROIDS[name]
            a = rec["a_au"] * asteroids.AU
            r = asteroids.asteroid_position(name, jd)
            rn = float(np.linalg.norm(r))
            self.assertTrue(np.all(np.isfinite(r)))
            self.assertTrue(a * (1 - rec["e"]) - 1 <= rn <=
                            a * (1 + rec["e"]) + 1, (name, rn))

    def test_path_shape(self):
        jd = 2460000.5
        for name in ("Bennu", "Apophis"):
            pts = asteroids.asteroid_path(name, jd, 300.0, n=150)
            self.assertEqual(pts.shape, (150, 3))
            self.assertTrue(np.all(np.isfinite(pts)))

    def test_intercept_ok(self):
        jd0 = core.julian_date(datetime.datetime(2027, 3, 15))
        plan = asteroids.best_intercept("Bennu", jd0)
        self.assertIsNotNone(plan)
        self.assertTrue(plan.ok)
        self.assertTrue(plan.tof_days > 0)
        self.assertTrue(plan.dv_total > 0)
        self.assertEqual(plan.dv_depart + plan.dv_arrival, plan.dv_total)
        self.assertIn("k", plan.elements)

    def test_intercept_multiple_asteroids(self):
        jd0 = core.julian_date(datetime.datetime(2026, 8, 28))
        for name in ("Eros", "Bennu"):
            plan = asteroids.best_intercept(name, jd0)
            self.assertTrue(plan is None or (plan.ok and plan.dv_total > 0),
                            name)

    def test_result_word_bands(self):
        mk = lambda dv: asteroids.InterceptPlan(
            "X", 0, 0, 100, dv, dv / 2, dv / 2,
            np.zeros(3), np.zeros(3), np.zeros(3), np.zeros(3), {}, True)
        self.assertEqual(mk(5.0).result_word(), "Easy catch!")
        self.assertEqual(mk(12.0).result_word(), "Challenging")
        self.assertEqual(mk(25.0).result_word(), "Long shot")
        nb = asteroids.InterceptPlan("X", 0, 0, 100, 0, 0, 0,
                                     np.zeros(3), np.zeros(3), np.zeros(3),
                                     np.zeros(3), {}, False)
        self.assertEqual(nb.result_word(), "No transfer found")

    def test_trajectory_path_none_safe(self):
        self.assertTrue(np.allclose(
            asteroids.intercept_trajectory_position(1.0, None, None, 0.0),
            [0, 0, 0]))
        self.assertEqual(
            asteroids.intercept_trajectory_path(1.0, None, None, 30, 1e6)
            .shape, (30, 3))


# --------------------------------------------------------------------------- constellations
class TestConstellations(unittest.TestCase):
    JD = 2460000.5

    def test_counts(self):
        self.assertEqual(constellations.constellation_names(),
                         ["GPS", "GLONASS", "BeiDou"])
        self.assertEqual(len(constellations.satellites("GPS")), 24)
        self.assertEqual(len(constellations.satellites("GLONASS")), 24)
        self.assertEqual(len(constellations.satellites("BeiDou")), 27 + 5)

    def test_facts_colors(self):
        for n in constellations.constellation_names():
            self.assertTrue(constellations.constellation_fact(n))
            self.assertTrue(constellations.color(n).startswith("#"))

    def test_shell_radii(self):
        jd = self.JD
        for name, lo, hi in (("GPS", 25000.0, 28000.0),
                             ("GLONASS", 24000.0, 27000.0)):
            for d in constellations.satellites(name):
                r = float(np.linalg.norm(constellations.stat(d, jd)))
                self.assertTrue(lo < r < hi, (d.name, r))
        for d in constellations.satellites("BeiDou"):
            if d.name.startswith("BeiDou GEO"):
                self.assertAlmostEqual(
                    float(np.linalg.norm(constellations.stat(d, jd))),
                    42164.0, delta=1.0)

    def test_raan_spacing(self):
        gps = constellations.satellites("GPS")
        raans = sorted(d.raan_deg % 360.0 for d in gps[::4])
        self.assertEqual(len(raans), 6)
        for i in range(1, 6):
            self.assertAlmostEqual((raans[i] - raans[0]) % 360.0,
                                   i * 60.0, places=3)

    def test_geo_stays_over_slot(self):
        geo = constellations.satellites("BeiDou")[-1]
        lon1 = constellations.sub(geo, self.JD)[1]
        lon2 = constellations.sub(geo, self.JD + 1.0)[1]
        self.assertLessEqual(abs(lon1 - lon2), 1.0)

    def test_sub_many_shape(self):
        rows = constellations.sub_many(constellations.satellites("GPS"),
                                       self.JD)
        self.assertEqual(rows.shape, (24, 2))
        self.assertTrue(np.all(np.abs(rows[:, 0]) <= 90.0))
        self.assertTrue(np.all(np.abs(rows[:, 1]) <= 180.0))

    def test_footprint_radius(self):
        self.assertAlmostEqual(
            constellations.footprint_radius_deg(35793.0, 0.0), 81.2, delta=1.0)
        self.assertEqual(constellations.footprint_radius_deg(35793.0, 90.0),
                         0.0)
        r5 = constellations.footprint_radius_deg(35793.0, 5.0)
        self.assertTrue(70.0 < r5 < 80.0, r5)

    def test_visibility_monotonic_with_mask(self):
        fleet = constellations.satellites("GPS")
        jd = self.JD
        low = constellations.visible(fleet, jd, 40.71, -74.01, mask_deg=5.0)
        mid = constellations.visible(fleet, jd, 40.71, -74.01, mask_deg=10.0)
        high = constellations.visible(fleet, jd, 40.71, -74.01, mask_deg=25.0)
        self.assertGreaterEqual(len(low), len(mid))
        self.assertGreaterEqual(len(mid), len(high))
        self.assertGreaterEqual(len(mid), 2)  # GPS never empty over NYC
        elevs = [e for _d, e in mid]
        self.assertEqual(elevs, sorted(elevs, reverse=True))

    def test_visible_places_rows(self):
        rows = constellations.visible_places(
            constellations.satellites("GPS"), self.JD,
            [{"name": "town", "lat": 0.0, "lon": 0.0}], mask_deg=10.0)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["count"] >= 0)
        if row["count"]:
            self.assertLessEqual(row["elev"], 90.0)


# --------------------------------------------------------------------------- satellites
class TestSatellites(unittest.TestCase):
    def test_catalog_and_states(self):
        self.assertEqual(len(satellites.CATALOG), 4)
        for d in satellites.CATALOG:
            r = satellites.propagate_eci(d, 0.0)
            self.assertTrue(np.all(np.isfinite(r)))
            self.assertGreater(np.linalg.norm(r), 6000.0)

    def test_track_positions(self):
        d = satellites.CATALOG[0]
        pts, jds = satellites.track_positions(d, 2460000.5, d.period_s * 2, 90)
        self.assertEqual(pts.shape, (90, 3))
        self.assertEqual(jds.shape, (90,))
        self.assertTrue(np.all(np.isfinite(pts)))

    def test_parse_tle_valid(self):
        l1 = ("1 25544U 98067A   24172.56859098  .00022029  00000-0 "
              "39874-3 0  9991")
        l2 = ("2 25544  51.6416 195.8944 0001839 101.5135 158.7405 "
              "15.50066165447066")
        prop = satellites.parse_tle(l1, l2)
        self.assertIsNotNone(prop)
        r = prop.eci(prop.epoch_jd + 0.25)
        self.assertIsNotNone(r)
        self.assertTrue(6550.0 < np.linalg.norm(r) < 6900.0,
                        np.linalg.norm(r))

    def test_parse_tle_invalid(self):
        # sgp4 is lenient on sloppy lines: it still builds a propagator, but
        # propagating it yields no usable position (eci() is None)
        prop = satellites.parse_tle("nonsense", "also nonsense")
        self.assertIsNotNone(prop)
        self.assertIsNone(prop.eci(2461000.5))
        l1 = ("1 25544U 98067A   24172.56859098  .00022029  00000-0 "
              "39874-3 0  9991")
        prop2 = satellites.parse_tle(l1, "garbage here")
        self.assertIsNotNone(prop2)
        self.assertIsNone(prop2.eci(2461000.5))

    def test_track_positions_sgp4_shape(self):
        prop = satellites.parse_tle(
            "1 25544U 98067A   24172.56859098  .00022029  00000-0 "
            "39874-3 0  9991",
            "2 25544  51.6416 195.8944 0001839 101.5135 158.7405 "
            "15.50066165447066")
        if prop is None:
            self.skipTest("sgp4 unavailable")
        out = satellites.track_positions_sgp4(prop, prop.epoch_jd, 3600.0, 60)
        self.assertEqual(out.shape, (60, 3))
        self.assertTrue(np.all(np.isfinite(out)))

    def test_fetch_iss_tle_fails_fast(self):
        original = satellites._TLE_URL
        try:
            satellites._TLE_URL = "http://127.0.0.1:1/definitely-not-here"
            self.assertIsNone(satellites.fetch_iss_tle(timeout=1.0))
        finally:
            satellites._TLE_URL = original

    def test_refresh_iss_background_failure(self):
        original = satellites._TLE_URL
        got = {}
        try:
            satellites._TLE_URL = "http://127.0.0.1:1/definitely-not-here"
            th = satellites.refresh_iss(
                lambda prop, src: got.update(prop=prop, src=src))
            th.join(timeout=10.0)
            self.assertFalse(th.is_alive())
            self.assertIsNone(got["prop"])
            self.assertEqual(got["src"], "CelesTrak live TLE")
        finally:
            satellites._TLE_URL = original

    def test_find_passes_structure(self):
        d = satellites.CATALOG[0]
        passes = satellites.find_passes(d, 2461000.0, 51.51, -0.13,
                                        horizon_deg=10.0, span_hours=36.0)
        self.assertGreaterEqual(len(passes), 1)
        rise = [p["rise_jd"] for p in passes]
        self.assertEqual(rise, sorted(rise))
        for p in passes:
            self.assertTrue(p["rise_jd"] <= p["max_jd"] < p["set_jd"])
            self.assertTrue(10.0 <= p["max_elev"] <= 90.0)

    def test_higher_horizon_never_more_passes(self):
        d = satellites.CATALOG[0]
        lo = satellites.find_passes(d, 2461000.0, 51.51, -0.13,
                                    horizon_deg=5.0, span_hours=36.0)
        hi = satellites.find_passes(d, 2461000.0, 51.51, -0.13,
                                    horizon_deg=30.0, span_hours=36.0)
        self.assertLessEqual(len(hi), len(lo))

    def test_find_passes_tle_backend(self):
        prop = satellites.parse_tle(
            "1 25544U 98067A   24172.56859098  .00022029  00000-0 "
            "39874-3 0  9991",
            "2 25544  51.6416 195.8944 0001839 101.5135 158.7405 "
            "15.50066165447066")
        if prop is None:
            self.skipTest("sgp4 unavailable")
        passes = satellites.find_passes(prop, prop.epoch_jd, 51.51, -0.13,
                                        horizon_deg=10.0, span_hours=24.0,
                                        is_tle=True)
        for p in passes:
            self.assertTrue(p["set_jd"] > p["rise_jd"])

    def test_format_pass_time(self):
        import re
        out = satellites.format_pass_time(2461000.0)
        self.assertRegex(out, r"^[A-Z][a-z]{2} \d{2} \d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)