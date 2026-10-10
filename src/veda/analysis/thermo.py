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

Jupiter and Saturn: molecular hydrogen's rotation is only partly excited at 70-200 K,
so its cp is far below the 7/2 R of the high-temperature limit, and it depends on the
fraction of para hydrogen.  VEDA uses the "frozen equilibrium" or "intermediate" cp:
the para fraction is the thermal-equilibrium value at the local temperature, but stays
fixed while a parcel moves, as for displacements fast compared with ortho-para
conversion, which sets the buoyancy frequency and the speed of sound (Conrath &
Gierasch 1984, Icarus 57, 184; Massie & Hunten 1982, Icarus 49, 213).  Its rotational
part comes from the rigid-rotor partition functions of para (even J) and ortho (odd J)
hydrogen, theta_rot = 85.35 K; for normal (3:1) and para hydrogen they give NIST's cp
within 0.4 % at 100-300 K.  Helium is 5/2 R.
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
    "He":  np.full(10, 20.786),
    "H2":  np.full(10, np.nan),          # computed: _h2_cp_molar
}
# Bodies whose atmosphere is (almost) entirely made of tabulated gases
_VARIABLE_CP_BODIES = ("venus", "mars", "titan", "pluto", "jupiter", "saturn")
R_MOLAR = 8.314462618                  # J/(mol K)
H2_THETA_ROT = 85.35                   # K, hcB/k with B = 59.32 cm^-1


def _h2_rotation(t: np.ndarray, odd: bool):
    """(cv_rot / R, partition function) of ortho (odd J) or para (even J) hydrogen."""
    j = np.arange(1 if odd else 0, 31, 2, dtype=float)
    g = (2.0 * j + 1.0) * (3.0 if odd else 1.0)               # nuclear spin weights 3 : 1
    x = (j * (j + 1.0) * H2_THETA_ROT)[None, :] / t[:, None]
    w = g[None, :] * np.exp(-(x - x.min(axis=1, keepdims=True)))
    z = w.sum(axis=1)
    m1 = (w * x).sum(axis=1) / z
    m2 = (w * x * x).sum(axis=1) / z
    return m2 - m1 ** 2, z * np.exp(-x.min(axis=1))


def h2_para_fraction(t_k) -> np.ndarray:
    """Equilibrium para fraction of hydrogen at temperature t_k (0.25 when hot)."""
    t = np.clip(np.atleast_1d(np.asarray(t_k, dtype=float)), 20.0, 1000.0)
    _, zp = _h2_rotation(t, False)
    _, zo = _h2_rotation(t, True)
    return zp / (zp + zo)


def _h2_cp_molar(t_k, para_fraction=None) -> np.ndarray:
    """cp of hydrogen (J/(mol K)) at fixed para fraction (default: the equilibrium one at
    t_k, the intermediate cp); vibration (theta 6332 K) is negligible below 1000 K."""
    t = np.clip(np.atleast_1d(np.asarray(t_k, dtype=float)), 20.0, 1000.0)
    cp_para, _ = _h2_rotation(t, False)
    cp_ortho, _ = _h2_rotation(t, True)
    fp = h2_para_fraction(t) if para_fraction is None else para_fraction
    return R_MOLAR * (2.5 + fp * cp_para + (1.0 - fp) * cp_ortho)


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
    molar = sum(f * (_h2_cp_molar(t.ravel()).reshape(t.shape) if g == "H2" else np.interp(tc, _T, _CP_MOLAR[g]))
                for g, f in fr.items())
    mu_kg = float(body.mean_molecular_weight) / 1000.0          # kg/mol
    out = molar / mu_kg
    out = np.where(np.isfinite(t), out, np.nan)
    return out


# Venus: cp = cp0 (T / T0)^nu, the fit of Lebonnois et al. (2010, JGR 115, E06006) to the
# VIRA heat capacity used by Venus general circulation models (LMD, OPUS-V), and the
# potential temperature that follows from it,
#     theta^nu = T^nu + nu T0^nu ln((p_ref / p)^(R / cp0)),
# (with one constant cp, 850 J/(kg K) before, the near-adiabatic lower atmosphere of the
# Venus-GRAM / VIRA mean profile had theta rising from 735 K at the surface to 797 K at
# 20 km, a stability it does not have; with cp(T) theta stays within 2 K of 735 K)
THETA_CP_FIT = {"venus": (1000.0, 460.0, 0.35)}        # cp0 (J/(kg K)), T0 (K), nu


def potential_temperature(body, t_k, p_hpa, r_spec) -> np.ndarray:
    """Potential temperature (K) referred to the body's reference pressure: with the
    variable-cp form above for Venus, else T (p_ref / p)^(R / cp) with the body's reference
    cp (registry value).  NaN where p is not positive."""
    t = np.asarray(t_k, dtype=np.float64)
    p = np.asarray(p_hpa, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        ln_p = np.log(body.reference_pressure_hpa / np.where(p > 0, p, np.nan))
        fit = THETA_CP_FIT.get(body.id)
        if fit:
            cp0, t0, nu = fit
            return (t ** nu + nu * t0 ** nu * (r_spec / cp0) * ln_p) ** (1.0 / nu)
        return t * np.exp(r_spec / body.isobaric_heat_capacity_cp * ln_p)


def potential_temperature_sensitivity(body, t_k, theta, r_spec):
    """(d ln theta / d ln T, d ln theta / d ln p) at each level, for first-order errors:
    (1, -R/cp) with a constant cp; on Venus ((T/theta)^nu, -(T0/theta)^nu R/cp0)."""
    fit = THETA_CP_FIT.get(body.id)
    if not fit:
        return 1.0, -r_spec / body.isobaric_heat_capacity_cp
    cp0, t0, nu = fit
    with np.errstate(invalid="ignore", divide="ignore"):
        return (np.asarray(t_k, dtype=float) / theta) ** nu, -(t0 / np.asarray(theta, dtype=float)) ** nu * r_spec / cp0
