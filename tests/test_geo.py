"""Edge-case suite for the geo layer: spherical-Earth helpers, the land
raster, and the shared places store (with its JSON files)."""

import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    from tests.helpers import isolated_env
except ImportError:
    from helpers import isolated_env

from spacekids.geo import earth, world, locations


class TestEarth(unittest.TestCase):
    def test_wrap_lon(self):
        self.assertAlmostEqual(earth.wrap_lon(190.0), -170.0)
        self.assertAlmostEqual(earth.wrap_lon(-190.0), 170.0)
        self.assertAlmostEqual(earth.wrap_lon(0.0), 0.0)
        self.assertAlmostEqual(earth.wrap_lon(180.0), -180.0)
        for v in (-190, -200, 360, 540, 179, -179, 0):
            self.assertTrue(-180.0 <= earth.wrap_lon(v) <= 180.0)

    def test_subpoint_equatorial_at_any_jd(self):
        lat, lon = earth.subpoint([7000.0, 0.0, 0.0], 2460000.5)
        self.assertAlmostEqual(lat, 0.0, places=9)
        self.assertTrue(-180.0 <= lon <= 180.0)
        # same ECI vector maps to a different longitude as time passes
        lat2, lon2 = earth.subpoint([7000.0, 0.0, 0.0], 2460001.5)
        self.assertAlmostEqual(lat2, 0.0, places=9)
        self.assertNotAlmostEqual(lon, lon2, places=4)

    def test_subpoint_pole_and_zero(self):
        lat, lon = earth.subpoint([0.0, 0.0, 6800.0], 2460000.5)
        self.assertAlmostEqual(lat, 90.0, places=9)
        self.assertTrue(math.isfinite(lon))
        self.assertEqual(earth.subpoint([0.0, 0.0, 0.0], 2460000.5),
                         (0.0, 0.0))

    def test_subsatellite_lat_bounds(self):
        for jd in (2451545.0, 2460000.5, 2465000.0):
            for r in ([8000, 0, 0], [-8000, 0, 0], [0, -8000, 0],
                      [1000, 2000, 7000], [-5000, 6000, -1000]):
                la, lo = earth.subpoint(r, jd)
                self.assertTrue(-90.0 <= la <= 90.0)
                self.assertTrue(-180.0 <= lo <= 180.0)

    def test_observer_ecef(self):
        r0 = earth.observer_ecef(0.0, 0.0)
        self.assertTrue(np.allclose(r0, [earth.R_EARTH, 0, 0]))
        rp = earth.observer_ecef(90.0, 0.0)
        self.assertTrue(np.allclose(rp, [0, 0, earth.R_EARTH],
                                    atol=1e-6))
        for la, lo in ((10.0, 20.0), (-33.0, 151.0), (89.0, 179.0)):
            v = earth.observer_ecef(la, lo, alt_km=0.5)
            self.assertAlmostEqual(np.linalg.norm(v),
                                   earth.R_EARTH + 0.5, places=6)

    def test_topocentric_zenith(self):
        obs = earth.observer_ecef(0.0, 0.0)
        sat = np.array([earth.R_EARTH + 400.0, 0.0, 0.0])
        az, el, d = earth.topocentric(sat, obs)
        self.assertAlmostEqual(el, 90.0, places=6)
        self.assertAlmostEqual(d, 400.0, places=6)
        self.assertAlmostEqual(az, 0.0, places=6)

    def test_elevation_consistent(self):
        obs = earth.observer_ecef(0.0, 0.0)
        self.assertAlmostEqual(
            earth.elevation_deg(
                np.array([earth.R_EARTH + 400.0, 0.0, 0.0]), obs),
            90.0, places=6)
        # a satellite at the same altitude across the globe is far below
        below = earth.elevation_deg(
            np.array([-(earth.R_EARTH + 400.0), 0.0, 0.0]), obs)
        self.assertLess(below, 0.0)

    def test_topocentric_degenerate(self):
        obs = earth.observer_ecef(30.0, 40.0)
        self.assertEqual(earth.topocentric(obs, obs), (0.0, 0.0, 0.0))

    def test_ground_distance(self):
        self.assertAlmostEqual(
            earth.ground_distance_km(0, 0, 0, 0), 0.0, places=9)
        self.assertAlmostEqual(
            earth.ground_distance_km(0, 0, 0, 1), 111.19, delta=0.5)
        self.assertAlmostEqual(
            earth.ground_distance_km(0, 0, 0, 180),
            math.pi * earth.R_EARTH, delta=1.0)
        dlat = earth.ground_distance_km(0, 0, 90, 0)
        self.assertAlmostEqual(dlat, math.pi / 2 * earth.R_EARTH, delta=1.0)

    def test_ring_points(self):
        for center in ((0.0, 0.0), (51.5, -0.1), (80.0, 160.0)):
            lats, lons = earth.ring_points(center[0], center[1], 12.0, n=48)
            self.assertEqual(len(lats), 48)
            self.assertTrue(np.all(np.abs(lats) <= 90.0))
            self.assertTrue(np.all(np.abs(lons) <= 180.0))


class TestWorldRaster(unittest.TestCase):
    def test_dimensions(self):
        self.assertEqual(world.W, 360)
        self.assertEqual(world.H, 180)

    def test_known_land(self):
        mask = world.land_mask()
        self.assertEqual(mask.shape, (world.H, world.W))
        self.assertEqual(mask.dtype, bool)
        x, y = world.latlon_to_cell(0.0, 20.0)   # west Africa
        self.assertTrue(mask[y, x], (x, y))
        x, y = world.latlon_to_cell(0.0, -150.0)  # mid-Pacific
        self.assertFalse(mask[y, x], (x, y))

    def test_latlon_to_cell_bounds(self):
        self.assertEqual(world.latlon_to_cell(90.0, -180.0), (0, 0))
        self.assertEqual(world.latlon_to_cell(-90.0, 180.0), (world.W - 1,
                                                              world.H - 1))
        for la, lo in ((10, 30), (-33, 151), (51, -0.1), (0, 0)):
            x, y = world.latlon_to_cell(la, lo)
            self.assertTrue(0 <= x < world.W)
            self.assertTrue(0 <= y < world.H)

    def test_land_cells(self):
        cells = world.land_cells()
        self.assertGreater(len(cells), 1000)
        for x, y in cells[:50]:
            self.assertTrue(0 <= x < world.W)
            self.assertTrue(0 <= y < world.H)


class TestLocations(unittest.TestCase):
    def test_builtins(self):
        self.assertEqual(len(locations.BUILTIN), 12)
        for rec in locations.BUILTIN:
            self.assertFalse(rec["user"])
            self.assertTrue(-90.0 <= rec["lat"] <= 90.0)
            self.assertTrue(-180.0 <= rec["lon"] <= 180.0)
        self.assertIsNotNone(locations.find("London"))

    def test_crud(self):
        with isolated_env():
            locations.add_location("Grandma's", 34.05, -118.24)
            rec = locations.find("Grandma's")
            self.assertIsNotNone(rec)
            self.assertTrue(rec["user"])
            self.assertAlmostEqual(rec["lat"], 34.05, places=4)
            self.assertIn("Grandma's", locations.user_names())
            locations.remove_location("Grandma's")
            self.assertIsNone(locations.find("Grandma's"))
            self.assertNotIn("Grandma's", locations.user_names())

    def test_add_updates_in_place(self):
        with isolated_env():
            locations.add_location("Base", 10.0, 20.0)
            locations.add_location("Base", 11.0, 21.0)
            user = [r for r in locations.all_locations() if r["user"]]
            self.assertEqual(len(user), 1)
            self.assertAlmostEqual(user[0]["lat"], 11.0, places=4)

    def test_lat_lon_rounding(self):
        with isolated_env():
            locations.add_location("X", 34.049999, -118.244999)
            rec = locations.find("X")
            self.assertAlmostEqual(rec["lat"], 34.05, places=4)
            self.assertAlmostEqual(rec["lon"], -118.245, places=4)

    def test_add_rejects_bad_values(self):
        with isolated_env():
            for bad in (("", 0, 0), ("   ", 0, 0),
                        ("x", 91, 0), ("x", -91, 0),
                        ("x", 0, 181), ("x", 0, -181),
                        ("x", "abc", 0), ("x", 0, None)):
                with self.assertRaises((ValueError, TypeError),
                                       msg=str(bad)):
                    locations.add_location(*bad)
            self.assertEqual(locations.user_names(), [])

    def test_permissive_bounds(self):
        with isolated_env():
            locations.add_location("N pole", 90.0, 0.0)
            locations.add_location("Dateline", 0.0, 180.0)
            self.assertEqual(len(locations.user_names()), 2)

    def test_remove_missing_silent(self):
        with isolated_env():
            locations.remove_location("Nobody Home")  # must not raise
            self.assertEqual(locations.user_names(), [])

    def test_corrupt_file_tolerated(self):
        with isolated_env() as tmp:
            paths = locations._store_path()
            with open(paths, "w", encoding="utf-8") as fh:
                fh.write("{ not json !")
            self.assertEqual(locations.all_locations(), locations.BUILTIN)
            with open(paths, "w", encoding="utf-8") as fh:
                json.dump([{"name": 42, "lat": "xx", "lon": []},
                           {"name": "ok", "lat": 1, "lon": 2}], fh)
            recs = locations.all_locations()
            self.assertEqual(len(recs), len(locations.BUILTIN) + 1)
            self.assertIsNotNone(locations.find("ok"))

    def test_clean_filters_invalid(self):
        with isolated_env():
            locations.add_location("A", 1.0, 1.0)
            locations.add_location("B", 2.0, 2.0)
            paths = locations._store_path()
            raw = [{"name": "A", "lat": 999, "lon": 1},   # latitude out of range
                   {"name": "  ", "lat": 2, "lon": 2}]   # blank name
            with open(paths, "w", encoding="utf-8") as fh:
                json.dump(raw, fh)
            self.assertEqual(locations.user_names(), [])

    def test_env_override_redirects_store(self):
        saved = (os.environ.get("SPACEKIDS_LOCATIONS"),
                 os.environ.get("SPACEKIDS_SETTINGS"))
        try:
            with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
                os.environ["SPACEKIDS_LOCATIONS"] = os.path.join(a, "one.json")
                locations.add_location("One", 1, 1)
                os.environ["SPACEKIDS_LOCATIONS"] = os.path.join(b, "two.json")
                self.assertEqual(locations.user_names(), [])
                os.environ["SPACEKIDS_LOCATIONS"] = os.path.join(a, "one.json")
                self.assertIn("One", locations.user_names())
        finally:
            for var in ("SPACEKIDS_LOCATIONS", "SPACEKIDS_SETTINGS"):
                if saved[0 if var == "SPACEKIDS_LOCATIONS" else 1] is None:
                    os.environ.pop(var, None)
                else:
                    os.environ[var] = saved[0 if var == "SPACEKIDS_LOCATIONS"
                                            else 1]


if __name__ == "__main__":
    unittest.main(verbosity=2)