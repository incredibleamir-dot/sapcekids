"""Constellation Lab - the GPS, GLONASS and BeiDou satellite fleets.

Each constellation is built from its real textbook shell: number of orbital
planes, satellites per plane, flight altitude and inclination.  Real fleets
manoeuvre, so the exact pod numbers and phases here are illustrative; the
*pattern* - how many satellites you can see from your town and when - matches
reality closely enough for a lab.

Every satellite is an ``OrbitDesign`` at a shared epoch, so anything that
already knows how to draw ground tracks or find passes can use them.
"""

import math

import numpy as np

from .core import gmst_deg
from .orbitlab import OrbitDesign
from ..geo.earth import R_EARTH, ecef_of, elevation_deg, observer_ecef, subpoint

EPOCH_JD = 2460000.5  # 2023-02-24 00:00 UT; fleet elements are defined here

_FLETS = {
    "GPS": dict(planes=6, slots=4, a=26560.0, inc=55.0, e=0.004,
                raan0=20.0, phase0=0.0,
                fact="GPS started in the 1970s and is run by the US space "
                     "force. You probably have one in every phone!"),
    "GLONASS": dict(planes=3, slots=8, a=25440.0, inc=64.8, e=0.0,
                    raan0=10.0, phase0=11.25,
                    fact="GLONASS is Russia's system - first fully working "
                         "sat-nav constellation in history."),
    "BeiDou": dict(planes=3, slots=9, a=27800.0, inc=55.0, e=0.0,
                   raan0=1.0, phase0=0.0,
                   fact="BeiDou ('the Big Dipper') is China's system. Its "
                        "GEO satellites stay over one spot of the sky."),
}
_BDS_GEO_LONS = [58.75, 80.0, 110.5, 140.0, 160.0]

_COLORS = {"GPS": "#5be0a0", "GLONASS": "#ff9a8a",
           "BeiDou": "#8fb0ff"}


def constellation_names():
    return list(_FLETS)


def constellation_fact(name):
    return _FLETS[name]["fact"]


def color(name):
    return _COLORS.get(name, "#5be0a0")


def _build(name):
    cfg = _FLETS[name]
    planes = cfg["planes"]
    slots = cfg["slots"]
    raan_sp = 360.0 / planes
    slot_sp = 360.0 / slots
    theta = gmst_deg(EPOCH_JD)
    out = []
    for i in range(planes):
        raan = cfg["raan0"] + i * raan_sp
        for j in range(slots):
            nu0 = (cfg["phase0"] + j * slot_sp
                   + i * slot_sp / planes) % 360.0
            out.append(OrbitDesign("%s-%d-%d" % (name, i + 1, j + 1),
                                   cfg["a"], cfg["e"], cfg["inc"], raan, 0.0,
                                   nu0))
    if name == "BeiDou":
        # GEO birds: sub-satellite longitude fixed by choosing nu0 = lon + GMST
        for k, lon in enumerate(_BDS_GEO_LONS, start=1):
            nu0 = (lon + theta) % 360.0
            out.append(OrbitDesign("BeiDou GEO-%d" % k,
                                   42164.0, 0.0, 0.0, 0.0, 0.0, nu0))
    return out


_CACHE = {}


def satellites(name):
    """The whole fleet for a constellation name (OrbitDesign list)."""
    if name not in _CACHE:
        _CACHE[name] = _build(name)
    return _CACHE[name]


def stat(n, jd):
    """ECI position (km) of one constellation satellite at JD ``jd``."""
    return n.state_at((float(jd) - EPOCH_JD) * 86400.0)[0]


def sub(design, jd):
    """(lat, lon) sub-satellite point of one fleet member at JD."""
    return subpoint(stat(design, jd), float(jd))


def sub_many(designs, jd):
    """(n,2) lat/lon array for a fleet at one JD (vectorised on jd only)."""
    theta = math.radians(gmst_deg(float(jd)))
    ct, st = math.cos(theta), math.sin(theta)
    rows = []
    for d in designs:
        r = stat(d, jd)
        rn = np.linalg.norm(r) or 1.0
        x = r[0] * ct + r[1] * st
        y = -r[0] * st + r[1] * ct
        rows.append((math.degrees(math.asin(max(-1.0, min(1.0, r[2] / rn)))),
                     math.degrees(math.atan2(y, x))))
    return np.asarray(rows, dtype=float)


def visible(designs, jd, lat, lon, mask_deg=10.0):
    """Fleet members currently above ``mask_deg`` for a ground observer."""
    obs = observer_ecef(lat, lon)
    hits = []
    for d in designs:
        el = elevation_deg(ecef_of(stat(d, jd), float(jd)), obs)
        if el >= mask_deg:
            hits.append((d, float(el)))
    hits.sort(key=lambda t: -t[1])
    return hits


def footprint_radius_deg(alt_km, mask_deg):
    """Central angle (deg) around an observer where a sat clears the mask."""
    h = float(alt_km)
    mask = math.radians(float(mask_deg))
    ratio = R_EARTH / (R_EARTH + h)
    inside = ratio * math.cos(mask)
    if inside > 1.0:
        return 90.0
    return math.degrees(math.acos(inside) - mask)


def visible_places(designs, jd, places, mask_deg=10.0):
    """For each place dict (name, lat, lon), how many sats are visible."""
    out = []
    for rec in places:
        hits = visible(designs, jd, rec["lat"], rec["lon"], mask_deg)
        out.append(dict(name=rec["name"], count=len(hits),
                        best=hits[0][0].name if hits else "-",
                        elev=hits[0][1] if hits else 0.0))
    return out