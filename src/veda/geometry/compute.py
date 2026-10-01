"""Radio-occultation observation geometry with SPICE.

Time convention: radio-science profile times are Earth *reception* times.
This was checked against the products: with it, the computed tangent radius
matches the published RADIUS column to about 1 km for Mars Express; treating
the times as geometric epochs gives errors of about 400 km. The spacecraft and
planet are therefore taken at their light-time corrected emission epochs as
seen from Earth ('CN').

The tangent track shown is the product's own (refracted) solution when the
product provides it. The straight-line spacecraft-Earth closest approach is
also computed, and its difference from the published radius is reported as a
measure of ray bending (hundreds of km deep in Venus' atmosphere).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import numpy as np
import spiceypy as sp

from ..core.registry import get_body
from .kernels import KernelPlan

_spice_lock = threading.Lock()     # CSPICE is not thread-safe
_loaded: set = set()

NAIF_BODY = {"venus": 299, "mars": 499, "jupiter": 599, "saturn": 699, "mercury": 199,
             "moon": 301, "titan": 606, "pluto": 999, "ceres": 2000001, "vesta": 2000004,
             "comet_67p": 1000012}
# Body-fixed frames (IAU_<NAME> from pck00011, except 67P whose frame comes with ROS_V38.TF)
BODY_FRAME = {"comet_67p": "67P/C-G_FIXED"}


def body_frame(body_id: str) -> str:
    return BODY_FRAME.get(body_id, f"IAU_{body_id.upper()}")


def _furnsh(plan: KernelPlan) -> None:
    for url in plan.urls:
        path = str(plan.local(url))
        if path not in _loaded:
            sp.furnsh(path)
            _loaded.add(path)


def _vec(arr: np.ndarray, digits: int = 3) -> List[List[float]]:
    return np.round(arr, digits).tolist()


def _unit(v) -> List[float]:
    v = np.asarray(v, float)
    return (v / np.linalg.norm(v)).tolist()


def observation_geometry(plan: KernelPlan, sc_id: int, body_id: str, et_profile: np.ndarray,
                         span_min: float = 90.0, step_s: float = 30.0,
                         product_track: Optional[Dict[str, np.ndarray]] = None) -> Dict[str, Any]:
    """Geometry of one occultation. ``et_profile`` are Earth-reception epochs (TDB s).

    ``product_track`` may carry the product's own per-sample ``latitude`` and
    ``longitude`` (deg) and ``radius`` (km) at the same epochs.
    """
    body = get_body(body_id)
    if body is None or body_id not in NAIF_BODY:
        raise ValueError(f"No SPICE body for '{body_id}'")
    bname, fixed, sc = str(NAIF_BODY[body_id]), body_frame(body_id), str(sc_id)
    et_all = np.asarray(et_profile, float)
    good = np.isfinite(et_all)
    if not good.any():
        raise ValueError("The product has no time column to compute geometry from")
    t0, t1 = float(et_all[good].min()), float(et_all[good].max())
    idx = np.flatnonzero(good)
    if idx.size > 400:
        idx = idx[np.linspace(0, idx.size - 1, 400).round().astype(int)]
    et_prof = et_all[idx]
    pt = {k: np.asarray(v, float)[idx] for k, v in (product_track or {}).items()
          if v is not None and len(v) == len(et_all)}

    with _spice_lock:
        _furnsh(plan)
        try:
            r_eq = float(sp.bodvrd(bname, "RADII", 3)[1][0])
            mid = 0.5 * (t0 + t1)
            lt_mid = sp.spkpos(bname, mid, "J2000", "CN", "399")[1]

            sc_fixed, earth_fixed, sun_fixed, sc_j2000, et_emit = [], [], [], [], []
            for t in et_prof:
                sc_e = sp.spkpos(sc, float(t), "J2000", "CN", "399")[0]
                pl_e, lt = sp.spkpos(bname, float(t), "J2000", "CN", "399")
                rot = sp.pxform("J2000", fixed, float(t) - lt)
                sun_j = sp.spkpos("10", float(t) - lt, "J2000", "NONE", bname)[0]
                sc_fixed.append(rot @ (sc_e - pl_e))
                earth_fixed.append(rot @ (-pl_e))
                sun_fixed.append(rot @ sun_j)
                sc_j2000.append(sc_e - pl_e)
                et_emit.append(float(t) - lt)
            sc_fixed, earth_fixed = np.array(sc_fixed), np.array(earth_fixed)
            sun_fixed, sc_j2000, et_emit = np.array(sun_fixed), np.array(sc_j2000), np.array(et_emit)

            # Orbit arc around the occultation (emission epochs)
            et_orbit = np.arange(mid - lt_mid - span_min * 60, mid - lt_mid + span_min * 60 + step_s, step_s)
            orbit_j2000 = np.array([sp.spkpos(sc, float(e), "J2000", "NONE", bname)[0] for e in et_orbit])
            orbit_fixed = np.array([sp.pxform("J2000", fixed, float(e)) @ v for e, v in zip(et_orbit, orbit_j2000)])
            earth_j2000_mid = -sp.spkpos(bname, mid, "J2000", "CN", "399")[0]
            sun_j2000_mid = sp.spkpos("10", mid - lt_mid, "J2000", "NONE", bname)[0]

            # Straight-line tangent point
            d = earth_fixed - sc_fixed
            k = np.clip(-np.einsum("ij,ij->i", sc_fixed, d) / np.einsum("ij,ij->i", d, d), 0, 1)
            sl = sc_fixed + k[:, None] * d
            sl_r = np.linalg.norm(sl, axis=1)

            # Tangent track: the product's refracted solution when available
            if {"latitude", "longitude"} <= pt.keys():
                lat_t, lon_t = pt["latitude"], pt["longitude"] % 360.0
                r_t = pt["radius"] if "radius" in pt else sl_r
                source = "product (refracted ray)"
            else:
                lat_t = np.degrees(np.arcsin(sl[:, 2] / sl_r))
                lon_t = np.degrees(np.arctan2(sl[:, 1], sl[:, 0])) % 360.0
                r_t = sl_r
                source = "straight line (SPICE)"
            clat, clon = np.radians(lat_t), np.radians(lon_t)
            tp = np.stack([r_t * np.cos(clat) * np.cos(clon), r_t * np.cos(clat) * np.sin(clon),
                           r_t * np.sin(clat)], axis=1)
            sun_dir = sun_fixed - tp
            sza = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", tp, sun_dir)
                                               / (np.linalg.norm(tp, axis=1) * np.linalg.norm(sun_dir, axis=1)), -1, 1)))
            lst = []
            for e, lon in zip(et_emit, clon):
                h, m, sec, _, _ = sp.et2lst(float(e), NAIF_BODY[body_id], float(lon), "PLANETOCENTRIC")
                lst.append(h + m / 60 + sec / 3600)
            sep = [np.degrees(sp.vsep(sp.spkpos("10", float(t), "J2000", "NONE", "399")[0],
                                      sp.spkpos(sc, float(t), "J2000", "CN", "399")[0])) for t in et_prof]
            _, ss_lon, ss_lat = sp.reclat(sp.subslr("INTERCEPT/ELLIPSOID", bname, mid - lt_mid, fixed, "NONE", "10")[0])
            _, se_lon, se_lat = sp.reclat(sp.subpnt("INTERCEPT/ELLIPSOID", bname, mid - lt_mid, fixed, "CN", "399")[0])
            utc_range = [sp.et2utc(t0, "ISOC", 0), sp.et2utc(t1, "ISOC", 0)]
        except sp.stypes.SpiceyError as exc:
            text = str(exc)
            if "SPKINSUFFDATA" in text or "Insufficient ephemeris" in text:
                raise LookupError("The spacecraft ephemeris has a gap at this time "
                                  "(no orbit data for the observation).") from exc
            raise LookupError(f"SPICE error: {text.splitlines()[0][:200]}") from exc

    n = -earth_j2000_mid / np.linalg.norm(earth_j2000_mid)        # Earth -> planet
    north = np.array([0.0, 0.0, 1.0]) - n[2] * n
    north /= np.linalg.norm(north)
    east = np.cross(north, n)

    def sky(v):  # x east, y north (sky plane), depth (+ = behind the planet as seen from Earth)
        v = np.asarray(v, float)
        return np.stack([v @ east, v @ north, v @ n], axis=-1)

    bending = None
    if "radius" in pt:
        diff = sl_r - pt["radius"]
        bending = {"median_km": float(np.nanmedian(diff)), "max_abs_km": float(np.nanmax(np.abs(diff)))}

    return {
        "mode": "occultation",
        "body_id": body_id, "body_name": body.name, "radius_km": r_eq, "frame_fixed": fixed,
        "utc_range": utc_range, "light_time_s": float(lt_mid), "time_convention": "Earth reception",
        "tangent_source": source, "straight_line_minus_product_radius": bending,
        "orbit": {"t_s": (et_orbit - (mid - lt_mid)).round(1).tolist(), "fixed": _vec(orbit_fixed),
                  "j2000": _vec(orbit_j2000), "sky": _vec(sky(orbit_j2000))},
        "profile": {
            "t_s": (et_prof - t0).round(2).tolist(),
            "sc_fixed": _vec(sc_fixed), "sc_sky": _vec(sky(sc_j2000)),
            "tangent_lat": np.round(lat_t, 4).tolist(), "tangent_lon": np.round(lon_t, 4).tolist(),
            "tangent_alt_km": np.round(r_t - r_eq, 3).tolist(),
            "sza": np.round(sza, 3).tolist(), "lst_h": np.round(lst, 4).tolist(), "sep_deg": np.round(sep, 4).tolist(),
        },
        "directions_fixed": {"earth": _unit(earth_fixed[len(earth_fixed) // 2]),
                             "sun": _unit(sun_fixed[len(sun_fixed) // 2])},
        "directions_j2000": {"earth": _unit(earth_j2000_mid), "sun": _unit(sun_j2000_mid)},
        "sky": {"sun_dir": np.round(sky(_unit(sun_j2000_mid)), 5).tolist(), "planet_radius_km": r_eq},
        "subsolar": {"lat": float(np.degrees(ss_lat)), "lon": float(np.degrees(ss_lon) % 360)},
        "subearth": {"lat": float(np.degrees(se_lat)), "lon": float(np.degrees(se_lon) % 360)},
    }


def orbit_geometry(plan: KernelPlan, sc_id: int, body_id: str, utc_start: str, utc_stop: str,
                   samples: int = 360) -> Dict[str, Any]:
    """Where the spacecraft was during any observation (in-situ, imaging, spectra...).

    Over the observation (at least an hour, centred on it) the spacecraft's
    position is given in the body-fixed frame, with the sub-spacecraft point,
    altitude, local solar time and solar zenith / emission / phase angles at
    that point.  Epochs are spacecraft times (TDB); positions are corrected for
    light time between the body and the spacecraft (LT+S).
    """
    body = get_body(body_id)
    if body is None or body_id not in NAIF_BODY:
        raise ValueError(f"No SPICE body for '{body_id}'")
    bname, fixed, sc = str(NAIF_BODY[body_id]), body_frame(body_id), str(sc_id)
    with _spice_lock:
        _furnsh(plan)
        try:
            e0 = sp.str2et(utc_start.replace("Z", ""))
            e1 = sp.str2et((utc_stop or utc_start).replace("Z", ""))
            t0, t1 = float(min(e0, e1)), float(max(e0, e1))
            if t1 - t0 < 3600:                       # short products: show the hour around them
                mid = 0.5 * (t0 + t1)
                w0, w1 = mid - 1800, mid + 1800
            elif t1 - t0 > 30 * 86400:               # long products: at most a month
                w0, w1 = t0, t0 + 30 * 86400
            else:
                w0, w1 = t0, t1
            ets = np.linspace(w0, w1, samples)
            radii = sp.bodvrd(bname, "RADII", 3)[1]
            r_eq = float(radii[0])
            pos, lat, lon, alt, lst, sza, emi, pha, inside = [], [], [], [], [], [], [], [], []
            for e in ets:
                p = sp.spkpos(sc, float(e), fixed, "LT+S", bname)[0]
                pos.append(p)
                spoint, trgepc, srfvec = sp.subpnt("INTERCEPT/ELLIPSOID", bname, float(e), fixed, "LT+S", sc)
                _, lo, la = sp.reclat(spoint)
                lat.append(np.degrees(la)); lon.append(np.degrees(lo) % 360)
                alt.append(float(np.linalg.norm(srfvec)))
                _, _, ph, inc, em = sp.ilumin("Ellipsoid", bname, float(e), fixed, "LT+S", sc, spoint)
                sza.append(np.degrees(inc)); emi.append(np.degrees(em)); pha.append(np.degrees(ph))
                h, m, s, _, _ = sp.et2lst(float(trgepc), NAIF_BODY[body_id], float(lo), "PLANETOCENTRIC")
                lst.append(h + m / 60 + s / 3600)
                inside.append(bool(t0 <= e <= t1))
            mid = 0.5 * (t0 + t1)
            sun = sp.spkpos("10", mid, fixed, "LT+S", bname)[0]
            earth = sp.spkpos("399", mid, fixed, "LT+S", bname)[0]
            _, ss_lon, ss_lat = sp.reclat(sp.subslr("INTERCEPT/ELLIPSOID", bname, mid, fixed, "LT+S", sc)[0])
            utc = [sp.et2utc(float(e), "ISOC", 0) for e in ets]
            utc_range = [sp.et2utc(t0, "ISOC", 0), sp.et2utc(t1, "ISOC", 0)]
        except sp.stypes.SpiceyError as exc:
            text = str(exc)
            if "SPKINSUFFDATA" in text or "Insufficient ephemeris" in text:
                raise LookupError("The spacecraft ephemeris has a gap at this time "
                                  "(no orbit data for the observation).") from exc
            if "FRAMEDATANOTFOUND" in text or "NOFRAME" in text or "UNKNOWNFRAME" in text:
                raise LookupError(f"No body-fixed frame for {body.name} in the loaded kernels") from exc
            raise LookupError(f"SPICE error: {text.splitlines()[0][:200]}") from exc
    pos = np.array(pos)
    return {
        "mode": "orbit", "body_id": body_id, "body_name": body.name, "radius_km": r_eq, "frame_fixed": fixed,
        "utc_range": utc_range, "time_convention": "spacecraft (TDB, light-time corrected positions)",
        "track": {
            "utc": utc, "in_observation": inside, "sc_fixed": _vec(pos),
            "lat": np.round(lat, 4).tolist(), "lon": np.round(lon, 4).tolist(),
            "alt_km": np.round(alt, 3).tolist(), "lst_h": np.round(lst, 4).tolist(),
            "sza": np.round(sza, 3).tolist(), "emission": np.round(emi, 3).tolist(),
            "phase": np.round(pha, 3).tolist(),
        },
        "directions_fixed": {"sun": _unit(sun), "earth": _unit(earth)},
        "subsolar": {"lat": float(np.degrees(ss_lat)), "lon": float(np.degrees(ss_lon) % 360)},
        "distance_range_km": [float(np.min(np.linalg.norm(pos, axis=1))), float(np.max(np.linalg.norm(pos, axis=1)))],
    }
