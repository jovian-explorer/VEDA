"""Real-gas compressibility of Titan's lower atmosphere.

Titan's troposphere is cold (70-95 K) and dense (1.5 bar at the surface), and nitrogen
there is not an ideal gas: p = Z n k T with the compressibility

    Z = 1 + B_mix(T) p / (R T),

B_mix = sum_ij x_i x_j B_ij(T) the second virial coefficient of the N2-CH4 mixture.
Each B_ij is from the Tsonopoulos (1974, AIChE J. 20, 263) correlation,

    B Pc / (R Tc) = f0(Tr) + omega f1(Tr),   Tr = T / Tc,
    f0 = 0.1445 - 0.330/Tr - 0.1385/Tr^2 - 0.0121/Tr^3 - 0.000607/Tr^8,
    f1 = 0.0637 + 0.331/Tr^2 - 0.423/Tr^3 - 0.008/Tr^8,

with the critical constants of Poling, Prausnitz & O'Connell (The Properties of Gases and
Liquids, 5th ed., appendix A) and, for the cross term, Tc12 = sqrt(Tc1 Tc2), Vc12 from the
mean of the cube roots of Vc, Zc12 and omega12 the means, Pc12 = Zc12 R Tc12 / Vc12.  It
gives B = -196 cm^3/mol for N2 at 91.4 K (tables: about -190).  The third virial term is
below 1e-4 of Z at 1.5 bar.

Checked on the Cassini radio occultation profiles of Titan (Schinder et al.), whose
archive gives temperature, pressure and number density at every level: their own
compressibility p / (n k T) is 0.958 to 0.964 at the surface and 0.995 at 50 km.

Venus' lower atmosphere is not ideal either (VIRA implies Z = 1.010 at the surface and
0.988 at 30 km), but there the second virial coefficient alone is not enough (Z = 1.002
at the surface), so VEDA keeps the ideal gas for Venus.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

R_UNIV = 8.314462618       # J/(mol K)

# Tc (K), Pc (Pa), Vc (m^3/mol), Zc, omega
CRITICAL = {
    "N2": (126.20, 33.98e5, 90.10e-6, 0.289, 0.037),
    "CH4": (190.56, 45.99e5, 98.60e-6, 0.286, 0.011),
}

# bodies with a real-gas equation of state and the gases it counts (mole fractions
# renormalised over these)
REAL_GAS_BODIES = {"titan": ("N2", "CH4")}


def _tsonopoulos(t: np.ndarray, tc: float, pc: float, omega: float) -> np.ndarray:
    tr = t / tc
    f0 = 0.1445 - 0.330 / tr - 0.1385 / tr ** 2 - 0.0121 / tr ** 3 - 0.000607 / tr ** 8
    f1 = 0.0637 + 0.331 / tr ** 2 - 0.423 / tr ** 3 - 0.008 / tr ** 8
    return (f0 + omega * f1) * R_UNIV * tc / pc                 # m^3/mol


def second_virial(t_k, fractions: Dict[str, float]) -> np.ndarray:
    """Second virial coefficient (m^3/mol) of a gas mixture at temperature ``t_k``."""
    t = np.asarray(t_k, dtype=float)
    gases = [g for g in fractions if g in CRITICAL and fractions[g] > 0]
    total = sum(fractions[g] for g in gases)
    b = np.zeros_like(t)
    for gi in gases:
        for gj in gases:
            ti, pi, vi, zi, wi = CRITICAL[gi]
            tj, pj, vj, zj, wj = CRITICAL[gj]
            if gi == gj:
                bij = _tsonopoulos(t, ti, pi, wi)
            else:
                tc = np.sqrt(ti * tj)
                vc = ((vi ** (1 / 3) + vj ** (1 / 3)) / 2.0) ** 3
                zc = (zi + zj) / 2.0
                bij = _tsonopoulos(t, tc, zc * R_UNIV * tc / vc, (wi + wj) / 2.0)
            b = b + fractions[gi] / total * fractions[gj] / total * bij
    return b


def compressibility(body, t_k, p_hpa) -> Optional[np.ndarray]:
    """Z = p / (n k T) at each level for a body with a real-gas equation of state in VEDA
    (Titan), else None (ideal gas)."""
    gases = REAL_GAS_BODIES.get(getattr(body, "id", ""))
    if not gases or t_k is None or p_hpa is None:
        return None
    comp = getattr(body, "atmospheric_composition", None) or {}
    fractions = {g: float(comp.get(g, 0.0)) for g in gases}
    if not any(fractions.values()):
        return None
    t = np.asarray(t_k, dtype=float)
    p = np.asarray(p_hpa, dtype=float) * 100.0
    with np.errstate(invalid="ignore", divide="ignore"):
        z = 1.0 + second_virial(t, fractions) * p / (R_UNIV * t)
    return np.where(np.isfinite(z) & (z > 0.5), z, np.nan)


def temperature_with_compressibility(body, p_pa: np.ndarray, rho: np.ndarray, r_spec, iterations: int = 6) -> np.ndarray:
    """T from p = Z(T, p) rho R T by fixed-point iteration (the ideal-gas T first)."""
    p = np.asarray(p_pa, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = p / (rho * r_spec)
        for _ in range(iterations):
            z = compressibility(body, t, p / 100.0)
            if z is None:
                return t
            t = p / (np.where(np.isfinite(z), z, 1.0) * rho * r_spec)
    return t
