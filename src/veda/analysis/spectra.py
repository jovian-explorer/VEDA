"""Vertical wavenumber spectra of temperature perturbations.

In a layer z1-z2 a profile's temperature is put on an even grid (its median level
spacing, at least 50 m), a quadratic fit is taken as the background T0(z), and the
normalised perturbation x = (T - T0) / T0 is Hann-windowed and Fourier transformed.
The one-sided power spectral density, in (cycles/km)^-1,

    P(m) = 2 |X(m)|^2 dz / sum(w^2),      m = k / (n dz),  k = 1 .. n/2,

integrates over m to the variance of the windowed perturbation (Parseval).  Wavelengths
from two level spacings up to the layer depth are resolved; the quadratic background
removes most of the power at the longest ones.  Saturated gravity waves give P ~ m^-3.

Spectra of several profiles are put on one logarithmic wavenumber grid (within the range
every profile resolves) and averaged; the mean comes with its standard error and a 95 %
bootstrap interval over the profiles.  The slope of log10 P against log10 m is fitted
between the third-longest wavelength the layer holds and four level spacings, with its
standard error from the fit and a bootstrap interval over the profiles.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

MIN_POINTS = 16
MIN_COVERAGE = 0.9
BOOTSTRAP_DRAWS = 1000
_SEED = 20261006


def profile_spectrum(z_km, t_k, z1: float, z2: float) -> Optional[Dict[str, Any]]:
    """Spectrum of one profile in the layer z1-z2 (module docstring), or None when the
    profile does not cover at least MIN_COVERAGE of the layer with MIN_POINTS levels."""
    z = np.asarray(z_km, dtype=float)
    t = np.asarray(t_k, dtype=float)
    ok = np.isfinite(z) & np.isfinite(t) & (t > 0) & (z >= z1) & (z <= z2)
    if ok.sum() < MIN_POINTS:
        return None
    zs, ts = z[ok], t[ok]
    order = np.argsort(zs)
    zs, ts = zs[order], ts[order]
    zs, idx = np.unique(zs, return_index=True)
    ts = ts[idx]
    if zs.size < MIN_POINTS or (zs[-1] - zs[0]) < MIN_COVERAGE * (z2 - z1):
        return None
    dz = max(float(np.median(np.diff(zs))), 0.05)
    grid = np.arange(zs[0], zs[-1] + 1e-9, dz)
    if grid.size < MIN_POINTS:
        return None
    tg = np.interp(grid, zs, ts)
    t0 = np.polyval(np.polyfit(grid - grid.mean(), tg, 2), grid - grid.mean())
    x = (tg - t0) / t0
    w = np.hanning(grid.size)
    spec = np.fft.rfft(x * w)
    m = np.fft.rfftfreq(grid.size, dz)
    psd = 2.0 * np.abs(spec) ** 2 * dz / np.sum(w * w)
    return {"m": m[1:], "psd": psd[1:], "dz": dz, "depth": float(grid[-1] - grid[0]),
            "variance": float(np.mean((x * w) ** 2) / np.mean(w * w))}


def _slope(logm: np.ndarray, logp: np.ndarray):
    ok = np.isfinite(logm) & np.isfinite(logp)
    if ok.sum() < 4:
        return None, None
    a = np.polyfit(logm[ok], logp[ok], 1, cov=True)
    return float(a[0][0]), float(np.sqrt(a[1][0, 0]))


def composite_spectrum(profiles: List[Dict[str, Any]], n_grid: int = 40) -> Dict[str, Any]:
    """Mean spectrum of profile spectra on a common log wavenumber grid, with standard
    error and bootstrap interval, and the fitted slope (module docstring)."""
    if not profiles:
        return {"n": 0}
    m_lo = max(p["m"][0] for p in profiles)
    m_hi = min(p["m"][-1] for p in profiles)
    if not m_hi > m_lo:
        return {"n": len(profiles), "error": "the profiles share no range of wavenumbers"}
    m = np.logspace(np.log10(m_lo), np.log10(m_hi), n_grid)
    mat = np.array([np.exp(np.interp(np.log(m), np.log(p["m"]), np.log(np.maximum(p["psd"], 1e-300))))
                    for p in profiles])
    n = mat.shape[0]
    mean = mat.mean(axis=0)
    sem = mat.std(axis=0, ddof=1) / np.sqrt(n) if n > 1 else np.full(m.size, np.nan)
    # slope band: from three cycles per layer depth to a quarter of the finest Nyquist
    depth = min(p["depth"] for p in profiles)
    dzmax = max(p["dz"] for p in profiles)
    band = (m >= 3.0 / depth) & (m <= 1.0 / (4.0 * dzmax))
    slope, slope_se = _slope(np.log10(m[band]), np.log10(mean[band])) if band.sum() >= 4 else (None, None)
    out: Dict[str, Any] = {"n": n, "m": m.tolist(), "mean": mean.tolist(),
                           "sem": [None if not np.isfinite(v) else float(v) for v in sem],
                           "slope": slope, "slope_se": slope_se,
                           "slope_band": [float(3.0 / depth), float(1.0 / (4.0 * dzmax))] if band.sum() >= 4 else None,
                           "ci95_low": None, "ci95_high": None, "slope_ci95": None}
    if n >= 2:
        rng = np.random.default_rng(_SEED)
        idx = rng.integers(0, n, (BOOTSTRAP_DRAWS, n))
        means = mat[idx].mean(axis=1)
        lo, hi = np.percentile(means, [2.5, 97.5], axis=0)
        out["ci95_low"], out["ci95_high"] = lo.tolist(), hi.tolist()
        if slope is not None:
            sl = [_slope(np.log10(m[band]), np.log10(mb[band]))[0] for mb in means]
            sl = np.array([s for s in sl if s is not None])
            if sl.size >= BOOTSTRAP_DRAWS // 2:
                out["slope_ci95"] = [float(v) for v in np.percentile(sl, [2.5, 97.5])]
    return out
