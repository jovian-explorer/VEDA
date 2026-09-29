"""Advanced Atmospheric Stability, Gravity Wave, and Ionospheric Profiler for VEDA.

Provides:
1. Cold Point Tropopause (CPT) and Lapse Rate Tropopause (LRT) Detection.
2. Gravity Wave Perturbation Analysis:
   - Background temperature extraction via adaptive polynomial / Savitzky-Golay filtering.
   - Temperature perturbation T'(z) = T(z) - T_bar(z).
   - Gravity wave specific potential energy E_p(z) = 0.5 * (g/N)^2 * (T'/T_bar)^2 [J/kg].
   - Dominant vertical wavelength extraction via FFT / periodogram.
3. Chapman Layer Modeling for Ionospheric Occultations:
   - Non-linear least squares fit of peak density (NmF2), peak altitude (hmF2), and neutral scale height (H).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.signal import savgol_filter
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


def extract_gravity_wave_activity(
    z_km: np.ndarray,
    t_k: np.ndarray,
    gz_ms2: np.ndarray,
    buoyancy_n2: Optional[np.ndarray] = None,
    filter_order: int = 3,
    cutoff_wavelength_km: float = 8.0,
) -> Dict[str, Any]:
    """Extract atmospheric gravity wave temperature perturbations and potential energy.

    Computes:
    - Background temperature T_bar(z)
    - Wave perturbation T'(z) = T(z) - T_bar(z)
    - Specific potential energy E_p(z) = 0.5 * (g / N)^2 * (T' / T_bar)^2 [J/kg]
    - Dominant vertical wavelength lambda_z [km]
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

    # 1. Background state extraction using Savitzky-Golay filter
    # Window length corresponds roughly to cutoff_wavelength_km
    pts_in_window = int(round(cutoff_wavelength_km / dz))
    if pts_in_window % 2 == 0:
        pts_in_window += 1
    pts_in_window = max(5, min(pts_in_window, len(z_uni) - 2 if len(z_uni) % 2 != 0 else len(z_uni) - 3))

    try:
        t_bar_uni = savgol_filter(t_uni, window_length=pts_in_window, polyorder=min(filter_order, pts_in_window - 1))
    except Exception:
        # Fallback to low-order polynomial fit
        poly = np.polyfit(z_uni, t_uni, deg=3)
        t_bar_uni = np.polyval(poly, z_uni)

    # Wave perturbation
    t_prime_uni = t_uni - t_bar_uni

    # Interpolate back to original sample grid
    t_bar = np.interp(z_clean, z_uni, t_bar_uni)
    t_prime = np.interp(z_clean, z_uni, t_prime_uni)

    # 2. Gravity wave potential energy E_p = 0.5 * (g / N)^2 * (T' / T_bar)^2
    # If N^2 not provided, approximate N ~ 0.02 rad/s (typical planetary value)
    if buoyancy_n2 is not None:
        n2_raw = np.asarray(buoyancy_n2, dtype=np.float64)
        n2_clean = n2_raw[ok][sort_idx]
        n_val = np.sqrt(np.clip(n2_clean, 1e-6, None))
    else:
        n_val = np.full(z_clean.shape, 0.02)

    with np.errstate(invalid="ignore", divide="ignore"):
        ep = 0.5 * (g_clean / n_val) ** 2 * (t_prime / t_bar) ** 2
        ep = np.nan_to_num(ep, nan=0.0, posinf=0.0, neginf=0.0)

    # 3. Dominant vertical wavelength from FFT of T'
    # Zero-mean detrending and Hanning window
    window_t = np.hanning(len(t_prime_uni))
    fft_vals = np.fft.rfft(t_prime_uni * window_t)
    fft_freqs = np.fft.rfftfreq(len(t_prime_uni), d=dz)  # cycles per km

    power = np.abs(fft_vals) ** 2
    # Ignore zero frequency and unphysically long/short wavelengths
    valid_freq_mask = (fft_freqs > (1.0 / 25.0)) & (fft_freqs < (1.0 / 0.5))
    dominant_lambda = None
    if valid_freq_mask.any():
        peak_idx = np.argmax(power[valid_freq_mask])
        peak_freq = fft_freqs[valid_freq_mask][peak_idx]
        if peak_freq > 0:
            dominant_lambda = round(float(1.0 / peak_freq), 2)

    # Output back aligned to original points
    out_t_bar = np.full(z.shape, np.nan)
    out_t_prime = np.full(z.shape, np.nan)
    out_ep = np.full(z.shape, np.nan)

    out_t_bar[ok] = t_bar
    out_t_prime[ok] = t_prime
    out_ep[ok] = ep

    return {
        "t_background_k": [None if not np.isfinite(v) else round(float(v), 2) for v in out_t_bar],
        "t_prime_k": [None if not np.isfinite(v) else round(float(v), 3) for v in out_t_prime],
        "potential_energy_j_kg": [None if not np.isfinite(v) else round(float(v), 3) for v in out_ep],
        "mean_potential_energy": round(float(np.mean(ep[ep > 0])), 3) if (ep > 0).any() else 0.0,
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
    except Exception:
        return {
            "nmf2_cm3": round(nm_guess, 2),
            "hmf2_km": round(hm_guess, 2),
            "scale_height_km": None,
            "r_squared": None,
        }
