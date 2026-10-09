"""Coincident pairs between groups of compared profiles: instrument intercomparison.

Profiles of two instruments are rarely taken at the same time and place, and comparing
their climatologies mixes sampling with calibration.  Pairs close in time, latitude,
longitude and local time compare the instruments on the same atmosphere.  For the first
group of a comparison (missions or instruments, ``Group composites by``) and each other
group, every candidate pair within the tolerances gets a normalised distance

    D^2 = (dt / T)^2 + (dlat / L)^2 + (dlon / G)^2 + (dlst / H)^2,

(longitude and local time wrapped; a criterion is dropped for a pair where a profile lacks
the quantity), and pairs are taken greedily from the smallest D with each profile used
once, so the pairs are independent.  At every level of the comparison grid the
differences (other minus first; in percent of the first for pressure and densities) give
the mean, its standard error s / sqrt(n) and a 95 % percentile bootstrap interval over
the pairs.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

DEFAULT_TOLERANCES = {"hours": 12.0, "lat": 5.0, "lon": 20.0, "lst": 1.5}
BOOTSTRAP_DRAWS = 1000
_SEED = 20261009


def _time(s: Dict[str, Any]) -> Optional[_dt.datetime]:
    t = (s.get("time_utc") or "").replace("Z", "")
    try:
        return _dt.datetime.fromisoformat(t[:26]) if t else None
    except ValueError:
        try:
            return _dt.datetime.fromisoformat(t[:19])
        except ValueError:
            return None


def _wrapped(a: Optional[float], b: Optional[float], period: float) -> Optional[float]:
    if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
        return None
    return abs((a - b + period / 2.0) % period - period / 2.0)


def separations(sa: Dict[str, Any], sb: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Time (h), latitude, longitude (deg) and local time (h) between two profile summaries."""
    ta, tb = _time(sa), _time(sb)
    la, lb = sa.get("latitude"), sb.get("latitude")
    return {"hours": None if ta is None or tb is None else abs((ta - tb).total_seconds()) / 3600.0,
            "lat": None if la is None or lb is None else abs(float(la) - float(lb)),
            "lon": _wrapped(sa.get("longitude"), sb.get("longitude"), 360.0),
            "lst": _wrapped(sa.get("lst"), sb.get("lst"), 24.0)}


def match_pairs(a: List[Dict[str, Any]], b: List[Dict[str, Any]], tol: Dict[str, float]) -> List[Tuple[int, int, Dict[str, Optional[float]]]]:
    """Independent pairs (index in a, index in b, separations), greedily by distance."""
    cands = []
    for i, sa in enumerate(a):
        for j, sb in enumerate(b):
            sep = separations(sa, sb)
            if sep["hours"] is None or sep["lat"] is None:
                continue                       # time and latitude are always needed
            d2, ok = 0.0, True
            for k, lim in tol.items():
                v = sep.get(k)
                if v is None or not lim:
                    continue
                if v > lim:
                    ok = False
                    break
                d2 += (v / lim) ** 2
            if ok:
                cands.append((d2, i, j, sep))
    cands.sort(key=lambda c: c[0])
    used_a, used_b, out = set(), set(), []
    for _, i, j, sep in cands:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            out.append((i, j, sep))
    return sorted(out)


def coincident_differences(mat: np.ndarray, summaries: List[Dict[str, Any]], keys: List[Any], log_like: bool,
                           sig: Callable[[float], Any], tol: Optional[Dict[str, float]] = None,
                           draws: int = BOOTSTRAP_DRAWS) -> List[Dict[str, Any]]:
    """Mean difference of coincident pairs between the first group and each other group
    (``keys``: each profile's (sort key, label) group, None outside any) on the grid."""
    import warnings
    tol = {**DEFAULT_TOLERANCES, **(tol or {})}
    order = sorted({k for k in keys if k is not None}, key=lambda k: k[0])
    if len(order) < 2:
        return []
    first = order[0]
    ia = [i for i, k in enumerate(keys) if k == first]
    out = []
    rng = np.random.default_rng(_SEED)
    tr = (lambda d: 100.0 * (np.exp(d) - 1.0)) if log_like else (lambda d: d)
    for other in order[1:]:
        ib = [i for i, k in enumerate(keys) if k == other]
        pairs = match_pairs([summaries[i] for i in ia], [summaries[i] for i in ib], tol)
        entry = {"label": f"{other[1]} minus {first[1]}", "group": other[1], "reference_group": first[1],
                 "n_pairs": len(pairs), "percent": bool(log_like), "tolerances": tol,
                 "pairs": [{"first": summaries[ia[i]]["observation_id"], "other": summaries[ib[j]]["observation_id"],
                            **{k: (None if v is None else round(float(v), 3)) for k, v in sep.items()}}
                           for i, j, sep in pairs]}
        if not pairs:
            out.append({**entry, "difference": [], "se": [], "ci95_low": [], "ci95_high": [], "pairs_per_level": []})
            continue
        d = np.array([mat[ib[j]] - mat[ia[i]] for i, j, _ in pairs])          # pairs x levels
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            n = np.isfinite(d).sum(axis=0)
            mean = np.where(n >= 1, np.nanmean(d, axis=0), np.nan)
            se = np.where(n >= 2, np.nanstd(d, axis=0, ddof=1) / np.sqrt(np.maximum(n, 1)), np.nan)
            lo = hi = np.full(mean.shape, np.nan)
            if len(pairs) >= 2:
                idx = rng.integers(0, len(pairs), size=(draws, len(pairs)))
                boot = np.nanmean(d[idx], axis=1)                              # draws x levels
                lo, hi = np.nanpercentile(boot, [2.5, 97.5], axis=0)
                lo, hi = np.where(n >= 2, lo, np.nan), np.where(n >= 2, hi, np.nan)
        entry.update({"difference": [sig(x) for x in tr(mean)],
                      "se": [sig(x) for x in (100.0 * se if log_like else se)],
                      "ci95_low": [sig(x) for x in tr(lo)], "ci95_high": [sig(x) for x in tr(hi)],
                      "pairs_per_level": [int(x) for x in n],
                      "pair_series": [[sig(x) for x in tr(row)] for row in d]})
        out.append(entry)
    return out
