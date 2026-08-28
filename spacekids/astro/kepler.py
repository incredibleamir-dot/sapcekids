"""Pure-numpy elliptical Kepler mechanics.

Everything in ``spacekids`` renders two-body orbits by the same small,
dependency-light solver: solve Kepler's equation for the eccentric anomaly,
then rotate the perifocal frame into an inertial frame.  poliastro - the
heart of the project - is used for the *orchestration* pieces where its real
value lives (``Orbit`` objects, propagation, the Izzo Lambert solution), see
``spacekids.astro.core``.
"""

import math

import numpy as np


def norm(v):
    return np.linalg.norm(v)


def two_body_accel(k, r):
    """Acceleration (km/s^2) in a central gravitational field."""
    rn = np.linalg.norm(r)
    if rn < 1e-9:
        return np.zeros(3)
    return -k * np.asarray(r, float) / rn ** 3


def integrate_state(k, r0, v0, ts, max_step_s=21600.0):
    """Integrated two-body positions (classic RK4) at times ``ts``.

    Works for any conic (elliptic, parabolic, hyperbolic) so an intercept
    Lambert solution always renders.  ``ts`` must be ascending.
    """
    r0 = np.asarray(r0, float)
    v0 = np.asarray(v0, float)
    ts = np.asarray(ts, float)
    out = np.empty((len(ts), 3))
    r, v = r0.copy(), v0.copy()
    prev = 0.0
    for j, tt in enumerate(ts):
        dt = tt - prev
        while dt > 1e-12:
            h = min(max_step_s, dt)
            a1 = two_body_accel(k, r)
            v1, v2 = v, v + a1 * h / 2.0
            r2 = r + v1 * h / 2.0
            a2 = two_body_accel(k, r2)
            v3 = v + a2 * h / 2.0
            r3 = r + v2 * h / 2.0
            a3 = two_body_accel(k, r3)
            v4 = v + a3 * h
            r4 = r + v3 * h
            a4 = two_body_accel(k, r4)
            r = r + (v1 + 2 * v2 + 2 * v3 + v4) * h / 6.0
            v = v + (a1 + 2 * a2 + 2 * a3 + a4) * h / 6.0
            dt -= h
        out[j] = r
        prev = tt
    return out


def angle_wrap(deg):
    """Wrap an angle to [0, 360)."""
    return np.mod(np.asarray(deg, dtype=float), 360.0)


def kepler_E(M, ecc, tol=1e-11, iters=60):
    """Solve M = E - e sin E for the eccentric anomaly (radians)."""
    M = np.asarray(M, dtype=float)
    E = M.copy()
    for _ in range(iters):
        dE = (E - ecc * np.sin(E) - M) / (1.0 - ecc * np.cos(E))
        E -= dE
        if np.max(np.abs(dE)) < tol:
            break
    return E


def nu_from_M(M_deg, ecc):
    """True anomaly (degrees) from mean anomaly (degrees); e < 1 only."""
    M = np.radians(np.asarray(M_deg, dtype=float))
    E = kepler_E(M, ecc)
    nu = 2.0 * np.arctan2(
        np.sqrt(1.0 + ecc) * np.sin(E / 2.0),
        np.sqrt(1.0 - ecc) * np.cos(E / 2.0),
    )
    return angle_wrap(np.degrees(nu))


def M_from_nu(nu_deg, ecc):
    """Mean anomaly (degrees) from true anomaly (degrees)."""
    nu = np.radians(np.asarray(nu_deg, dtype=float))
    E = 2.0 * np.arctan2(
        np.sqrt(1.0 - ecc) * np.sin(nu / 2.0),
        np.sqrt(1.0 + ecc) * np.cos(nu / 2.0),
    )
    M = np.degrees(E - ecc * np.sin(E))
    return np.mod(M, 360.0)


def mean_motion(k, a):
    """Mean motion as rad per second for semi-major axis ``a`` (km)."""
    return np.sqrt(np.abs(k) / a ** 3)


def period_s(k, a):
    """Orbital period in seconds for semi-major axis ``a`` (km)."""
    return 2.0 * np.pi / mean_motion(k, a)


def _rot_matrices(i, raan, argp):
    """Perifocal -> inertial rotation matrices for three Euler angles (deg)."""
    c1, s1 = np.cos(np.radians(raan)), np.sin(np.radians(raan))
    c2, s2 = np.cos(np.radians(i)), np.sin(np.radians(i))
    c3, s3 = np.cos(np.radians(argp)), np.sin(np.radians(argp))
    R1 = np.array([[1, 0, 0], [0, c2, -s2], [0, s2, c2]])   # rotate around X
    R3 = np.array([[c1, -s1, 0], [s1, c1, 0], [0, 0, 1]])   # rotate around Z
    R3p = np.array([[c3, -s3, 0], [s3, c3, 0], [0, 0, 1]])  # rotate around Z
    return R3, R1, R3p


def propagate_elements(k, a, e, i_deg, raan_deg, argp_deg, nu0_deg, dt_s,
                       t0_s=0.0):
    """Propagate an elliptical orbit and return the state at ``t0 + dt``.

    Returns
    -------
    (r, v) : two float (3,) arrays, km and km/s, inertial.
    """
    if e >= 1.0:
        raise ValueError("kepler.propagate_elements supports e < 1 only")
    n = mean_motion(k, a)
    M0 = np.radians(M_from_nu(nu0_deg, e))
    M = np.mod(M0 + n * dt_s, 2.0 * np.pi)
    E = kepler_E(M, e)
    nu = np.degrees(2.0 * np.arctan2(
        np.sqrt(1.0 + e) * np.sin(E / 2.0),
        np.sqrt(1.0 - e) * np.cos(E / 2.0)))

    p = a * (1.0 - e ** 2)
    r = p / (1.0 + e * np.cos(np.radians(nu)))
    xp = r * np.cos(np.radians(nu))
    yp = r * np.sin(np.radians(nu))

    if r < 1e-6:
        return np.zeros(3), np.zeros(3)

    # perifocal velocity of an ellipse: exact closed form (km/s)
    mu = k
    v_scale = math.sqrt(mu / p)
    vxp = -v_scale * np.sin(np.radians(nu))
    vyp = v_scale * (e + np.cos(np.radians(nu)))

    R3, R1, R3p = _rot_matrices(i_deg, raan_deg, argp_deg)
    r = R3 @ R1 @ R3p @ np.array([xp, yp, 0.0])
    v = R3 @ R1 @ R3p @ np.array([vxp, vyp, 0.0])
    return r, v


def sample_elements(k, a, e, i_deg, raan_deg, argp_deg, n=360, nu_start=0.0,
                    nu_span=360.0):
    """Sample an orbit's path from ``nu_start`` spanning ``nu_span`` degrees.

    Returns an array shaped (n, 3) of inertial positions in km.
    """
    nus = nu_start + np.linspace(0.0, nu_span, n)
    p = a * (1.0 - e ** 2)
    r = p / (1.0 + e * np.cos(np.radians(nus)))
    xp = r * np.cos(np.radians(nus))
    yp = r * np.sin(np.radians(nus))
    R3, R1, R3p = _rot_matrices(i_deg, raan_deg, argp_deg)
    rot = R3 @ R1 @ R3p
    pts = np.stack([xp, yp, np.zeros_like(xp)], axis=-1)
    return (rot @ pts.T).T


def checksum(elements):
    """3-char TLE-field checksum (kept for parity checking when needed)."""
    return sum(int(ch) for ch in elements if ch.isdigit()) % 10


def elements_from_state(k, r, v):
    """Classical elements (float dict) recovered from inertial r (km), v (km/s).

    Mirrors the standard two-body IOD.  Angles in degrees.
    """
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    rn, vn = norm(r), norm(v)
    h = np.cross(r, v)
    hn = norm(h)
    eps = (vn ** 2) / 2.0 - k / rn
    a = -k / (2.0 * eps)
    e_vec = (np.cross(v, h) / k) - r / rn
    e = norm(e_vec)

    zi = np.array([0.0, 0.0, 1.0])
    n_vec = np.cross(zi, h)
    nn = norm(n_vec)

    i = np.degrees(np.arccos(np.clip(h[2] / hn, -1.0, 1.0)))
    raan = 0.0
    if nn > 1e-9:
        raan = np.degrees(np.arccos(np.clip(n_vec[0] / nn, -1.0, 1.0)))
        if n_vec[1] < 0:
            raan = 360.0 - raan
    argp = 0.0
    if nn > 1e-9 and e > 1e-9:
        argp = np.degrees(np.arccos(np.clip(
            np.dot(n_vec, e_vec) / (nn * e), -1.0, 1.0)))
        if e_vec[2] < 0:
            argp = 360.0 - argp
    nu = 0.0
    if e > 1e-9:
        nu = np.degrees(np.arccos(np.clip(np.dot(e_vec, r) / (e * rn), -1.0, 1.0)))
        if np.dot(r, v) < 0:
            nu = 360.0 - nu
    else:
        if nn > 1e-9:
            nu = np.degrees(np.arccos(np.clip(np.dot(n_vec, r) / (nn * rn), -1.0, 1.0)))
            if r[2] < 0 or np.dot(r, h) < 0:
                nu = 360.0 - nu
    return {
        "a": float(a), "e": float(e),
        "i": float(i), "raan": float(raan), "argp": float(argp),
        "nu": float(nu % 360.0), "k": float(k),
    }