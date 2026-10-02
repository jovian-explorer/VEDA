"""Choosing profiles for a cross-mission comparison by time and observing geometry.

Profiles are taken from the archive catalogue of every profile data set of the
chosen missions on the body, spread evenly over the requested dates (not just
the first ones), downloaded when needed, and kept when their latitude, local
solar time and solar zenith angle fall in the requested ranges.  Geometry is
known only once a profile is read, so each mission has a budget of profiles to
try; what was tried, kept and why others were left out is reported.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..archives import catalog
from ..archives.datasets import datasets_for, get_dataset
from ..core.models import ObservationProfile

IONOSPHERE_VARIABLES = {"electron_density_cm3"}
_IONO = re.compile(r"ionosph|electron", re.I)


@dataclass
class ProfileFilter:
    start: Optional[str] = None            # ISO date or date-time, inclusive
    end: Optional[str] = None
    lat_min: Optional[float] = None        # degrees north
    lat_max: Optional[float] = None
    lst_min: Optional[float] = None        # local solar time, hours; lst_min > lst_max wraps midnight
    lst_max: Optional[float] = None
    sza_min: Optional[float] = None        # solar zenith angle, degrees
    sza_max: Optional[float] = None
    per_mission: int = 10                  # profiles kept per mission
    download: bool = True                  # fetch profiles not yet downloaded
    include_uploads: bool = True           # files the user loaded for this body

    def geometry_limits(self) -> bool:
        return any(v is not None for v in (self.lat_min, self.lat_max, self.lst_min, self.lst_max,
                                           self.sza_min, self.sza_max))


def _median(a) -> Optional[float]:
    if a is None:
        return None
    a = np.asarray(a, dtype=float)
    return float(np.nanmedian(a)) if np.isfinite(a).any() else None


def profile_geometry(p: ObservationProfile) -> Dict[str, Optional[float]]:
    """Latitude, local solar time (h) and solar zenith angle (deg) of a profile: the median
    along the ray path where the archive gives them per level, else its header values."""
    track = p.track or {}
    attrs = p.raw_attributes or {}
    lst = _median(track.get("lst"))
    sza = _median(track.get("sza"))
    if lst is None and isinstance(attrs.get("LST"), (int, float)):
        lst = float(attrs["LST"])
    if sza is None and isinstance(attrs.get("SZA"), (int, float)):
        sza = float(attrs["SZA"])
    return {"latitude": p.latitude, "lst": lst, "sza": sza}


def _in(v: Optional[float], lo: Optional[float], hi: Optional[float]) -> Optional[bool]:
    """True/False against [lo, hi]; None when the value is unknown but a limit is set."""
    if lo is None and hi is None:
        return True
    if v is None or not np.isfinite(v):
        return None
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def _lst_in(v: Optional[float], lo: Optional[float], hi: Optional[float]) -> Optional[bool]:
    if lo is not None and hi is not None and lo > hi:          # e.g. 22 h to 2 h
        if v is None or not np.isfinite(v):
            return None
        return v >= lo or v <= hi
    return _in(v, lo, hi)


def passes(geom: Dict[str, Optional[float]], f: ProfileFilter) -> Tuple[bool, str]:
    checks = (("latitude", _in(geom["latitude"], f.lat_min, f.lat_max)),
              ("local time", _lst_in(geom["lst"], f.lst_min, f.lst_max)),
              ("solar zenith angle", _in(geom["sza"], f.sza_min, f.sza_max)))
    for name, ok in checks:
        if ok is None:
            return False, f"{name} unknown"
        if not ok:
            return False, f"{name} outside the range"
    return True, ""


def _candidates(ds_ids: List[str], f: ProfileFilter, variable: str, n: int) -> Tuple[int, List[Dict[str, Any]]]:
    """Up to ``n`` profile products of the data sets in the date range, evenly spread in time."""
    q = catalog.SearchQuery(dataset_ids=ds_ids, start=f.start, end=f.end, kind="profile",
                            downloaded_only=not f.download, limit=1)
    total = catalog.search(q)["total"]
    if not total:
        return 0, []
    want_iono = variable in IONOSPHERE_VARIABLES
    out: List[Dict[str, Any]] = []
    seen = set()
    # One candidate from each of n evenly spaced positions of the time-ordered list:
    # the first product of the right kind (ionosphere or neutral atmosphere) at or
    # after the position, so the budget is not spent on the wrong kind.
    q.limit = 20
    for k in range(min(n, total)):
        q.offset = (k * total) // min(n, total)
        for p in catalog.search(q)["products"]:
            if p["product_id"] not in seen and bool(_IONO.search(p.get("product_type") or "")) == want_iono:
                seen.add(p["product_id"])
                out.append(p)
                break
    return total, [out[i] for i in spread_order(len(out))]


def spread_order(n: int) -> List[int]:
    """0..n-1 reordered so that every prefix is spread over the whole range (first, middle,
    quarters, ...): when only some candidates are kept they still span the dates."""
    order, seen = [], set()
    denom = 1
    while len(order) < n:
        for num in range(0, denom + 1):
            i = min(n - 1, round(num * (n - 1) / denom)) if n > 1 else 0
            if i not in seen:
                seen.add(i)
                order.append(i)
        denom *= 2
    return order


def select_profiles(manager, body_id: str, mission_ids: List[str], variable: str,
                    f: ProfileFilter) -> Tuple[List[ObservationProfile], Dict[str, Any]]:
    """Profiles of ``mission_ids`` on ``body_id`` matching ``f``, with a per-mission report."""
    kept: List[ObservationProfile] = []
    report: Dict[str, Any] = {}
    budget = f.per_mission * (4 if f.geometry_limits() else 1)
    for mid in mission_ids:
        ds_ids = [d.id for d in datasets_for(mid, body_id) if not d.portal_only and not d.service
                  and any(kind == "profile" for _, _, kind in d.rules)]
        r = {"in_date_range": 0, "tried": 0, "kept": 0, "left_out": {}, "failed": 0}
        report[mid] = r
        if not ds_ids:
            r["note"] = "no profile data sets for this body"
            continue
        not_indexed = [d for d in ds_ids if not catalog.dataset_status(get_dataset(d))["indexed_products"]]
        if not_indexed:
            r["not_indexed"] = not_indexed
        r["in_date_range"], cands = _candidates(ds_ids, f, variable, budget)
        n_kept = 0
        for p in cands:
            if n_kept >= f.per_mission:
                break
            r["tried"] += 1
            try:
                prof = manager.load_profile(mid, p["product_id"])
            except Exception:  # noqa: BLE001 - one bad product must not stop the comparison
                prof = None
            if prof is None:
                r["failed"] += 1
                continue
            ok, why = passes(profile_geometry(prof), f)
            if not ok:
                r["left_out"][why] = r["left_out"].get(why, 0) + 1
                continue
            kept.append(prof)
            n_kept += 1
        r["kept"] = n_kept
    if f.include_uploads:
        kept += _uploads(manager, body_id, f, report)
    return kept, report


def _uploads(manager, body_id: str, f: ProfileFilter, report: Dict[str, Any]) -> List[ObservationProfile]:
    """The user's loaded profiles of this body that match the dates and geometry."""
    from .uploads_adapter import MISSION_ID, list_uploads
    items = [i for i in list_uploads() if i["body_id"] == body_id and i["data_type"] == "profile"]
    if not items:
        return []
    r = {"in_date_range": 0, "tried": 0, "kept": 0, "left_out": {}, "failed": 0}
    out = []
    for it in items:
        t = (it.get("time_utc") or "")[:19]
        if (f.start or f.end) and not t:
            r["left_out"]["time unknown"] = r["left_out"].get("time unknown", 0) + 1
            continue
        if (f.start and t < f.start) or (f.end and t[:10] > f.end[:10]):
            continue
        r["in_date_range"] += 1
        r["tried"] += 1
        prof = manager.load_profile(MISSION_ID, it["observation_id"])
        if prof is None:
            r["failed"] += 1
            continue
        ok, why = passes(profile_geometry(prof), f)
        if not ok:
            r["left_out"][why] = r["left_out"].get(why, 0) + 1
            continue
        out.append(prof)
    r["kept"] = len(out)
    report[MISSION_ID] = r
    return out
