"""Transfer study: Hohmann baseline, TOF-sensitivity sweeps, and orbit
comparison for the Transfer Study tab.

Provides cost curves (dv vs flight time) and the data needed to visualise
multiple transfer options in 3D.
"""

import math
from dataclasses import dataclass

import numpy as np

from .core import julian_date, best_lambert
from .kepler import (elements_from_state, integrate_state, norm,
                     mean_motion, period_s)
from .bodies import (AU, MU_SUN, MU_EARTH, planet, position,
                     state as planet_state, moon_geo_state,
                     moon_geo_position)

LEO_RADIUS = planet("Earth")["radius_km"] + 200.0
MOON_RADIUS = 384400.0


def moon_hohmann():
    """Return a HohmannResult for Earth parking orbit -> lunar distance.

    Uses the geocentric two-body model (a is the Moon's semi-major axis
    around Earth), which is the textbook lunar-transfer baseline.
    """
    return hohmann_circular(MU_EARTH, LEO_RADIUS, MOON_RADIUS)


@dataclass
class HohmannResult:
    """Textbook circular-coplanar Hohmann transfer between two orbits."""
    a_inner: float
    a_outer: float
    a_transfer: float
    e_transfer: float
    tof_days: float
    dv1: float
    dv2: float
    dv_total: float


def hohmann_circular(k, r1, r2):
    """Hohmann between two circular coplanar orbits radii r1, r2 (km).

    Returns a HohmannResult.
    """
    a_t = (r1 + r2) / 2.0
    e_t = abs(r2 - r1) / (r2 + r1)
    v_circ1 = math.sqrt(k / r1)
    v_circ2 = math.sqrt(k / r2)
    v_pe = math.sqrt(k * (2.0 / r1 - 1.0 / a_t))
    v_ap = math.sqrt(k * (2.0 / r2 - 1.0 / a_t))
    dv1 = abs(v_pe - v_circ1)
    dv2 = abs(v_circ2 - v_ap)
    tof_s = math.pi * math.sqrt(a_t ** 3 / k)
    return HohmannResult(
        a_inner=r1, a_outer=r2, a_transfer=a_t, e_transfer=e_t,
        tof_days=tof_s / 86400.0, dv1=dv1, dv2=dv2, dv_total=dv1 + dv2)


def dv_vs_tof(planet_name, jd_launch, tof_min_d, tof_max_d, step_d=5.0):
    """Scan Lambert dv cost over a range of flight times.

    Returns arrays (tof_days, dv_total, dv_depart, dv_arrive, c3).
    """
    is_moon = planet_name == "Moon"
    mu = MU_EARTH if is_moon else MU_SUN
    jd0 = julian_date(jd_launch)
    if is_moon:
        v_circ = math.sqrt(MU_EARTH / LEO_RADIUS)
        r0 = np.array([LEO_RADIUS, 0.0, 0.0], float)
        v_e = np.array([0.0, v_circ, 0.0], float)
    else:
        r0, v_e = planet_state("Earth", jd0)
        r0 = np.asarray(r0, float)
        v_e = np.asarray(v_e, float)

    tofs = np.arange(tof_min_d, tof_max_d + step_d * 0.5, step_d)
    n = len(tofs)
    dv_tot = np.full(n, np.nan)
    dv_dep = np.full(n, np.nan)
    dv_arr = np.full(n, np.nan)
    c3_arr = np.full(n, np.nan)

    for j, tof_d in enumerate(tofs):
        tof_s = float(tof_d) * 86400.0
        jd_arr = jd0 + tof_d
        if is_moon:
            r1, v_m = moon_geo_state(jd_arr)
        else:
            r1, v_m = planet_state(planet_name, jd_arr)
        r1 = np.asarray(r1, float)
        v_m = np.asarray(v_m, float)

        pair = best_lambert(mu, r0, r1, tof_s,
                            v_depart=v_e, v_arrival=v_m)
        if pair is None:
            continue
        v0, v1 = pair
        dd0 = float(np.linalg.norm(v0 - v_e))
        dd1 = float(np.linalg.norm(v_m - v1))
        dv_tot[j] = dd0 + dd1
        dv_dep[j] = dd0
        dv_arr[j] = dd1
        c3_arr[j] = float(np.linalg.norm(v0 - v_e)) ** 2

    return {
        "tof_days": tofs,
        "dv_total": dv_tot,
        "dv_depart": dv_dep,
        "dv_arrive": dv_arr,
        "c3": c3_arr,
    }


def transfer_orbit_path(planet_name, jd_launch, tof_days, n=300):
    """Sample the Lambert transfer arc for visualisation.

    Returns (path_pts, earth_orbit_pts, target_orbit_pts, transfer_info).
    """
    is_moon = planet_name == "Moon"
    mu = MU_EARTH if is_moon else MU_SUN
    jd0 = julian_date(jd_launch)
    if is_moon:
        v_circ = math.sqrt(MU_EARTH / LEO_RADIUS)
        r0 = np.array([LEO_RADIUS, 0.0, 0.0], float)
        v_e = np.array([0.0, v_circ, 0.0], float)
    else:
        r0, v_e = planet_state("Earth", jd0)
        r0 = np.asarray(r0, float)
        v_e = np.asarray(v_e, float)

    tof_s = float(tof_days) * 86400.0
    jd_arr = jd0 + tof_days
    if is_moon:
        r1, v_m = moon_geo_state(jd_arr)
    else:
        r1, v_m = planet_state(planet_name, jd_arr)
    r1 = np.asarray(r1, float)

    pair = best_lambert(mu, r0, r1, tof_s,
                        v_depart=v_e, v_arrival=v_m)
    if pair is None:
        return np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 3)), None
    v0, v1 = pair
    ts = np.linspace(0.0, tof_s, n)
    path_pts = integrate_state(mu, r0, v0, ts)

    earth_jds = np.linspace(jd0 - 30.0, jd0 + tof_days + 30.0, n)
    earth_pts = np.empty((n, 3))
    for i, jd in enumerate(earth_jds):
        earth_pts[i] = position("Earth", jd)

    target_jds = np.linspace(jd0 - 30.0, jd0 + tof_days + 30.0, n)
    target_pts = np.empty((n, 3))
    for i, jd in enumerate(target_jds):
        if is_moon:
            target_pts[i] = moon_geo_position(jd)
        else:
            target_pts[i] = position(planet_name, jd)

    info = {
        "r0": r0, "v0": v0, "r1": r1, "v1": v1,
        "jd_launch": jd0, "jd_arrive": jd_arr,
        "mu": mu,
    }
    return path_pts, earth_pts, target_pts, info
