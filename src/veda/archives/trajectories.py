"""Probe trajectories archived in their own formats, read for the Geometry tab.

Galileo probe (GP-J-DWE-3-ENTRY-V1.0, ``data/dwe/probetrj.tab``): the navigation team's
post-entry trajectory (run JNEFF, "OD126 with 53 sec late parachute"), one row a second
from entry (450 km above 1 bar) for 5400 s.  A row is six 60-byte records:

    time past entry (s), altitude above the 1-bar level (km)
    position (km), velocity (km/s): Jupiter-centred EME50
    local up, west and north unit vectors

The header gives Jupiter's pole and the prime meridian's direction at entry, both in
EME50, and the rotation period (9.92492104 h, System III).  Planetocentric latitude is
the angle of the position from the equator; east longitude is the angle from the prime
meridian, less the planet's rotation since entry.  At entry this gives 6.53 N, 4.88 W;
the probe's SPK (s960730a.bsp, IAU_JUPITER) gives 6.53 N, 4.94 W at the same time.

The trajectory is a ballistic reconstruction: below about 50 km the probe moves with the
planet's rotation only.  The winds measured by the Doppler wind experiment (100-180 m/s,
Atkinson et al. 1998) carried it further east, roughly 0.4 deg of longitude over the
descent, which the file does not include.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Dict, List

import numpy as np

_FLOAT = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?"


def _vector_after(text: str, heading: str) -> np.ndarray:
    """The three numbers on the line after ``heading`` in the label's header note."""
    i = text.index(heading)
    nums = re.findall(_FLOAT, text[text.index("\n", i):])[:3]
    return np.array([float(x) for x in nums])


def read_galileo_probe_trajectory(label: Path) -> Dict[str, List]:
    """UTC, planetocentric latitude, east longitude and altitude above 1 bar (km) of the
    Galileo probe from probetrj.lbl / probetrj.tab (module docstring)."""
    text = label.read_text(encoding="latin-1", errors="replace")
    pole = _vector_after(text, "JOVIAN UNIT POLE VECTOR")
    meridian = _vector_after(text, "AND THE JOVIAN EQUATOR IN EME50")
    period_h = float(re.search(r"PLANET ROTATION PERIOD, HRS\s+(" + _FLOAT + ")", text).group(1))
    et1950 = float(re.search(r"SECONDS PAST 1950\)\s*=\s*(" + _FLOAT + ")", text).group(1))
    table = next(p for p in label.parent.iterdir() if p.name.lower() == "probetrj.tab")
    lines = [ln for ln in table.read_bytes().decode("ascii", errors="replace").splitlines() if ln.strip()]
    rows = np.array([[float(x) for x in re.findall(_FLOAT, " ".join(lines[i:i + 6]))[:5]]
                     for i in range(0, len(lines) - 5, 6)])
    t, alt, r = rows[:, 0], rows[:, 1], rows[:, 2:5]
    rh = r / np.linalg.norm(r, axis=1)[:, None]
    east = np.cross(pole, meridian)
    w = 360.0 / (period_h * 3600.0)
    lat = np.degrees(np.arcsin(np.clip(rh @ pole, -1, 1)))
    lon = (np.degrees(np.arctan2(rh @ east, rh @ meridian)) - w * t) % 360.0
    # entry epoch: ephemeris time (seconds past 1950 ET) -> UTC (ET - UTC = 61.184 s in 1995)
    entry = _dt.datetime(1950, 1, 1) + _dt.timedelta(seconds=et1950 - 61.184)
    utc = [(entry + _dt.timedelta(seconds=float(s))).isoformat(timespec="milliseconds") for s in t]
    return {"utc": utc, "lat": lat.tolist(), "lon": lon.tolist(), "alt_km": alt.tolist(),
            "source": ("Reconstructed: the navigation team's post-entry trajectory (Doppler wind data, "
                       "probetrj.tab); planetocentric latitude, System III longitude; it leaves out the eastward "
                       "drift with the winds during the descent (about 0.4 deg, Atkinson et al. 1998)")}


def read_vega_balloon_track(label: Path) -> Dict[str, List]:
    """A VEGA balloon's tracked position (VEGA1/VEGA2-V-2/3-VENUS-V1.0 vg1bl_rdr, vg2bl_rdr):
    radius (km), latitude and east longitude (radians) "estimated" from VLBI tracking,
    zero where there is no position; time in seconds from 0 h UT on the label's start date."""
    from ..readers.pds3_reader import read_pds3_table
    tbl = read_pds3_table(str(label))
    col = lambda name: np.asarray(next(v for k, v in tbl.columns.items()            # noqa: E731
                                       if k.strip('"').lower() == name), dtype=float)
    r, lat, lon, t = col("radius"), col("latitude"), col("longitude"), col("time")
    ok = np.isfinite(r) & (r > 0) & np.isfinite(lat) & np.isfinite(lon)
    from ..core.registry import get_body
    day = _dt.datetime.fromisoformat(str(tbl.metadata.get("START_TIME", "1985-06-11"))[:10])
    return {"utc": [(day + _dt.timedelta(seconds=float(s))).isoformat(timespec="seconds") for s in t[ok]],
            "lat": np.round(np.degrees(lat[ok]), 4).tolist(), "lon": np.round(np.degrees(lon[ok]) % 360, 4).tolist(),
            "alt_km": np.round(r[ok] - get_body("venus").radius_km, 3).tolist(),
            "source": ("Measured: the balloon's position from VLBI tracking in its record "
                       f"({label.stem}; Lorenz et al. 2018); altitudes above the 6051.8 km sphere")}


# product id (or part of it) -> reader of a probe's or balloon's track in its own format
READERS = {"PROBETRJ": read_galileo_probe_trajectory, "BL_RDR": read_vega_balloon_track}
