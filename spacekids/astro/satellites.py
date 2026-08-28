"""ISS Spotter - real satellites, ground tracks and sky passes over a town.

Two propagation back-ends:

* a small catalog of popular satellites with their approximate mean elements
  (instant, fully offline),
* a live TLE refresh from CelesTrak when the computer is online, propagated
  properly with SGP4 via the ``sgp4`` package.

The page picks whichever is newest; both go through a common
``(jd -> sub-satellite point + ECEF)`` interface so nothing else cares.
"""

import datetime
import math
import threading

import numpy as np

from .core import gmst_deg, julian_date, mu_km3s2
from .orbitlab import OrbitDesign
from ..geo.earth import (R_EARTH, elevation_deg, ecef_of,
                         observer_ecef, subpoint, wrap_lon)

K_EARTH = mu_km3s2("earth")

# --------------------------------------------------------------------------- catalog
CATALOG = [
    OrbitDesign("ISS (Zarya)", 6786.0, 0.0005, 51.64),
    OrbitDesign("Hubble Space Telescope", 6922.0, 0.0002, 28.47),
    OrbitDesign("GPS Galaxy 15", 26560.0, 0.004, 55.0),
    OrbitDesign("NOAA-20 Weather", 7306.0, 0.0001, 98.7),
]

CITIES = [
    ("London", 51.51, -0.13),
    ("New York", 40.71, -74.01),
    ("Tokyo", 35.68, 139.69),
    ("Sydney", -33.87, 151.21),
    ("Cape Town", -33.92, 18.42),
    ("São Paulo", -23.55, -46.63),
    ("Riyadh", 24.71, 46.68),
    ("Beijing", 39.90, 116.41),
    ("Cairo", 30.04, 31.24),
    ("Lagos", 6.52, 3.38),
    ("Buenos Aires", -34.60, -58.38),
    ("Delhi", 28.61, 77.21),
]

TLE_SOURCES = {
    "ISS (Zarya)": "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
}


# --------------------------------------------------------------------------- propagation
def propagate_eci(design, dt_from_epoch_s):
    """ECI position (km) of a catalog satellite dt seconds after its epoch."""
    return design.state_at(float(dt_from_epoch_s))[0]


def track_positions(design, jd_start, duration_s, n=720):
    """ECI positions of a catalog satellite sampled over ``duration_s``."""
    jds = jd_start + np.linspace(0.0, float(duration_s), n) / 86400.0
    out = np.empty((n, 3))
    for i, dt in enumerate(np.linspace(0.0, float(duration_s), n)):
        out[i] = propagate_eci(design, dt)
    return out, jds


# --------------------------------------------------------------------------- SGP4 (live TLE)
class _Sgp4Propagator:
    def __init__(self, line1, line2):
        from sgp4.api import Satrec
        self.sat = Satrec.twoline2rv(line1, line2)
        self.epoch_jd = self.sat.jdsatepoch

    def eci(self, jd):
        from sgp4.api import jday
        fr = (jd - 0.5) % 1.0
        jd0 = jd - 0.5 - fr + 0.5
        e, _r, v = self.sat.sgp4(jd0, fr)
        if e > 0:
            return None
        return np.array(_r, dtype=float)  # sgp4 already returns km


_sgp4_cache = None
_tle_lock = threading.Lock()
_TLE_URL = TLE_SOURCES["ISS (Zarya)"]


def fetch_iss_tle(timeout=8.0):
    """Fetch a live ISS TLE; returns (line1, line2) or None.

    Called from a worker thread; the network failure path is silent on purpose.
    """
    try:
        import urllib.request
        with urllib.request.urlopen(_TLE_URL, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "replace")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            if ln.startswith("1 "):
                return ln.strip(), lines[i + 1].strip()
    except Exception:
        return None
    return None


def parse_tle(line1, line2):
    """Try a real SGP4 propagator for a TLE, else None."""
    try:
        return _Sgp4Propagator(line1, line2)
    except Exception:
        return None


def refresh_iss(slot_update):
    """Fetch a fresh ISS TLE in a background thread and run ``slot_update``.

    ``slot_update(prop, source_name)`` is called with ``None`` on failure.
    """
    def work():
        try:
            tle = fetch_iss_tle()
            prop = parse_tle(*tle) if tle else None
            slot_update(prop, "CelesTrak live TLE")
        except Exception:
            slot_update(None, "catalog")
    th = threading.Thread(target=work, daemon=True)
    th.start()
    return th


def track_positions_sgp4(prop, jd_start, duration_s, n=720):
    """ECI positions (SGP4) sampled every ``duration_s/n`` seconds."""
    out = np.empty((n, 3))
    for i in range(n):
        jd = jd_start + duration_s * i / max(1, n - 1) / 86400.0
        r = prop.eci(jd)
        out[i] = r if r is not None else np.zeros(3)
    return out


# --------------------------------------------------------------------------- passes over a town
def find_passes(design_or_prop, jd_start, city_lat, city_lon,
                horizon_deg=10.0, span_hours=48.0, step_s=60, is_tle=False):
    """Find visible passes of a satellite over a town in the next day(s).

    Returns a list of dicts sorted by rise time:
      rise_jd, max_jd, set_jd, max_elev.
    """
    obs = observer_ecef(city_lat, city_lon)
    count = int(span_hours * 3600.0 / step_s)
    rises = []

    def _close(cur, best):
        """Finalise one pass, guaranteeing rise <= max < set (a pass always
        spans at least one step, so the UI never shows a negative length)."""
        cur["set_jd"] = max(cur.get("set_jd") or cur["max_jd"],
                            cur["max_jd"] + step_s / 86400.0)
        if cur["max_elev"] >= horizon_deg:
            rises.append(cur)

    cur = None
    best = {"el": -90.0}
    for i in range(count):
        jd = jd_start + i * step_s / 86400.0
        if is_tle:
            r = design_or_prop.eci(jd)
        else:
            r = propagate_eci(design_or_prop, (i * step_s))
            jd = jd_start + i * step_s / 86400.0
        if r is None:
            continue
        el = elevation_deg(ecef_of(r, jd), obs)
        if el >= horizon_deg:
            if cur is None:
                cur = {"rise_jd": jd, "max_jd": jd, "set_jd": None,
                       "max_elev": -90.0}
            if el > best["el"]:
                best["el"] = el
                cur["max_jd"] = jd
                cur["max_elev"] = el
        else:
            if cur is not None:
                cur["set_jd"] = jd - step_s / 86400.0
                _close(cur, best)
                cur = None
                best = {"el": -90.0}
    if cur is not None:
        cur["set_jd"] = jd_start + count * step_s / 86400.0
        _close(cur, best)
    rises.sort(key=lambda p: p["rise_jd"])
    return rises[:12]


def format_pass_time(jd):
    """Local friendly string for a JD (naive display, DST-free)."""
    sec = (jd - julian_date(datetime.datetime(1970, 1, 1))) * 86400.0
    return (datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=sec)) \
        .strftime("%a %d %H:%M")