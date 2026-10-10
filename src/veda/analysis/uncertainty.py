"""1-sigma uncertainties of the derived quantities of a profile.

The archives give 1-sigma uncertainties of the measured quantities (temperature,
pressure, densities) at each level.  They are carried into the derived quantities:

* analytically, to first order, where a quantity depends on the values at one level
  only (errors of T and p taken as independent):
    scale height       H = R T / g              sigma_H   = H sigma_T / T
    mass density       rho = p / (R T)          sigma_rho = rho sqrt((sigma_p/p)^2 + (sigma_T/T)^2)
    potential temp.    theta = T (p0/p)^kappa   sigma_th  = theta sqrt((sigma_T/T)^2 + (kappa sigma_p/p)^2)
    speed of sound     c = sqrt(gamma R T)      sigma_c   = c sigma_T / (2 T)
* by Monte Carlo where a quantity depends on several levels (vertical derivatives) or
  on the whole profile (the temperature retrieved from a density profile, whose top
  boundary is fitted): the profile is redrawn ``MC_DRAWS`` times with Gaussian errors of
  the archived size, everything is recomputed, and the spread of the results (half
  the width of their central 68 %, the standard deviation for normal results) is the
  uncertainty.  Lapse rate, N^2, d(theta)/dz, and temperature and
  pressure from density are done this way (densities are redrawn log-normally, with
  their relative error, so that they stay positive).

How the errors of different levels are correlated, no archive VEDA reads says.  It is
estimated from each profile itself (``error_correlation_from_scatter``): independent
errors of the archived size would make the second differences of neighbouring values
scatter with a known variance; where the profile's own second differences scatter much
less (Mars Express MaRS temperatures: median 5 % of that variance in 38 profiles; SOIR:
0.1 % in 60), its errors cannot be independent, and the draws get the Gaussian
correlation exp(-dz^2 / (2 L^2)) with the shortest L that their scatter allows (the
atmosphere's own structure adds scatter, so this is a lower bound on L).  A data set can
instead give a correlation length (``Dataset.uncertainty_correlation_km``).

Correlation between levels makes the 1-sigma of a difference of levels smaller (lapse
rate, N^2, d(theta)/dz, the temperature retrieved from density and the noise level of
the hydrostatic check) and that of a sum of levels larger (layer means, the pressure
integrated from density); taking the errors as independent overstated the first and
understated the second.

The draws use a fixed seed, so the same profile always gets the same uncertainties.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

MC_DRAWS = 200
_SEED = 20261006


def _draws(sigma: np.ndarray, z_km: np.ndarray, corr_km: float, rng: np.random.Generator) -> np.ndarray:
    """(MC_DRAWS, n) Gaussian perturbations with standard deviation ``sigma`` per level
    (NaN sigma gives zero), independent or with a Gaussian correlation length."""
    s = np.where(np.isfinite(sigma) & (sigma > 0), sigma, 0.0)
    n = s.size
    eps = rng.standard_normal((MC_DRAWS, n))
    if corr_km and corr_km > 0 and n > 1:
        # White noise smoothed with a Gaussian kernel of width L / sqrt(2) (cut at 4 L):
        # correlation exp(-dz^2 / (2 L^2)) on an even grid, nearly so on an uneven one;
        # each row is normalised to unit variance.
        from scipy import sparse
        z = np.where(np.isfinite(z_km), z_km, 0.0)
        order = np.argsort(z)
        zs = z[order]
        # every level's neighbours within 4 L, built at once (a loop over levels took
        # 10-20 s per variable for the 52,201-level MSL entry profile)
        j0 = np.searchsorted(zs, zs - 4 * corr_km)
        j1 = np.searchsorted(zs, zs + 4 * corr_km)
        counts = j1 - j0
        if counts.sum() > _MAX_KERNEL_TERMS:
            return _draws_on_grid(z, corr_km, rng.standard_normal) * s
        rows = np.repeat(np.arange(n), counts)
        starts = np.repeat(np.cumsum(counts) - counts, counts)
        cols = j0[rows] + (np.arange(rows.size) - starts)
        w = np.exp(-((zs[cols] - zs[rows]) / corr_km) ** 2)
        w /= np.sqrt(np.bincount(rows, weights=w * w, minlength=n))[rows]
        kern = sparse.csr_matrix((w, (order[rows], order[cols])), shape=(n, n))
        eps = (kern @ eps.T).T
    return eps * s


# Above this many kernel terms (densely sampled profiles with a long correlation length:
# the Phoenix entry profile has 91,835 levels) the draws are made on an even grid instead
_MAX_KERNEL_TERMS = 4_000_000


def _draws_on_grid(z: np.ndarray, corr_km: float, normal) -> np.ndarray:
    """(MC_DRAWS, n) unit-variance draws with correlation exp(-dz^2 / (2 L^2)) at heights
    ``z``, made on an even grid of spacing L / 4 (white noise smoothed with the Gaussian
    kernel of _draws) and interpolated linearly to the levels; each level is divided by
    the standard deviation that the interpolation leaves (between 0.985 and 1)."""
    step = corr_km / 4.0
    lo, hi = float(np.min(z)) - 4 * corr_km, float(np.max(z)) + 4 * corr_km
    grid = lo + step * np.arange(int(np.ceil((hi - lo) / step)) + 1)
    half = int(np.ceil(4 * corr_km / step))
    k = np.exp(-((np.arange(-half, half + 1) * step) / corr_km) ** 2)
    k /= np.sqrt(np.sum(k * k))
    from scipy.signal import fftconvolve
    white = normal((MC_DRAWS, grid.size + 2 * half))
    smooth = fftconvolve(white, k[None, :], mode="valid", axes=1)          # (MC_DRAWS, grid.size)
    i = np.clip(np.searchsorted(grid, z, side="right") - 1, 0, grid.size - 2)
    w = (z - grid[i]) / step
    r = np.exp(-(step / corr_km) ** 2 / 2.0)
    norm = np.sqrt((1 - w) ** 2 + w ** 2 + 2 * w * (1 - w) * r)
    return (smooth[:, i] * (1 - w) + smooth[:, i + 1] * w) / norm


def error_correlation_from_scatter(z_km, values, sigma, log: bool = False, min_levels: int = 10) -> float:
    """Shortest Gaussian correlation length L (km) of a profile's errors that is consistent
    with the scatter of its own values (0: independent errors are consistent with it).

    With errors e_i of 1-sigma s_i and correlation r(dz) = exp(-dz^2 / (2 L^2)), the second
    difference d_i = v_{i-1} - 2 v_i + v_{i+1} has variance
        s^2 (6 - 8 r(D) + 2 r(2 D))            (even spacing D, equal s)
    or 6 s^2 when the errors are independent.  The ratio of the observed variance of d_i
    / sqrt(s_{i-1}^2 + 4 s_i^2 + s_{i+1}^2) (robust, from the median absolute deviation) to
    1 is solved for L.  The profile's own structure only adds to the observed variance,
    so the L found is a lower bound.  ``log``: relative errors of a positive quantity."""
    z = np.asarray(z_km, dtype=float)
    v = np.asarray(values, dtype=float)
    s = np.asarray(sigma, dtype=float)
    if z.shape != v.shape or z.shape != s.shape:
        return 0.0
    ok = np.isfinite(z) & np.isfinite(v) & np.isfinite(s) & (s > 0)
    if log:
        ok &= v > 0
    if ok.sum() < min_levels + 2:
        return 0.0
    order = np.argsort(z[ok])
    z, v, s = z[ok][order], v[ok][order], s[ok][order]
    if log:
        s, v = s / v, np.log(v)
    keep = np.r_[True, np.diff(z) > 0]
    z, v, s = z[keep], v[keep], s[keep]
    if z.size < min_levels + 2:
        return 0.0
    e = (v[:-2] - 2.0 * v[1:-1] + v[2:]) / np.sqrt(s[:-2] ** 2 + 4.0 * s[1:-1] ** 2 + s[2:] ** 2)
    ratio = (1.4826 * np.median(np.abs(e - np.median(e)))) ** 2
    if not np.isfinite(ratio) or ratio >= 1.0:
        return 0.0
    spacing = float(np.median(np.diff(z)))
    longest = float(z[-1] - z[0])

    def var_ratio(length):
        a = spacing * spacing / (2.0 * length * length)
        return (6.0 - 8.0 * np.exp(-a) + 2.0 * np.exp(-4.0 * a)) / 6.0
    if var_ratio(longest) >= ratio:
        return round(longest, 4)
    lo, hi = 1e-3 * spacing, longest              # var_ratio falls as L grows
    for _ in range(60):
        mid = np.sqrt(lo * hi)
        if var_ratio(mid) > ratio:
            lo = mid
        else:
            hi = mid
    return round(float(hi), 4)


def gradient_operator(z_km: np.ndarray, ok: np.ndarray):
    """Sparse matrix M with M @ v[ok] = _gradient_nan_safe(z, v)[ok] (atmospheric.py): the
    same averaging of repeated altitudes and the same central differences over at least
    +-MIN_DERIVATIVE_HALF_WINDOW_KM, as a linear operator that can be applied to many
    redrawn profiles at once."""
    from scipy import sparse
    from .atmospheric import MIN_DERIVATIVE_HALF_WINDOW_KM
    z = np.asarray(z_km, dtype=float)[ok]
    zu, inv = np.unique(z, return_inverse=True)
    nu, nk = zu.size, z.size
    if nu < 2:
        return None
    counts = np.bincount(inv, minlength=nu).astype(float)
    avg = sparse.csr_matrix((1.0 / counts[inv], (inv, np.arange(nk))), shape=(nu, nk))
    half = np.empty_like(zu)
    half[1:-1] = (zu[2:] - zu[:-2]) / 2.0
    half[0], half[-1] = zu[1] - zu[0], zu[-1] - zu[-2]
    half = np.maximum(half, MIN_DERIVATIVE_HALF_WINDOW_KM)
    lo = np.maximum(zu - half, zu[0])
    hi = np.minimum(zu + half, zu[-1])

    def interp(x):
        k = np.clip(np.searchsorted(zu, x, side="right") - 1, 0, nu - 2)
        t = (x - zu[k]) / (zu[k + 1] - zu[k])
        rows = np.arange(nu)
        return sparse.csr_matrix((np.concatenate([1.0 - t, t]), (np.concatenate([rows, rows]),
                                  np.concatenate([k, k + 1]))), shape=(nu, nu))
    diff = sparse.diags(1.0 / (hi - lo)) @ (interp(hi) - interp(lo))
    back = sparse.csr_matrix((np.ones(nk), (np.arange(nk), inv)), shape=(nk, nu))
    return back @ diff @ avg


def _std(a: np.ndarray) -> np.ndarray:
    """Spread of the draws (axis 0): half the width of their central 68.27 % (the standard
    deviation when they are normal), NaN where fewer than half give a value.  The standard
    deviation itself was swayed by a few draws far out where the result depends strongly
    on the errors (SOIR temperature from density with 30-50 % density errors: up to
    50 times the half-width, thousands of kelvin); on normal results the two agree (Mars
    Express lapse rate: 0.98-0.99)."""
    a = np.asarray(a, dtype=float)
    ok = np.isfinite(a).sum(axis=0)
    srt = np.sort(np.where(np.isfinite(a), a, np.inf), axis=0)      # finite values first
    # (np.nanpercentile, column by column, took 40 s for the 52,201 levels of the MSL profile;
    # this is its 'linear' method, vectorised)

    def quantile(q):
        pos = np.maximum(ok - 1, 0) * q
        i0 = np.floor(pos).astype(int)
        i1 = np.minimum(i0 + 1, np.maximum(ok - 1, 0))
        v0 = np.take_along_axis(srt, i0[None, :], axis=0)[0]
        v1 = np.take_along_axis(srt, i1[None, :], axis=0)[0]
        with np.errstate(invalid="ignore"):
            return v0 + (pos - i0) * (v1 - v0)
    spread = (quantile(0.84135) - quantile(0.15865)) / 2.0
    return np.where(ok >= MC_DRAWS // 2, spread, np.nan)


def _sigma_of(profile, key: str, shape) -> Optional[np.ndarray]:
    s = (profile.uncertainty or {}).get(key)
    if s is None:
        return None
    s = np.asarray(s, dtype=float)
    return s if s.shape == shape and np.any(np.isfinite(s) & (s > 0)) else None


def propagate(profile, body, derived: Dict[str, np.ndarray], gz: Optional[np.ndarray],
              corr_km: float = 0.0) -> Dict[str, np.ndarray]:
    """1-sigma uncertainties of ``derived`` (from compute_atmospheric_diagnostics) from the
    profile's archived uncertainties; also stored in ``profile.uncertainty``.  ``corr_km``:
    the data set's correlation length of the errors; 0: estimated from each variable's own
    scatter (error_correlation_from_scatter), noted in ``profile.raw_attributes``."""
    from .thermo import heat_capacity
    z = np.asarray(profile.altitude_km, dtype=float)
    out: Dict[str, np.ndarray] = {}
    t = profile.temperature_k
    s_t = _sigma_of(profile, "temperature_k", z.shape) if t is not None else None
    p = profile.pressure_hpa
    s_p = _sigma_of(profile, "pressure_hpa", z.shape) if p is not None and np.shape(p) == z.shape else None
    from .atmospheric import gas_constant_levels
    r_spec = gas_constant_levels(profile, body)
    with np.errstate(invalid="ignore", divide="ignore"):
        rel_t = s_t / t if s_t is not None else None
        rel_p = s_p / p if s_p is not None else None
        if rel_t is not None and "scale_height" in derived:
            out["scale_height"] = np.abs(derived["scale_height"]) * rel_t
        if rel_t is not None and "speed_of_sound" in derived:
            out["speed_of_sound"] = np.abs(derived["speed_of_sound"]) * rel_t / 2.0
        if (rel_t is not None or rel_p is not None) and "density" in derived:
            rt = rel_t if rel_t is not None else 0.0
            rp = rel_p if rel_p is not None else 0.0
            out["density"] = np.abs(derived["density"]) * np.sqrt(rt ** 2 + rp ** 2)
            from .thermo import potential_temperature_sensitivity
            th = np.abs(derived["potential_temperature"])
            a_t, a_p = potential_temperature_sensitivity(body, t, th, r_spec)
            out["potential_temperature"] = th * np.sqrt((a_t * rt) ** 2 + (a_p * rp) ** 2)
        if "t_minus_co2_condensation" in derived and (s_t is not None or s_p is not None):
            from .condensation import co2_condensation_sigma
            s_tc = (co2_condensation_sigma(derived["co2_condensation_temperature"], p, s_p) if s_p is not None
                    else 0.0)
            if s_p is not None:
                out["co2_condensation_temperature"] = s_tc
            out["t_minus_co2_condensation"] = np.sqrt((s_t if s_t is not None else 0.0) ** 2 + s_tc ** 2)
            margin = np.asarray(derived["t_minus_co2_condensation"], dtype=float)
            if np.isfinite(margin).any():           # the 1-sigma where T comes closest to the frost point
                s_min = out["t_minus_co2_condensation"][int(np.nanargmin(margin))]
                if np.isfinite(s_min):
                    if profile.raw_attributes is not None:
                        profile.raw_attributes["co2_margin_min_sigma_k"] = round(float(s_min), 2)

    attrs = profile.raw_attributes if profile.raw_attributes is not None else {}

    def corr_of(key, values, sigma, log=False):
        length = corr_km if corr_km and corr_km > 0 else error_correlation_from_scatter(z, values, sigma, log)
        attrs[f"error_correlation_{key}_km"] = length
        return length
    l_t = corr_of("temperature", t, s_t) if s_t is not None else 0.0
    l_p = corr_of("pressure", p, s_p, log=True) if s_p is not None else 0.0

    rng = np.random.default_rng(_SEED)
    t_draws = None
    if s_t is not None:
        t_draws = t + _draws(s_t, z, l_t, rng)
        t_draws[t_draws <= 0] = np.nan
    ok_t = np.isfinite(z) & np.isfinite(t) if t is not None else None
    if t_draws is not None and gz is not None and ok_t.sum() >= 2:
        op = gradient_operator(z, ok_t)
        if op is not None:
            dtdz = np.full(t_draws.shape, np.nan)
            dtdz[:, ok_t] = (op @ t_draws[:, ok_t].T).T
            if "lapse_rate" in derived:
                out["lapse_rate"] = _std(-dtdz)
            if "buoyancy_freq_sq" in derived:
                with np.errstate(invalid="ignore", divide="ignore"):
                    n2 = (gz / t_draws) * (dtdz / 1000.0 + gz / heat_capacity(body, t_draws))
                out["buoyancy_freq_sq"] = _std(n2)
    if "dtheta_dz" in derived and p is not None and (s_t is not None or s_p is not None):
        from .thermo import potential_temperature
        tt = t_draws if t_draws is not None else np.broadcast_to(t, (MC_DRAWS, z.size))
        pp = p + _draws(s_p, z, l_p, rng) if s_p is not None else np.broadcast_to(p, (MC_DRAWS, z.size))
        theta = potential_temperature(body, tt, pp, r_spec)
        ok_th = np.isfinite(z) & np.isfinite(derived["potential_temperature"])
        op = gradient_operator(z, ok_th) if ok_th.sum() >= 2 else None
        if op is not None:
            d = np.full(theta.shape, np.nan)
            d[:, ok_th] = (op @ theta[:, ok_th].T).T
            out["dtheta_dz"] = _std(d)

    # uncertainty and noise level of the hydrostatic consistency check
    if (profile.raw_attributes or {}).get("hydrostatic_median_pct") is not None and p is not None \
            and (s_t is not None or s_p is not None) and gz is not None:
        from .hydrostatic import hydrostatic_uncertainty
        tt = t_draws if t_draws is not None else np.broadcast_to(t, (MC_DRAWS, z.size))
        pp = p + _draws(s_p, z, l_p, rng) if s_p is not None else np.broadcast_to(p, (MC_DRAWS, z.size))
        from .atmospheric import hydrostatic_geopotential, hydrostatic_gravity
        g_h = hydrostatic_gravity(profile, body, z, gz)
        profile.raw_attributes.update(hydrostatic_uncertainty(z, p, t, g_h, r_spec, np.where(pp > 0, pp, np.nan), tt,
                                                              phi=hydrostatic_geopotential(profile, g_h)))

    if "temperature_from_density" in derived:
        rho, s_rho = _density_and_sigma(profile, body, z.shape)
        if rho is not None and s_rho is not None:
            from .hydrostatic import temperature_from_density_draws
            # log-normal draws (relative error sigma / rho): densities stay positive
            with np.errstate(invalid="ignore", divide="ignore"):
                rel = np.where(np.isfinite(s_rho) & (rho > 0), s_rho / rho, np.nan)
            rho_draws = rho * np.exp(_draws(rel, z, corr_of("density", rho, s_rho, log=True), rng))
            from .atmospheric import density_gas_constant, hydrostatic_geopotential, hydrostatic_gravity
            g_h = hydrostatic_gravity(profile, body, z, gz)
            r = temperature_from_density_draws(z, rho_draws, g_h, density_gas_constant(profile, body), s_rho,
                                               phi=hydrostatic_geopotential(profile, g_h))
            out["temperature_from_density"] = _std(r["temperature_k"])
            out["pressure_from_density"] = _std(r["pressure_pa"] / 100.0)

    out = {k: v for k, v in out.items() if v is not None and np.any(np.isfinite(v))}
    profile.uncertainty.update(out)
    return out


def _density_and_sigma(profile, body, shape):
    from .atmospheric import K_BOLTZMANN
    rho = profile.derived.get("density_measured")
    s = _sigma_of(profile, "density_measured", shape)
    if rho is None and profile.derived.get("number_density_m3") is not None:
        from .atmospheric import density_gas_constant
        r_gas = density_gas_constant(profile, body)
        rho = np.asarray(profile.derived["number_density_m3"], dtype=float) * K_BOLTZMANN / r_gas
        sn = _sigma_of(profile, "number_density_m3", shape)
        s = None if sn is None else sn * K_BOLTZMANN / r_gas
    if rho is None or np.shape(rho) != shape:
        return None, None
    return np.asarray(rho, dtype=float), s
