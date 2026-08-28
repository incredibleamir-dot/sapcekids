"""Small solar-system helper: mean elements and heliocentric positions.

A kids' app needs stable, predictable planet motion - real ephemeris files
(SPICE) would download gigabyte datasets on first run.  We instead use JPL's
classic *mean orbital elements (J2000)* for the planets: exactly the numbers
printed in every textbook, propagated with the Kepler solver in
``spacekids.astro.kepler``.  Good to a fraction of a degree over a kid's
lifetime, honest, and fast enough to animate at 60 fps.
"""

import math

import numpy as np

from .kepler import (mean_motion, propagate_elements, period_s)

# --------------------------------------------------------------------------- planet records
# a in km, angles in degrees, T = reference Julian date of the mean longitude
_PLANETS = {
    "Earth": dict(a_au=1.00000011, e=0.01671022, i=0.00005,
                  L=100.46435, peri=102.94719, node=174.873,
                  color="#3f86e0", radius_km=6371, ring=False),
    "Mars": dict(a_au=1.52371034, e=0.09339410, i=1.84969142,
                 L=355.45332, peri=336.04084, node=49.55953891,
                 color="#e2623a", radius_km=3390, ring=False),
    "Venus": dict(a_au=0.72332982, e=0.00677191, i=3.39467605,
                  L=181.97973, peri=131.60270, node=76.67984,
                  color="#ffd98a", radius_km=6052, ring=False),
    "Mercury": dict(a_au=0.38709893, e=0.20563069, i=7.00487,
                    L=252.25084, peri=77.45645, node=48.33167,
                    color="#b9c3cf", radius_km=2440, ring=False),
}

AU = 149597870.691  # km
T_REF = 2451545.0   # J2000.0

MU_SUN = 1.32712440018e11  # km^3/s^2

for _name, _rec in _PLANETS.items():
    _rec["a"] = _rec["a_au"] * AU
    _rec["raan"] = _rec["node"]
    _rec["argp"] = (_rec["peri"] - _rec["node"]) % 360.0
    _rec["nu0"] = (_rec["L"] - _rec["peri"]) % 360.0
    _rec["period_days"] = period_s(MU_SUN, _rec["a"]) / 86400.0
    _rec["n"] = mean_motion(MU_SUN, _rec["a"])  # rad/s
    # mean daily motion in degrees/day for building M(jd)
    _rec["n_deg_day"] = math.degrees(_rec["n"]) * 86400.0


def planets():
    """Ordered planet names (small inner-system subset we can draw well)."""
    return ["Mercury", "Venus", "Earth", "Mars"]


def planet(name):
    """Return the mutable record dict for a planet name."""
    return _PLANETS[name]


def position(name, jd):
    """Heliocentric inertial position (km, xyz) of a planet at JD ``jd``."""
    return state(name, jd)[0]


def state(name, jd):
    """(r, v) heliocentric inertial state of a planet at JD ``jd`` (km, km/s)."""
    rec = _PLANETS[name]
    k = MU_SUN
    # mean anomaly driven by mean motion from the reference date
    M = (rec["L"] - rec["peri"]) + rec["n_deg_day"] * (jd - T_REF)
    M %= 360.0
    # back out true anomaly from M with the planet's eccentricity
    from .kepler import nu_from_M
    nu = nu_from_M(M, rec["e"])
    return propagate_elements(k, rec["a"], rec["e"], rec["i"],
                              rec["raan"], rec["argp"], nu, 0.0)


def path(name, jd0, days, n=180):
    """Sample a planet path from jd0 for ``days`` days, (n, 3) array in km."""
    rec = _PLANETS[name]
    from .kepler import nu_from_M
    pts = np.empty((n, 3))
    for i in range(n):
        jd = jd0 + days * i / max(1, n - 1)
        M = ((rec["L"] - rec["peri"]) + rec["n_deg_day"] * (jd - T_REF)) % 360.0
        nu = nu_from_M(M, rec["e"])
        r, _ = propagate_elements(MU_SUN, rec["a"], rec["e"], rec["i"],
                                  rec["raan"], rec["argp"], nu, 0.0)
        pts[i] = r
    return pts