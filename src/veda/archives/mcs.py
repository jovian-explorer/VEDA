"""Mars Climate Sounder (MRO MCS) profiles from the 4-hour DDR files.

Each DDR file (MRO-M-MCS-5-DDR, NASA PDS Atmospheres Node) holds a few hundred retrieved
profiles, one per table row: a header (time, Ls, local true solar time, latitude and
longitude of the profile, the radius of the surface point, quality flags) and 105 levels
on fixed pressure surfaces (p_i = 610 Pa exp(-0.125 (i - 10))) with temperature, its
1-sigma, dust, water and CO2 ice opacities, and the level's altitude above the surface
point, latitude and longitude (Kleinboehl et al. 2009).  VEDA offers each row as a profile
of its own, product id ``<file>_P<row>`` (``2006120120_DDR_P017``): read from the file,
which is downloaded once, and never stored in the catalogue, which lists the files.

Altitudes are put on VEDA's Mars sphere (3389.5 km) from the radius of the surface point
plus the level's altitude above it, so MCS lines up with the radio occultations.  The
local true solar time is given in fractions of a sol.  Rows whose first field is not 0
(invalid record) give no profile; levels with -9999 are missing.
"""
from __future__ import annotations

import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROW_ID = re.compile(r"^(?P<file>.+_DDR)_P(?P<row>\d{3,4})$", re.IGNORECASE)
FILL = -9999.0
LEVEL = "FRAME_STRUCTURE."

_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_CACHE_MAX = 24
_lock = threading.Lock()


def split_id(product_id: str) -> Optional[Tuple[str, int]]:
    """(file product id, row) of an MCS profile id, or None."""
    m = ROW_ID.match(product_id or "")
    return (m.group("file"), int(m.group("row"))) if m else None


def row_id(file_id: str, row: int) -> str:
    return f"{file_id}_P{row:03d}"


def sub_product(file_prod: Dict[str, Any], row: int) -> Dict[str, Any]:
    """The catalogue entry of one row of a DDR file (the file's own entry, as a profile)."""
    return {**file_prod, "product_id": row_id(file_prod["product_id"], row), "kind": "profile",
            "product_type": f"MCS temperature profile (row {row} of the 4-hour file)", "row": row,
            "file_product_id": file_prod["product_id"]}


def _num(table: Dict[str, Any], name: str) -> Optional[np.ndarray]:
    v = table.get(name)
    if v is None or isinstance(v, list):
        return None
    a = np.asarray(v, dtype=float)
    return np.where(np.isclose(a, FILL), np.nan, a)


def read_file(label_path: Path) -> Dict[str, Any]:
    """Every row of a DDR file: header arrays (rows,) and level arrays (rows, 105); cached."""
    key = str(label_path)
    try:
        stamp = label_path.stat().st_mtime
    except OSError:
        stamp = 0.0
    with _lock:
        hit = _CACHE.get(key)
        if hit is not None and hit["stamp"] == stamp:
            _CACHE.move_to_end(key)
            return hit
    from ..readers.product import open_product
    obj = next(o for o in open_product(str(label_path)).objects if o.kind == "table")
    names = {f.name for f in obj.fields}
    want = ["1", "UTC (assembled)", "L_S", "LTST", "SOLAR_ZEN", "PROFILE_LAT", "PROFILE_LON", "SURF_RAD",
            "T_QUAL", "P_QUAL", "OBS_QUAL", "GQUAL"]
    want += [LEVEL + n for n in ("PRES", "T", "T_ERR", "ALT", "LAT", "LON", "DUST", "DUST_ERR", "H2OICE", "H2OICE_ERR")]
    t = obj.read_table([n for n in want if n in names])
    out: Dict[str, Any] = {"stamp": stamp, "rows": int(obj.shape[0])}
    for n in want:
        if n == "UTC (assembled)":
            out["time"] = [str(x) for x in t.get(n) or []]
        elif n in t:
            out[n.replace(LEVEL, "level_")] = _num(t, n)
    with _lock:
        _CACHE[key] = out
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return out


def row_geometry(d: Dict[str, Any], row: int) -> Dict[str, Optional[float]]:
    """Latitude, local time (h), solar zenith angle and Ls of one row (None where missing)."""
    def g(k, scale=1.0):
        a = d.get(k)
        v = None if a is None else float(a[row])
        return None if v is None or not np.isfinite(v) else v * scale
    return {"latitude": g("PROFILE_LAT"), "lst": g("LTST", 24.0), "sza": g("SOLAR_ZEN"), "ls": g("L_S")}


def valid_rows(d: Dict[str, Any]) -> List[int]:
    """Rows that are valid records with at least five levels of temperature."""
    flag = d.get("1")
    t = d.get("level_T")
    out = []
    for i in range(d["rows"]):
        if flag is not None and np.isfinite(flag[i]) and flag[i] != 0:
            continue
        if t is None or np.isfinite(t[i]).sum() < 5:
            continue
        out.append(i)
    return out


def row_profile(ds, prod: Dict[str, Any], label_path: Path, row: int):
    """One row of a DDR file as an ObservationProfile."""
    from ..core.models import ObservationProfile, ProvenanceRecord
    from ..core.registry import get_body
    d = read_file(label_path)
    if not 0 <= row < d["rows"] or row not in valid_rows(d):
        raise ValueError(f"{prod['product_id']}: row {row} of {label_path.name} holds no valid MCS profile")
    body = get_body("mars")
    surf = float(d["SURF_RAD"][row]) if d.get("SURF_RAD") is not None else np.nan
    alt = d["level_ALT"][row] + surf - body.radius_km
    p_hpa = d["level_PRES"][row] / 100.0
    t = d["level_T"][row]
    # the levels with a retrieved temperature (the others are -9999 in all columns)
    good = np.isfinite(alt) & np.isfinite(t) & np.isfinite(p_hpa)
    alt, p_hpa, t = alt[good], p_hpa[good], t[good]
    unc = {}
    if d.get("level_T_ERR") is not None:
        s = d["level_T_ERR"][row][good]
        unc = {"temperature_k": s, "temperature_c": s}
    track = {k: d[f"level_{k.upper()[:3]}"][row][good]
             for k in ("latitude", "longitude") if d.get(f"level_{k.upper()[:3]}") is not None}
    # dust (21.6 um) and water-ice (11.9 um) opacity per km, with their 1-sigma
    aerosols = {}
    for key, col in (("dust_opacity_per_km", "DUST"), ("ice_opacity_per_km", "H2OICE")):
        if d.get(f"level_{col}") is not None and np.isfinite(d[f"level_{col}"][row][good]).any():
            aerosols[key] = d[f"level_{col}"][row][good]
            if d.get(f"level_{col}_ERR") is not None:
                unc[key] = d[f"level_{col}_ERR"][row][good]
    geom = row_geometry(d, row)
    flags = {k: float(d[k][row]) for k in ("T_QUAL", "P_QUAL", "OBS_QUAL", "GQUAL")
             if d.get(k) is not None and np.isfinite(d[k][row])}
    attrs = {"DATASET_ID": ds.id, "VOLUME": prod.get("volume"),
             "ALTITUDE_REFERENCE": f"a sphere of radius {body.radius_km:g} km (from the radius of the surface point "
                                   "plus the level's altitude above it)",
             "MCS_FILE": prod.get("file_product_id") or split_id(prod["product_id"])[0], "MCS_ROW": row,
             **{f"MCS_{k}": v for k, v in flags.items()},
             **({"LST": geom["lst"]} if geom["lst"] is not None else {}),
             **({"SZA": geom["sza"]} if geom["sza"] is not None else {}),
             **({"LS": geom["ls"]} if geom["ls"] is not None else {})}
    times = d.get("time") or []
    time_utc = times[row] if row < len(times) and times[row] else (prod.get("start_time") or "")
    prof = ObservationProfile(
        observation_id=prod["product_id"], mission_id=ds.mission_id, body_id="mars", instrument=ds.instrument,
        time_utc=time_utc, latitude=geom["latitude"],
        longitude=None if d.get("PROFILE_LON") is None or not np.isfinite(d["PROFILE_LON"][row]) else float(d["PROFILE_LON"][row]),
        altitude_km=alt, pressure_hpa=p_hpa, temperature_k=t, temperature_c=t - 273.15,
        provenance=ProvenanceRecord(mission_id=ds.mission_id, instrument=ds.instrument, product_level=ds.level,
                                    original_file=label_path.name, archive_source=ds.archive,
                                    archive_url=prod.get("url", ""), doi_or_citation=ds.citation or ds.doi,
                                    retrieval_method=prod.get("product_type", "")),
        raw_attributes=attrs, uncertainty=unc, track=track)
    prof.derived.update(aerosols)
    return prof


def candidates(ds, files: List[Dict[str, Any]], fetch, geometry_ok, per_file: int) -> List[Dict[str, Any]]:
    """Profile entries from DDR ``files`` (catalogue rows), up to ``per_file`` rows each,
    spread over the file, of the valid rows whose geometry ``geometry_ok`` accepts;
    ``fetch(file)`` gives the downloaded label path (or raises).  The files' rows are
    interleaved, so the first entries span all the files' dates."""
    from ..missions.selection import spread_order
    per: List[List[Dict[str, Any]]] = []
    for f in files:
        try:
            d = read_file(Path(fetch(f)))
        except Exception:  # noqa: BLE001 - a file that cannot be read gives no candidates
            continue
        rows = [r for r in valid_rows(d) if geometry_ok(row_geometry(d, r))]
        rows = [rows[i] for i in spread_order(len(rows))][:per_file]
        per.append([sub_product(f, r) for r in rows])
    out = []
    for k in range(max((len(x) for x in per), default=0)):
        out += [x[k] for x in per if k < len(x)]
    return out
