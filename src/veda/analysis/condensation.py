"""Carbon dioxide condensation on Mars and Venus: how close a temperature profile comes
to the frost point of its CO2.

The saturation (frost-point) temperature of CO2 at partial pressure p_CO2 is the vapour
pressure relation of James et al. (1992, in *Mars*, Kieffer et al. eds., University of
Arizona Press, 934-968), as used for example in the MAIC-2 model (Greve et al. 2010,
Planet. Space Sci. 58, 931; arXiv:0903.2688, eq. 7):

    T_CO2 = b / (a - ln p_CO2),   a = 23.3494, b = 3182.48 K,   p_CO2 in hPa

(700 Pa gives 148.7 K).  p_CO2 = x_CO2 p with x_CO2 the body's CO2 volume fraction from
the registry composition (Mars 0.951, Venus 0.965); the total pressure instead would give
values 0.34 K higher at 6 hPa.  T - T_CO2 at or below zero means the CO2 is saturated or
supersaturated: CO2 ice clouds and snowfall in the Martian polar night (Colaprete et al.
2003, JGR 108(E7), 5081; Hu et al. 2012, JGR 117, E07002) and the cold layer near 125 km at
the Venus terminator (Mahieux et al. 2012, JGR 117, E07001).  Its uncertainty follows from
those of T and p: d T_CO2 / d ln p = T_CO2^2 / b.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

A_CO2 = 23.3494
B_CO2 = 3182.48            # K


def co2_volume_fraction(body) -> Optional[float]:
    """CO2 volume fraction of the body's atmosphere (0-1), or None without CO2."""
    comp = getattr(body, "atmospheric_composition", None) or {}
    x = comp.get("CO2")
    return float(x) / 100.0 if x else None


def co2_condensation_temperature(p_hpa, x_co2: float) -> np.ndarray:
    """Frost-point temperature (K) of CO2 at total pressure ``p_hpa`` (hPa) and CO2 volume
    fraction ``x_co2`` (module docstring); NaN where the pressure is not positive."""
    p = np.asarray(p_hpa, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        lp = np.log(np.where(p > 0, p * x_co2, np.nan))
        return B_CO2 / (A_CO2 - lp)


def co2_condensation_sigma(t_co2, p_hpa, sigma_p_hpa) -> np.ndarray:
    """1-sigma of T_CO2 from that of the pressure: (T_CO2^2 / b) sigma_p / p."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray(t_co2, dtype=float) ** 2 / B_CO2 * np.abs(np.asarray(sigma_p_hpa, dtype=float)
                                                                   / np.asarray(p_hpa, dtype=float))
