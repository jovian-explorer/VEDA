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


def correlation(x, y, log_x: bool = False, log_y: bool = False) -> Dict[str, Any]:
    """Correlation and least-squares regression of y on x across profiles (one pair per
    profile; pairs with a non-finite value, or a non-positive one on a log axis, left out;
    log axes use log10).

    Pearson r with a 95 % interval from Fisher's z (atanh r +- 1.96 / sqrt(n - 3)) and
    its two-sided p-value (t = r sqrt((n - 2) / (1 - r^2)), n - 2 degrees of freedom);
    Spearman's rank correlation with a 95 % bootstrap interval; the line y = a + b x with
    the standard errors of a and b, a 95 % interval of b from Student's t and one from the
    bootstrap (pairs resampled BOOTSTRAP_DRAWS times)."""
    from scipy import stats
    xv = np.asarray(x, dtype=float).ravel()
    yv = np.asarray(y, dtype=float).ravel()
    if xv.shape != yv.shape:
        raise ValueError("x and y must have the same length")
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(xv) & np.isfinite(yv) & ((xv > 0) if log_x else True) & ((yv > 0) if log_y else True)
        xs = np.log10(xv[ok]) if log_x else xv[ok]
        ys = np.log10(yv[ok]) if log_y else yv[ok]
    n = int(xs.size)
    if n < 4:
        raise ValueError(f"a correlation needs at least 4 profiles with both values; there are {n}")
    if np.ptp(xs) == 0 or np.ptp(ys) == 0:
        raise ValueError("one of the two quantities does not vary across these profiles")
    r, p = stats.pearsonr(xs, ys)
    zf, half = np.arctanh(np.clip(r, -0.999999, 0.999999)), 1.96 / np.sqrt(n - 3) if n > 3 else np.nan
    rho = float(stats.spearmanr(xs, ys)[0])
    lr = stats.linregress(xs, ys)
    tq = float(stats.t.ppf(0.975, n - 2))
    rng = np.random.default_rng(_SEED)
    idx = rng.integers(0, n, (BOOTSTRAP_DRAWS, n))
    slopes, rhos = [], []
    for i in idx:
        xi, yi = xs[i], ys[i]
        if np.ptp(xi) == 0 or np.ptp(yi) == 0:
            continue
        slopes.append(np.polyfit(xi, yi, 1)[0])
        rhos.append(stats.spearmanr(xi, yi)[0])
    out = {"n": n, "log_x": bool(log_x), "log_y": bool(log_y),
           "pearson_r": float(r), "pearson_ci95": [float(np.tanh(zf - half)), float(np.tanh(zf + half))],
           "p_value": float(p), "spearman_rho": rho,
           "spearman_ci95": [float(v) for v in np.percentile(rhos, [2.5, 97.5])] if len(rhos) >= BOOTSTRAP_DRAWS // 2 else None,
           "slope": float(lr.slope), "slope_se": float(lr.stderr), "intercept": float(lr.intercept),
           "intercept_se": float(lr.intercept_stderr),
           "slope_ci95_t": [float(lr.slope - tq * lr.stderr), float(lr.slope + tq * lr.stderr)],
           "slope_ci95_bootstrap": [float(v) for v in np.percentile(slopes, [2.5, 97.5])] if len(slopes) >= BOOTSTRAP_DRAWS // 2 else None}
    xl = np.array([xs.min(), xs.max()])
    yl = lr.intercept + lr.slope * xl
    out["line_x"] = (10 ** xl if log_x else xl).tolist()
    out["line_y"] = (10 ** yl if log_y else yl).tolist()
    return out
