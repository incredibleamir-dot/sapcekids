"""Porkchop plot: C3 and dv contour grids for interplanetary transfers.

Scans a grid of launch dates and times-of-flight, runs the Lambert solver
for each pair, and returns the characteristic energy (C3) and total delta-v
so the page can draw a filled-contour porkchop chart.

Based on the classic JPL porkchop plot methodology used for Mars,
Venus and asteroid mission planning.
"""

import numpy as np

from .core import julian_date, lambert_solutions
from .bodies import (MU_SUN, MU_EARTH, planet, state as planet_state,
                     moon_geo_state)


def _earth_boot(jd):
    """(r0, v_earth) parking launch state at JD ``jd``.

    Planets leave from heliocentric Earth; the Moon leaves from a low
    Earth parking orbit (200 km altitude above Earth's surface), so the
    departure reference velocity is the LEO circular speed.
    """
    rec = planet("Earth")
    r_leo = rec["radius_km"] + 200.0
    v_circ = np.sqrt(MU_EARTH / r_leo)
    r0 = np.array([r_leo, 0.0, 0.0], float)
    v_e = np.array([0.0, v_circ, 0.0], float)
    return r0, v_e


def porkchop_grid(planet_name, jd_start, jd_end, jd_step,
                  tof_min_d, tof_max_d, tof_step_d,
                  moon_tof_min_d=1.0, moon_tof_max_d=10.0):
    """Compute a 2-D grid of C3 and dv for Earth -> ``planet_name``.

    Parameters
    ----------
    planet_name : str
        Target body ("Mars", "Venus", "Moon", ...).
    jd_start, jd_end : float
        Launch-date window in Julian dates.
    jd_step : float
        Launch-date spacing (days).
    tof_min_d, tof_max_d : float
        Time-of-flight bounds (days).  Ignored for the Moon, which uses
        the geocentric ``moon_tof_*`` bounds and a finer TOF step.
    tof_step_d : float
        TOF spacing (days).  Ignored for the Moon (uses 0.5 d).

    Returns
    -------
    dict with keys:
        "launch_jds"  - 1-D array of launch JDs
        "tof_days"    - 1-D array of flight times
        "c3"          - 2-D array (n_launch, n_tof) in km^2/s^2
        "dv"          - 2-D array (n_launch, n_tof) in km/s
        "valid"       - 2-D bool mask (True where Lambert converged)
    """
    is_moon = planet_name == "Moon"
    mu = MU_EARTH if is_moon else MU_SUN
    if is_moon:
        tof_min_d, tof_max_d = moon_tof_min_d, moon_tof_max_d
        tof_step_d = 0.5

    launch_jds = np.arange(jd_start, jd_end + jd_step * 0.5, jd_step)
    tof_days = np.arange(tof_min_d, tof_max_d + tof_step_d * 0.5, tof_step_d)

    n_ld = len(launch_jds)
    n_tof = len(tof_days)

    c3_grid = np.full((n_ld, n_tof), np.nan)
    dv_grid = np.full((n_ld, n_tof), np.nan)
    valid = np.zeros((n_ld, n_tof), dtype=bool)

    for i, jd_launch in enumerate(launch_jds):
        if is_moon:
            r0, v_e = _earth_boot(jd_launch)
        else:
            r0, v_e = planet_state("Earth", jd_launch)
        r0 = np.asarray(r0, float)
        v_e = np.asarray(v_e, float)

        for j, tof_d in enumerate(tof_days):
            tof_s = float(tof_d) * 86400.0
            jd_arrive = jd_launch + tof_d
            if is_moon:
                r1, v_tgt = moon_geo_state(jd_arrive)
            else:
                r1, v_tgt = planet_state(planet_name, jd_arrive)
            r1 = np.asarray(r1, float)
            v_tgt = np.asarray(v_tgt, float)

            pairs = lambert_solutions(mu, r0, r1, tof_s, M=0)
            if not pairs:
                continue

            best_v0 = None
            best_dv = np.inf
            for v0, v1 in pairs:
                dv_dep = float(np.linalg.norm(v0 - v_e))
                dv_arr = float(np.linalg.norm(v_tgt - v1))
                if dv_dep + dv_arr < best_dv:
                    best_dv = dv_dep + dv_arr
                    best_v0 = v0

            if best_v0 is None:
                continue

            v_inf_dep = float(np.linalg.norm(best_v0 - v_e))
            c3 = v_inf_dep ** 2

            c3_grid[i, j] = c3
            dv_grid[i, j] = best_dv
            valid[i, j] = True

    return {
        "launch_jds": launch_jds,
        "tof_days": tof_days,
        "c3": c3_grid,
        "dv": dv_grid,
        "valid": valid,
    }


def best_window(result):
    """Find the lowest-dv point in a porkchop grid.

    Returns (jd_launch, tof_days, c3, dv) or None if nothing valid.
    """
    if not np.any(result["valid"]):
        return None
    dv = result["dv"].copy()
    dv[~result["valid"]] = np.inf
    idx = np.unravel_index(np.argmin(dv), dv.shape)
    jd = result["launch_jds"][idx[0]]
    tof = result["tof_days"][idx[1]]
    return float(jd), float(tof), float(result["c3"][idx]), float(dv[idx])
