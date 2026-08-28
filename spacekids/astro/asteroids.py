"""Catch the Asteroid! - intercepting a real NEO with poliastro's Lambert.

The kid picks a launch day; poliastro's Izzo Lambert solver finds the exact
``delta-v`` needed to fly from Earth to where the asteroid will be after the
chosen flight time.  The asteroid's orbital shape is real (textbook elements
for Eros, Bennu, Apophis, Didymos); the calendar phase is illustrative, and
the page says so.
"""

import math
from dataclasses import dataclass

import numpy as np

from .core import best_lambert, julian_date
from .kepler import elements_from_state, integrate_state, norm, propagate_elements
from .bodies import MU_SUN, T_REF, state as planet_state

AU = 149597870.691

# approximate J2000 ecliptic elements; M0 is illustrative (see module docstring)
_ASTEROIDS = {
    "Eros": dict(a_au=1.458, e=0.223, i=10.83, node=304.4, argp=178.8,
                 M0=160.0, diameter_km=16.8, color="#e6b566",
                 fact="Eros was visited by the NEAR spacecraft in 2000."),
    "Bennu": dict(a_au=1.126, e=0.204, i=6.03, node=2.06, argp=66.22,
                  M0=315.0, diameter_km=0.49, color="#c98aff",
                  fact="Bennu is NASA's OSIRIS-REx asteroid, being studied now."),
    "Apophis": dict(a_au=0.9227, e=0.1915, i=3.33, node=204.45, argp=126.4,
                    M0=70.0, diameter_km=0.37, color="#ff8a80",
                    fact="Apophis swings very close to Earth in 2029!"),
    "Didymos": dict(a_au=1.6443, e=0.3838, i=3.41, node=73.2, argp=319.3,
                    M0=235.0, diameter_km=0.78, color="#8fd3ff",
                    fact="NASA crashed a probe into Didymos in 2022 (DART)."),
}


def asteroid_names():
    return list(_ASTEROIDS.keys())


def asteroid_fact(name):
    return _ASTEROIDS[name]["fact"]


@dataclass
class InterceptPlan:
    asteroid: str
    launch_jd: float
    arrival_jd: float
    tof_days: float
    dv_total: float    # km/s (departure + arrival burns)
    dv_depart: float
    dv_arrival: float
    r0: np.ndarray     # Earth at launch
    r1: np.ndarray     # asteroid at arrival
    v0: np.ndarray     # transfer velocity at launch
    v1: np.ndarray     # transfer velocity at arrival
    elements: dict
    ok: bool

    def result_word(self):
        if not self.ok:
            return "No transfer found"
        if self.dv_total < 9.0:
            return "Easy catch!"
        if self.dv_total < 18.0:
            return "Challenging"
        return "Long shot"


def _elements(name):
    rec = _ASTEROIDS[name]
    return dict(
        k=MU_SUN,
        a=rec["a_au"] * AU,
        e=rec["e"],
        i=rec["i"],
        raan=rec["node"],
        argp=rec["argp"],
        nu0=_nu_from_M0(rec),
    )


def _nu_from_M0(rec):
    from .kepler import nu_from_M
    return nu_from_M(rec["M0"], rec["e"])


def asteroid_position(name, jd):
    """Heliocentric position (km) of the asteroid at JD ``jd`` (illustrative)."""
    el = _elements(name)
    r, _v = propagate_elements(el["k"], el["a"], el["e"], el["i"],
                               el["raan"], el["argp"], el["nu0"],
                               (jd - T_REF) * 86400.0)
    return r


def asteroid_path(name, jd0, days, n=200):
    """Sample the asteroid's orbit from jd0 for ``days`` days, (n,3) km array."""
    el = _elements(name)
    pts = np.empty((n, 3))
    for i in range(n):
        jd = jd0 + days * i / max(1, n - 1)
        pts[i] = asteroid_position(name, jd)
    return pts


def intercept_at(name, jd_launch, tof_days):
    """Lambert intercept for one flight time; returns an InterceptPlan."""
    r0, v_earth = planet_state("Earth", jd_launch)
    r0 = np.asarray(r0, float).copy()
    v_earth = np.asarray(v_earth, float)
    arrival_jd = jd_launch + tof_days
    r1 = np.asarray(asteroid_position(name, arrival_jd), float)
    v_ast = _asteroid_velocity(name, arrival_jd)

    tof_s = tof_days * 86400.0
    pair = best_lambert(MU_SUN, r0, r1, tof_s, v_depart=v_earth, v_arrival=v_ast)
    if pair is None:
        return InterceptPlan(name, jd_launch, arrival_jd, tof_days,
                             0, 0, 0, r0, r1, np.zeros(3), np.zeros(3), {}, False)
    v0, v1 = pair
    dv0 = norm(v0 - v_earth)
    dv1 = norm(v_ast - v1)
    el = elements_from_state(MU_SUN, r0, v0)
    return InterceptPlan(name, jd_launch, arrival_jd, tof_days,
                         dv0 + dv1, dv0, dv1, r0, r1, v0, v1, el, True)


def _asteroid_velocity(name, jd):
    el = _elements(name)
    return propagate_elements(el["k"], el["a"], el["e"], el["i"],
                              el["raan"], el["argp"], el["nu0"],
                              (jd - T_REF) * 86400.0)[1]


def best_intercept(name, jd_launch, tof_min=30.0, tof_max=400.0, step=10.0,
                   span_days=15.0, day_step=5.0):
    """Scan launch days and flight times for the cheapest intercept.

    Real intercept plans pitch the launch day as well as the burn, so we let
    the window slide a little around the picked date.
    """
    best = None
    jd = jd_launch - span_days
    while jd <= jd_launch + span_days:
        t = tof_min
        while t <= tof_max:
            p = intercept_at(name, jd, t)
            if p.ok and (best is None or p.dv_total < best.dv_total):
                best = p
            t += step
        jd += day_step
    return best


def intercept_trajectory_position(k, r0, v0, t_since_launch_s):
    """Probe position (km) t seconds after launch; RK4, handles any conic."""
    if r0 is None or v0 is None:
        return np.zeros(3)
    return integrate_state(k, np.asarray(r0, float), np.asarray(v0, float),
                           np.array([t_since_launch_s]))[0]


def intercept_trajectory_path(k, r0, v0, n, tof_s):
    """Whole intercept path as n sampled positions for the drawn arc."""
    if r0 is None or v0 is None:
        return np.zeros((n, 3))
    ts = np.linspace(0.0, tof_s, n)
    return integrate_state(k, np.asarray(r0, float), np.asarray(v0, float), ts)