"""Hydrostatic retrievals and checks on vertical profiles.

Temperature from a density profile (accelerometer, stellar and solar occultation
data): with the hydrostatic equation dp/dz = -rho g and the ideal gas law
p = rho R T,

    p(z) = p_top + integral_z^z_top rho(z') g(z') dz',      T(z) = p(z) / (rho(z) R)

The upper boundary is p_top = rho_top R T_top, T_top being the temperature of an
isothermal layer fitted to the top of the profile: ln rho = c - Phi / (R T_top), with
Phi the geopotential (integral of g dz), i.e. the density scale height H = R T / g.  An error
dT_top in it decays downwards as dT_top rho_top / rho(z), i.e. by e every scale height,
so the temperatures are independent of it a few scale heights below the top.  Between
two levels the density is taken as exponential, so the integral is exact for an
isothermal layer: integral rho dz = (rho_1 - rho_2) dz / ln(rho_1 / rho_2).
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

# Part of the profile's altitude range at its top used to fit the boundary scale height
TOP_FIT_FRACTION = 0.2
TOP_FIT_MIN_POINTS = 5


def _layer_integral(z: np.ndarray, rho: np.ndarray, g: np.ndarray) -> np.ndarray:
    """integral of rho g dz over each layer between consecutive levels (z ascending, m)."""
    dz = np.diff(z)
    r1, r2 = rho[:-1], rho[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.log(r1 / r2)
        expo = np.where(np.abs(ratio) > 1e-9, (r1 - r2) / ratio, 0.5 * (r1 + r2))
    return expo * dz * 0.5 * (g[:-1] + g[1:])


def temperature_from_density(z_km, rho, g_ms2, r_spec: float, rho_sigma=None,
                             t_top: Optional[float] = None) -> Dict[str, object]:
    """Temperature (K) and pressure (Pa) at the levels of a mass density profile (kg/m^3)
    by downward hydrostatic integration (module docstring).  ``t_top`` fixes the
    temperature at the top instead of fitting the top scale height; ``rho_sigma`` weights
    that fit.  Levels without a positive density, and profiles too short to fit, give NaN.
    """
    z = np.asarray(z_km, dtype=float)
    rho = np.asarray(rho, dtype=float)
    g = np.broadcast_to(np.asarray(g_ms2, dtype=float), z.shape)
    n = z.size
    t_out = np.full(n, np.nan)
    p_out = np.full(n, np.nan)
    result: Dict[str, object] = {"temperature_k": t_out, "pressure_pa": p_out, "top_temperature_k": None,
                                 "top_km": None}
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(z) & np.isfinite(rho) & (rho > 0) & np.isfinite(g)
    if ok.sum() < TOP_FIT_MIN_POINTS:
        return result
    idx = np.where(ok)[0]
    idx = idx[np.argsort(z[idx], kind="stable")]
    zs, rs, gs = z[idx] * 1000.0, rho[idx], g[idx]

    if t_top is None:
        span = zs[-1] - zs[0]
        top = zs >= zs[-1] - TOP_FIT_FRACTION * span
        if top.sum() < TOP_FIT_MIN_POINTS:
            top = np.zeros(zs.size, dtype=bool)
            top[-TOP_FIT_MIN_POINTS:] = True
        w = None
        if rho_sigma is not None:
            s = np.asarray(rho_sigma, dtype=float)[idx][top]
            with np.errstate(divide="ignore", invalid="ignore"):
                w = np.where(np.isfinite(s) & (s > 0), rs[top] / s, np.nan)   # 1 / sigma(ln rho)
            if not np.isfinite(w).all():
                w = None
        # ln rho against the geopotential (integral of g dz): its slope is -1 / (R T) for
        # an isothermal layer even where g changes over the fitted heights
        phi = np.concatenate([[0.0], np.cumsum(0.5 * (gs[1:] + gs[:-1]) * np.diff(zs))])
        slope = np.polyfit(phi[top], np.log(rs[top]), 1, w=w)[0]
        if not np.isfinite(slope) or slope >= 0:
            return result                 # density not falling with height at the top
        t_top = -1.0 / (slope * r_spec)
    result["top_temperature_k"] = float(t_top)
    result["top_km"] = float(zs[-1] / 1000.0)

    p_top = rs[-1] * r_spec * t_top
    layers = _layer_integral(zs, rs, gs)
    p = p_top + np.concatenate([np.cumsum(layers[::-1])[::-1], [0.0]])
    t_out[idx] = p / (rs * r_spec)
    p_out[idx] = p
    return result

