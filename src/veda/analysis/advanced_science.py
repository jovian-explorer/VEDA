"""Ionospheric profile diagnostics (body independent).

Total electron content of a radio-occultation electron density profile:
    TEC [TECU] = 1e-7 * integral(Ne [cm^-3] dz [km])        (1 TECU = 1e16 el m^-2)
and the peak (NmF2 / hmF2 style) density and altitude.

Thermodynamic diagnostics (lapse rate, scale height, potential temperature,
N^2) live in ``atmospheric.py``, which uses each body's own constants and a
temperature-dependent cp (``thermo.py``).
"""
from __future__ import annotations

from typing import Dict, Union

import numpy as np
from scipy import integrate

# 1 TECU = 1e16 electrons m^-2:  integral(Ne [cm^-3] dz [km]) * 1e5 cm/km * 1e4 cm^2/m^2 / 1e16 = 1e-7
TECU_CONVERSION_FACTOR: float = 1e-7


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

    # Sort strictly by increasing altitude
    sort_idx = np.argsort(alt_v)
    alt_sorted = alt_v[sort_idx]
    ne_sorted = ne_v[sort_idx]

    # Deduplicate strictly identical altitudes if present
    alt_uniq, uniq_idx = np.unique(alt_sorted, return_index=True)
    ne_uniq = ne_sorted[uniq_idx]

    if alt_uniq.size < 2:
        return empty_res

    # Trapezoidal integration of the densities as they are: negative values are noise about
    # zero (below and above the layer of an occultation profile), and setting them to zero
    # would keep only the positive half of the noise, a bias of 0.4 sigma per level.  A
    # profile of noise alone gives about zero, below zero if its noise is.
    integral_val = float(integrate.trapezoid(ne_uniq, x=alt_uniq))
    vtec_tecu = float(TECU_CONVERSION_FACTOR * integral_val)

    # Peak ionospheric F2 parameters (NmF2 and hmF2); a profile without a positive density has none
    peak_idx = int(np.argmax(ne_sorted))
    peak_density = float(ne_sorted[peak_idx])
    peak_alt = float(alt_sorted[peak_idx])
    if peak_density <= 0.0:
        peak_density = peak_alt = float(np.nan)

    return {
        "vtec_tecu": vtec_tecu,
        "alt_min_km": float(np.min(alt_uniq)),
        "alt_max_km": float(np.max(alt_uniq)),
        "peak_density_cm3": peak_density,
        "peak_alt_km": peak_alt,
    }
