"""Small flat-Earth geometry helpers shared by the satellite pages.

The Earth is treated as a sphere of radius ``R_EARTH`` here - plenty for a
kids' playground where the ISS is 400 km up.
"""

import math

import numpy as np

from ..astro.core import gmst_deg

R_EARTH = 6371.0  # km
FLAT = 0.0


def wrap_lon(lon_deg):
    return (np.asarray(lon_deg, dtype=float) + 180.0) % 360.0 - 180.0


def subpoint(r_eci, jd):
    """Sub-satellite latitude/longitude from an ECI position vector (km)."""
    r = np.asarray(r_eci, dtype=float)
    theta = math.radians(gmst_deg(jd)) if not isinstance(jd, np.ndarray) else 0.0
    x = r[0] * math.cos(theta) + r[1] * math.sin(theta)
    y = -r[0] * math.sin(theta) + r[1] * math.cos(theta)
    z = r[2]
    lat = math.degrees(math.asin(max(-1.0, min(1.0, z / (np.linalg.norm(r) or 1.0)))))
    lon = math.degrees(math.atan2(y, x))
    return lat, wrap_lon(lon)


def ecef_of(sat_r_eci, jd):
    """ECEF (geocentric) position of a satellite given its ECI position."""
    r = np.asarray(sat_r_eci, dtype=float)
    theta = math.radians(gmst_deg(jd))
    x = r[0] * math.cos(theta) + r[1] * math.sin(theta)
    y = -r[0] * math.sin(theta) + r[1] * math.cos(theta)
    return np.array([x, y, r[2]])


def observer_ecef(lat_deg, lon_deg, alt_km=0.0):
    """ECEF of an observer on the spherical Earth."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    r = R_EARTH + alt_km
    return np.array([
        r * math.cos(lat) * math.cos(lon),
        r * math.cos(lat) * math.sin(lon),
        r * math.sin(lat),
    ])


def topocentric(sat_ecef, obs_ecef):
    """Unit ENU-ish frame vectors (east, north, radial-up) at the observer."""
    lat = math.atan2(obs_ecef[2], math.hypot(obs_ecef[0], obs_ecef[1]))
    lon = math.atan2(obs_ecef[1], obs_ecef[0])
    up = obs_ecef / float(np.linalg.norm(obs_ecef))
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north = np.cross(up, east)
    rel = sat_ecef - obs_ecef
    d = float(np.linalg.norm(rel))
    if d < 1e-9:
        return 0.0, 0.0, 0.0
    az = math.degrees(math.atan2(np.dot(rel, east), np.dot(rel, north)))
    el = math.degrees(math.asin(np.dot(rel, up) / d))
    return az % 360.0, el, d


def elevation_deg(sat_ecef, obs_ecef):
    return topocentric(sat_ecef, obs_ecef)[1]


def ground_distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    p1 = math.radians(lat1), math.radians(lon1)
    p2 = math.radians(lat2), math.radians(lon2)
    dlat = p2[0] - p1[0]
    dlon = p2[1] - p1[1]
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(p1[0]) * math.cos(p2[0]) * math.sin(dlon / 2) ** 2)
    return 2.0 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))


def ring_points(center_lat, center_lon, radius_deg, n=96):
    """(lats, lons) of a small circle of ``radius_deg`` around a lat/lon."""
    phi0 = math.radians(center_lat)
    lam0 = math.radians(center_lon)
    rho = math.radians(radius_deg)
    lats = np.empty(n)
    lons = np.empty(n)
    for k in range(n):
        az = 2.0 * math.pi * k / n
        phi = math.asin(math.sin(phi0) * math.cos(rho)
                        + math.cos(phi0) * math.sin(rho) * math.cos(az))
        lam = lam0 + math.atan2(
            math.sin(az) * math.sin(rho) * math.cos(phi0),
            math.cos(rho) - math.sin(phi0) * math.sin(phi))
        lats[k] = math.degrees(phi)
        lons[k] = wrap_lon(math.degrees(lam))
    return lats, lons