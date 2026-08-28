"""Rocket to Mars - mission planning.

The kid picks a launch date.  poliastro's Izzo Lambert solver takes the
spacecraft from where Earth is on launch day to where Mars is after the
classic Hohmann transfer time.  If Mars is lined up nicely the resulting
``delta-v`` is small ("easy mission"), otherwise it is big ("too much
rocket!"), which is exactly how real launch windows work.
"""

import math
from dataclasses import dataclass

import numpy as np

from .core import julian_date, best_lambert
from .kepler import elements_from_state, integrate_state, norm
from .bodies import AU, MU_SUN, position, state as planet_state


@dataclass
class TransferPlan:
    """A computed Earth->Mars transfer for one launch date."""
    launch_jd: float
    arrival_jd: float
    tof_days: float
    dv_depart: float      # km/s, burn needed to leave Earth on the transfer
    dv_arrival: float     # km/s, burn needed to slow down at Mars
    dv_total: float       # km/s
    r0: np.ndarray        # Earth position at launch (km)
    r1: np.ndarray        # Mars position at arrival (km)
    v_transfer0: np.ndarray   # spacecraft velocity right after launch burn (km/s)
    v_transfer1: np.ndarray   # spacecraft velocity arriving at Mars (km/s)
    elements: dict        # ecliptic classical elements of the transfer orbit
    ok: bool              # False when the geometry gives no sane transfer


def hohmann_baseline():
    """Textbook Earth->Mars Hohmann numbers (circular, coplanar approx)."""
    a1 = AU
    a2 = 1.52371034 * AU
    k = MU_SUN
    a_t = (a1 + a2) / 2.0
    e_t = (a2 - a1) / (a2 + a1)
    v1 = math.sqrt(k / a1)
    v2 = math.sqrt(k / a2)
    v_pe = math.sqrt(k * (2.0 / a1 - 1.0 / a_t))
    v_ap = math.sqrt(k * (2.0 / a2 - 1.0 / a_t))
    tof_s = math.pi * math.sqrt(a_t ** 3 / k)
    return {
        "a_t": a_t, "e_t": e_t,
        "tof_days": tof_s / 86400.0,
        "dv1": v_pe - v1, "dv2": v2 - v_ap,
        "dv_total": (v_pe - v1) + (v2 - v_ap),
    }


def _single_plan(jd_launch, tof_s):
    """Lambert transfer for one launch JD with a fixed transfer time."""
    r0, v_e = planet_state("Earth", jd_launch)
    r0 = np.asarray(r0, float).copy()
    v_e = np.asarray(v_e, float)
    arrival_jd = jd_launch + tof_s / 86400.0
    r1, v_m = planet_state("Mars", arrival_jd)
    r1 = np.asarray(r1, float).copy()
    v_m = np.asarray(v_m, float)

    pair = best_lambert(MU_SUN, r0, r1, tof_s, v_depart=v_e, v_arrival=v_m)
    if pair is None:
        return TransferPlan(jd_launch, arrival_jd, tof_s / 86400.0, 0.0, 0.0,
                            0.0, r0, r1, np.zeros(3), np.zeros(3), {}, False)
    v0, v1 = pair
    dv0 = norm(v0 - v_e)
    dv1 = norm(v_m - v1)
    el = elements_from_state(MU_SUN, r0, v0)
    return TransferPlan(jd_launch, arrival_jd, tof_s / 86400.0,
                        dv0, dv1, dv0 + dv1, r0, r1, v0, v1, el, True)


def plan_at_tof(launch_dt, tof_days):
    """One Lambert transfer for a chosen launch day and flight time.

    Used by the page's Experiment sliders so a kid can trade flight time
    against rocket power and see the cost curve live.
    """
    jd0 = julian_date(launch_dt)
    return _single_plan(jd0, float(tof_days) * 86400.0)


def plan_mission(launch_dt):
    """Plan the transfer for a dataclass of the chosen launch datetime.

    The kid picks one day; the app shows what the classic Hohmann time (the
    textbook number) costs from that day, then scans the neighbouring launch
    days AND flight times so it can point at the cheapest nearby real window.
    """
    jd0 = julian_date(launch_dt)
    baseline = hohmann_baseline()
    tof_s = baseline["tof_days"] * 86400.0

    chosen = _single_plan(jd0, tof_s)

    best = None
    for d in range(-46, 47):
        for tof_d in range(160, 351, 8):
            p = _single_plan(jd0 + d, tof_d * 86400.0)
            if p.ok and (best is None or p.dv_total < best.dv_total):
                best = p
    return chosen, best


def trajectory_position(k, r0, v0, t_since_launch_s):
    """Spacecraft inertial position (km) t seconds after launch.

    Uses direct RK4 integration of the two-body problem, so the animation
    renders correctly even when the Lambert solution is a hyperbolic arc.
    """
    if r0 is None or v0 is None:
        return np.zeros(3)
    return integrate_state(k, np.asarray(r0, float), np.asarray(v0, float),
                           np.array([t_since_launch_s]))[0]


def trajectory_path(k, r0, v0, n, tof_s):
    """Whole transfer path as n sampled positions (for drawing the arc)."""
    if r0 is None or v0 is None:
        return np.zeros((n, 3))
    ts = np.linspace(0.0, tof_s, n)
    return integrate_state(k, np.asarray(r0, float), np.asarray(v0, float), ts)


def phase_angle_deg(jd):
    """Angle (deg) between Sun->Earth and Sun->Mars lines at JD ``jd``."""
    re = position("Earth", jd)
    rm = position("Mars", jd)
    c = np.dot(re, rm) / (norm(re) * norm(rm))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))