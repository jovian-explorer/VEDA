"""COSMIC-2 Advanced Atmospheric & Ionospheric Science Module.

This module provides high-precision physical and numerical calculations for
Radio Occultation (RO) and Space Weather data products, conforming to WMO and
CODATA physical standards as specified in SCIENCE_SPECS.md.

Algorithms implemented:
1. Potential Temperature (theta) calculation with automatic temperature unit detection.
2. Brunt-Vaisala buoyancy frequency squared (N^2) for static stability and TIL detection.
3. Vertical Total Electron Content (VTEC) trapezoidal integration from ionospheric electron density.
4. Scintillation S4 event categorization, climatology fractions, and burst counting.

Author: Account 2 (Specialist Science Authority)
Task: TASK-2026-001
Date: 2026-09-19
"""

from __future__ import annotations

from typing import Any, Dict, Union
import numpy as np
from scipy import integrate

# ==============================================================================
# 1. PHYSICAL CONSTANTS (WMO / US Standard Atmosphere / CODATA)
# ==============================================================================

# Standard acceleration due to gravity at sea level [m s^-2]
G_0: float = 9.80665

# Specific gas constant for dry air [J kg^-1 K^-1]
R_DRY: float = 287.0578

# Specific heat capacity of dry air at constant pressure [J kg^-1 K^-1]
C_P: float = 1004.6

# Poisson constant (dimensionless) kappa = R_dry / c_p (~0.2857435)
KAPPA: float = R_DRY / C_P

# Standard reference pressure [hPa]
P_REF: float = 1000.0

# 1 TECU = 10^16 electrons m^-2
# Integrated factor: integral(Ne [cm^-3] * dz [km]) * 10^5 [cm/km] * 10^4 [m^-2/cm^-2] / 10^16 = 10^-7
TECU_CONVERSION_FACTOR: float = 1e-7


# ==============================================================================
# 2. HELPER UTILITIES
# ==============================================================================

def _smooth_1d(arr: np.ndarray, window: int) -> np.ndarray:
    """Apply robust symmetric moving average filter handling NaNs.
    
    Parameters:
        arr: 1D input array.
        window: Filter window length (must be >= 1).
        
    Returns:
        1D smoothed array of same length.
    """
    n = len(arr)
    if window <= 1 or n < 2:
        return arr.copy()
    
    # Ensure window is odd for symmetric centering
    if window % 2 == 0:
        window += 1
    window = min(window, n if n % 2 != 0 else n - 1)
    if window <= 1:
        return arr.copy()
        
    half = window // 2
    smoothed = np.full(n, np.nan, dtype=np.float64)
    
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        sub = arr[start:end]
        valid_sub = sub[np.isfinite(sub)]
        if len(valid_sub) > 0:
            smoothed[i] = np.mean(valid_sub)
            
    return smoothed


# ==============================================================================
# 3. CORE SCIENTIFIC ALGORITHMS
# ==============================================================================

def compute_potential_temperature(
    temperature_k: Union[np.ndarray, list],
    pressure_hpa: Union[np.ndarray, list],
) -> np.ndarray:
    """Compute Poisson potential temperature profile in Kelvin.

    Formula:
        theta(z) = T(z) * (P_ref / P(z)) ^ kappa

    Parameters:
        temperature_k: 1D array of dry or atmospheric temperature. If values
            are detected to be in Celsius (e.g. mean of finite values < 100),
            they are automatically converted to Kelvin (T_K = T_C + 273.15).
        pressure_hpa: 1D array of atmospheric pressure in hPa.

    Returns:
        1D float64 NumPy array of potential temperature theta in Kelvin.
        Values where P <= 0, T <= 0, or either input is NaN will be set to NaN.
    """
    temp = np.asarray(temperature_k, dtype=np.float64).flatten()
    pres = np.asarray(pressure_hpa, dtype=np.float64).flatten()

    if temp.shape != pres.shape:
        raise ValueError(
            f"Shape mismatch: temperature {temp.shape} and pressure {pres.shape} must match."
        )

    if temp.size == 0:
        return np.empty(0, dtype=np.float64)

    # Unit auto-detection: Atmospheric temperatures in Celsius rarely exceed 60 C.
    # In Kelvin, atmospheric temperatures typically range between 180 K and 320 K.
    finite_temps = temp[np.isfinite(temp)]
    if finite_temps.size > 0 and np.mean(finite_temps) < 100.0:
        temp_k = temp + 273.15
    else:
        temp_k = temp.copy()

    # Mask valid strictly positive pressures and absolute temperatures
    valid_mask = np.isfinite(temp_k) & np.isfinite(pres) & (pres > 0.0) & (temp_k > 0.0)

    theta = np.full(temp.shape, np.nan, dtype=np.float64)
    if np.any(valid_mask):
        p_valid = pres[valid_mask]
        t_valid = temp_k[valid_mask]
        theta[valid_mask] = t_valid * np.power(P_REF / p_valid, KAPPA)

    return theta


def compute_brunt_vaisala(
    altitude_km: Union[np.ndarray, list],
    theta_k: Union[np.ndarray, list],
    smooth_window: int = 5,
) -> np.ndarray:
    """Compute Brunt-Vaisala buoyancy frequency squared (N^2) in rad^2 s^-2.

    Formula:
        N^2(z) = (g_0 / theta(z)) * (d theta(z) / dz_meters)
    where geometric altitude is converted to meters: z_meters = z_km * 1000.0.

    Parameters:
        altitude_km: 1D geometric altitude array in km.
        theta_k: 1D potential temperature array in Kelvin.
        smooth_window: Window size for preliminary smoothing of theta (default 5).

    Returns:
        1D float64 NumPy array of N^2 in s^-2.
        - Tropospheric baseline: ~ 1e-4 s^-2.
        - Stratospheric values: ~ 4e-4 to 6e-4 s^-2.
        - Tropopause Inversion Layer (TIL): peaks > 5e-4 s^-2.
        - Where theta <= 0 or inputs are NaN, N^2 is set to NaN.
    """
    alt = np.asarray(altitude_km, dtype=np.float64).flatten()
    th = np.asarray(theta_k, dtype=np.float64).flatten()

    if alt.shape != th.shape:
        raise ValueError(
            f"Shape mismatch: altitude {alt.shape} and theta {th.shape} must match."
        )

    n_pts = alt.size
    if n_pts < 2:
        return np.full(n_pts, np.nan, dtype=np.float64)

    # Preliminary smoothing on theta
    th_smoothed = _smooth_1d(th, smooth_window) if smooth_window > 1 else th.copy()

    # Identify finite points
    valid = np.isfinite(alt) & np.isfinite(th_smoothed) & (th_smoothed > 0.0)
    if np.sum(valid) < 2:
        return np.full(n_pts, np.nan, dtype=np.float64)

    alt_v = alt[valid]
    th_v = th_smoothed[valid]

    # Handle monotonic order: ensure ascending altitude for numerical gradient
    sort_order = np.argsort(alt_v)
    alt_sorted = alt_v[sort_order]
    th_sorted = th_v[sort_order]

    # Guard against duplicate altitudes (zero division in gradient)
    diffs = np.diff(alt_sorted)
    if np.any(diffs <= 0):
        # Resolve duplicate altitudes by small monotonic jitter
        alt_sorted = alt_sorted.copy()
        for j in range(1, len(alt_sorted)):
            if alt_sorted[j] <= alt_sorted[j - 1]:
                alt_sorted[j] = alt_sorted[j - 1] + 1e-6

    # Convert altitude to meters
    alt_m_sorted = alt_sorted * 1000.0

    # Second-order central difference gradient with one-sided edge differences
    dth_dz_sorted = np.gradient(th_sorted, alt_m_sorted)

    # Invert sorting back to original order of valid points
    inv_order = np.empty_like(sort_order)
    inv_order[sort_order] = np.arange(len(sort_order))
    dth_dz_v = dth_dz_sorted[inv_order]

    # Calculate N^2 = (g_0 / theta) * (d theta / dz)
    n2_v = (G_0 / th_v) * dth_dz_v

    # Map back to full-length array
    n2_full = np.full(n_pts, np.nan, dtype=np.float64)
    n2_full[valid] = n2_v

    return n2_full


def compute_vtec(
    altitude_km: Union[np.ndarray, list],
    electron_density_cm3: Union[np.ndarray, list],
) -> Dict[str, float]:
    """Compute integrated Vertical Total Electron Content (VTEC).

    Integrates ionospheric electron density Ne(z) from bottom to top:
        VTEC [TECU] = 10^-7 * integral(Ne [cm^-3] * dz [km])

    Parameters:
        altitude_km: 1D altitude array in km (typically ~100 to 800 km).
        electron_density_cm3: 1D electron density in el/cm^3.

    Returns:
        dict containing:
            vtec_tecu (float): Total vertical electron content in TECU.
            alt_min_km (float): Lower integration boundary in km.
            alt_max_km (float): Upper integration boundary in km.
            peak_density_cm3 (float): Maximum electron density (NmF2) in el/cm^3.
            peak_alt_km (float): Altitude of maximum electron density (hmF2) in km.
    """
    alt = np.asarray(altitude_km, dtype=np.float64).flatten()
    ne = np.asarray(electron_density_cm3, dtype=np.float64).flatten()

    empty_res: Dict[str, float] = {
        "vtec_tecu": float(np.nan),
        "alt_min_km": float(np.nan),
        "alt_max_km": float(np.nan),
        "peak_density_cm3": float(np.nan),
        "peak_alt_km": float(np.nan),
    }

    if alt.shape != ne.shape or alt.size < 2:
        return empty_res

    valid = np.isfinite(alt) & np.isfinite(ne) & (alt >= 0.0)
    if np.sum(valid) < 2:
        return empty_res

    alt_v = alt[valid]
    ne_v = ne[valid]

    # Clamp unphysical negative retrieved electron density artifacts to 0
    ne_phys = np.maximum(ne_v, 0.0)

    # Sort strictly by increasing altitude
    sort_idx = np.argsort(alt_v)
    alt_sorted = alt_v[sort_idx]
    ne_sorted = ne_phys[sort_idx]

    # Deduplicate strictly identical altitudes if present
    alt_uniq, uniq_idx = np.unique(alt_sorted, return_index=True)
    ne_uniq = ne_sorted[uniq_idx]

    if alt_uniq.size < 2:
        return empty_res

    # Trapezoidal integration using scipy.integrate.trapezoid
    integral_val = float(integrate.trapezoid(ne_uniq, x=alt_uniq))
    vtec_tecu = float(TECU_CONVERSION_FACTOR * integral_val)

    # Peak ionospheric F2 parameters (NmF2 and hmF2)
    peak_idx = int(np.argmax(ne_sorted))
    peak_density = float(ne_sorted[peak_idx])
    peak_alt = float(alt_sorted[peak_idx])

    return {
        "vtec_tecu": max(0.0, vtec_tecu),
        "alt_min_km": float(np.min(alt_uniq)),
        "alt_max_km": float(np.max(alt_uniq)),
        "peak_density_cm3": peak_density,
        "peak_alt_km": peak_alt,
    }


def classify_scintillation(
    s4_values: Union[np.ndarray, list],
    threshold_moderate: float = 0.3,
    threshold_strong: float = 0.6,
) -> Dict[str, Any]:
    """Classify scintillation activity based on S4 index time series or profile.

    Parameters:
        s4_values: 1D array of S4 scintillation index (unitless, 0 to ~1.5).
        threshold_moderate: Cutoff for moderate scintillation (default 0.3).
        threshold_strong: Cutoff for strong/severe scintillation (default 0.6).

    Returns:
        dict containing:
            s4_max (float): Maximum S4 value.
            s4_mean (float): Mean S4 value across all valid samples.
            category (str): "quiet" (<0.3), "moderate" (0.3 - 0.6), or "severe" (>=0.6).
            fraction_moderate (float): Ratio of points where S4 >= threshold_moderate.
            fraction_strong (float): Ratio of points where S4 >= threshold_strong.
            event_count (int): Number of distinct contiguous intervals where S4 >= threshold_moderate.
    """
    s4 = np.asarray(s4_values, dtype=np.float64).flatten()

    empty_res: Dict[str, Any] = {
        "s4_max": float(np.nan),
        "s4_mean": float(np.nan),
        "category": "unknown",
        "fraction_moderate": 0.0,
        "fraction_strong": 0.0,
        "event_count": 0,
    }

    if s4.size == 0:
        return empty_res

    valid = np.isfinite(s4) & (s4 >= 0.0)
    if not np.any(valid):
        return empty_res

    valid_s4 = s4[valid]
    n_valid = valid_s4.size

    s4_max = float(np.max(valid_s4))
    s4_mean = float(np.mean(valid_s4))

    above_mod = valid_s4 >= threshold_moderate
    above_strong = valid_s4 >= threshold_strong

    fraction_mod = float(np.sum(above_mod) / n_valid)
    fraction_str = float(np.sum(above_strong) / n_valid)

    if s4_max >= threshold_strong:
        category = "severe"
    elif s4_max >= threshold_moderate:
        category = "moderate"
    else:
        category = "quiet"

    # Count contiguous scintillation burst events exceeding threshold_moderate
    if n_valid == 0 or not np.any(above_mod):
        event_count = 0
    else:
        # A contiguous event starts if first element is True, or on rising edges (False -> True)
        rising_edges = (~above_mod[:-1]) & above_mod[1:]
        event_count = int(above_mod[0]) + int(np.sum(rising_edges))

    return {
        "s4_max": s4_max,
        "s4_mean": s4_mean,
        "category": category,
        "fraction_moderate": fraction_mod,
        "fraction_strong": fraction_str,
        "event_count": event_count,
    }
