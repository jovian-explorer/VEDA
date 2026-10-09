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

Hydrostatic consistency of a profile with temperature and pressure: the pressure
integrated with the profile's own temperature,

    p_hyd(z) = p_0 exp(-integral_z0^z g / (R T) dz'),

against the archived pressure, p_0 chosen so that the median of ln(p / p_hyd) is zero
(one bad level does not offset the rest).  The largest relative difference says whether
the pressure, temperature and altitudes of a profile belong together.

Its noise level (hydrostatic_uncertainty), from the archived 1-sigma of p and T by
Monte Carlo: the departures that a perfectly hydrostatic profile with the same errors
would show (the median over the draws of its median departure, and the 95th percentile
of its largest), errors taken as independent between levels.  Departures well above it
are not explained by the errors.  Retrievals whose p and T come from one integration
have strongly correlated errors and usually depart much less than this level.

Every function takes ``phi``, the geopotential at the levels (m^2/s^2), for archives
whose pressures are integrated in it: the integrals then use its differences, d Phi,
instead of g dz.  The MGS and MRO radio occultation archives give it at each tangent
point, from a full gravity field with the planet's rotation; the tangent point drifts
in latitude along a profile (MGS: up to 0.03 deg per 330 m of height), so Phi changes
with position as well as with height, and d Phi / dz differed from VEDA's g(z) by up to
2 % (30 MGS profiles: the temperature integrated from the archive density and top
temperature was up to 2.4 % off the archive's with g(z), 0.26 % with Phi).
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

# Part of the profile's altitude range at its top used to fit the boundary scale height
TOP_FIT_FRACTION = 0.2
TOP_FIT_MIN_POINTS = 5
# The density must fall by at least this much (natural logarithm: a factor e, one scale
# height) from the bottom to the top of a profile for its top temperature to be fitted.
# Over less, every level depends on the boundary: a few kilometres of a MAVEN pass leg
# near periapsis gave 4 to 7 K.
MIN_DENSITY_FALL = 1.0


def _layer_integral(z: np.ndarray, rho: np.ndarray, g: np.ndarray, phi: Optional[np.ndarray] = None) -> np.ndarray:
    """integral of rho g dz (or of rho d Phi, with the geopotential ``phi`` at the
    levels) over each layer between consecutive levels (z ascending, m)."""
    dz = np.diff(z)
    r1, r2 = rho[:-1], rho[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.log(r1 / r2)
        expo = np.where(np.abs(ratio) > 1e-9, (r1 - r2) / ratio, 0.5 * (r1 + r2))
    return expo * (np.diff(phi) if phi is not None else dz * 0.5 * (g[:-1] + g[1:]))


def _levels(phi, shape) -> Optional[np.ndarray]:
    """The geopotential at the levels (m^2/s^2) as an array of ``shape``, or None."""
    return None if phi is None else np.broadcast_to(np.asarray(phi, dtype=float), shape)


def _integral_over(zs: np.ndarray, gs: np.ndarray, phs: Optional[np.ndarray], divisor: np.ndarray) -> np.ndarray:
    """integral of g / divisor dz over each layer: the trapezoid rule on g / divisor, or
    with the geopotential, d Phi times the mean of 1 / divisor at the layer's ends."""
    if phs is None:
        f = gs / divisor
        return 0.5 * (f[1:] + f[:-1]) * np.diff(zs)
    inv = 1.0 / divisor
    return np.diff(phs) * 0.5 * (inv[1:] + inv[:-1])


def temperature_from_density(z_km, rho, g_ms2, r_spec, rho_sigma=None,
                             t_top: Optional[float] = None, phi=None) -> Dict[str, object]:
    """Temperature (K) and pressure (Pa) at the levels of a mass density profile (kg/m^3)
    by downward hydrostatic integration (module docstring).  ``t_top`` fixes the
    temperature at the top instead of fitting the top scale height; ``rho_sigma`` weights
    that fit.  ``r_spec`` (J/(kg K)) is one value or one per level, where the mean molar
    mass changes with height (T = p / (rho R(z)); the top fit uses ln(rho R) against the
    integral of g / R dz, whose slope is -1/T for an isothermal layer).  ``phi``: the
    geopotential at the levels (m^2/s^2), used instead of g dz where given.  Levels without
    a positive density, and profiles too short to fit, give NaN.
    """
    z = np.asarray(z_km, dtype=float)
    rho = np.asarray(rho, dtype=float)
    g = np.broadcast_to(np.asarray(g_ms2, dtype=float), z.shape)
    r_all = np.broadcast_to(np.asarray(r_spec, dtype=float), z.shape)
    ph = _levels(phi, z.shape)
    n = z.size
    t_out = np.full(n, np.nan)
    p_out = np.full(n, np.nan)
    result: Dict[str, object] = {"temperature_k": t_out, "pressure_pa": p_out, "top_temperature_k": None,
                                 "top_km": None}
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(z) & np.isfinite(rho) & (rho > 0) & np.isfinite(g) & np.isfinite(r_all) & (r_all > 0)
        if ph is not None:
            ok &= np.isfinite(ph)
    if ok.sum() < TOP_FIT_MIN_POINTS:
        return result
    idx = np.where(ok)[0]
    idx = idx[np.argsort(z[idx], kind="stable")]
    zs, rs, gs, rr = z[idx] * 1000.0, rho[idx], g[idx], r_all[idx]
    phs = None if ph is None else ph[idx]

    if t_top is None and not np.log(rs[0] * rr[0] / (rs[-1] * rr[-1])) >= MIN_DENSITY_FALL:
        return result                     # less than a scale height: the top is not determined
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
        # ln(rho R) (the number density, up to a constant) against the integral of g / R dz
        # (the geopotential over R): its slope is -1 / T for an isothermal layer even where
        # g and the molar mass change over the fitted heights
        phi_r = np.concatenate([[0.0], np.cumsum(_integral_over(zs, gs, phs, rr))])
        slope = np.polyfit(phi_r[top], np.log(rs[top] * rr[top]), 1, w=w)[0]
        if not np.isfinite(slope) or slope >= 0:
            return result                 # density not falling with height at the top
        t_top = -1.0 / slope
    result["top_temperature_k"] = float(t_top)
    result["top_km"] = float(zs[-1] / 1000.0)

    p_top = rs[-1] * rr[-1] * t_top
    layers = _layer_integral(zs, rs, gs, phs)
    p = p_top + np.concatenate([np.cumsum(layers[::-1])[::-1], [0.0]])
    t_out[idx] = p / (rs * rr)
    p_out[idx] = p
    return result



def temperature_from_density_draws(z_km, rho_draws, g_ms2, r_spec, rho_sigma=None, phi=None) -> Dict[str, np.ndarray]:
    """temperature_from_density for many redrawn density profiles at once (rows of
    ``rho_draws``, all positive where the first row is), for Monte Carlo uncertainties:
    the same levels, top fit (weighted by ``rho_sigma`` as there) and integration
    (in the geopotential ``phi`` where given).  Returns (draws, n) arrays of temperature
    (K) and pressure (Pa), NaN where a draw gives none."""
    z = np.asarray(z_km, dtype=float)
    rd = np.atleast_2d(np.asarray(rho_draws, dtype=float))
    g = np.broadcast_to(np.asarray(g_ms2, dtype=float), z.shape)
    r_all = np.broadcast_to(np.asarray(r_spec, dtype=float), z.shape)
    ph = _levels(phi, z.shape)
    d, n = rd.shape
    t_out = np.full((d, n), np.nan)
    p_out = np.full((d, n), np.nan)
    with np.errstate(invalid="ignore"):
        ok = (np.isfinite(z) & np.all(np.isfinite(rd) & (rd > 0), axis=0) & np.isfinite(g)
              & np.isfinite(r_all) & (r_all > 0))
        if ph is not None:
            ok &= np.isfinite(ph)
    if ok.sum() < TOP_FIT_MIN_POINTS:
        return {"temperature_k": t_out, "pressure_pa": p_out}
    idx = np.where(ok)[0]
    idx = idx[np.argsort(z[idx], kind="stable")]
    zs, rs, gs, rr = z[idx] * 1000.0, rd[:, idx], g[idx], r_all[idx]
    phs = None if ph is None else ph[idx]
    if not np.log(rs[0, 0] * rr[0] / (rs[0, -1] * rr[-1])) >= MIN_DENSITY_FALL:
        return {"temperature_k": t_out, "pressure_pa": p_out}
    span = zs[-1] - zs[0]
    top = zs >= zs[-1] - TOP_FIT_FRACTION * span
    if top.sum() < TOP_FIT_MIN_POINTS:
        top = np.zeros(zs.size, dtype=bool)
        top[-TOP_FIT_MIN_POINTS:] = True
    w = np.ones(int(top.sum()))
    if rho_sigma is not None:
        sg = np.asarray(rho_sigma, dtype=float)[idx][top]
        with np.errstate(divide="ignore", invalid="ignore"):
            ww = np.where(np.isfinite(sg) & (sg > 0), rd[0, idx][top] / sg, np.nan)
        if np.isfinite(ww).all():
            w = ww
    phi_r = np.concatenate([[0.0], np.cumsum(_integral_over(zs, gs, phs, rr))])[top]
    wt = w * w                                     # polyfit's w multiplies the residuals
    pm = np.sum(wt * phi_r) / np.sum(wt)
    y = np.log(rs[:, top] * rr[top])
    ym = (y * wt).sum(axis=1, keepdims=True) / np.sum(wt)
    slope = ((y - ym) * (wt * (phi_r - pm))).sum(axis=1) / np.sum(wt * (phi_r - pm) ** 2)
    good = np.isfinite(slope) & (slope < 0)
    t_top = np.where(good, -1.0 / np.where(good, slope, -1.0), np.nan)
    dz = np.diff(zs)
    r1, r2 = rs[:, :-1], rs[:, 1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.log(r1 / r2)
        expo = np.where(np.abs(ratio) > 1e-9, (r1 - r2) / ratio, 0.5 * (r1 + r2))
    layers = expo * (np.diff(phs) if phs is not None else dz * 0.5 * (gs[:-1] + gs[1:]))
    p_top = rs[:, -1] * rr[-1] * t_top
    pres = p_top[:, None] + np.concatenate([np.cumsum(layers[:, ::-1], axis=1)[:, ::-1], np.zeros((d, 1))], axis=1)
    t_out[:, idx] = pres / (rs * rr)
    p_out[:, idx] = pres
    return {"temperature_k": t_out, "pressure_pa": p_out}


def hydrostatic_consistency(z_km, p_hpa, t_k, g_ms2, r_spec, phi=None) -> Dict[str, Optional[float]]:
    """How far a profile's pressure is from hydrostatic balance with its temperature:
    the pressure integrated with the profile's temperature (module docstring) against the
    archived one.  ``r_spec``: one gas constant or one per level; ``phi``: the geopotential
    at the levels, used instead of g dz where given.  Returns the largest and the median
    |p / p_hyd - 1| in percent over the levels with all three quantities, and the altitude
    of the largest (None without data)."""
    z = np.asarray(z_km, dtype=float)
    p = np.asarray(p_hpa, dtype=float)
    t = np.asarray(t_k, dtype=float)
    g = np.broadcast_to(np.asarray(g_ms2, dtype=float), z.shape)
    ph = _levels(phi, z.shape)
    empty = {"hydrostatic_max_pct": None, "hydrostatic_median_pct": None, "hydrostatic_max_km": None}
    if not (z.shape == p.shape == t.shape):
        return empty
    r_all = np.broadcast_to(np.asarray(r_spec, dtype=float), z.shape)
    with np.errstate(invalid="ignore"):
        ok = (np.isfinite(z) & np.isfinite(p) & np.isfinite(t) & (p > 0) & (t > 0) & np.isfinite(g)
              & np.isfinite(r_all) & (r_all > 0))
        if ph is not None:
            ok &= np.isfinite(ph)
    if ok.sum() < 3:
        return empty
    idx = np.where(ok)[0]
    idx = idx[np.argsort(z[idx], kind="stable")]
    zs, ps, ts, gs = z[idx] * 1000.0, p[idx], t[idx], g[idx]
    # integral of g / (R T) dz (or d Phi / (R T)) with the trapezoid rule (g / T varies slowly)
    expo = np.concatenate([[0.0], np.cumsum(_integral_over(zs, gs, None if ph is None else ph[idx],
                                                           r_all[idx] * ts))])
    p_hyd = np.exp(np.median(np.log(ps) + expo) - expo)
    dev = np.abs(ps / p_hyd - 1.0) * 100.0
    i = int(np.argmax(dev))
    return {"hydrostatic_max_pct": float(dev[i]), "hydrostatic_median_pct": float(np.median(dev)),
            "hydrostatic_max_km": float(zs[i] / 1000.0)}


def hydrostatic_uncertainty(z_km, p_hpa, t_k, g_ms2, r_spec, p_draws, t_draws, phi=None) -> Dict[str, Optional[float]]:
    """Noise level of hydrostatic_consistency (module docstring): the departures that a
    perfectly hydrostatic profile with the profile's own temperature would show when its
    pressure and temperature are redrawn within their errors (``p_draws``, ``t_draws``:
    draws x levels, the archived values plus their Gaussian errors; ``phi`` as there)."""
    import warnings
    z = np.asarray(z_km, dtype=float)
    p = np.asarray(p_hpa, dtype=float)
    t = np.asarray(t_k, dtype=float)
    g = np.broadcast_to(np.asarray(g_ms2, dtype=float), z.shape)
    r_all = np.broadcast_to(np.asarray(r_spec, dtype=float), z.shape)
    ph = _levels(phi, z.shape)
    empty = {"hydrostatic_noise_median_pct": None, "hydrostatic_noise_max_pct": None}
    with np.errstate(invalid="ignore"):
        ok = (np.isfinite(z) & np.isfinite(p) & np.isfinite(t) & (p > 0) & (t > 0) & np.isfinite(g)
              & np.isfinite(r_all) & (r_all > 0))
        if ph is not None:
            ok &= np.isfinite(ph)
    if ok.sum() < 3:
        return empty
    idx = np.where(ok)[0]
    idx = idx[np.argsort(z[idx], kind="stable")]
    zs, gs, rs = z[idx] * 1000.0, g[idx], r_all[idx]
    phs = None if ph is None else ph[idx]
    expo = np.concatenate([[0.0], np.cumsum(_integral_over(zs, gs, phs, rs * t[idx]))])
    p_cons = np.exp(np.median(np.log(p[idx]) + expo) - expo)        # hydrostatic with the profile's T
    noise_p = p_draws[:, idx] - p[idx] + p_cons
    med, mx = [], []
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for i in range(p_draws.shape[0]):
            b = hydrostatic_consistency(zs / 1000.0, noise_p[i], t_draws[i, idx], gs, rs, phs)
            if b["hydrostatic_median_pct"] is not None:
                med.append(b["hydrostatic_median_pct"])
                mx.append(b["hydrostatic_max_pct"])
    if len(med) < 2:
        return empty
    return {"hydrostatic_noise_median_pct": float(np.median(med)),
            "hydrostatic_noise_max_pct": float(np.percentile(mx, 95))}
