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
  the archived size, everything is recomputed, and the standard deviation of the
  results is the uncertainty.  Lapse rate, N^2, d(theta)/dz, and temperature and
  pressure from density are done this way (densities are redrawn log-normally, with
  their relative error, so that they stay positive).

Errors at different levels are taken as independent, since no archive VEDA reads says
how they are correlated; a data set can give a correlation length (``Dataset.
uncertainty_correlation_km``), and the draws then have a Gaussian correlation
exp(-dz^2 / (2 L^2)) between levels dz apart.  Independent errors make vertical
derivatives of finely sampled profiles very uncertain, as they are: the difference of two
noisy values over a short distance.

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
        rows, cols, vals = [], [], []
        for i in range(n):
            j0, j1 = np.searchsorted(zs, [zs[i] - 4 * corr_km, zs[i] + 4 * corr_km])
            w = np.exp(-((zs[j0:j1] - zs[i]) / corr_km) ** 2)
            w /= np.sqrt(np.sum(w * w))
            rows.append(np.full(j1 - j0, order[i]))
            cols.append(order[j0:j1])
            vals.append(w)
        kern = sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
        eps = (kern @ eps.T).T
    return eps * s


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
    """Standard deviation over the draws (axis 0), NaN where fewer than half give a value."""
    import warnings
    ok = np.isfinite(a).sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        std = np.nanstd(a, axis=0, ddof=1)
    return np.where(ok >= MC_DRAWS // 2, std, np.nan)


def _sigma_of(profile, key: str, shape) -> Optional[np.ndarray]:
    s = (profile.uncertainty or {}).get(key)
    if s is None:
        return None
    s = np.asarray(s, dtype=float)
    return s if s.shape == shape and np.any(np.isfinite(s) & (s > 0)) else None


def propagate(profile, body, derived: Dict[str, np.ndarray], gz: Optional[np.ndarray],
              corr_km: float = 0.0) -> Dict[str, np.ndarray]:
    """1-sigma uncertainties of ``derived`` (from compute_atmospheric_diagnostics) from the
    profile's archived uncertainties; also stored in ``profile.uncertainty``."""
    from .thermo import heat_capacity
    z = np.asarray(profile.altitude_km, dtype=float)
    out: Dict[str, np.ndarray] = {}
    t = profile.temperature_k
    s_t = _sigma_of(profile, "temperature_k", z.shape) if t is not None else None
    p = profile.pressure_hpa
    s_p = _sigma_of(profile, "pressure_hpa", z.shape) if p is not None and np.shape(p) == z.shape else None
    r_spec = body.gas_constant_r
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
            kappa = r_spec / body.isobaric_heat_capacity_cp
            out["potential_temperature"] = np.abs(derived["potential_temperature"]) * np.sqrt(rt ** 2 + (kappa * rp) ** 2)

    rng = np.random.default_rng(_SEED)
    t_draws = None
    if s_t is not None:
        t_draws = t + _draws(s_t, z, corr_km, rng)
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
        kappa = r_spec / body.isobaric_heat_capacity_cp
        p_ref = body.reference_pressure_hpa
        tt = t_draws if t_draws is not None else np.broadcast_to(t, (MC_DRAWS, z.size))
        pp = p + _draws(s_p, z, corr_km, rng) if s_p is not None else np.broadcast_to(p, (MC_DRAWS, z.size))
        with np.errstate(invalid="ignore", divide="ignore"):
            theta = tt * (p_ref / np.where(pp > 0, pp, np.nan)) ** kappa
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
        pp = p + _draws(s_p, z, corr_km, rng) if s_p is not None else np.broadcast_to(p, (MC_DRAWS, z.size))
        profile.raw_attributes.update(hydrostatic_uncertainty(z, p, t, gz, r_spec, np.where(pp > 0, pp, np.nan), tt))

    if "temperature_from_density" in derived:
        rho, s_rho = _density_and_sigma(profile, body, z.shape)
        if rho is not None and s_rho is not None:
            from .hydrostatic import temperature_from_density_draws
            # log-normal draws (relative error sigma / rho): densities stay positive
            with np.errstate(invalid="ignore", divide="ignore"):
                rel = np.where(np.isfinite(s_rho) & (rho > 0), s_rho / rho, np.nan)
            rho_draws = rho * np.exp(_draws(rel, z, corr_km, rng))
            r = temperature_from_density_draws(z, rho_draws, gz, body.gas_constant_r, s_rho)
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
        rho = np.asarray(profile.derived["number_density_m3"], dtype=float) * K_BOLTZMANN / body.gas_constant_r
        sn = _sigma_of(profile, "number_density_m3", shape)
        s = None if sn is None else sn * K_BOLTZMANN / body.gas_constant_r
    if rho is None or np.shape(rho) != shape:
        return None, None
    return np.asarray(rho, dtype=float), s
