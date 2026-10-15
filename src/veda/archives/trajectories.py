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
    return {"utc": utc, "lat": lat.tolist(), "lon": lon.tolist(), "alt_km": alt.tolist()}


# product id -> reader, for Dataset.descent_trajectory entries in these formats
READERS = {"PROBETRJ": read_galileo_probe_trajectory}
