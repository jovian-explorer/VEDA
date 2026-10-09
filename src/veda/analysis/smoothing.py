"""Error-weighted vertical smoothing of a profile on an even grid, with the 1-sigma of the
smoothed values.

Each smoothed value is a weighted mean of the values within +-1.5 FWHM of its level,

    x_i' = sum_j a_ij x_j,    a_ij = K(z_i - z_j) / sigma_j^2 / sum_k K(z_i - z_k) / sigma_k^2,

with K a Gaussian of the chosen full width at half maximum (the vertical resolution the
profile is brought to) and sigma_j the 1-sigma of each value (equal weights without one):
noisy levels count less.  Levels without a value are skipped, so near the ends of a
profile and at data gaps the window is one-sided.  The 1-sigma of a smoothed value counts
the correlation of the errors between levels, r(dz) = exp(-dz^2 / (2 L^2)):

    sigma_i'^2 = sum_j sum_k a_ij a_ik sigma_j sigma_k r(z_j - z_k),

which for independent errors (L = 0) is sum_j a_ij^2 sigma_j^2, about sigma^2 / (number of
levels in the window) for a constant sigma, and stays near sigma when L is larger than the
window.  The smoothed errors are correlated over about sqrt(L^2 + 2 s^2), s the Gaussian's
standard deviation (FWHM / 2.355).

L is taken at the scale of the window (matched_correlation_km): the length at which the
error model predicts the profile's own residual about its smoothed version.  The length
from the level-to-level scatter (uncertainty.error_correlation_from_scatter) is shorter
for real profiles: with it, Mars Express, MGS and MRO profiles smoothed to 2 km scatter
about their smoothed version by only 0.19, 0.29 and 0.40 (medians) of the predicted
variance, i.e. much of their archived error is correlated over more than the window and
is not reduced by smoothing; the matched lengths are 1.25, 1.84 and 2.21 km (medians;
0.47, 1.17 and 1.61 km from the scatter).  On synthetic errors correlated over 0.3, 1 and
3 km it finds 0.30, 1.02 and 3.07 km, and the smoothed 1-sigma then agrees with Monte
Carlo to 1 %.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

FWHM_TO_STD = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))      # 0.4247
WINDOW_FWHM = 1.5                                            # the kernel is cut at +-1.5 FWHM
MAX_HALF_WINDOW = 100                                        # grid levels on each side


def half_window(step_km: float, fwhm_km: float) -> int:
    """Grid levels on each side of a level within the smoothing window."""
    return int(np.floor(WINDOW_FWHM * fwhm_km / step_km + 1e-9))


def smooth_on_grid(values: np.ndarray, sigma: Optional[np.ndarray], step_km: float, fwhm_km: float,
                   corr_km: float = 0.0) -> Dict[str, Optional[np.ndarray]]:
    """Smooth ``values`` on an even grid of spacing ``step_km`` to a vertical resolution
    ``fwhm_km`` (module docstring).  ``sigma``: the 1-sigma of each value, or None (equal
    weights, no uncertainty); ``corr_km``: the Gaussian correlation length of those errors
    on the grid.  Returns the smoothed values, their 1-sigma (None without ``sigma``), the
    weights (levels x window) and their offsets, to smooth other quantities (a systematic
    uncertainty) with the same weights, and the correlation length of the smoothed errors."""
    x = np.asarray(values, dtype=float)
    n = x.size
    h = half_window(step_km, fwhm_km)
    if h > MAX_HALF_WINDOW:
        raise ValueError(f"Smoothing to {fwhm_km:g} km spans more than {2 * MAX_HALF_WINDOW + 1} levels of a "
                         f"{step_km:g} km grid; choose a grid step of at least {WINDOW_FWHM * fwhm_km / MAX_HALF_WINDOW:.2g} km.")
    offsets = np.arange(-h, h + 1)
    idx = np.arange(n)[:, None] + offsets[None, :]                     # (n, window)
    inside = (idx >= 0) & (idx < n)
    idc = np.clip(idx, 0, n - 1)
    s = None if sigma is None else np.asarray(sigma, dtype=float)
    valid = np.isfinite(x) if s is None else (np.isfinite(x) & np.isfinite(s) & (s > 0))
    k = np.exp(-0.5 * (offsets * step_km / (fwhm_km * FWHM_TO_STD)) ** 2)
    w = np.where(inside & valid[idc], k[None, :], 0.0)
    if s is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            w = w / np.where(valid[idc], s[idc], 1.0) ** 2
    total = w.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        a = np.where(total > 0, w / total, 0.0)
    keep = np.isfinite(x) & (total[:, 0] > 0)
    out = np.where(keep, np.sum(a * np.where(inside & valid[idc], x[idc], 0.0), axis=1), np.nan)
    s_out = None
    corr_out = float(np.hypot(corr_km, np.sqrt(2.0) * fwhm_km * FWHM_TO_STD))
    if s is not None:
        b = a * np.where(inside & valid[idc], s[idc], 0.0)                  # a_ij sigma_j
        lag = (offsets[:, None] - offsets[None, :]) * step_km
        r = np.exp(-lag ** 2 / (2.0 * corr_km ** 2)) if corr_km > 0 else np.eye(offsets.size)
        var = np.einsum("ip,pq,iq->i", b, r, b)
        s_out = np.where(keep & (var >= 0), np.sqrt(np.maximum(var, 0.0)), np.nan)
    return {"values": out, "sigma": s_out, "weights": a, "offsets": offsets, "correlation_km": corr_out}


def residual_variance(values: np.ndarray, sigma: np.ndarray, step_km: float, fwhm_km: float,
                      corr_km: float) -> Dict[str, float]:
    """The mean square of the residual (values - smoothed values) over the levels at least
    a window away from the ends and gaps, and the mean the error model predicts for it,
    diag((I - A) C (I - A)^T): sigma_i^2 + sigma_i'^2 - 2 sum_j a_ij sigma_i sigma_j r_ij.
    Errors correlated over longer than the window hardly show in the residual."""
    x = np.asarray(values, dtype=float)
    s = np.asarray(sigma, dtype=float)
    out = smooth_on_grid(x, s, step_km, fwhm_km, corr_km)
    a, off = out["weights"], out["offsets"]
    n = x.size
    idx = np.arange(n)[:, None] + off[None, :]
    inside = (idx >= 0) & (idx < n)
    sj = np.where(inside, s[np.clip(idx, 0, n - 1)], 0.0)
    r = np.exp(-(off * step_km) ** 2 / (2.0 * corr_km ** 2)) if corr_km > 0 else (off == 0).astype(float)
    with np.errstate(invalid="ignore"):
        cross = np.sum(a * np.nan_to_num(sj) * r[None, :], axis=1) * s
        pred = s ** 2 + out["sigma"] ** 2 - 2.0 * cross
        res2 = (x - out["values"]) ** 2
    h = off.size // 2
    good = np.isfinite(res2) & np.isfinite(pred)
    # interior: the whole window on valid levels
    ok = good.copy()
    for d in range(1, h + 1):
        ok[d:] &= good[:-d]
        ok[:-d] &= good[d:]
    ok[:h] = False
    ok[n - h:] = False
    if ok.sum() < 3:
        return {"observed": float("nan"), "predicted": float("nan"), "levels": int(ok.sum())}
    return {"observed": float(np.mean(res2[ok])), "predicted": float(np.mean(pred[ok])), "levels": int(ok.sum())}


def matched_correlation_km(values: np.ndarray, sigma: np.ndarray, step_km: float, fwhm_km: float,
                           corr_min_km: float, corr_max_km: float = 50.0) -> float:
    """Correlation length of a profile's errors at the scale of the smoothing: the L (at
    least ``corr_min_km``, the length its level-to-level scatter allows) at which the error
    model predicts the residual values - smoothed values the profile actually has.  Real
    radio occultation profiles scatter less about their smoothed version than their
    archived errors would make them with the shorter length (Mars Express, MGS, MRO at
    2 km: 0.2-0.4 of the predicted variance): much of the error is correlated over more
    than the window and is not reduced by smoothing.  Structure of the atmosphere smaller
    than the window adds to the residual, so this is still a lower bound."""
    base = residual_variance(values, sigma, step_km, fwhm_km, corr_min_km)
    if not np.isfinite(base["observed"]) or base["observed"] >= base["predicted"]:
        return corr_min_km
    hi = residual_variance(values, sigma, step_km, fwhm_km, corr_max_km)
    if base["observed"] <= hi["predicted"]:
        return corr_max_km
    lo_l, hi_l = max(corr_min_km, 1e-3), corr_max_km
    for _ in range(40):                                     # bisection in log L
        mid = float(np.sqrt(lo_l * hi_l))
        if residual_variance(values, sigma, step_km, fwhm_km, mid)["predicted"] > base["observed"]:
            lo_l = mid
        else:
            hi_l = mid
        if hi_l / lo_l < 1.01:
            break
    return float(np.sqrt(lo_l * hi_l))


def apply_weights(other: np.ndarray, weights: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """The same weighted means of another quantity on the grid (e.g. a systematic
    uncertainty, which two retrievals' difference makes linear in the values); NaN where
    a weighted level has none."""
    y = np.asarray(other, dtype=float)
    n = y.size
    idx = np.arange(n)[:, None] + offsets[None, :]
    inside = (idx >= 0) & (idx < n)
    vals = np.where(inside, y[np.clip(idx, 0, n - 1)], 0.0)
    used = weights > 0
    bad = np.any(used & ~np.isfinite(vals), axis=1) | ~np.any(used, axis=1)
    return np.where(bad, np.nan, np.sum(weights * np.where(np.isfinite(vals), vals, 0.0), axis=1))
