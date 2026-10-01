"""Temperature-dependent heat capacity of planetary atmospheres.

cp of CO2 changes strongly with temperature (about 735 J/(kg K) at 200 K,
850 at 300 K, 1180 at 700 K for pure CO2), so a single constant puts the dry
adiabatic lapse rate g/cp, and with it N^2, wrong by 10-30 % on Mars and in
the deep Venus atmosphere.  For Venus, Mars, Titan and Pluto cp(T) is the
mole-fraction weighted ideal-gas heat capacity of the main constituents
(JANAF thermochemical tables, ideal gas at 1 bar), divided by the mean molar
mass.  Other bodies keep their constant cp from the registry.

Interpolation is linear in T between tabulated points and held constant
outside 100-1000 K.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

# Molar heat capacity Cp (J mol^-1 K^-1), ideal gas, JANAF tables
_T = np.array([100.0, 200.0, 298.15, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0])
_CP_MOLAR: Dict[str, np.ndarray] = {
    "CO2": np.array([29.208, 32.359, 37.129, 41.325, 44.627, 47.321, 49.564, 51.434, 52.999, 54.308]),
    "N2":  np.array([29.104, 29.107, 29.124, 29.249, 29.580, 30.110, 30.754, 31.433, 32.090, 32.697]),
    "O2":  np.array([29.106, 29.126, 29.376, 30.106, 31.091, 32.090, 32.981, 33.733, 34.355, 34.870]),
    "Ar":  np.full(10, 20.786),
    "CH4": np.array([33.258, 33.473, 35.695, 40.500, 46.342, 52.227, 57.794, 62.932, 67.601, 71.795]),
    "CO":  np.array([29.104, 29.108, 29.142, 29.342, 29.794, 30.443, 31.171, 31.899, 32.577, 33.183]),
}
# Bodies whose atmosphere is (almost) entirely made of tabulated gases
_VARIABLE_CP_BODIES = ("venus", "mars", "titan", "pluto")


def cp_model(body) -> str:
    """'temperature-dependent (...)' or 'constant'."""
    comp = _tabulated_fractions(body)
    return f"temperature-dependent ({', '.join(comp)})" if comp else "constant"


def _tabulated_fractions(body) -> Dict[str, float]:
    if body is None or body.id not in _VARIABLE_CP_BODIES:
        return {}
    comp = {k: float(v) for k, v in (body.atmospheric_composition or {}).items() if k in _CP_MOLAR}
    total = sum((body.atmospheric_composition or {}).values()) or 0.0
    if not comp or total <= 0 or sum(comp.values()) < 0.95 * total:
        return {}
    s = sum(comp.values())
    return {k: v / s for k, v in comp.items()}


def heat_capacity(body, t_k) -> np.ndarray:
    """cp in J/(kg K) at temperature(s) ``t_k`` for ``body`` (array, NaN where T is not finite)."""
    t = np.asarray(t_k, dtype=np.float64)
    fr = _tabulated_fractions(body)
    if not fr:
        out = np.full(t.shape, float(body.isobaric_heat_capacity_cp), dtype=np.float64)
        out[~np.isfinite(t)] = np.nan
        return out
    tc = np.clip(t, _T[0], _T[-1])
    molar = sum(f * np.interp(tc, _T, _CP_MOLAR[g]) for g, f in fr.items())
    mu_kg = float(body.mean_molecular_weight) / 1000.0          # kg/mol
    out = molar / mu_kg
    out = np.where(np.isfinite(t), out, np.nan)
    return out
