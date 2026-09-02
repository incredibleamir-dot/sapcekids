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
# Classic JPL mean orbital elements (J2000 ecliptic).
_PLANETS = {
    "Mercury": dict(a_au=0.38709893, e=0.20563069, i=7.00487,
                    L=252.25084, peri=77.45645, node=48.33167,
                    color="#b9c3cf", radius_km=2440, ring=False),
    "Venus": dict(a_au=0.72332982, e=0.00677191, i=3.39467605,
                  L=181.97973, peri=131.60270, node=76.67984,
                  color="#ffd98a", radius_km=6052, ring=False),
    "Earth": dict(a_au=1.00000011, e=0.01671022, i=0.00005,
                  L=100.46435, peri=102.94719, node=174.873,
                  color="#3f86e0", radius_km=6371, ring=False),
    "Mars": dict(a_au=1.52371034, e=0.09339410, i=1.84969142,
                 L=355.45332, peri=336.04084, node=49.55953891,
                 color="#e2623a", radius_km=3390, ring=False),
    "Jupiter": dict(a_au=5.20288700, e=0.04838624, i=1.30439695,
                    L=34.39644051, peri=14.72847983, node=100.47390909,
                    color="#e0b28a", radius_km=69911, ring=False),
    "Saturn": dict(a_au=9.53667594, e=0.05386179, i=2.48599187,
                   L=49.95424423, peri=92.59887831, node=113.66242448,
                   color="#f0d48a", radius_km=58232, ring=True),
    "Uranus": dict(a_au=19.18916464, e=0.04725744, i=0.77263783,
                   L=313.23810451, peri=170.95427630, node=74.01692503,
                   color="#8fd3e8", radius_km=25362, ring=False),
    "Neptune": dict(a_au=30.06992276, e=0.00859048, i=1.77004347,
                    L=304.88003433, peri=44.96476227, node=131.78422574,
                    color="#5b8def", radius_km=24622, ring=False),
}

# --------------------------------------------------------------------------- moon
# The Moon orbits Earth (not the Sun), so it is handled separately from the
# planets above.  radius and period are real; its phase around Earth is
# driven from the classic mean longitude/motion so `position()`/`path()`
# work for display and for the lunar transfer logic.
MOON = dict(earth_radius_au=1.00000011,
            a_km=384400.0, e=0.0549, i=5.145, node=125.08, argp=318.15,
            L=218.316, peri=83.353, period_days=27.321661,
            color="#d8d8e8", radius_km=1737.1)

AU = 149597870.691  # km
T_REF = 2451545.0   # J2000.0

MU_SUN = 1.32712440018e11  # km^3/s^2
MU_EARTH = 3.986004418e5   # km^3/s^2

for _name, _rec in _PLANETS.items():
    _rec["a"] = _rec["a_au"] * AU
    _rec["raan"] = _rec["node"]
    _rec["argp"] = (_rec["peri"] - _rec["node"]) % 360.0
    _rec["nu0"] = (_rec["L"] - _rec["peri"]) % 360.0
    _rec["period_days"] = period_s(MU_SUN, _rec["a"]) / 86400.0
    _rec["n"] = mean_motion(MU_SUN, _rec["a"])  # rad/s
    # mean daily motion in degrees/day for building M(jd)
    _rec["n_deg_day"] = math.degrees(_rec["n"]) * 86400.0


def planets(full=False):
    """Ordered planet names.

    With ``full=False`` returns the inner-system subset used by the classic
    2-D scenes; with ``full=True`` returns all eight planets.
    """
    if full:
        return list(_PLANETS.keys())
    return ["Mercury", "Venus", "Earth", "Mars"]


def target_bodies():
    """Names selectable as interplanetary targets (all 8 planets + Moon)."""
    return list(_PLANETS.keys()) + ["Moon"]


def planet(name):
    """Return the mutable record dict for a planet name."""
    return _PLANETS[name]


def position(name, jd):
    """Heliocentric inertial position (km, xyz) of a body at JD ``jd``.

    Planets are heliocentric; the Moon is Earth-centred (returned in
    heliocentric frame = Earth helio + lunar geocentric offset).
    """
    return state(name, jd)[0]


def state(name, jd):
    """(r, v) inertial state of a body at JD ``jd`` (km, km/s).

    For planets this is heliocentric.  For the Moon it is the lunar
    geocentric state added to Earth's heliocentric state, so it is
    consistent in a heliocentric frame.
    """
    if name == "Moon":
        return _moon_state(jd)
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


def _moon_state(jd):
    """Moon geocentric state (km, km/s) added to Earth's heliocentric state."""
    m_r, m_v = _moon_geo_state(jd)
    e_r, e_v = state("Earth", jd)
    return e_r + m_r, e_v + m_v


def _moon_geo_state(jd):
    """Moon geocentric position/velocity about Earth (km, km/s).

    The inertial geocentric frame uses the J2000 ecliptic (Moon's mean
    elements), so the magnitude of ``m_r`` is ~384,400 km and a Lambert
    transfer from low Earth orbit can target it directly.
    """
    rec = MOON
    n_deg_day = math.degrees(mean_motion(MU_EARTH, rec["a_km"])) * 86400.0
    M = (rec["L"] - rec["peri"]) + n_deg_day * (jd - T_REF)
    M %= 360.0
    from .kepler import nu_from_M
    nu = nu_from_M(M, rec["e"])
    return propagate_elements(MU_EARTH, rec["a_km"], rec["e"], rec["i"],
                              rec["node"], rec["argp"], nu, 0.0)


def moon_geo_state(jd):
    """Public geocentric lunar state for lunar-transfer calculations."""
    return _moon_geo_state(jd)


def moon_geo_position(jd):
    """Public geocentric lunar position (km, xyz) about Earth."""
    return _moon_geo_state(jd)[0]


def path(name, jd0, days, n=180):
    """Sample a body path from jd0 for ``days`` days, (n, 3) array in km."""
    pts = np.empty((n, 3))
    for i in range(n):
        jd = jd0 + days * i / max(1, n - 1)
        pts[i] = position(name, jd)
    return pts