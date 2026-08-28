"""Build My Satellite - orbit design + ground-track ground truth.

Turns the kid's sliders into classical elements and produces the numbers a
real flight-dynamics textbook would: period, speeds, apogee/perigee, a
friendly classification, and the sub-satellite ground track over time.
"""

import math
from dataclasses import dataclass

import numpy as np

from .kepler import mean_motion, period_s, propagate_elements
from .core import mu_km3s2

RE = 6371.0  # km, mean Earth radius


@dataclass
class OrbitDesign:
    """A toy orbit the kid designed with the page's sliders."""
    name: str
    a_km: float
    e: float
    inc_deg: float
    raan_deg: float = 0.0
    argp_deg: float = 0.0
    nu0_deg: float = 0.0

    @property
    def k(self):
        return mu_km3s2("earth")

    @property
    def rp_km(self):
        return self.a_km * (1.0 - self.e)

    @property
    def ra_km(self):
        return self.a_km * (1.0 + self.e)

    @property
    def alt_peri(self):
        return self.rp_km - RE

    @property
    def alt_apo(self):
        return self.ra_km - RE

    @property
    def period_s(self):
        return period_s(self.k, self.a_km)

    @property
    def period_min(self):
        return self.period_s / 60.0

    def speed_at(self, r_km):
        return math.sqrt(self.k * (2.0 / r_km - 1.0 / self.a_km))

    @property
    def speed_peri(self):
        return self.speed_at(self.rp_km)

    @property
    def speed_apo(self):
        return self.speed_at(self.ra_km)

    def classification(self):
        ap = self.alt_apo
        pe = self.alt_peri
        e = self.e
        if e < 0.02 and abs(pe - 35786.0) < 2500.0 and self.inc_deg < 5.0:
            return "GEO - TV satellite (always over the same spot)"
        if ap <= 2000.0:
            return "LEO - low Earth orbit (the ISS lives here)"
        if e > 0.30 and ap > 35786.0:
            return "HEO - a swooping elliptical orbit"
        return "MEO - medium Earth orbit (GPS lives here)"

    def is_valid(self):
        return self.a_km > RE and 0.0 <= self.e < 1.0

    def state_at(self, dt_s):
        """(r, v) ECI at dt_s seconds after the design epoch."""
        return propagate_elements(self.k, self.a_km, self.e, self.inc_deg,
                                  self.raan_deg, self.argp_deg, self.nu0_deg,
                                  float(dt_s))

    def ground_track(self, n=720, duration_s=None, start_jd=0.0):
        """(lats, lons) arrays for the sub-satellite point over one orbit."""
        from ..geo.earth import subpoint
        duration_s = duration_s or self.period_s
        times = np.linspace(0.0, float(duration_s), n)
        lats = np.zeros(n)
        lons = np.zeros(n)
        for i, dt in enumerate(times):
            r, _v = self.state_at(dt)
            jd = start_jd + dt / 86400.0
            la, lo = subpoint(r, jd)
            lats[i], lons[i] = la, lo
        return lats, lons


PRESETS = {
    "ISS (Low Orbit)": OrbitDesign("ISS", 6772.0, 0.0006, 51.64),
    "Hubble (Low, tilted)": OrbitDesign("HST", 6920.0, 0.0003, 28.47),
    "GPS (Medium)": OrbitDesign("GPS", 26560.0, 0.0, 55.0),
    "TV satellite (GEO)": OrbitDesign("GEO", 42164.0, 0.0, 0.1),
    "Egg (Elliptical)": OrbitDesign("Egg", 20000.0, 0.65, 45.0),
}


def design_from_sliders(altitude_km, ecc, inc_deg, raan_deg, argp_deg):
    """OrbitDesign from the page's raw slider values."""
    a = RE + altitude_km
    return OrbitDesign("Custom", a, ecc, inc_deg, raan_deg, argp_deg,
                       nu0_deg=0.0)