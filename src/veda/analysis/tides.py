"""Harmonic fits of one quantity against local time or longitude (thermal tides, waves).

With one value per profile at a fixed altitude (the altitude cut), the local-time
structure of migrating tides, or the longitude structure of non-migrating tides and
stationary waves seen at a near-fixed local time, is fitted by least squares as

    y(x) = a_0 + sum_{n=1..N} [a_n cos(n w x) + b_n sin(n w x)],    w = 2 pi / P,

with P = 24 h for local time or 360 deg for longitude.  Each harmonic is
A_n cos(n w (x - x_n)): amplitude A_n = sqrt(a_n^2 + b_n^2) and the x of its first
maximum x_n = atan2(b_n, a_n) / (n w), in [0, P / n).  Uncertainties come from the
covariance of the fit, s^2 (X^T X)^-1 with s^2 the residual variance, propagated to
A_n and x_n to first order.  For quantities spanning orders of magnitude (densities,
pressure) the fit is to ln y, and A_n is given in percent of the mean (100 A_n, the
first-order relative amplitude).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


def harmonic_fit(x, y, period: float, harmonics: int = 2, log: bool = False,
                 samples: int = 97) -> Dict[str, Any]:
    """Least-squares fit of ``harmonics`` harmonics of ``period`` to y(x) (module docstring).

    Points without a finite x or y (or y <= 0 when ``log``) are left out.  At least one
    more point than parameters is needed.  ``max_gap`` is the widest stretch of the
    period without data: the fit is poorly constrained there, and a harmonic n is not
    resolved when the gap exceeds P / (2 n)."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.shape != y.shape:
        raise ValueError("x and y must have the same length")
    if not period or period <= 0:
        raise ValueError("period must be positive")
    harmonics = int(harmonics)
    if not 1 <= harmonics <= 6:
        raise ValueError("harmonics must be between 1 and 6")
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(x) & np.isfinite(y) & ((y > 0) if log else True)
        yy = np.log(y[ok]) if log else y[ok]
    xx = np.mod(x[ok], period)
    n_par = 2 * harmonics + 1
    if xx.size < n_par + 1:
        raise ValueError(f"{harmonics} harmonic(s) need at least {n_par + 1} points with values; there are {xx.size}")
    w = 2.0 * np.pi / period

    def design(t):
        cols = [np.ones_like(t)]
        for n in range(1, harmonics + 1):
            cols += [np.cos(n * w * t), np.sin(n * w * t)]
        return np.column_stack(cols)

    X = design(xx)
    coef, *_ = np.linalg.lstsq(X, yy, rcond=None)
    resid = yy - X @ coef
    dof = xx.size - n_par
    s2 = float(resid @ resid) / dof
    try:
        cov = s2 * np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        raise ValueError("the points do not constrain these harmonics (too few distinct x)")
    if not np.all(np.isfinite(cov)) or np.linalg.cond(X.T @ X) > 1e12:
        raise ValueError("the points do not constrain these harmonics (too few distinct x)")

    scale = 100.0 if log else 1.0
    comps: List[Dict[str, Optional[float]]] = []
    for n in range(1, harmonics + 1):
        i, j = 2 * n - 1, 2 * n
        a, b = coef[i], coef[j]
        va, vb, cab = cov[i, i], cov[j, j], cov[i, j]
        amp = float(np.hypot(a, b))
        if amp > 0:
            s_amp = float(np.sqrt(max(a * a * va + b * b * vb + 2 * a * b * cab, 0.0)) / amp)
            s_ph = float(np.sqrt(max(b * b * va + a * a * vb - 2 * a * b * cab, 0.0)) / amp ** 2)   # radians
        else:
            s_amp, s_ph = float(np.sqrt(va)), float("nan")
        x_max = float(np.mod(np.arctan2(b, a) / (n * w), period / n))
        comps.append({"n": n, "amplitude": amp * scale, "amplitude_sigma": s_amp * scale,
                      "x_of_max": x_max, "x_of_max_sigma": s_ph / (n * w) if np.isfinite(s_ph) else None})
    srt = np.sort(xx)
    gaps = np.diff(np.concatenate([srt, [srt[0] + period]]))
    ss_tot = float(((yy - yy.mean()) ** 2).sum())
    xs = np.linspace(0.0, period, samples)
    curve = design(xs) @ coef
    return {
        "period": float(period), "harmonics": harmonics, "log": bool(log), "n_points": int(xx.size),
        "mean": float(np.exp(coef[0]) if log else coef[0]),
        "components": comps,
        "residual_rms": float(np.sqrt(resid @ resid / xx.size)) * scale,
        "r_squared": float(1.0 - (resid @ resid) / ss_tot) if ss_tot > 0 else None,
        "max_gap": float(gaps.max()),
        "curve_x": xs.tolist(),
        "curve_y": (np.exp(curve) if log else curve).tolist(),
    }
