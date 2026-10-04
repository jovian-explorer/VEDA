"""Where the Sun is seen from a planet or moon: subsolar point, local true solar time,
solar zenith angle and, for Mars, the solar longitude Ls.

Many archived profiles give a time and a position but not the local time or the
solar zenith angle (Mars Express and Venus Express radio occultations, for
example), which comparisons filter and group by.  They follow from where the
Sun is in the body's own rotating frame:

* the body's heliocentric position from the JPL approximate Keplerian elements
  (Standish, "Keplerian Elements for Approximate Positions of the Major Planets",
  valid 1800-2050; error well under 0.1 deg for Venus and Mars).  A moon uses its
  planet's position: the direction to the Sun differs by less than 0.01 deg;
* the body's orientation (north pole and prime meridian) from the IAU WGCCRE
  rotation models (Archinal et al. 2011, Celest. Mech. Dyn. Astr. 109, 101).

Light travel time from the Sun (minutes) is ignored: it shifts the subsolar
point by less than 0.01 deg.  Times are UTC; TDB - UTC is taken as 69.2 s.
Longitudes are planetocentric, east-positive (the PDS convention), latitudes
planetocentric.
"""
from __future__ import annotations

import datetime as _dt
import functools
import math
from typing import Dict, Optional

import numpy as np

_J2000 = _dt.datetime(2000, 1, 1, 12, 0, 0)
_TDB_MINUS_UTC_S = 69.184            # 32.184 s + 37 leap seconds (since 2017; 32-36 before)
_OBLIQUITY = math.radians(23.43928)  # J2000 ecliptic to equator

# a (au), e, I, L, long. perihelion, long. ascending node (deg) and their rates per
# Julian century, J2000 ecliptic and equinox (Standish, table 1, 1800-2050)
_ELEMENTS = {
    "venus": ((0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255),
              (0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418)),
    "earth": ((1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0),
              (0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0)),
    "mars": ((1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891),
             (0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343)),
    "jupiter": ((5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909),
                (-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106)),
    "saturn": ((9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448),
               (-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794)),
}
# The planet whose heliocentric position a moon shares
_PARENT = {"titan": "saturn", "enceladus": "saturn", "io": "jupiter", "europa": "jupiter",
           "ganymede": "jupiter", "callisto": "jupiter"}

# IAU rotation: pole RA, Dec (deg) and rates per century; prime meridian W (deg) and rate
# per day (WGCCRE 2009; the small periodic terms are left out, < 0.01 deg)
_ROTATION = {
    "venus": (272.76, 0.0, 67.16, 0.0, 160.20, -1.4813688),
    "mars": (317.68143, -0.1061, 52.88650, -0.0609, 176.630, 350.89198226),
    "jupiter": (268.056595, -0.006499, 64.495303, 0.002413, 284.95, 870.5360000),
    "saturn": (40.589, -0.036, 83.537, -0.004, 38.90, 810.7939024),
    "titan": (39.4827, 0.0, 83.4279, 0.0, 186.5855, 22.5769768),
}


def supported(body_id: str) -> bool:
    return body_id in _ROTATION


def circular_median(values, period: float) -> Optional[float]:
    """Median of angles or clock times that wrap at ``period`` (360 deg, 24 h).

    A plain median of 23.9 h and 0.1 h is 12 h; here the values are first taken
    relative to one of them, so a ray path that crosses midnight or the 0/360 (or
    +-180) meridian gives its true middle.  Valid when the values span less than
    half a period, as along one profile.  The result keeps the input convention:
    [0, period), or [-period/2, period/2) when any value is negative.
    """
    if values is None:
        return None
    a = np.asarray(values, dtype=float).ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    ref = a[0]
    m = ref + float(np.median((a - ref + period / 2.0) % period - period / 2.0))
    lo = -period / 2.0 if np.min(a) < 0 else 0.0
    return float((m - lo) % period + lo)


def _days_tdb(time_utc: str) -> Optional[float]:
    t = parse_utc(time_utc)
    if t is None:
        return None
    return (t - _J2000).total_seconds() / 86400.0 + _TDB_MINUS_UTC_S / 86400.0


def parse_utc(time_utc: str) -> Optional[_dt.datetime]:
    """'2004-05-18T15:08:04.584', '2004-05-18 15:08', '2004-05-18' or with Z -> datetime."""
    if not time_utc:
        return None
    s = str(time_utc).strip().replace(" ", "T").rstrip("Zz")
    if "+" in s[10:]:
        s = s[:10] + s[10:].split("+")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


def _heliocentric(planet: str, days: float) -> np.ndarray:
    """Heliocentric position (au) in the J2000 equatorial frame."""
    base, rate = _ELEMENTS[planet]
    T = days / 36525.0
    a, e, inc, L, varpi, node = (b + r * T for b, r in zip(base, rate))
    w = varpi - node
    M = math.radians(((L - varpi) + 180.0) % 360.0 - 180.0)
    E = M + e * math.sin(M)
    for _ in range(12):                      # Kepler's equation
        E -= (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
    xp, yp = a * (math.cos(E) - e), a * math.sqrt(1.0 - e * e) * math.sin(E)
    w, node, inc = math.radians(w), math.radians(node), math.radians(inc)
    cw, sw, cn, sn, ci, si = math.cos(w), math.sin(w), math.cos(node), math.sin(node), math.cos(inc), math.sin(inc)
    x = (cw * cn - sw * sn * ci) * xp + (-sw * cn - cw * sn * ci) * yp
    y = (cw * sn + sw * cn * ci) * xp + (-sw * sn + cw * cn * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    ce, se = math.cos(_OBLIQUITY), math.sin(_OBLIQUITY)
    return np.array([x, ce * y - se * z, se * y + ce * z])


def _pole_and_w(body: str, days: float):
    ra0, ra_t, dec0, dec_t, w0, w_d = _ROTATION[body]
    T = days / 36525.0
    ra, dec = math.radians(ra0 + ra_t * T), math.radians(dec0 + dec_t * T)
    return ra, dec, math.radians((w0 + w_d * days) % 360.0), w_d


def _to_body_frame(v: np.ndarray, ra: float, dec: float, w: float) -> np.ndarray:
    # ICRF -> body-fixed: Rz(W) Rx(90 deg - dec) Rz(90 deg + ra)
    def rz(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])

    def rx(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[1.0, 0.0, 0.0], [0.0, c, s], [0.0, -s, c]])
    return rz(w) @ rx(math.pi / 2 - dec) @ rz(math.pi / 2 + ra) @ v


def subsolar_point(body_id: str, time_utc: str) -> Optional[Dict[str, float]]:
    """Planetocentric latitude and east longitude (deg) of the subsolar point, and for
    Mars the solar longitude Ls (deg)."""
    out = _subsolar_point(body_id.lower(), time_utc)
    return dict(out) if out is not None else None


@functools.lru_cache(maxsize=4096)
def _subsolar_point(body: str, time_utc: str) -> Optional[Dict[str, float]]:
    # (cached: the local time and zenith angle of every level of a profile are computed
    # for the same time, which made this a quarter of the time of reading Mars profiles)
    days = _days_tdb(time_utc)
    if body not in _ROTATION or days is None:
        return None
    planet = _PARENT.get(body, body)
    r = _heliocentric(planet, days)
    sun = -r / np.linalg.norm(r)
    ra, dec, w, _ = _pole_and_w(body, days)
    s = _to_body_frame(sun, ra, dec, w)
    out = {"subsolar_latitude": math.degrees(math.asin(max(-1.0, min(1.0, s[2])))),
           "subsolar_longitude": math.degrees(math.atan2(s[1], s[0])) % 360.0}
    if body == "mars":
        out["ls"] = solar_longitude(days, ra, dec)
    return out


def solar_longitude(days: float, ra: float, dec: float) -> float:
    """Mars' areocentric longitude of the Sun Ls (deg): 0 at the northern spring equinox,
    90 at northern summer solstice."""
    pole = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    r = _heliocentric("mars", days)
    r2 = _heliocentric("mars", days + 1.0)
    h = np.cross(r, r2)
    h /= np.linalg.norm(h)                         # orbit normal
    e = np.cross(pole, h)
    e /= np.linalg.norm(e)                         # direction to the Sun at Ls = 0
    sun = -r / np.linalg.norm(r)
    return math.degrees(math.atan2(np.dot(np.cross(h, e), sun), np.dot(e, sun))) % 360.0


# Mars year 34 began (Ls = 0) on 2017-05-05 (Piqueux et al. 2015 calendar, Clancy et al.
# 2000 numbering: MY 1 began on 1955-04-11); a Mars year is 686.97 days.
_MY34_START = _dt.datetime(2017, 5, 5, 12)
_MARS_YEAR_DAYS = 686.9726


def mars_time_from_ls(mars_year: int, ls: float) -> Optional[str]:
    """UTC time (ISO, to the minute) when Mars reached solar longitude ``ls`` in Mars
    year ``mars_year``: the inverse of the Ls computed here, for data sets that give only
    a Mars year and Ls (CRISM limb profiles)."""
    try:
        my, target = int(mars_year), float(ls) % 360.0
    except (TypeError, ValueError):
        return None
    t0 = _MY34_START + _dt.timedelta(days=(my - 34) * _MARS_YEAR_DAYS)

    def off(d: float) -> float:          # Ls(t0 + d) - target, wrapped to [-180, 180)
        ss = _subsolar_point("mars", (t0 + _dt.timedelta(days=d)).isoformat())
        return (ss["ls"] - target + 180.0) % 360.0 - 180.0

    d = target / 360.0 * _MARS_YEAR_DAYS          # mean motion first guess
    for _ in range(20):                           # Newton steps with a numerical slope
        f = off(d)
        if abs(f) < 1e-4:
            break
        slope = (off(d + 0.5) - f) / 0.5
        d -= f / (slope if slope > 0.1 else 0.524)
    return (t0 + _dt.timedelta(days=d)).strftime("%Y-%m-%dT%H:%M")


def light_time_s(body_id: str, time_utc: str) -> Optional[float]:
    """One-way light time (s) between the body and Earth."""
    body = _PARENT.get(body_id.lower(), body_id.lower())
    days = _days_tdb(time_utc)
    if body not in _ELEMENTS or days is None:
        return None
    lt = 0.0
    for _ in range(2):                  # the body's position when the light left it
        d = np.linalg.norm(_heliocentric(body, days - lt / 86400.0) - _heliocentric("earth", days))
        lt = d * 499.004784             # s per au
    return float(lt)


def et_to_utc(et: float) -> str:
    """Ephemeris seconds past J2000 (TDB) -> UTC ISO time (to 1 ms; TDB - UTC as above)."""
    t = _J2000 + _dt.timedelta(seconds=float(et) - _TDB_MINUS_UTC_S)
    return t.isoformat(timespec="milliseconds")


def solar_geometry(body_id: str, time_utc: str, latitude: Optional[float],
                   longitude: Optional[float]) -> Optional[Dict[str, float]]:
    """Local true solar time (h), solar zenith angle (deg), subsolar point (deg) and, on
    Mars, Ls (deg) at a point; None when the body, time or position is unknown."""
    if latitude is None or longitude is None or not (np.isfinite(latitude) and np.isfinite(longitude)):
        return None
    ss = subsolar_point(body_id, time_utc)
    if ss is None:
        return None
    lat, dlon = math.radians(latitude), math.radians(longitude - ss["subsolar_longitude"])
    slat = math.radians(ss["subsolar_latitude"])
    cos_sza = math.sin(lat) * math.sin(slat) + math.cos(lat) * math.cos(slat) * math.cos(dlon)
    sza = math.degrees(math.acos(max(-1.0, min(1.0, cos_sza))))
    # Noon at the subsolar longitude.  On a body rotating eastward (prograde) places east
    # of it have passed noon; on retrograde Venus they have not reached it yet.
    sign = 1.0 if _ROTATION[body_id.lower()][5] > 0 else -1.0
    hour_angle = ((longitude - ss["subsolar_longitude"]) * sign + 180.0) % 360.0 - 180.0
    out = {"lst": (12.0 + hour_angle / 15.0) % 24.0, "sza": sza, **ss}
    return out
