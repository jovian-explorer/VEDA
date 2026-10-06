"""Bootstrap statistics of one value per profile (the points of an altitude cut).

The mean of the points, its standard error s / sqrt(n), and 95 % percentile bootstrap
intervals of the mean and of the median: the points are resampled with replacement
BOOTSTRAP_DRAWS times and the statistic recomputed; the 2.5 and 97.5 percentiles of the
results bound the interval.  For quantities averaged in log space (densities, pressure)
the statistics are those of ln y, given back as values (geometric mean).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

BOOTSTRAP_DRAWS = 1000
_SEED = 20261006


def bootstrap_statistics(values, log: bool = False, groups: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Statistics of ``values`` (non-finite, and non-positive when ``log``, left out),
    and of each group of them when ``groups`` (one label per value) is given."""
    v = np.asarray(values, dtype=float).ravel()
    labels = list(groups) if groups is not None else None
    if labels is not None and len(labels) != v.size:
        raise ValueError("groups must have one label per value")
    out = _stats(v, log)
    if labels is not None:
        out["groups"] = [{"label": g, **_stats(v[[lab == g for lab in labels]], log)}
                         for g in dict.fromkeys(labels)]
    return out


def _stats(v: np.ndarray, log: bool) -> Dict[str, Any]:
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(v) & ((v > 0) if log else True)
        x = np.log(v[ok]) if log else v[ok]
    n = int(x.size)
    res: Dict[str, Any] = {"n": n, "mean": None, "sem": None, "mean_ci95": None, "median": None, "median_ci95": None}
    if n == 0:
        return res
    back = (lambda a: float(np.exp(a))) if log else float
    res["mean"], res["median"] = back(x.mean()), back(np.median(x))
    if n < 2:
        return res
    sem = float(x.std(ddof=1) / np.sqrt(n))
    res["sem"] = sem * 100.0 if log else sem                   # percent of the (geometric) mean for log
    rng = np.random.default_rng(_SEED)
    idx = rng.integers(0, n, (BOOTSTRAP_DRAWS, n))
    means = x[idx].mean(axis=1)
    medians = np.median(x[idx], axis=1)
    res["mean_ci95"] = [back(q) for q in np.percentile(means, [2.5, 97.5])]
    res["median_ci95"] = [back(q) for q in np.percentile(medians, [2.5, 97.5])]
    return res
