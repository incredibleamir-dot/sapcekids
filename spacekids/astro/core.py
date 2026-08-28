"""poliastro facade.

A single, thin adaptation layer over the poliastro library so every page in
the app talks to one stable API regardless of the poliastro release that gets
installed.  Where poliastro cannot help (this pinned 2017-era 0.7.0 has no
``Hohmann`` convenience class), the math is re-implemented in the ``kepler``
module and clearly documented.

poliastro is genuinely used for:

* ``Orbit`` objects built from classical elements (``twobody.Orbit``),
* orbit propagation (``Orbit.propagate``),
* the Izzo Lambert solution (``poliastro.iod.izzo.lambert``).
"""

import datetime
import warnings

import numpy as np

import astropy.units as u
from astropy.time import Time

try:
    import poliastro
    from poliastro.bodies import Sun, Earth, Mars, Moon, Mercury, Venus
    from poliastro.twobody import Orbit as _POrbit
    from poliastro.iod.izzo import lambert as _lambert

    PO_VERSION = getattr(poliastro, "__version__", "?")
    PO_FOUND = True
except Exception:  # pragma: no cover - defensive for exotic installs
    poliastro = None
    PO_VERSION = None
    PO_FOUND = False

# gravitational parameters, km^3/s^2 (SI derived from astropy bodies)
if PO_FOUND:
    _MU = {
        "sun": float(Sun.k.to_value(u.km ** 3 / u.s ** 2)),
        "earth": float(Earth.k.to_value(u.km ** 3 / u.s ** 2)),
        "mars": float(Mars.k.to_value(u.km ** 3 / u.s ** 2)),
        "moon": float(Moon.k.to_value(u.km ** 3 / u.s ** 2)),
    }
else:  # pragma: no cover
    _MU = {"sun": 1.32712440018e11, "earth": 3.986004418e5, "mars": 4.282837e4}

# Keplerian reference J2000 (JD 2451545.0) days offset used by gmst
J2000_JD = 2451545.0


def mu_km3s2(name):
    """Gravitational parameter of a named body (km^3/s^2)."""
    return float(_MU.get(name.lower(), _MU["earth"]))


def julian_date(when):
    """Julian date for a datetime (naive = UTC) via astropy when possible."""
    if isinstance(when, Time):
        return when.jd
    if isinstance(when, datetime.datetime):
        if when.tzinfo is not None:
            when = when.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return Time(when, scale="utc").jd
    return float(when)


def jd_to_datetime(jd):
    """Naive UTC datetime from a Julian date."""
    return datetime.datetime(1858, 11, 17) + datetime.timedelta(
        days=float(jd) - 2400000.5)


def fmt_date(jd):
    """Short '3 Jun 2026' style string from a JD."""
    return jd_to_datetime(jd).strftime("%d %b %Y")


def gmst_deg(jd_ut):
    """Greenwich Mean Sidereal Time in degrees from a JD (UT1~UTC)."""
    T = (jd_ut - J2000_JD) / 36525.0
    theta = 280.46061837 + 360.98564736629 * (jd_ut - J2000_JD) \
        + 0.000387933 * T * T - T ** 3 / 38710000.0
    return np.mod(theta, 360.0)


# -------------------------------------------------------------------------- poliastro
def build_orbit(body_name, a_km, ecc, inc_deg, raan_deg, argp_deg, nu_deg,
                epoch=None):
    """Build a poliastro ``Orbit`` around ``body_name``.

    ``body_name`` is ``sun``/``earth``/``mars``/``moon``.
    """
    if not PO_FOUND:  # pragma: no cover
        raise RuntimeError("poliastro is not available")
    body = {"sun": Sun, "earth": Earth, "mars": Mars,
            "moon": Moon}[body_name.lower()]
    epoch = epoch if epoch is not None else Time.now()
    return _POrbit.from_classical(
        body,
        float(a_km) * u.km,
        float(ecc) * u.one,
        float(inc_deg) * u.deg,
        float(raan_deg) * u.deg,
        float(argp_deg) * u.deg,
        float(nu_deg) * u.deg,
        epoch=epoch,
    )


def po_propagate(po, dt_s):
    """Propagate a poliastro Orbit by ``dt_s`` seconds; returns (r, v) km, km/s."""
    out = po.propagate(float(dt_s) * u.s)
    return (np.asarray(out.r.value, dtype=float),
            np.asarray(out.v.value, dtype=float))


def po_elements(po):
    """Float dict of classical elements of a poliastro Orbit."""
    return {
        "a": float(po.a.to_value(u.km)),
        "e": float(po.ecc.value),
        "i": float(po.inc.to_value(u.deg)),
        "raan": float(po.raan.to_value(u.deg)),
        "argp": float(po.argp.to_value(u.deg)),
        "nu": float(po.nu.to_value(u.deg)),
    }


def lambert_solutions(k, r0, r1, tof_s, M=0):
    """Izzo Lambert solver: velocity pairs taking r0 -> r1 in tof seconds.

    Returns a list of ``(v0, v1)`` (floats, km/s).  Empty on failure or NaN.
    """
    if not PO_FOUND or tof_s <= 0:  # pragma: no cover
        return []
    try:
        gen = _lambert(float(k) * u.km ** 3 / u.s ** 2,
                       np.asarray(r0, float) * u.km,
                       np.asarray(r1, float) * u.km,
                       float(tof_s) * u.s,
                       M=int(M))
    except Exception:
        return []
    pairs = []
    try:
        for v0, v1 in gen:
            if np.all(np.isfinite(v0.value)) and np.all(np.isfinite(v1.value)):
                pairs.append((np.asarray(v0.value, float),
                              np.asarray(v1.value, float)))
    except Exception:
        pass  # Izzo 0.7.0 sometimes aborts a branch; keep the good pairs
    return pairs


def poliastro_status():
    """Short human-readable note shown in the About dialog."""
    if PO_FOUND:
        return "poliastro %s (Orbit, propagation, Izzo Lambert)" % PO_VERSION
    return "poliastro not installed - math falls back to Keplian solver"


def best_lambert(k, r0, r1, tof_s, v_depart=None, v_arrival=None):
    """Convenience: the cheapest Izzo Lambert pair, or None.

    Izzo 0.7.0 can return several families for one ``tof`` (prograde,
    retrograde and others).  Passing the actual velocities at both ends makes
    us pick the pair that costs the least rocket fuel.
    """
    pairs = lambert_solutions(k, r0, r1, tof_s, M=0)
    if not pairs:
        return None
    if v_depart is None and v_arrival is None:
        return pairs[0]
    v_d = np.asarray(v_depart, float) if v_depart is not None else None
    v_a = np.asarray(v_arrival, float) if v_arrival is not None else None

    def cost(pair):
        v0, v1 = pair
        c = 0.0
        if v_d is not None:
            c += float(np.linalg.norm(v0 - v_d))
        if v_a is not None:
            c += float(np.linalg.norm(v_a - v1))
        return c

    return min(pairs, key=cost)