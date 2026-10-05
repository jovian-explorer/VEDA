"""Advanced Atmospheric Stability, Gravity Wave, and Ionospheric Profiler for VEDA.

Provides:
1. Cold Point Tropopause (CPT) and Lapse Rate Tropopause (LRT) Detection.
2. Gravity Wave Perturbation Analysis:
   - Background temperature by a zero-phase Butterworth low-pass with a stated cutoff wavelength.
   - Temperature perturbation T'(z) = T(z) - T_bar(z).
   - Gravity wave specific potential energy E_p(z) = 0.5 * (g/N_bar)^2 * (T'/T_bar)^2 [J/kg], N_bar from T_bar.
   - Dominant vertical wavelength extraction via FFT / periodogram.
3. Chapman Layer Modeling for Ionospheric Occultations:
   - Non-linear least squares fit of peak density (NmF2), peak altitude (hmF2), and neutral scale height (H).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.optimize import curve_fit


def detect_tropopause(
    z_km: np.ndarray,
    t_k: np.ndarray,
    min_alt_km: float = 6.0,
    max_alt_km: float = 25.0,
) -> Dict[str, Optional[float]]:
    """Detect Cold Point Tropopause (CPT) and Lapse Rate Tropopause (LRT).

    CPT: Altitude of absolute minimum temperature within tropopause search window.
    LRT: Lowest level where -dT/dz <= 2 K/km, and 2 km layer above doesn't exceed 2 K/km.
    """
    z = np.asarray(z_km, dtype=np.float64)
    t = np.asarray(t_k, dtype=np.float64)

    res: Dict[str, Optional[float]] = {
        "cpt_alt_km": None,
        "cpt_temp_k": None,
        "lrt_alt_km": None,
        "lrt_temp_k": None,
    }

    ok = np.isfinite(z) & np.isfinite(t)
    if ok.sum() < 5:
        return res

    z_clean = z[ok]
    t_clean = t[ok]
    sort_idx = np.argsort(z_clean)
    z_clean, t_clean = z_clean[sort_idx], t_clean[sort_idx]

    # Window mask
    window = (z_clean >= min_alt_km) & (z_clean <= max_alt_km)
    if not window.any():
        window = np.ones_like(z_clean, dtype=bool)

    z_win = z_clean[window]
    t_win = t_clean[window]

    # 1. Cold Point Tropopause (CPT)
    min_idx = np.argmin(t_win)
    res["cpt_alt_km"] = round(float(z_win[min_idx]), 2)
    res["cpt_temp_k"] = round(float(t_win[min_idx]), 2)

    # 2. Lapse Rate Tropopause (LRT)
    # Compute lapse rate Gamma = -dT/dz in K/km
    gamma = -np.gradient(t_clean, z_clean)

    for i in range(len(z_clean) - 1):
        if z_clean[i] < min_alt_km or z_clean[i] > max_alt_km:
            continue
        if gamma[i] <= 2.0:
            # Check 2 km column above
            z_above = z_clean[i] + 2.0
            mask_above = (z_clean >= z_clean[i]) & (z_clean <= z_above)
            if mask_above.sum() >= 2:
                avg_gamma_above = np.mean(gamma[mask_above])
                if avg_gamma_above <= 2.0:
                    res["lrt_alt_km"] = round(float(z_clean[i]), 2)
                    res["lrt_temp_k"] = round(float(t_clean[i]), 2)
                    break

    return res


# Where to look for a cold-point tropopause on each body, as an altitude range (km above
# the reference radius) or a pressure range (hPa) where altitudes are relative to a
# pressure level.  Bodies not listed have no cold-point tropopause in their profiles:
# Venus' tropopause near 60 km is a change in static stability with temperature still
# falling into the mesosphere, and Mars has no persistent temperature minimum.
TROPOPAUSE_SEARCH: Dict[str, Dict[str, Tuple[float, float]]] = {
    "titan": {"altitude_km": (25.0, 70.0)},        # 44 km, 70.4 K (Huygens HASI, Fulchignoni et al. 2005)
    "jupiter": {"pressure_hpa": (30.0, 500.0)},    # near 100 hPa (Lindal et al. 1981)
    "saturn": {"pressure_hpa": (30.0, 500.0)},     # 60-100 hPa (Lindal et al. 1985)
}


def tropopause_for_body(
    body_id: str,
    z_km: np.ndarray,
    t_k: np.ndarray,
    p_hpa: Optional[np.ndarray] = None,
) -> Dict[str, Optional[float]]:
    """Cold-point tropopause of a profile, searched where the body has one.

    The coldest level counts only when the profile has warmer levels both below
    and above it inside the search range, so a profile that starts or ends in
    the range does not report its first or last level as the tropopause.
    Returns ``cpt_alt_km``, ``cpt_temp_k`` and ``cpt_pressure_hpa`` (None when
    the body has no listed range or the profile shows no interior minimum).
    """
    res: Dict[str, Optional[float]] = {"cpt_alt_km": None, "cpt_temp_k": None, "cpt_pressure_hpa": None}
    rule = TROPOPAUSE_SEARCH.get(body_id)
    if rule is None or z_km is None or t_k is None:
        return res
    z = np.asarray(z_km, dtype=np.float64)
    t = np.asarray(t_k, dtype=np.float64)
    p = None if p_hpa is None else np.asarray(p_hpa, dtype=np.float64)
    if p is not None and p.shape != z.shape:
        p = None
    if "pressure_hpa" in rule:
        if p is None:
            return res
        lo, hi = rule["pressure_hpa"]
        with np.errstate(invalid="ignore"):
            inside = np.isfinite(p) & (p >= lo) & (p <= hi)
    else:
        lo, hi = rule["altitude_km"]
        with np.errstate(invalid="ignore"):
            inside = (z >= lo) & (z <= hi)
    ok = inside & np.isfinite(z) & np.isfinite(t)
    if ok.sum() < 5:
        return res
    order = np.argsort(z[ok])
    zz, tt = z[ok][order], t[ok][order]
    i = int(np.argmin(tt))
    if i == 0 or i == tt.size - 1:
        return res                                   # minimum at the edge: no interior cold point
    res["cpt_alt_km"] = round(float(zz[i]), 2)
    res["cpt_temp_k"] = round(float(tt[i]), 2)
    if p is not None:
        pp = p[ok][order][i]
        res["cpt_pressure_hpa"] = float(f"{pp:.4g}") if np.isfinite(pp) else None
    return res


def extract_gravity_wave_activity(
    z_km: np.ndarray,
    t_k: np.ndarray,
    gz_ms2: np.ndarray,
    buoyancy_n2: Optional[np.ndarray] = None,
    filter_order: int = 4,
    cutoff_wavelength_km: float = 8.0,
    cp_j_kg_k: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Extract atmospheric gravity wave temperature perturbations and potential energy.

    Computes:
    - Background temperature T_bar(z): a zero-phase Butterworth low-pass of T(z) on a
      100 m grid.  ``cutoff_wavelength_km`` is where the filter splits a wave in half:
      T' keeps the full amplitude of shorter waves (>= 98 % below 0.6 x cutoff) and
      almost none of longer ones (<= 4 % above 1.5 x cutoff).
    - Wave perturbation T'(z) = T(z) - T_bar(z)
    - Specific potential energy E_p(z) = 0.5 * (g / N_bar)^2 * (T' / T_bar)^2 [J/kg],
      N_bar^2 = (g / T_bar) (dT_bar/dz + g / cp) being the stability of the background
      (``cp_j_kg_k`` per sample).  The local N^2 contains the wave itself and goes to
      zero or below inside large waves; E_p is undefined (NaN) where N_bar^2 <= 0.
      Without cp, ``buoyancy_n2`` (masked where <= 0) or N = 0.02 rad/s is used.
    - Dominant vertical wavelength lambda_z [km], among the waves T' keeps
    """
    z = np.asarray(z_km, dtype=np.float64)
    t = np.asarray(t_k, dtype=np.float64)
    g = np.asarray(gz_ms2, dtype=np.float64)

    ok = np.isfinite(z) & np.isfinite(t) & np.isfinite(g)
    if ok.sum() < 15:
        return {
            "t_background_k": [],
            "t_prime_k": [],
            "potential_energy_j_kg": [],
            "mean_potential_energy": 0.0,
            "dominant_wavelength_km": None,
        }

    z_clean = z[ok]
    t_clean = t[ok]
    g_clean = g[ok]

    sort_idx = np.argsort(z_clean)
    z_clean, t_clean, g_clean = z_clean[sort_idx], t_clean[sort_idx], g_clean[sort_idx]

    # Interpolate onto a uniform 100m grid for consistent filtering and spectral analysis
    dz = 0.1  # 100 meters
    z_uni = np.arange(np.min(z_clean), np.max(z_clean) + 1e-4, dz)
    if z_uni.size < 15:
        return {
            "t_background_k": [],
            "t_prime_k": [],
            "potential_energy_j_kg": [],
            "mean_potential_energy": 0.0,
            "dominant_wavelength_km": None,
        }

    t_uni = np.interp(z_uni, z_clean, t_clean)
    g_uni = np.interp(z_uni, z_clean, g_clean)

    # 1. Background: zero-phase (forward-backward) Butterworth low-pass.  The 8 km
    # Savitzky-Golay window used before put most of a 6-8 km wave into the background
    # (T' kept 58 % of a 6 km and 24 % of an 8 km wave) and overshot 4 km waves (120 %).
    # A cubic fit is removed first, so the padding at the ends adds no step and a smoothly
    # curved profile leaves no residual at the top and bottom.
    zc = (z_uni - z_uni.mean()) / max(np.ptp(z_uni), dz)        # centred and scaled: a well-conditioned fit
    trend = np.polyval(np.polyfit(zc, t_uni, 3), zc)
    try:
        sos = butter(filter_order, (1.0 / cutoff_wavelength_km) / (0.5 / dz), btype="low", output="sos")
        t_bar_uni = trend + sosfiltfilt(sos, t_uni - trend)
    except ValueError:
        t_bar_uni = trend          # profile too short for the filter's padding: cubic background

    # Wave perturbation
    t_prime_uni = t_uni - t_bar_uni

    # Interpolate back to original sample grid
    t_bar = np.interp(z_clean, z_uni, t_bar_uni)
    t_prime = np.interp(z_clean, z_uni, t_prime_uni)

    # 2. Gravity wave potential energy E_p = 0.5 * (g / N_bar)^2 * (T' / T_bar)^2
    if cp_j_kg_k is not None and np.shape(cp_j_kg_k) == z.shape:
        cp_clean = np.asarray(cp_j_kg_k, dtype=np.float64)[ok][sort_idx]
        cp_uni = np.interp(z_uni, z_clean, cp_clean)
        with np.errstate(invalid="ignore", divide="ignore"):
            n2_uni = (g_uni / t_bar_uni) * (np.gradient(t_bar_uni, dz * 1000.0) + g_uni / cp_uni)
        n2_clean = np.interp(z_clean, z_uni, n2_uni)
    elif buoyancy_n2 is not None:
        n2_clean = np.asarray(buoyancy_n2, dtype=np.float64)[ok][sort_idx]
    else:
        n2_clean = np.full(z_clean.shape, 0.02 ** 2)       # typical planetary value
    n2_clean = np.where(n2_clean > 0, n2_clean, np.nan)    # no E_p where unstable

    with np.errstate(invalid="ignore", divide="ignore"):
        ep = 0.5 * g_clean ** 2 / n2_clean * (t_prime / t_bar) ** 2
    ep[~np.isfinite(ep)] = np.nan

    # 3. Dominant vertical wavelength from FFT of T'
    # Zero-mean detrending and Hanning window
    window_t = np.hanning(len(t_prime_uni))
    fft_vals = np.fft.rfft(t_prime_uni * window_t)
    fft_freqs = np.fft.rfftfreq(len(t_prime_uni), d=dz)  # cycles per km

    power = np.abs(fft_vals) ** 2
    # Only waves the background filter leaves in T' (shorter than the cutoff), down to 0.5 km
    valid_freq_mask = (fft_freqs > (1.0 / cutoff_wavelength_km)) & (fft_freqs < (1.0 / 0.5))
    dominant_lambda = None
    if valid_freq_mask.any():
        peak_idx = np.argmax(power[valid_freq_mask])
        peak_freq = fft_freqs[valid_freq_mask][peak_idx]
        # a peak just short of the cutoff is the edge of a longer wave the filter removed
        if peak_freq >= 1.15 / cutoff_wavelength_km:
            dominant_lambda = round(float(1.0 / peak_freq), 2)

    # Output back aligned to original points
    out_t_bar = np.full(z.shape, np.nan)
    out_t_prime = np.full(z.shape, np.nan)
    out_ep = np.full(z.shape, np.nan)

    # the values are in altitude order; put each back at its own sample (profiles listed
    # from the top down would otherwise get their perturbations upside down)
    at = np.flatnonzero(ok)[sort_idx]
    out_t_bar[at] = t_bar
    out_t_prime[at] = t_prime
    out_ep[at] = ep

    return {
        "t_background_k": [None if not np.isfinite(v) else round(float(v), 2) for v in out_t_bar],
        "t_prime_k": [None if not np.isfinite(v) else round(float(v), 3) for v in out_t_prime],
        "potential_energy_j_kg": [None if not np.isfinite(v) else round(float(v), 3) for v in out_ep],
        "mean_potential_energy": round(float(np.nanmean(ep[ep > 0])), 3) if (ep > 0).any() else 0.0,
        "dominant_wavelength_km": dominant_lambda,
    }


def fit_chapman_ionosphere(
    z_km: np.ndarray,
    ne_cm3: np.ndarray,
) -> Dict[str, Any]:
    """Fit analytical alpha-Chapman model to an occultation electron density profile.

    Formula:
    Ne(z) = Nm * exp(0.5 * (1 - (z - hm)/H - exp(-(z - hm)/H)))
    """
    z = np.asarray(z_km, dtype=np.float64)
    ne = np.asarray(ne_cm3, dtype=np.float64)

    ok = np.isfinite(z) & np.isfinite(ne) & (ne > 0)
    if ok.sum() < 8:
        return {"nmf2_cm3": None, "hmf2_km": None, "scale_height_km": None, "r_squared": None}

    z_c = z[ok]
    ne_c = ne[ok]

    # Initial parameter guesses
    nm_guess = float(np.max(ne_c))
    hm_guess = float(z_c[np.argmax(ne_c)])
    h_guess = 50.0  # typical Chapman scale height in km

    def chapman_func(z_val, nm, hm, h):
        zeta = (z_val - hm) / np.clip(h, 1.0, 500.0)
        zeta_clipped = np.clip(zeta, -50.0, 50.0)
        return nm * np.exp(0.5 * (1.0 - zeta_clipped - np.exp(-zeta_clipped)))

    try:
        popt, _ = curve_fit(
            chapman_func,
            z_c,
            ne_c,
            p0=[nm_guess, hm_guess, h_guess],
            bounds=([nm_guess * 0.2, hm_guess - 100.0, 5.0], [nm_guess * 3.0, hm_guess + 100.0, 300.0]),
            maxfev=2000,
        )
        nm_fit, hm_fit, h_fit = popt

        # Goodness of fit (R^2)
        residuals = ne_c - chapman_func(z_c, *popt)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((ne_c - np.mean(ne_c)) ** 2)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "nmf2_cm3": round(float(nm_fit), 2),
            "hmf2_km": round(float(hm_fit), 2),
            "scale_height_km": round(float(h_fit), 2),
            "r_squared": round(float(r2), 4),
        }
    except (RuntimeError, ValueError):
        # no convergence: report no fit (the measured peak is given separately as
        # ne_peak_cm3 / hmf2_km; labelling it "Chapman fit" would be wrong)
        return {"nmf2_cm3": None, "hmf2_km": None, "scale_height_km": None, "r_squared": None}
