"""Multi-planet thermodynamic and atmospheric analysis engine for VEDA.

Applies body-specific thermodynamic constants (surface gravity, specific gas
constant R, isobaric heat capacity Cp, reference pressure) to calculate:
- Environmental lapse rate (-dT/dz)
- Potential temperature (theta) via Poisson equation
- Brunt-Vaisala buoyancy frequency squared (N^2)
- Mass density (rho)
- Scale height (H)
- Cross-mission comparative composites with +/- 1 sigma envelopes
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from .. import __version__
from ..core.models import BodyInfo, ObservationProfile
from ..core.registry import get_body
from .uncertainty import error_correlation_from_scatter


# Vertical derivatives (lapse rate, N^2, d(theta)/dz) are central differences over at
# least +-this distance (100 m resolution), however finely a profile is sampled.
MIN_DERIVATIVE_HALF_WINDOW_KM = 0.05


def _gradient_nan_safe(z_km: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Compute dv/dz robustly handling non-finite values and non-monotonic or duplicate altitudes."""
    z = np.asarray(z_km, dtype=np.float64)
    val = np.asarray(v, dtype=np.float64)
    out = np.full(val.shape, np.nan, dtype=np.float64)
    ok = np.isfinite(z) & np.isfinite(val)
    if ok.sum() < 2:
        return out

    # Samples at the same altitude are averaged (descending probes and entry data
    # repeat altitudes); the derivative is taken on the unique, increasing altitudes.
    zu, inv = np.unique(z[ok], return_inverse=True)
    vu = np.bincount(inv, weights=val[ok]) / np.bincount(inv)
    if zu.size < 2:
        return out
    # Central difference over the neighbouring levels, but never over less than +-50 m:
    # dense data (entry accelerometers every few metres, a lander's altitude jitter after
    # touchdown) would otherwise turn sample noise into huge gradients.  On an even,
    # coarser grid this is exactly the ordinary central difference.  Near the ends the
    # window is one-sided.
    half = np.empty_like(zu)
    half[1:-1] = (zu[2:] - zu[:-2]) / 2.0
    half[0], half[-1] = zu[1] - zu[0], zu[-1] - zu[-2]
    half = np.maximum(half, MIN_DERIVATIVE_HALF_WINDOW_KM)
    lo = np.maximum(zu - half, zu[0])
    hi = np.minimum(zu + half, zu[-1])
    grad_u = (np.interp(hi, zu, vu) - np.interp(lo, zu, vu)) / (hi - lo)
    out[ok] = grad_u[inv]
    return out


def gravity_profile(body: BodyInfo, z_km: np.ndarray, latitude_deg: Optional[float] = None,
                    altitude_reference: str = "") -> Tuple[np.ndarray, str]:
    """Gravity (m/s^2) at the altitudes of a profile, and a description of the model.

    Spherical bodies: g0 (R / (R + z))^2.  Rotating oblate planets with a gravity field
    in the registry (Jupiter, Saturn), at a known latitude: the magnitude of the
    effective gravity (gravitation with J2, minus the centrifugal acceleration),
        g_r = GM/r^2 [1 - 3 J2 (a/r)^2 P2(sin phi)] - w^2 r cos^2 phi
        g_t = 3 GM J2 a^2 / r^4 sin phi cos phi + w^2 r sin phi cos phi
    with r the 1-bar ellipsoid radius at planetocentric latitude phi plus the altitude
    (or the reference sphere plus the altitude, for altitudes taken from a radius).
    That is 23.1 m/s^2 at Jupiter's equator and 26.9 at its poles (one constant 24.79
    before), 9.0 and 12.1 on Saturn (10.44).
    """
    z = np.asarray(z_km, dtype=np.float64)
    lat = None if latitude_deg is None else float(latitude_deg)
    if body.gm_km3_s2 and body.rotation_period_h and body.equatorial_radius_km and lat is not None \
            and np.isfinite(lat):
        phi = np.radians(lat)
        s, c = np.sin(phi), np.cos(phi)
        a, b = body.equatorial_radius_km, body.polar_radius_km or body.equatorial_radius_km
        from_radius = (altitude_reference or "").startswith("a sphere of radius")
        r0 = body.radius_km if from_radius else a * b / np.hypot(b * c, a * s)
        r = np.maximum(r0 + z, 0.5 * b) * 1e3                       # m
        gm = body.gm_km3_s2 * 1e9                                     # m^3/s^2
        aj = (body.j2_reference_radius_km or a) * 1e3
        w2 = (2.0 * np.pi / (body.rotation_period_h * 3600.0)) ** 2
        p2 = 1.5 * s * s - 0.5
        g_r = gm / r ** 2 * (1.0 - 3.0 * body.j2 * (aj / r) ** 2 * p2) - w2 * r * c * c
        g_t = 3.0 * gm * body.j2 * aj ** 2 / r ** 4 * s * c + w2 * r * s * c
        return np.hypot(g_r, g_t), (f"effective gravity at {lat:.1f} deg latitude "
                                    f"(J2 {body.j2:.6g}, rotation {body.rotation_period_h:g} h)")
    r_body = body.radius_km
    # (altitudes below the reference level, e.g. the Hellas basin below the Mars reference sphere or the
    # Galileo probe below 1 bar, are valid: gravity is slightly larger there)
    g = body.surface_gravity * (r_body / np.maximum(r_body + z, 1e-3 * r_body)) ** 2
    return g, f"g0 (R/(R+z))^2, g0 = {body.surface_gravity:g} m/s^2, R = {r_body:g} km"


def hydrostatic_geopotential(profile: ObservationProfile, g) -> Optional[np.ndarray]:
    """The geopotential (m^2/s^2) the archive gives at each level of the profile, for the
    hydrostatic integrals (hydrostatic.py: d Phi instead of g dz), or None.  Read only for
    data sets whose pressures are integrated in it (Dataset.hydrostatic_in_geopotential:
    the MGS and MRO radio occultations).  None where it is missing at a level that has an
    altitude, or where its vertical gradient is not within 10 % of the profile's gravity
    ``g`` (a unit VEDA would misread)."""
    phi = (profile.track or {}).get("geopotential")
    z = np.asarray(profile.altitude_km, dtype=float)
    if phi is None or np.shape(phi) != z.shape:
        return None
    phi = np.asarray(phi, dtype=float)
    have = np.isfinite(z)
    if have.sum() < 3 or not np.isfinite(phi[have]).all():
        return None
    o = np.argsort(z[have], kind="stable")
    zz, pp = z[have][o] * 1000.0, phi[have][o]
    gg = np.broadcast_to(np.asarray(g, dtype=float), z.shape)[have][o]
    dz = np.diff(zz)
    step = dz > 0
    if step.sum() < 2:
        return None
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.nanmedian((np.diff(pp)[step] / dz[step]) / (0.5 * (gg[1:] + gg[:-1]))[step])
    return phi if 0.9 <= ratio <= 1.1 else None


def compute_atmospheric_diagnostics(
    profile: ObservationProfile,
    body: Optional[BodyInfo] = None,
) -> Dict[str, np.ndarray]:
    """Compute full suite of thermodynamic derived quantities for a profile, and their
    1-sigma uncertainties from the archived ones (uncertainty.py, into profile.uncertainty)."""
    if body is None:
        body = get_body(profile.body_id)
    if body is None:
        return {}
    derived = _diagnostics(profile, body)
    if derived:
        try:
            from .uncertainty import propagate
            z = np.asarray(profile.altitude_km, dtype=float)
            gz, _ = gravity_profile(body, z, profile.latitude,
                                    (profile.raw_attributes or {}).get("ALTITUDE_REFERENCE", ""))
            propagate(profile, body, derived, gz, _correlation_km(profile))
        except Exception:                     # uncertainties are extra; never lose the values
            pass
    if profile.alternatives:
        try:
            _systematic(profile, body, derived)
        except Exception:                     # as above
            pass
    return derived


def _systematic(profile: ObservationProfile, body: BodyInfo, derived: Dict[str, np.ndarray]) -> None:
    """Systematic uncertainty of the measured and derived quantities: half the difference
    between the values from the two alternative retrievals (``profile.alternatives``, e.g.
    radio occultation profiles integrated down from a low and a high temperature at the
    top), each derived quantity recomputed from both.  Kept in ``profile.systematic``,
    apart from the random 1-sigma."""
    import copy
    z = np.asarray(profile.altitude_km, dtype=float)
    sides = []
    for i in (0, 1):
        alt = copy.copy(profile)
        alt.raw_attributes = dict(profile.raw_attributes or {})
        alt.derived = {k: v for k, v in profile.derived.items()
                       if k in ("number_density_m3", "density_measured", "molar_mass")}
        alt.uncertainty, alt.systematic, alt.alternatives = {}, {}, {}
        for key, pair in profile.alternatives.items():
            v = np.asarray(pair[i], dtype=float)
            if v.shape != z.shape:
                return
            setattr(alt, key, v)
            if key == "temperature_k":
                alt.temperature_c = v - 273.15
        values = dict(alt.derived)
        values.update(_diagnostics(alt, body))
        values.update({k: getattr(alt, k) for k in profile.alternatives})
        sides.append(values)
    out: Dict[str, np.ndarray] = {}
    for key in list(profile.alternatives) + list(derived):
        a, b = sides[0].get(key), sides[1].get(key)
        if a is None or b is None or np.shape(a) != z.shape or np.shape(b) != z.shape:
            continue
        with np.errstate(invalid="ignore"):
            half = np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) / 2.0
        if np.any(np.isfinite(half) & (half > 0)):
            out[key] = half
    if "temperature_k" in out:
        out["temperature_c"] = out["temperature_k"]
    profile.systematic.update(out)


def _correlation_km(profile: ObservationProfile) -> float:
    """Vertical correlation length of the archived errors, where the data set gives one."""
    ds_id = (profile.raw_attributes or {}).get("DATASET_ID")
    if not ds_id:
        return 0.0
    from ..archives.datasets import get_dataset
    ds = get_dataset(ds_id)
    return float(getattr(ds, "uncertainty_correlation_km", 0.0) or 0.0) if ds else 0.0


def _interpolated_sigma(z_grid: np.ndarray, z: np.ndarray, s: np.ndarray, corr_km: float) -> np.ndarray:
    """1-sigma of a value interpolated linearly between levels a and b (weights 1 - w, w):
    sqrt((1-w)^2 s_a^2 + w^2 s_b^2 + 2 w (1-w) r s_a s_b), r = exp(-dz^2 / (2 L^2)) the
    correlation of the two levels' errors (0 when independent, L = 0).  Interpolating
    the sigmas themselves took the errors as fully correlated (r = 1), up to 1.41 times
    too large midway between independent levels."""
    out = np.full(np.shape(z_grid), np.nan)
    if z.size == 0:
        return out
    if z.size == 1:
        out[np.asarray(z_grid) == z[0]] = s[0]
        return out
    zg = np.asarray(z_grid, dtype=float)
    inside = (zg >= z[0]) & (zg <= z[-1])
    k = np.clip(np.searchsorted(z, zg[inside], side="right") - 1, 0, z.size - 2)
    dz = z[k + 1] - z[k]
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(dz > 0, (zg[inside] - z[k]) / dz, 0.0)
    r = np.exp(-dz ** 2 / (2.0 * corr_km ** 2)) if corr_km > 0 else np.zeros_like(dz)
    sa, sb = s[k], s[k + 1]
    out[inside] = np.sqrt(np.maximum((1 - w) ** 2 * sa ** 2 + w ** 2 * sb ** 2 + 2 * w * (1 - w) * r * sa * sb, 0.0))
    return out


def _grid_error_correlation_km(corr_levels_km: float, z_levels: np.ndarray) -> float:
    """Length L (km) of a Gaussian correlation exp(-dz^2 / (2 L^2)) between the errors of
    a profile's values on a comparison grid: that of the errors at its levels and that
    made by interpolating between them, L = sqrt(L_levels^2 + dz_levels^2 / 3) (the
    variance-matched width of the linear interpolation kernel).  Used for the 1-sigma of a
    layer mean; on real Mars Express profiles it gives that of the exact propagation
    (A C A^T, A the interpolation weights) within 15 % on 0.1-1 km grids and 2-10 km
    layers, where treating the grid values as independent gave 0.2-1 times it."""
    dz = np.diff(np.asarray(z_levels, dtype=float))
    dz = dz[np.isfinite(dz) & (dz > 0)]
    spacing = float(np.median(dz)) if dz.size else 0.0
    return round(float(np.hypot(corr_levels_km, spacing / np.sqrt(3.0))), 4)


def _diagnostics(profile: ObservationProfile, body: BodyInfo) -> Dict[str, np.ndarray]:
    derived: Dict[str, np.ndarray] = {}
    z = profile.altitude_km
    if z is None or z.size < 2:
        return derived
    _ionosphere_diagnostics(profile, z)
    _hydrostatic_temperature(profile, body, z, derived)

    t_k = profile.temperature_k
    if t_k is None and profile.temperature_c is not None:
        t_k = profile.temperature_c + 273.15
        profile.temperature_k = t_k
    elif profile.temperature_c is None and t_k is not None:
        profile.temperature_c = t_k - 273.15

    if t_k is None:
        return derived

    # 1. Environmental Lapse Rate (-dT/dz) in K/km
    dtdz = _gradient_nan_safe(z, t_k)
    lapse_rate = -dtdz
    derived["lapse_rate"] = lapse_rate

    # 2. Local gravitational acceleration: g(z) = g0 (R / (R + z))^2, or on Jupiter and
    # Saturn the effective gravity at the profile's latitude (J2 and rotation)
    gz, profile.raw_attributes["gravity_model"] = gravity_profile(
        body, z, profile.latitude, (profile.raw_attributes or {}).get("ALTITUDE_REFERENCE", ""))
    phi = hydrostatic_geopotential(profile, gz)
    if phi is not None:
        profile.raw_attributes["gravity_model"] += "; hydrostatic integrals in the archive's geopotential"

    # 3. Scale height H = Z R_spec T / g(z) (km) and speed of sound with cp(T); Z the
    # compressibility, 1 but in Titan's dense cold troposphere (realgas.py)
    from .realgas import compressibility
    from .thermo import cp_model, heat_capacity
    r_spec = gas_constant_levels(profile, body)       # per level where the archive gives the molar mass
    cp_t = heat_capacity(body, t_k)                 # J/(kg K), temperature dependent for CO2/N2 atmospheres
    profile.raw_attributes["cp_model"] = cp_model(body)
    p_now = profile.pressure_hpa
    z_c = compressibility(body, t_k, p_now) if p_now is not None and np.shape(p_now) == z.shape else None
    zc = 1.0 if z_c is None else np.where(np.isfinite(z_c), z_c, 1.0)
    if z_c is not None and np.isfinite(z_c).any():
        k_low = int(np.nanargmin(np.where(np.isfinite(z_c), z, np.inf)))
        profile.raw_attributes["equation_of_state"] = (
            f"real gas, second virial coefficient of the N2-CH4 mixture (Z = {z_c[k_low]:.4f} at {z[k_low]:.1f} km)")
    with np.errstate(invalid="ignore", divide="ignore"):
        h_scale = (zc * r_spec * t_k) / (gz * 1000.0)
        gamma = np.where(cp_t > r_spec, cp_t / (cp_t - r_spec), np.nan)
        cs = np.sqrt(gamma * r_spec * t_k)
    derived["scale_height"] = h_scale
    derived["speed_of_sound"] = cs

    # 4. Static stability, from temperature alone:
    #    N^2 = (g / T) (dT/dz + g / cp(T)),  dry adiabatic lapse rate Gamma_d = g / cp(T)
    #    (z in km, so dT/dz in K/km is divided by 1000; g in m/s^2; cp in J/(kg K))
    dtdz_m = dtdz / 1000.0
    with np.errstate(invalid="ignore", divide="ignore"):
        gamma_d = gz / cp_t                          # K/m
        n2 = (gz / t_k) * (dtdz_m + gamma_d)
        tau_b = np.where(n2 > 0, (2.0 * np.pi / np.sqrt(n2)) / 60.0, np.nan)
    derived["dry_adiabatic_lapse_rate"] = gamma_d * 1000.0      # K/km
    derived["buoyancy_freq_sq"] = n2
    derived["buoyancy_period"] = tau_b

    # 5. Pressure-based quantities
    p_hpa = profile.pressure_hpa
    if p_hpa is not None and p_hpa.size == z.size:
        # Potential temperature with the conventional constant kappa = R / cp_ref, cp_ref
        # being cp at the body's reference temperature (registry value); referenced to
        # the body's reference pressure (e.g. 1 bar for the giant planets, 6.1 hPa for Mars).
        kappa = r_spec / body.isobaric_heat_capacity_cp
        p_ref = body.reference_pressure_hpa

        with np.errstate(invalid="ignore", divide="ignore"):
            theta = t_k * (p_ref / np.where(p_hpa > 0, p_hpa, np.nan)) ** kappa
            # Mass density rho = P / (Z R T) in kg/m^3 (P in Pa = hPa * 100)
            rho = (p_hpa * 100.0) / (zc * r_spec * t_k)

        derived["potential_temperature"] = theta
        derived["dtheta_dz"] = _gradient_nan_safe(z, theta)
        derived["density"] = rho

        # How well the archived pressure, temperature and altitudes fit hydrostatic balance
        from .hydrostatic import hydrostatic_consistency
        profile.raw_attributes.update(hydrostatic_consistency(z, p_hpa, t_k, gz, zc * r_spec, phi))

        # CO2 atmospheres (Mars, Venus): the CO2 frost point and how close T comes to it
        from .condensation import co2_condensation_temperature, co2_volume_fraction
        x_co2 = co2_volume_fraction(body)
        if x_co2:
            t_co2 = co2_condensation_temperature(p_hpa, x_co2)
            margin = t_k - t_co2
            if np.isfinite(margin).any():
                derived["co2_condensation_temperature"] = t_co2
                derived["t_minus_co2_condensation"] = margin
                k = int(np.nanargmin(margin))
                profile.raw_attributes["co2_margin_min_k"] = round(float(margin[k]), 2)
                profile.raw_attributes["co2_margin_min_km"] = round(float(z[k]), 2)

    # 6. Cold-point tropopause (where the body has one) and gravity waves
    try:
        from .wave_and_stability import extract_gravity_wave_activity, tropopause_for_body
        profile.raw_attributes.update(tropopause_for_body(body.id, z, t_k, p_hpa))

        gw = extract_gravity_wave_activity(z, t_k, gz, derived.get("buoyancy_freq_sq"), cp_j_kg_k=cp_t)
        if gw.get("t_prime_k"):
            derived["t_prime"] = np.array([np.nan if x is None else x for x in gw["t_prime_k"]])
            derived["wave_potential_energy"] = np.array([np.nan if x is None else x for x in gw["potential_energy_j_kg"]])
            profile.raw_attributes["gw_mean_ep_j_kg"] = gw.get("mean_potential_energy")
            profile.raw_attributes["gw_dominant_wavelength_km"] = gw.get("dominant_wavelength_km")
    except Exception:
        pass

    return derived


K_BOLTZMANN = 1.380649e-23          # J/K


def _hydrostatic_temperature(profile: ObservationProfile, body: BodyInfo, z: np.ndarray,
                             derived: Dict[str, np.ndarray]) -> None:
    """Temperature and pressure from a measured mass density profile (or a total number
    density, rho = n k_B / R_spec) by downward hydrostatic integration (hydrostatic.py),
    as for accelerometer and occultation densities; the fitted top temperature and the
    top altitude go into the profile's attributes."""
    rho = profile.derived.get("density_measured")
    sigma = (profile.uncertainty or {}).get("density_measured")
    if rho is None and profile.derived.get("number_density_m3") is not None:
        r_gas = density_gas_constant(profile, body)
        rho = np.asarray(profile.derived["number_density_m3"], dtype=float) * K_BOLTZMANN / r_gas
        s = (profile.uncertainty or {}).get("number_density_m3")
        sigma = None if s is None else np.asarray(s, dtype=float) * K_BOLTZMANN / r_gas
    if rho is None or np.shape(rho) != np.shape(z):
        return
    if sigma is not None and np.shape(sigma) != np.shape(z):
        sigma = None
    r = _hydrostatic_retrieval(profile, body, z, rho, sigma)
    if r is None:
        return
    from .realgas import REAL_GAS_BODIES, temperature_with_compressibility
    if body.id in REAL_GAS_BODIES:
        # p = Z(T, p) rho R T: Titan's troposphere is 4 % denser than an ideal gas at its T and p
        r["temperature_k"] = temperature_with_compressibility(body, r["pressure_pa"], rho, density_gas_constant(profile, body))
    derived["temperature_from_density"] = r["temperature_k"]
    derived["pressure_from_density"] = r["pressure_pa"] / 100.0
    profile.raw_attributes["hydrostatic_top_temperature_k"] = round(r["top_temperature_k"], 2)
    profile.raw_attributes["hydrostatic_top_km"] = round(r["top_km"], 2)


def gas_constant_levels(profile: ObservationProfile, body: BodyInfo):
    """Specific gas constant (J/(kg K)) of the atmosphere at the profile's levels: from the
    mean molar mass the archive gives at each level (``derived["molar_mass"]``, g/mol;
    SOIR: falling from 43.4 g/mol below 120 km to about 20 at 175 km as CO2 gives way to O
    and CO), where it gives one, otherwise the body's bulk value."""
    mu = (profile.derived or {}).get("molar_mass")
    z = np.asarray(profile.altitude_km, dtype=float)
    if mu is None or np.shape(mu) != z.shape:
        return body.gas_constant_r
    mu = np.asarray(mu, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(mu) & (mu > 0), 8314.46 / mu, body.gas_constant_r)


def density_gas_constant(profile: ObservationProfile, body: BodyInfo):
    """Specific gas constant (J/(kg K)) for the hydrostatic retrieval from the profile's
    density: the archive's mean molar mass per level where it gives one
    (gas_constant_levels), else that of the one gas the density is of, where the data
    set says so (DENSITY_MOLAR_MASS; Cassini UVIS: molecular hydrogen in Saturn's
    thermosphere, where the bulk molar mass 2.30 g/mol made the temperatures 14 % too high),
    else the body's mean one."""
    if (profile.derived or {}).get("molar_mass") is not None:
        return gas_constant_levels(profile, body)
    mu = (profile.raw_attributes or {}).get("DENSITY_MOLAR_MASS")
    try:
        mu = float(mu)
    except (TypeError, ValueError):
        return body.gas_constant_r
    return 8314.46 / mu if mu > 0 else body.gas_constant_r


def _hydrostatic_retrieval(profile: ObservationProfile, body: BodyInfo, z: np.ndarray, rho: np.ndarray,
                           sigma: Optional[np.ndarray]) -> Optional[Dict[str, Any]]:
    """temperature_from_density at the profile's gravity, or None when it gives nothing."""
    from .hydrostatic import temperature_from_density
    g, _ = gravity_profile(body, z, profile.latitude, (profile.raw_attributes or {}).get("ALTITUDE_REFERENCE", ""))
    r = temperature_from_density(z, rho, g, density_gas_constant(profile, body), rho_sigma=sigma,
                                 phi=hydrostatic_geopotential(profile, g))
    return None if r["top_temperature_k"] is None else r


def _ionosphere_diagnostics(profile: ObservationProfile, z: np.ndarray) -> None:
    """Total electron content, density peak and Chapman fit of an electron density profile.

    Independent of temperature: most ionospheric occultations have none.
    """
    ne = profile.electron_density_cm3
    if ne is None or ne.size != z.size or ne.size < 2:
        return
    try:
        from .advanced_science import compute_vtec
        vtec_res = compute_vtec(z, ne)
        profile.raw_attributes["vtec_tecu"] = vtec_res.get("vtec_tecu")
        profile.raw_attributes["hmf2_km"] = vtec_res.get("peak_alt_km")
        profile.raw_attributes["nmf2_cm3"] = vtec_res.get("peak_density_cm3")
        if ne.size >= 8:
            from .wave_and_stability import fit_chapman_ionosphere
            profile.raw_attributes["chapman_fit"] = fit_chapman_ionosphere(z, ne)
    except Exception:
        pass


def _finite(x: Any) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return float(f"{x:.6g}") if np.isfinite(x) else None


# Per-profile scalar diagnostics offered in comparisons (altitude cut, CSV export):
# key -> (label, unit)
# key: (label, unit) or (label, unit, what the values mean); the unit is added to the label
# in parentheses, so labels have none of their own
PROFILE_DIAGNOSTICS: Dict[str, Tuple[str, ...]] = {
    "cpt_alt_km": ("Cold-point tropopause altitude", "km"),
    "cpt_temp_k": ("Cold-point tropopause temperature", "K"),
    "cpt_pressure_hpa": ("Cold-point tropopause pressure", "hPa"),
    "ne_peak_cm3": ("Peak electron density", "cm^-3"),
    "ne_peak_alt_km": ("Altitude of the electron density peak", "km"),
    "chapman_nm_cm3": ("Chapman fit peak density", "cm^-3"),
    "chapman_hm_km": ("Chapman fit peak altitude", "km"),
    "chapman_h_km": ("Chapman fit scale height", "km"),
    "chapman_r2": ("Chapman fit R^2", ""),
    "tec_tecu": ("Electron content of the profile", "TECU"),
    "gw_mean_ep_j_kg": ("Mean gravity-wave potential energy", "J/kg"),
    "gw_wavelength_km": ("Dominant vertical wavelength", "km"),
    "hydrostatic_max_pct": ("Largest departure of the pressure from hydrostatic balance", "%"),
    "hydrostatic_median_pct": ("Median departure of the pressure from hydrostatic balance", "%"),
    "hydrostatic_max_km": ("Altitude of the largest departure from hydrostatic balance", "km"),
    "hydrostatic_noise_median_pct": ("Median departure expected from the profile's errors alone", "%"),
    "hydrostatic_noise_max_pct": ("Largest departure expected from the errors alone, 95th percentile", "%"),
    "hydrostatic_top_temperature_k": ("Top temperature of the hydrostatic retrieval from density", "K"),
    "co2_margin_min_k": ("Smallest T minus CO₂ frost point", "K",
                         "Below 0 K the temperature is under the CO₂ frost point somewhere in the profile: "
                         "CO₂ can condense there (supersaturated)."),
    "co2_margin_min_km": ("Altitude of the smallest T minus CO₂ frost point", "km"),
    "co2_margin_min_sigma_k": ("1-sigma of the smallest T minus CO₂ frost point", "K"),
}


def profile_diagnostics(profile: ObservationProfile) -> Dict[str, Optional[float]]:
    """The scalar diagnostics of one profile (see PROFILE_DIAGNOSTICS), None where absent."""
    a = profile.raw_attributes or {}
    chap = a.get("chapman_fit") if isinstance(a.get("chapman_fit"), dict) else {}
    ep = _finite(a.get("gw_mean_ep_j_kg"))
    out = {
        "cpt_alt_km": _finite(a.get("cpt_alt_km")),
        "cpt_temp_k": _finite(a.get("cpt_temp_k")),
        "cpt_pressure_hpa": _finite(a.get("cpt_pressure_hpa")),
        "ne_peak_cm3": _finite(a.get("nmf2_cm3")),
        "ne_peak_alt_km": _finite(a.get("hmf2_km")),
        "chapman_nm_cm3": _finite(chap.get("nmf2_cm3")),
        "chapman_hm_km": _finite(chap.get("hmf2_km")),
        "chapman_h_km": _finite(chap.get("scale_height_km")),
        "chapman_r2": _finite(chap.get("r_squared")),
        "tec_tecu": _finite(a.get("vtec_tecu")),
        "gw_mean_ep_j_kg": ep if ep else None,          # 0.0 means "not computed"
        "gw_wavelength_km": _finite(a.get("gw_dominant_wavelength_km")),
        "hydrostatic_max_pct": _finite(a.get("hydrostatic_max_pct")),
        "hydrostatic_median_pct": _finite(a.get("hydrostatic_median_pct")),
        "hydrostatic_max_km": _finite(a.get("hydrostatic_max_km")),
        "hydrostatic_noise_median_pct": _finite(a.get("hydrostatic_noise_median_pct")),
        "hydrostatic_noise_max_pct": _finite(a.get("hydrostatic_noise_max_pct")),
        "hydrostatic_top_temperature_k": _finite(a.get("hydrostatic_top_temperature_k")),
        "co2_margin_min_k": _finite(a.get("co2_margin_min_k")),
        "co2_margin_min_km": _finite(a.get("co2_margin_min_km")),
        "co2_margin_min_sigma_k": _finite(a.get("co2_margin_min_sigma_k")),
    }
    return out


def _empty_comparison(body: BodyInfo, variable_name: str, grid_km: Optional[List[float]] = None) -> Dict[str, Any]:
    """Comparison result with no usable profiles; same keys as a full result."""
    return {
        "body_id": body.id,
        "body_name": body.name,
        "variable_name": variable_name,
        "grid_km": grid_km or [],
        "composite_mean": [],
        "composite_std": [],
        "composite_plus_1sigma": [],
        "composite_minus_1sigma": [],
        "profile_count": 0,
        "profiles": [],
    }


def _vertical_reference_warning(summaries: List[Dict[str, Any]]) -> str:
    """A note when the compared profiles measure altitude from different references
    (a sphere around the body centre, the 1-bar level, a landing site)."""
    kinds = {}
    for s in summaries:
        ref = s.get("altitude_reference")
        if not ref:
            continue                      # unknown (user files): no claim either way
        kind = "the body's reference sphere" if ref.startswith("a sphere of radius") else ref
        kinds.setdefault(kind, set()).add(s["mission_id"])
    if len(kinds) < 2:
        return ""
    parts = "; ".join(f"{', '.join(sorted(m)).upper()}: {k}" for k, m in kinds.items())
    return f"Altitudes are measured from different references ({parts}), so they are offset from each other."


def _geom(p) -> Dict[str, Any]:
    from ..missions.selection import profile_geometry
    return profile_geometry(p)


GROUPINGS = ("latitude", "lst", "sza", "ls", "year", "month", "month_of_year", "mission")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _group_key(s: Dict[str, Any], by: str, width: float):
    """(sort key, label) of a profile's group, or None when the profile lacks the quantity."""
    if by in ("latitude", "lst", "sza", "ls"):
        v = s.get(by)
        if v is None or not np.isfinite(v):
            return None
        w = width or {"latitude": 30.0, "lst": 3.0, "sza": 30.0, "ls": 30.0}[by]
        lo = np.floor(v / w) * w
        unit = {"latitude": "°", "lst": " h", "sza": "°", "ls": "°"}[by]
        name = {"latitude": "Latitude", "lst": "Local time", "sza": "SZA", "ls": "Ls"}[by]
        return lo, f"{name} {lo:g} to {lo + w:g}{unit}"
    t = s.get("time_utc") or ""
    if by == "year":
        return (t[:4], t[:4]) if len(t) >= 4 else None
    if by == "month":
        return (t[:7], t[:7]) if len(t) >= 7 else None
    if by == "month_of_year":                           # calendar month on Earth, all years together (not a planetary season)
        return (int(t[5:7]), _MONTHS[int(t[5:7]) - 1]) if len(t) >= 7 and t[5:7].isdigit() else None
    if by == "mission":
        m = (s.get("mission_label") or s.get("mission_id") or "").upper()
        return (m, m) if m else None
    return None


# inverse_variance: weights 1/sigma^2 from the random 1-sigma; inverse_variance_total:
# 1/(sigma^2 + s^2) with the systematic uncertainty s added where the profile has one (across
# profiles their boundary temperatures are independent, so s acts as a random error of the
# composite).  Both need the random 1-sigma: a profile with only a systematic uncertainty
# (Akatsuki, Pioneer Venus) has an incomplete error budget, and weighting it by s alone,
# below 0.1 K at Akatsuki's lower levels, would let it outweigh every other profile.
WEIGHTINGS = ("equal", "inverse_variance", "inverse_variance_total")

MAX_CROSS_SECTION_CELLS = 400000


def _reference_series(body: BodyInfo, variable_name: str, z_grid: np.ndarray, by_pressure: bool) -> Optional[Dict[str, Any]]:
    """The body's reference atmosphere (analysis/reference.py) on the comparison grid."""
    from .reference import reference_info, reference_on_pressure, reference_profile
    info = reference_info(body.id)
    if info is None:
        return None
    v = (reference_on_pressure(body.id, variable_name, 10.0 ** -z_grid, body) if by_pressure
         else reference_profile(body.id, variable_name, z_grid, body))
    if v is None:
        return {**info, "series": None, "note": f"The reference atmosphere has no {variable_name}."}
    return {**info, "series": [None if not np.isfinite(x) else float(f"{x:.6g}") for x in v]}


def uncertainty_budget(mat: np.ndarray, rand_s: np.ndarray, sys_s: np.ndarray,
                       weighting: str = "equal") -> Dict[str, np.ndarray]:
    """What makes up the spread of the compared profiles and the uncertainty of their mean,
    at each level of ``mat`` (profiles x levels, in log space for log-averaged variables,
    whose 1-sigma ``rand_s`` and systematic uncertainty ``sys_s`` are then relative).

    Over the values that have a random 1-sigma at a level, with errors independent of the
    atmosphere and between profiles,

        spread^2 = variability^2 + <sigma^2>,

    spread the sample standard deviation of those values: the natural variability between
    the profiles is sqrt(max(0, spread^2 - <sigma^2>)), and random_fraction = <sigma^2> /
    spread^2 the share of the variance the random errors explain (above 1: the archived
    errors are larger than the scatter they would cause).  The random error of the mean is
    sqrt(sum sigma^2) / n (inverse-variance weights: 1 / sqrt(sum 1/sigma^2)).  The
    systematic uncertainty s (the boundary temperature of radio occultation retrievals) of
    the mean is sqrt(sum s^2) / n where it is independent between profiles (each retrieval
    starts from its own unknown top temperature) and mean(s) where all of them share it."""
    import warnings
    out: Dict[str, np.ndarray] = {}
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        has = np.isfinite(mat) & np.isfinite(rand_s) & (rand_s > 1e-6 * np.maximum(np.abs(mat), 1e-300))
        n = has.sum(axis=0)
        x = np.where(has, mat, np.nan)
        spread = np.where(n >= 2, np.nanstd(x, axis=0, ddof=1), np.nan)
        s2 = np.where(has, rand_s, np.nan) ** 2
        noise2 = np.where(n >= 2, np.nanmean(s2, axis=0), np.nan)
        out["profiles_with_sigma"] = n.astype(float)
        out["spread"] = spread
        out["random_rms"] = np.sqrt(noise2)
        out["variability"] = np.sqrt(np.maximum(spread ** 2 - noise2, 0.0))
        out["random_fraction"] = noise2 / spread ** 2
        w = np.where(has, 1.0 / np.where(has, rand_s, 1.0) ** 2, 0.0)
        if weighting == "inverse_variance":
            out["mean_random"] = np.where(n >= 2, 1.0 / np.sqrt(w.sum(axis=0)), np.nan)
        else:
            out["mean_random"] = np.where(n >= 2, np.sqrt(np.nansum(s2, axis=0)) / n, np.nan)
        # systematic: over the values with a value there (weights as for the mean)
        hs = np.isfinite(mat) & np.isfinite(sys_s) & (sys_s > 0)
        ns = hs.sum(axis=0)
        sv = np.where(hs, sys_s, np.nan)
        out["systematic_rms"] = np.where(ns >= 1, np.sqrt(np.nanmean(sv ** 2, axis=0)), np.nan)
        if weighting == "inverse_variance":
            ww = np.where(hs & has, w, 0.0)
            sw = ww.sum(axis=0)
            out["mean_systematic_independent"] = np.where(sw > 0, np.sqrt(np.nansum(ww ** 2 * np.nan_to_num(sv) ** 2, axis=0)) / sw, np.nan)
            out["mean_systematic_correlated"] = np.where(sw > 0, np.nansum(ww * np.nan_to_num(sv), axis=0) / sw, np.nan)
        else:
            nall = np.isfinite(mat).sum(axis=0)
            out["mean_systematic_independent"] = np.where(ns >= 1, np.sqrt(np.nansum(sv ** 2, axis=0)) / nall, np.nan)
            out["mean_systematic_correlated"] = np.where(ns >= 1, np.nansum(sv, axis=0) / nall, np.nan)
    return out


def latitude_cross_section(mat: np.ndarray, smat: Optional[np.ndarray], latitudes: List[Optional[float]],
                           width: float, log_like: bool, weighting: str = "equal") -> Dict[str, Any]:
    """Zonal mean in latitude bands of ``width`` degrees (from -90) at each level of the
    grid: the (weighted) mean of the profiles whose latitude falls in the band, its
    standard error (spread / sqrt(n_eff), two or more profiles) and the number of profiles,
    as [band][level] lists; in log space for log-averaged variables (mean as values,
    standard error in percent).  Profiles without a latitude are left out (counted)."""
    edges = np.arange(-90.0, 90.0 + 1e-9, width)
    if edges[-1] < 90.0:
        edges = np.append(edges, 90.0)
    lat = np.array([np.nan if v is None else float(v) for v in latitudes])
    centers, means, sems, counts = [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        idx = np.where((lat >= lo) & ((lat < hi) | ((hi >= 90.0) & (lat <= hi))))[0]
        if not idx.size:
            continue
        st = _level_statistics(mat[idx], None if smat is None else smat[idx], weighting)
        m, e = st["mean"], st["sem"]
        ok = st["n"] >= 1
        val = np.exp(m) if log_like else m
        err = 100.0 * e if log_like else e
        centers.append(round(float((lo + hi) / 2), 4))
        means.append([None if not (o and np.isfinite(v)) else float(f"{v:.6g}") for v, o in zip(val, ok)])
        sems.append([None if not np.isfinite(v) else float(f"{v:.4g}") for v in err])
        counts.append([int(x) for x in st["n"]])
    return {"width": width, "edges": [float(x) for x in edges], "latitude_centers": centers, "mean": means,
            "sem": sems, "sem_unit": "%" if log_like else "", "profiles": counts,
            "without_latitude": int(np.sum(~np.isfinite(lat)))}


# Outlier screen: robust z per level needs at least this many profiles there, and a
# profile is flagged when |z| exceeds the threshold on at least this fraction of its levels
OUTLIER_MIN_PROFILES = 5
OUTLIER_LEVEL_FRACTION = 0.10


def screen_outliers(mat: np.ndarray, threshold: float) -> List[Dict[str, Any]]:
    """Robust z of every value against the other profiles at its level,
    z = 0.6745 (x - median) / MAD (MAD the median absolute deviation; 0.6745 makes it
    comparable to a standard score for normal data), at levels with at least
    OUTLIER_MIN_PROFILES values; ``mat`` is profiles x levels, in log space for
    log-averaged variables.  Per profile: the fraction of its screened levels with
    |z| > threshold, the largest |z|, and whether it is flagged (fraction at least
    OUTLIER_LEVEL_FRACTION)."""
    import warnings
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        n = np.sum(np.isfinite(mat), axis=0)
        med = np.nanmedian(mat, axis=0)
        mad = np.nanmedian(np.abs(mat - med), axis=0)
        z = 0.6745 * (mat - med) / mad
        z[:, (n < OUTLIER_MIN_PROFILES) | ~(mad > 0)] = np.nan
    out = []
    for row in z:
        ok = np.isfinite(row)
        if not ok.any():
            out.append({"flagged": False, "fraction": None, "max_abs_z": None})
            continue
        frac = float(np.mean(np.abs(row[ok]) > threshold))
        out.append({"flagged": frac >= OUTLIER_LEVEL_FRACTION, "fraction": round(frac, 3),
                    "max_abs_z": round(float(np.max(np.abs(row[ok]))), 2)})
    return out


def _level_statistics(mat: np.ndarray, smat: Optional[np.ndarray], weighting: str) -> Dict[str, np.ndarray]:
    """Mean, spread, standard error of the mean and effective number of profiles at each
    level of ``mat`` (profiles x levels, already in log space for log-averaged variables;
    ``smat`` the 1-sigma of each value in the same space, or None).

    Equal weights: mean, sample standard deviation s, n_eff = n, SEM = s / sqrt(n).
    Inverse variance: w = 1 / sigma^2 for the values that have an uncertainty (the others,
    and uncertainties under a millionth of the value, are left out at that level), mean = sum(w x) / sum(w), spread
    s^2 = sum(w (x - mean)^2) / (V1 - V2 / V1) with V1 = sum(w), V2 = sum(w^2), effective
    number n_eff = V1^2 / V2 (Kish) and SEM = s / sqrt(n_eff).  The SEM includes the
    natural variability between profiles, not only their measurement errors."""
    import warnings
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if weighting == "inverse_variance" and smat is not None:
            # an uncertainty under a millionth of the value is no uncertainty (archives write
            # 0 or 1e-13 for values they assume, such as a retrieval's boundary temperature)
            usable = np.isfinite(mat) & np.isfinite(smat) & (smat > 1e-6 * np.maximum(np.abs(mat), 1e-300))
            w = np.where(usable, 1.0 / np.where(usable, smat, 1.0) ** 2, 0.0)
            x = np.where(w > 0, mat, 0.0)
            n = np.sum(w > 0, axis=0)
            v1, v2 = np.sum(w, axis=0), np.sum(w * w, axis=0)
            mean = np.where(v1 > 0, np.sum(w * x, axis=0) / v1, np.nan)
            var = np.sum(w * (x - mean) ** 2, axis=0) / (v1 - v2 / v1)
            std = np.where(n >= 2, np.sqrt(var), np.nan)
            n_eff = np.where(v2 > 0, v1 * v1 / v2, 0.0)
        else:
            n = np.sum(np.isfinite(mat), axis=0)
            mean = np.nanmean(mat, axis=0)
            std = np.nanstd(mat, axis=0, ddof=1) if mat.shape[0] > 1 else np.full(mat.shape[1], np.nan)
            std = np.where(n >= 2, std, np.nan)
            n_eff = n.astype(float)
        sem = std / np.sqrt(n_eff)
    lo, hi = _bootstrap_mean_interval(mat, smat if weighting == "inverse_variance" else None)
    return {"n": n, "mean": mean, "std": std, "sem": sem, "n_eff": n_eff, "ci_lo": lo, "ci_hi": hi}


BOOTSTRAP_DRAWS = 1000
_BOOTSTRAP_SEED = 20261006


def _bootstrap_mean_interval(mat: np.ndarray, smat: Optional[np.ndarray],
                             level: float = 0.95) -> Tuple[np.ndarray, np.ndarray]:
    """Percentile bootstrap interval of the (weighted) mean at each level: the profiles are
    resampled with replacement BOOTSTRAP_DRAWS times (fewer for very large comparisons,
    at least 200), the mean recomputed with the same weights, and the 2.5 and 97.5
    percentiles of the resampled means taken (NaN where fewer than half the resamples
    have a value, or with fewer than two profiles).  Unlike mean +- 2 SEM it needs no
    normal distribution of the profiles, so it shows skewed or bimodal samples."""
    import warnings
    n_prof, n_lev = mat.shape
    nan = np.full(n_lev, np.nan)
    if n_prof < 2:
        return nan, nan.copy()
    means, w = _bootstrap_means(mat, smat)
    draws = means.shape[0]
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        enough = np.isfinite(means).sum(axis=0) >= draws // 2
        a = 100.0 * (1.0 - level) / 2.0
        lo, hi = np.nanpercentile(means, [a, 100.0 - a], axis=0)
    two = np.sum(w > 0, axis=0) >= 2
    return np.where(enough & two, lo, np.nan), np.where(enough & two, hi, np.nan)


def _bootstrap_means(mat: np.ndarray, smat: Optional[np.ndarray], seed: int = _BOOTSTRAP_SEED,
                     draws: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """(draws x levels) means of the profiles resampled with replacement (the weights of
    _level_statistics), and the weights used."""
    n_prof, n_lev = mat.shape
    if draws is None:
        draws = int(max(200, min(BOOTSTRAP_DRAWS, 2e9 / max(1, n_prof * n_lev))))
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n_prof, np.full(n_prof, 1.0 / n_prof), size=draws).astype(float)
    finite = np.isfinite(mat)
    if smat is not None:
        usable = finite & np.isfinite(smat) & (smat > 1e-6 * np.maximum(np.abs(mat), 1e-300))
        w = np.where(usable, 1.0 / np.where(usable, smat, 1.0) ** 2, 0.0)
    else:
        w = finite.astype(float)
    x = np.where(w > 0, mat, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        den = counts @ w
        return np.where(den > 0, (counts @ (w * x)) / den, np.nan), w


def _group_differences(mat: np.ndarray, summaries: List[Dict[str, Any]], log_like: bool, by: str, width: float,
                       sig, smat: Optional[np.ndarray] = None, weighting: str = "equal",
                       level: float = 0.95) -> List[Dict[str, Any]]:
    """Each group's composite mean minus that of the first group, at every level, with the
    standard error sqrt(SEM_a^2 + SEM_b^2) and a percentile bootstrap interval (each group
    resampled on its own, the means recomputed with the same weights, their difference
    taken).  Only where both means are given (half of each group's profiles reach the
    level).  For log-averaged variables the difference is in percent of the first group's
    (geometric) mean."""
    import warnings
    keys = [_group_key(s, by, width) for s in summaries]
    order = sorted({k for k in keys if k is not None}, key=lambda k: k[0])
    if len(order) < 2:
        return []
    groups = []
    for gi, key in enumerate(order):
        idx = [i for i, k in enumerate(keys) if k == key]
        sm = None if smat is None else smat[idx]
        st = _level_statistics(mat[idx], sm, weighting)
        m = np.where(st["n"] >= max(1, int(np.ceil(0.5 * len(idx)))), st["mean"], np.nan)
        boot = _bootstrap_means(mat[idx], sm if weighting == "inverse_variance" else None,
                                seed=_BOOTSTRAP_SEED + 7919 * gi, draws=BOOTSTRAP_DRAWS)[0] if len(idx) >= 2 else None
        groups.append((key[1], m, st["sem"], boot, len(idx)))
    a_label, a_mean, a_sem, a_boot, _ = groups[0]
    out = []
    tr = (lambda d: 100.0 * (np.exp(d) - 1.0)) if log_like else (lambda d: d)
    q = 100.0 * (1.0 - level) / 2.0
    for label, m, sem, boot, n in groups[1:]:
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            d = m - a_mean
            se = np.sqrt(sem ** 2 + a_sem ** 2)
            lo = hi = np.full(d.shape, np.nan)
            if boot is not None and a_boot is not None:
                diffs = boot - a_boot
                ok = np.isfinite(diffs).sum(axis=0) >= diffs.shape[0] // 2
                lo, hi = np.nanpercentile(diffs, [q, 100.0 - q], axis=0)
                lo, hi = np.where(ok & np.isfinite(d), lo, np.nan), np.where(ok & np.isfinite(d), hi, np.nan)
        out.append({"label": f"{label} minus {a_label}", "group": label, "reference_group": a_label, "n": n,
                    "difference": [sig(x) for x in tr(d)],
                    # (log-averaged variables: the standard error of the log-ratio, as percent)
                    "se": [sig(x) for x in (100.0 * se if log_like else se)],
                    "ci95_low": [sig(x) for x in tr(lo)], "ci95_high": [sig(x) for x in tr(hi)],
                    "percent": bool(log_like)})
    return out


def _group_composites(mat: np.ndarray, summaries: List[Dict[str, Any]], log_like: bool, by: str,
                      width: float, sig, smat: Optional[np.ndarray] = None,
                      weighting: str = "equal") -> List[Dict[str, Any]]:
    """Composite mean and spread of each group of profiles (climatology bins).  Same rules
    as the overall composite: the spread where two or more of the group's profiles
    overlap, the mean where at least half of them (and at least one) do."""
    keys = [_group_key(s, by, width) for s in summaries]
    out = []
    for key in sorted({k for k in keys if k is not None}, key=lambda k: k[0]):
        idx = [i for i, k in enumerate(keys) if k == key]
        st = _level_statistics(mat[idx], None if smat is None else smat[idx], weighting)
        n, s, e = st["n"], st["std"], st["sem"]
        m = np.where(n >= max(1, int(np.ceil(0.5 * len(idx)))), st["mean"], np.nan)
        tr = np.exp if log_like else (lambda a: a)
        out.append({"label": key[1], "n": len(idx), "observation_ids": [summaries[i]["observation_id"] for i in idx],
                    "mean": [sig(x) for x in tr(m)], "plus_1sigma": [sig(x) for x in tr(m + s)],
                    "minus_1sigma": [sig(x) for x in tr(m - s)],
                    "plus_sem": [sig(x) for x in tr(m + e)], "minus_sem": [sig(x) for x in tr(m - e)],
                    "ci95_low": [sig(x) for x in tr(np.where(np.isfinite(m), st["ci_lo"], np.nan))],
                    "ci95_high": [sig(x) for x in tr(np.where(np.isfinite(m), st["ci_hi"], np.nan))],
                    "n_effective": [None if not np.isfinite(x) else round(float(x), 2) for x in st["n_eff"]],
                    "profiles_per_level": [int(x) for x in n]})
    unknown = sum(1 for k in keys if k is None)
    if unknown:
        out.append({"label": f"{unknown} profile{'s' if unknown > 1 else ''} without {by}", "n": unknown,
                    "observation_ids": [summaries[i]["observation_id"] for i, k in enumerate(keys) if k is None],
                    "mean": [], "plus_1sigma": [], "minus_1sigma": [], "profiles_per_level": [], "ungrouped": True})
    return out


# Most levels a comparison grid may have (a 0.01 km step over a 5000 km thermosphere
# profile would otherwise send hundreds of MB to the window)
MAX_GRID_LEVELS = 20000

# Variables compared in log space (they change by orders of magnitude with height)
LOG_VARIABLES = {"pressure_hpa", "density", "density_measured", "number_density_m3", "electron_density_cm3",
                 "pressure_from_density"}


def _compared_variable(p: ObservationProfile, variable_name: str) -> Optional[np.ndarray]:
    """The values of ``variable_name`` in profile ``p`` (archived or derived), or None."""
    if variable_name in ("temperature_k", "temperature_c", "pressure_hpa", "refractivity", "electron_density_cm3"):
        v = getattr(p, variable_name)
    else:
        v = p.derived.get(variable_name)
    return None if v is None else np.asarray(v, dtype=float)


def _compared_sigma(p: ObservationProfile, variable_name: str) -> Optional[np.ndarray]:
    """1-sigma uncertainty of ``variable_name`` in profile ``p`` (archived or propagated), or None."""
    s = (p.uncertainty or {}).get(variable_name)
    return None if s is None else np.asarray(s, dtype=float)


VERTICALS = ("altitude", "pressure")


def _vertical_coordinate(p: ObservationProfile, vertical: str) -> Optional[np.ndarray]:
    """Altitude (km), or -log10(pressure / hPa) in pressure mode (None without pressure)."""
    if vertical == "pressure":
        pr = p.pressure_hpa
        if pr is None or p.altitude_km is None or np.shape(pr) != np.shape(p.altitude_km):
            return None
        pr = np.asarray(pr, dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(pr > 0, -np.log10(pr), np.nan)
    return None if p.altitude_km is None else np.asarray(p.altitude_km, dtype=float)


def _altitude_range(p: ObservationProfile, ok: np.ndarray) -> List[float]:
    z = np.asarray(p.altitude_km, dtype=float)
    z = z[ok & np.isfinite(z)] if z.shape == ok.shape else z[np.isfinite(z)]
    return [round(float(z.min()), 2), round(float(z.max()), 2)] if z.size else []


def compare_profiles_on_body(
    profiles: List[ObservationProfile],
    body: BodyInfo,
    altitude_step_km: float = 0.5,
    variable_name: str = "temperature_k",
    group_by: str = "",
    group_width: float = 0.0,
    vertical: str = "altitude",
    pressure_step_decades: float = 0.02,
    weighting: str = "equal",
    outlier_z: Optional[float] = None,
    drop_outliers: bool = False,
    cross_section_width: Optional[float] = None,
    reference: bool = False,
    smoothing_km: Optional[float] = None,
) -> Dict[str, Any]:
    """Cross-compare multi-mission profiles for a target planetary body.

    Interpolates all profiles onto a uniform vertical grid and calculates
    multi-spacecraft composite mean, dispersion (+/- 1 sigma), and individual curves.
    ``vertical="pressure"`` uses a grid uniform in log10(pressure) instead of altitude
    (``pressure_step_decades`` apart): profiles measured from different altitude
    references (the 1-bar level, an ellipsoid, a landing site) then line up, and
    profiles without a pressure column are left out.  ``smoothing_km``: each profile is
    first smoothed on the grid to this vertical resolution (Gaussian FWHM, error-weighted;
    analysis/smoothing.py), with its 1-sigma propagated.
    """
    if vertical not in VERTICALS:
        raise ValueError(f"vertical must be one of: {', '.join(VERTICALS)}")
    if weighting not in WEIGHTINGS:
        raise ValueError(f"weighting must be one of: {', '.join(WEIGHTINGS)}")
    by_pressure = vertical == "pressure"
    if not profiles:
        return _empty_comparison(body, variable_name)
    if by_pressure and variable_name == "pressure_hpa":
        return {**_empty_comparison(body, variable_name),
                "error": "Pressure is the vertical coordinate here; compare another variable, or use altitude."}
    step = pressure_step_decades if by_pressure else altitude_step_km
    unsmoothed_note = ""
    if smoothing_km and by_pressure:
        # (a resolution in km has no fixed width in log pressure)
        smoothing_km, unsmoothed_note = None, "; not smoothed (smoothing works on altitude levels)"
    if smoothing_km:
        from .smoothing import MAX_HALF_WINDOW, WINDOW_FWHM, half_window
        if half_window(step, smoothing_km) > MAX_HALF_WINDOW:
            return {**_empty_comparison(body, variable_name),
                    "error": (f"Smoothing to {smoothing_km:g} km spans more than {2 * MAX_HALF_WINDOW + 1} levels of the "
                              f"{step:g} km grid; choose a grid step of at least "
                              f"{WINDOW_FWHM * smoothing_km / MAX_HALF_WINDOW:.2g} km.")}

    # Determine altitude span covering the observations
    valid_profiles = [p for p in profiles if p is not None]
    if not valid_profiles:
        return _empty_comparison(body, variable_name)

    all_z = [c for c in (_vertical_coordinate(p, vertical) for p in valid_profiles) if c is not None and c.size > 0]
    if not all_z:
        return _empty_comparison(body, variable_name)

    z_mins = [float(np.nanmin(z)) for z in all_z if np.isfinite(z).any()]
    z_maxs = [float(np.nanmax(z)) for z in all_z if np.isfinite(z).any()]
    if not z_mins or not z_maxs:
        return _empty_comparison(body, variable_name)

    # Grid levels on whole multiples of the step (20.0, 20.5 km ...), covering every
    # profile; negative altitudes (below the reference level) are kept.
    # (in pressure mode the coordinate is -log10(p / hPa), increasing upwards like altitude)
    grid_lo = np.ceil(float(np.min(z_mins)) / step - 1e-9) * step
    grid_hi = np.floor(float(np.max(z_maxs)) / step + 1e-9) * step
    if grid_hi <= grid_lo:
        grid_hi = grid_lo + step

    num_steps = int(round((grid_hi - grid_lo) / step)) + 1
    if num_steps > MAX_GRID_LEVELS:
        need = (grid_hi - grid_lo) / (MAX_GRID_LEVELS - 1)
        unit = "decades of pressure" if by_pressure else "km"
        return {**_empty_comparison(body, variable_name),
                "error": (f"A step of {step:g} {unit} gives {num_steps} levels; "
                          f"choose a step of at least {need:.2g} {unit}.")}
    z_grid = np.round(grid_lo + step * np.arange(max(num_steps, 2)), 6)

    interpolated_matrix = []
    sigma_matrix = []           # each value's 1-sigma, in log space (relative) for log-averaged variables
    systematic_matrix = []      # each value's systematic uncertainty, the same way
    profile_summaries = []
    # Quantities that vary exponentially with height are interpolated and averaged in
    # log space (geometric mean, spread as a factor) when every value of every profile
    # is positive.  This is decided before any profile is interpolated: deciding it
    # profile by profile mixed log and linear values in one composite.
    log_like = variable_name in LOG_VARIABLES and not any(
        np.any(v[np.isfinite(v)] <= 0)
        for v in (_compared_variable(p, variable_name) for p in valid_profiles) if v is not None)

    for p in valid_profiles:
        v = _compared_variable(p, variable_name)

        z_p = _vertical_coordinate(p, vertical)
        if v is None or z_p is None or z_p.size < 2 or v.shape != z_p.shape:
            continue

        ok = np.isfinite(z_p) & np.isfinite(v)
        if ok.sum() < 2:
            continue

        z_clean = z_p[ok]
        v_clean = v[ok]
        sort_idx = np.argsort(z_clean)
        z_clean, v_clean = z_clean[sort_idx], v_clean[sort_idx]

        # Interpolate onto the common grid, never extrapolating beyond the profile and
        # never bridging data gaps wider than five times the profile's typical spacing.
        f = np.log(v_clean) if log_like else v_clean
        v_interp = np.interp(z_grid, z_clean, f, left=np.nan, right=np.nan)
        if z_clean.size > 2:
            dz = np.diff(z_clean)
            typical = float(np.median(dz[dz > 0])) if np.any(dz > 0) else 0.0
            if typical > 0:
                for gap_lo, gap_hi in zip(z_clean[:-1][dz > 5 * typical], z_clean[1:][dz > 5 * typical]):
                    v_interp[(z_grid > gap_lo) & (z_grid < gap_hi)] = np.nan
        # the profile's own 1-sigma on the grid (in the variable's units), where it has one
        sig_p = _compared_sigma(p, variable_name)
        s_interp = None
        corr_levels = 0.0
        if sig_p is not None and sig_p.shape == z_p.shape:
            s_clean = sig_p[ok][sort_idx]
            if np.isfinite(s_clean).any():
                good = np.isfinite(s_clean)
                # correlation length of the errors: the data set's, or the shortest the
                # profile's own scatter allows (uncertainty.error_correlation_from_scatter)
                corr_levels = _correlation_km(p) or error_correlation_from_scatter(
                    z_clean, v_clean, s_clean, log=log_like)
                s_interp = _interpolated_sigma(z_grid, z_clean[good], s_clean[good], corr_levels)
                s_interp[~np.isfinite(v_interp)] = np.nan
        # the systematic uncertainty on the grid: linear interpolation is exact for it (the
        # half difference of two retrievals interpolated level by level)
        sys_p = (p.systematic or {}).get(variable_name)
        sys_interp = None
        if sys_p is not None and np.shape(sys_p) == z_p.shape:
            y_sys = np.asarray(sys_p, dtype=float)[ok][sort_idx]
            good_sys = np.isfinite(y_sys)
            if good_sys.sum() >= 2:
                sys_interp = np.interp(z_grid, z_clean[good_sys], y_sys[good_sys], left=np.nan, right=np.nan)
                sys_interp[~np.isfinite(v_interp)] = np.nan
        grid_corr = _grid_error_correlation_km(corr_levels, z_clean) if s_interp is not None else 0.0
        if smoothing_km:
            # to the chosen vertical resolution, weights 1/sigma^2, 1-sigma propagated with
            # the errors' correlation on the grid; the systematic part with the same weights
            from .smoothing import apply_weights, matched_correlation_km, smooth_on_grid
            with np.errstate(invalid="ignore", divide="ignore"):
                s_f = None if s_interp is None else (s_interp / np.exp(v_interp) if log_like else s_interp)
                sys_f = None if sys_interp is None else (sys_interp / np.exp(v_interp) if log_like else sys_interp)
                if s_f is not None:
                    # the errors' correlation at the scale of the window, from the profile's own
                    # residual about its smoothed version (the level-to-level one is shorter)
                    grid_corr = matched_correlation_km(v_interp, s_f, step, smoothing_km, grid_corr)
                sm = smooth_on_grid(v_interp, s_f, step, smoothing_km, grid_corr)
                v_interp = sm["values"]
                if s_interp is not None:
                    s_interp = sm["sigma"] * np.exp(v_interp) if log_like else sm["sigma"]
                if sys_interp is not None:
                    sys_f = apply_weights(sys_f, sm["weights"], sm["offsets"])
                    sys_interp = sys_f * np.exp(v_interp) if log_like else sys_f
            grid_corr = sm["correlation_km"]
        interpolated_matrix.append(v_interp)
        with np.errstate(invalid="ignore", divide="ignore"):
            sigma_matrix.append(np.full(z_grid.size, np.nan) if s_interp is None else
                                (s_interp / np.exp(v_interp) if log_like else s_interp))
            systematic_matrix.append(np.full(z_grid.size, np.nan) if sys_interp is None else
                                     (sys_interp / np.exp(v_interp) if log_like else sys_interp))

        profile_summaries.append({
            "observation_id": p.observation_id,
            "mission_id": p.mission_id,
            "instrument": p.instrument,
            "time_utc": p.time_utc,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "n_points": int(v_clean.size),
            "z_range_km": _altitude_range(p, ok),
            "altitude_reference": (p.raw_attributes or {}).get("ALTITUDE_REFERENCE", ""),
            # the mission a loaded file comes from, as the user said (for legends and colours)
            "mission_label": (p.raw_attributes or {}).get("SOURCE_MISSION") or p.mission_id,
            # archive data set and volume (none for loaded files), for the Cite panel
            "dataset_id": (p.raw_attributes or {}).get("DATASET_ID"),
            "volume": (p.raw_attributes or {}).get("VOLUME"),
            **{k: v for k, v in _geom(p).items() if k in ("lst", "sza", "ls")},
            "diagnostics": {k: v for k, v in profile_diagnostics(p).items() if v is not None},
            "interpolated_series": v_interp,
            **({"interpolated_sigma": [None if not np.isfinite(x) else float(f"{x:.4g}") for x in s_interp]}
               if s_interp is not None else {}),
            **({"interpolated_systematic": [None if not np.isfinite(x) else float(f"{x:.4g}") for x in sys_interp]}
               if sys_interp is not None else {}),
            **({"sigma_correlation_km": round(float(grid_corr), 4)}
               if s_interp is not None and vertical != "pressure" else {}),
        })

    if not interpolated_matrix:
        return _empty_comparison(body, variable_name, [] if by_pressure else [round(float(z), 4) for z in z_grid])

    mat = np.array(interpolated_matrix)  # shape: (n_profiles, n_grid)
    smat = np.array(sigma_matrix)
    rand_s, sys_s = np.array(sigma_matrix), np.array(systematic_matrix)   # for the uncertainty budget
    if weighting == "inverse_variance_total":
        # the random 1-sigma with the systematic uncertainty added in quadrature where given
        sysm = np.array(systematic_matrix)
        with np.errstate(invalid="ignore"):
            smat = np.where(np.isfinite(smat), np.sqrt(smat ** 2 + np.nan_to_num(sysm) ** 2), np.nan)
    stat_weighting = "inverse_variance" if weighting.startswith("inverse_variance") else weighting
    # Outlier screen: flag profiles far from the others (robust z per level); they are
    # left out of the composites only when asked, and are always reported
    screen = None
    if outlier_z:
        # against the profile's own group when grouped (a climatology mixes latitudes or
        # seasons that differ for real), else against all profiles
        flags = screen_outliers(mat, outlier_z)
        if group_by:
            keys = [_group_key(s_, group_by, group_width) for s_ in profile_summaries]
            for key in {k for k in keys if k is not None}:
                idx = [i for i, k in enumerate(keys) if k == key]
                for i, fl in zip(idx, screen_outliers(mat[idx], outlier_z)):
                    flags[i] = fl
        for s_, fl in zip(profile_summaries, flags):
            s_["outlier"] = fl
        flagged = [s_["observation_id"] for s_, fl in zip(profile_summaries, flags) if fl["flagged"]]
        screen = {"z": outlier_z, "level_fraction": OUTLIER_LEVEL_FRACTION, "min_profiles": OUTLIER_MIN_PROFILES,
                  "against": "own group" if group_by else "all profiles",
                  "flagged": flagged, "left_out": bool(drop_outliers and flagged)}
        if drop_outliers and flagged and len(flagged) < len(profile_summaries):
            keep = [i for i, fl in enumerate(flags) if not fl["flagged"]]
            screen["left_out_profiles"] = [profile_summaries[i] for i, fl in enumerate(flags) if fl["flagged"]]
            mat, smat = mat[keep], smat[keep]
            rand_s, sys_s = rand_s[keep], sys_s[keep]
            profile_summaries = [profile_summaries[i] for i in keep]
            interpolated_matrix = [interpolated_matrix[i] for i in keep]
    if stat_weighting == "inverse_variance" and not np.isfinite(smat).any():
        return {**_empty_comparison(body, variable_name),
                "error": "None of these profiles has an uncertainty for this variable; use equal weights."}
    stats = _level_statistics(mat, smat, stat_weighting)   # no spread from a single profile
    n_per_level = stats["n"]
    mean_min = max(2, int(np.ceil(0.5 * len(interpolated_matrix))))
    mean_f, std_f, sem_f = stats["mean"], stats["std"], stats["sem"]
    if log_like:
        mean_v, lo_v, hi_v = np.exp(mean_f), np.exp(mean_f - std_f), np.exp(mean_f + std_f)
        std_v = np.full_like(mean_v, np.nan)                  # spread is a factor, see lo/hi
        sem_v = np.full_like(mean_v, np.nan)
        sem_lo, sem_hi = np.exp(mean_f - sem_f), np.exp(mean_f + sem_f)
        for s in profile_summaries:
            s["interpolated_series"] = np.exp(s["interpolated_series"])
    else:
        mean_v, std_v, sem_v = mean_f, std_f, sem_f
        lo_v, hi_v = mean_f - std_f, mean_f + std_f
        sem_lo, sem_hi = mean_f - sem_f, mean_f + sem_f
    left_out = (screen or {}).get("left_out_profiles") or []
    if log_like:
        for s in left_out:
            s["interpolated_series"] = np.exp(s["interpolated_series"])
    for s in profile_summaries + left_out:
        s["interpolated_series"] = [None if not np.isfinite(x) else float(f"{x:.6g}")
                                    for x in s["interpolated_series"]]
    sig = (lambda x: None if not np.isfinite(x) else float(f"{x:.6g}"))
    groups = _group_composites(mat, profile_summaries, log_like, group_by, group_width, sig,
                               smat, stat_weighting) if group_by else []
    group_differences = _group_differences(mat, profile_summaries, log_like, group_by, group_width, sig,
                                           smat, stat_weighting) if group_by else []
    budget = uncertainty_budget(mat, rand_s, sys_s, stat_weighting)
    pct = (lambda a: 100.0 * a) if log_like else (lambda a: a)       # log space: relative, in percent

    return {
        "group_by": group_by or "",
        "group_width": group_width,
        "groups": groups,
        # each group minus the first, with standard error and bootstrap interval
        "group_differences": group_differences,
        "averaging": ("geometric mean and 1-sigma factor (log space)" if log_like else "arithmetic mean and 1-sigma (sample)")
                     + ("; inverse-variance weights" if weighting == "inverse_variance" else
                        "; inverse-variance weights (random and systematic uncertainty)"
                        if weighting == "inverse_variance_total" else "")
                     + (f"; each profile smoothed to {smoothing_km:g} km (Gaussian FWHM, weights 1/sigma^2 where it has a 1-sigma)"
                        if smoothing_km else unsmoothed_note),
        "smoothing_km": smoothing_km or None,
        "profiles_per_level": [int(n) for n in n_per_level],
        # (levels of equal pressure need no common altitude reference)
        "vertical_reference_warning": "" if by_pressure else _vertical_reference_warning(profile_summaries),
        "vertical": vertical,
        "body_id": body.id,
        "body_name": body.name,
        "variable_name": variable_name,
        "grid_km": [] if by_pressure else [round(float(z), 4) for z in z_grid],
        "altitude_step_km": None if by_pressure else altitude_step_km,
        **({"grid_hpa": [float(f"{10.0 ** -z:.6g}") for z in z_grid],
            "pressure_step_decades": pressure_step_decades} if by_pressure else {}),
        # The mean of whichever profiles reach a level jumps where that number changes
        # (one profile alone is just that profile), so it is given only where at least
        # two profiles and at least half of them overlap; profiles_per_level says how many.
        "composite_mean": [sig(x) if n >= mean_min else None for x, n in zip(mean_v, n_per_level)],
        "composite_std": [sig(x) for x in std_v],
        "composite_plus_1sigma": [sig(x) for x in hi_v],
        "composite_minus_1sigma": [sig(x) for x in lo_v],
        # standard error of the mean (a factor in log space for log-averaged variables:
        # see the plus/minus values) and the effective number of profiles at each level
        "weighting": weighting,
        "outlier_screen": screen,
        "reference": _reference_series(body, variable_name, z_grid, by_pressure) if reference else None,
        # zonal mean in latitude bands (latitude-altitude cross section), when asked
        "cross_section": (None if not cross_section_width else
                          {"error": "Too many levels for a cross section; choose a coarser grid step."}
                          if mat.shape[1] * int(np.ceil(180.0 / cross_section_width)) > MAX_CROSS_SECTION_CELLS else
                          latitude_cross_section(mat, smat, [s_["latitude"] for s_ in profile_summaries],
                                                 cross_section_width, log_like, stat_weighting)),
        "composite_sem": [sig(x) for x in sem_v],
        "composite_plus_sem": [sig(x) if n >= mean_min else None for x, n in zip(sem_hi, n_per_level)],
        "composite_minus_sem": [sig(x) if n >= mean_min else None for x, n in zip(sem_lo, n_per_level)],
        "n_effective": [None if not np.isfinite(x) else round(float(x), 2) for x in stats["n_eff"]],
        # 95 % percentile bootstrap interval of the mean (resampling the profiles)
        "composite_ci95_low": [sig(x) if n >= mean_min else None
                               for x, n in zip(np.exp(stats["ci_lo"]) if log_like else stats["ci_lo"], n_per_level)],
        "composite_ci95_high": [sig(x) if n >= mean_min else None
                                for x, n in zip(np.exp(stats["ci_hi"]) if log_like else stats["ci_hi"], n_per_level)],
        "profile_count": len(profile_summaries),
        "profiles": profile_summaries,
        # spread = natural variability (+) random errors; random and systematic errors of the mean
        # (log-averaged variables: 100 x the 1-sigma of ln(value), the percent of the value while small)
        "uncertainty_budget": {
            "percent": bool(log_like),
            **{k: [sig(x) for x in (budget[k] if k in ("random_fraction", "profiles_with_sigma") else pct(budget[k]))]
               for k in budget}},
        # label and unit of each per-profile diagnostic at least one profile has
        "diagnostic_labels": {k: list(PROFILE_DIAGNOSTICS[k]) for k in PROFILE_DIAGNOSTICS
                              if any(k in s["diagnostics"] for s in profile_summaries)},
    }


def export_profile_to_csv(profile: ObservationProfile) -> str:
    """Serialize profile and derived thermodynamics to CSV format."""
    lines = [
        f"# VEDA Scientific Data Export - Mission: {profile.mission_id.upper()}, Observation: {profile.observation_id}",
        f"# Target Body: {profile.body_id}, Instrument: {profile.instrument}, Time UTC: {profile.time_utc}",
        f"# Latitude: {profile.latitude}, Longitude: {profile.longitude}",
    ]
    if profile.provenance:
        lines.append(f"# Archive: {profile.provenance.archive_source} ({profile.provenance.archive_url})")
        lines.append(f"# Source file: {profile.provenance.original_file} ({profile.provenance.product_level})")
        lines.append(f"# Citation: {profile.provenance.doi_or_citation}")
    lines.append("# Archived columns are as published, converted to the units in the header; other columns are derived by VEDA.")
    lines.append(f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA, doi:10.5281/zenodo.23215291), MIT License")

    cols = ["altitude_km"]
    data_arrays = [profile.altitude_km]

    if profile.temperature_k is not None:
        cols.append("temperature_k")
        data_arrays.append(profile.temperature_k)
    if profile.temperature_c is not None:
        cols.append("temperature_c")
        data_arrays.append(profile.temperature_c)
    if profile.pressure_hpa is not None:
        cols.append("pressure_hpa")
        data_arrays.append(profile.pressure_hpa)
    if profile.refractivity is not None:
        cols.append("refractivity_n")
        data_arrays.append(profile.refractivity)
    if profile.electron_density_cm3 is not None:
        cols.append("electron_density_cm3")
        data_arrays.append(profile.electron_density_cm3)

    for k, v in profile.derived.items():
        cols.append(k)
        data_arrays.append(v)
    values_cols = list(cols[1:])
    for k in values_cols:
        key = "refractivity" if k == "refractivity_n" else k
        if key in (profile.uncertainty or {}):
            cols.append(f"sigma_{k}")
            data_arrays.append(np.asarray(profile.uncertainty[key], dtype=float))
    for k in values_cols:
        if k in (profile.systematic or {}):
            cols.append(f"systematic_{k}")
            data_arrays.append(np.asarray(profile.systematic[k], dtype=float))
    if any(c.startswith("sigma_") for c in cols):
        lines.append("# sigma_* columns are 1-sigma uncertainties: archived, or propagated from them by VEDA (User Guide).")
    if any(c.startswith("systematic_") for c in cols):
        lines.append("# systematic_* columns are systematic uncertainties, apart from sigma_*: half the difference between the "
                     "archive's retrievals with its lower and upper boundary temperature at the top, each quantity derived from both.")

    lines.append(",".join(cols))
    n_rows = profile.altitude_km.size if profile.altitude_km is not None else 0
    for i in range(n_rows):
        row = []
        for arr in data_arrays:
            if arr is not None and i < arr.size and np.isfinite(arr[i]):
                row.append(f"{arr[i]:.5g}")
            else:
                row.append("")
        lines.append(",".join(row))

    return "\n".join(lines)


def _csv_num(v: Any) -> str:
    # six significant figures: fixed decimals wrote densities of 1e-7 kg/m3 as 0.0000
    return f"{v:.6g}" if isinstance(v, (int, float)) and np.isfinite(v) else ""


def _csv_field(s: Any) -> str:
    s = "" if s is None else str(s)
    return f'"{s.replace(chr(34), chr(34) * 2)}"' if any(c in s for c in ',"\n') else s


_MEASURED = ("temperature_k", "pressure_hpa", "refractivity", "electron_density_cm3")
_TRACK = ("latitude", "longitude", "lst", "sza")


def export_profiles_long_csv(profiles: List[ObservationProfile], body: Optional[BodyInfo] = None) -> str:
    """Every profile at its own levels, one row per profile and level ("tidy" or long
    format, for pandas, R or a spreadsheet pivot): the archived quantities, everything
    VEDA derives from them, their 1-sigma uncertainties, and the position along the
    ray path where the archive gives it.  Nothing is interpolated."""
    from ..missions.selection import profile_geometry

    def arr(a, n):
        a = np.asarray(a, dtype=float).ravel() if a is not None else None
        return a if a is not None and a.size == n else None

    var_cols: List[str] = []
    for p in profiles:
        for k in list(_MEASURED) + sorted(p.derived):
            v = getattr(p, k, None) if k in _MEASURED else p.derived.get(k)
            if v is not None and k not in var_cols:
                var_cols.append(k)
    sigma_cols = [k for k in var_cols if any(k in (p.uncertainty or {}) for p in profiles)]
    sys_cols = [k for k in var_cols if any(k in (p.systematic or {}) for p in profiles)]
    track_cols = [k for k in _TRACK if any(k in (p.track or {}) for p in profiles)]

    lines = [
        f"# VEDA profiles at their archived levels (long format): {len(profiles)} profiles"
        + (f", body={body.name}" if body else ""),
        "# One row per profile and level. Archived quantities are as published, converted to the units in the column names;",
        "# the other quantities are derived by VEDA (see the User Guide). sigma_* columns are 1-sigma uncertainties.",
        "# altitude_km is above each profile's altitude reference, given with its source below (most data sets: the",
        "# body's reference radius); profile_* columns are each profile's header values,",
        "# level_* columns the position of each level along the ray path where the archive gives it.",
        f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA, doi:10.5281/zenodo.23215291), MIT License",
    ]
    from ..core.registry import get_variable_info
    extra_units = {"dtheta_dz": "K/km", "number_density_m3": "m^-3", "molar_mass": "g/mol",
                   "co2_condensation_temperature": "K", "t_minus_co2_condensation": "K"}
    unit_of = (lambda k: (get_variable_info(k) or {}).get("units") or extra_units.get(k))
    units = [f"{k}={unit_of(k)}" for k in var_cols if unit_of(k)]
    if units:
        lines.append("# units: " + "; ".join(units) + " (sigma_* and systematic_* as their quantity)")
    if sys_cols:
        lines.append("# systematic_* columns are systematic uncertainties (the boundary temperature of radio occultation "
                     "retrievals: half the difference between the archive's lower- and upper-boundary retrievals).")
    for p in profiles:
        if p.provenance:
            ref = (p.raw_attributes or {}).get("ALTITUDE_REFERENCE")
            lines.append(f"# {p.observation_id}: {p.provenance.archive_source}, {p.provenance.original_file}"
                         + (f", {p.provenance.doi_or_citation}" if p.provenance.doi_or_citation else "")
                         + (f"; altitude above {ref}" if ref else ""))
    header = (["mission", "instrument", "observation_id", "time_utc", "profile_latitude_deg", "profile_longitude_deg",
               "profile_lst_h", "profile_sza_deg", "profile_ls_deg", "altitude_km"]
              + var_cols + [f"sigma_{k}" for k in sigma_cols] + [f"systematic_{k}" for k in sys_cols]
              + [f"level_{k}" + {"latitude": "_deg", "longitude": "_deg", "lst": "_h", "sza": "_deg"}[k] for k in track_cols])
    lines.append(",".join(header))
    for p in profiles:
        z = np.asarray(p.altitude_km, dtype=float).ravel()
        n = z.size
        geom = profile_geometry(p)
        fixed = [_csv_field((p.raw_attributes or {}).get("SOURCE_MISSION") or p.mission_id), _csv_field(p.instrument),
                 _csv_field(p.observation_id), _csv_field(p.time_utc), _csv_num(p.latitude), _csv_num(p.longitude),
                 _csv_num(geom.get("lst")), _csv_num(geom.get("sza")), _csv_num(geom.get("ls"))]
        cols = [arr(getattr(p, k, None) if k in _MEASURED else p.derived.get(k), n) for k in var_cols]
        cols += [arr((p.uncertainty or {}).get(k), n) for k in sigma_cols]
        cols += [arr((p.systematic or {}).get(k), n) for k in sys_cols]
        cols += [arr((p.track or {}).get(k), n) for k in track_cols]
        for i in range(n):
            if not np.isfinite(z[i]):
                continue
            lines.append(",".join(fixed + [f"{z[i]:.4f}"] + [_csv_num(c[i]) if c is not None else "" for c in cols]))
    return "\n".join(lines) + "\n"


def _altitude_note(profiles: List[Dict[str, Any]]) -> str:
    """'# Altitude above ... (km)' for the comparison CSV: the shared altitude reference."""
    refs = {p.get("altitude_reference") or "" for p in profiles} - {""}
    sphere = lambda r: r.startswith(("a sphere", "as given"))  # noqa: E731
    if len(refs) == 1 and not sphere(next(iter(refs))):
        return f"# Altitude above {next(iter(refs))} (km)"
    if len(refs) > 1 and not all(sphere(r) for r in refs):
        return "# Altitude above each profile's own reference (km; see altitude_reference)"
    return "# Altitude above the body's reference radius (km)"


_BUDGET_COLUMNS = ("profiles_with_sigma", "spread", "random_rms", "variability", "random_fraction", "systematic_rms",
                   "mean_random", "mean_systematic_independent", "mean_systematic_correlated")


def export_comparison_to_csv(comparison: Dict[str, Any]) -> str:
    """The comparison as on screen: gridded composite, group composites and every
    profile, with a header describing each profile (time, position, geometry)."""
    from ..core.registry import get_variable_info
    body_name = comparison.get("body_name", "Body")
    var_name = comparison.get("variable_name", "variable")
    units = (get_variable_info(var_name) or {}).get("units", "")
    by_pressure = comparison.get("vertical") == "pressure"
    grid = comparison.get("grid_hpa", []) if by_pressure else comparison.get("grid_km", [])
    profiles = comparison.get("profiles", [])
    # group labels in plain ASCII ("Latitude 0 to 30 deg"): spreadsheets misread the degree sign
    groups = [{**g, "label": g["label"].replace("°", " deg")}
              for g in comparison.get("groups") or [] if not g.get("ungrouped") and g.get("mean")]

    lines = [
        f"# VEDA comparison: body={body_name}, variable={var_name}" + (f" [{units}]" if units else ""),
        f"# profiles={len(profiles)}, averaging={comparison.get('averaging', '')}"
        + ("; sem = spread / sqrt(n_effective); ci95 = 95 % bootstrap interval of the mean (profiles resampled)"
           if comparison.get("composite_plus_sem") else "")
        + (f", grouped by {comparison.get('group_by')}" if groups else ""),
        "# Profiles from the official mission archives (see each product for its source); means and spreads computed by VEDA.",
        (f"# Common grid uniform in log pressure, every {comparison.get('pressure_step_decades'):g} decades."
         if by_pressure else
         _altitude_note(profiles)
         + (f", common grid every {comparison['altitude_step_km']:g} km." if comparison.get("altitude_step_km") else "."))
        + (f" Note: {comparison['vertical_reference_warning']}" if comparison.get("vertical_reference_warning") else ""),
        f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA, doi:10.5281/zenodo.23215291), MIT License",
    ]
    diag_keys = list(comparison.get("diagnostic_labels") or {})
    lines.append("# column, mission, instrument, observation, time_utc, latitude_deg, longitude_deg, lst_h, sza_deg, ls_deg"
                 + "".join(f", {k}" for k in diag_keys) + ", altitude_reference")
    cols = []
    for p in profiles:
        col = f"{p.get('mission_label') or p.get('mission_id')}_{p.get('observation_id')}"
        cols.append(col)
        lines.append("# " + ", ".join(_csv_field(x) for x in (
            col, p.get("mission_label") or p.get("mission_id"), p.get("instrument"), p.get("observation_id"),
            p.get("time_utc"), _csv_num(p.get("latitude")), _csv_num(p.get("longitude")),
            _csv_num(p.get("lst")), _csv_num(p.get("sza")), _csv_num(p.get("ls")),
            *(_csv_num((p.get("diagnostics") or {}).get(k)) for k in diag_keys), p.get("altitude_reference") or "")))
    for g in groups:
        lines.append(f"# group {_csv_field(g['label'])}: n={g['n']}, profiles={' '.join(g['observation_ids'])}")
    if comparison.get("smoothing_km"):
        lines.append(f"# each profile smoothed to {comparison['smoothing_km']:g} km before averaging: Gaussian of that full "
                     "width at half maximum, cut at +-1.5 times it, weights 1/sigma^2 where the profile has a 1-sigma "
                     "(analysis/smoothing.py); sigma_* are the smoothed values' 1-sigma, error correlation counted.")
    scr = comparison.get("outlier_screen")
    if scr:
        lines.append(f"# outlier screen: robust z > {scr['z']:g} on at least {100 * scr['level_fraction']:g} % of a profile's levels"
                     f" (levels with {scr['min_profiles']} or more profiles); flagged: {' '.join(scr['flagged']) or 'none'}"
                     + ("; left out of the composites and of the columns below" if scr.get("left_out") else
                        "; kept in the composites"))

    header = ["pressure_hpa" if by_pressure else "altitude_km", f"composite_mean_{var_name}", "composite_std", "plus_1sigma",
              "minus_1sigma", "composite_sem", "plus_sem", "minus_sem", "ci95_low", "ci95_high", "profiles_at_level",
              "n_effective"]
    for g in groups:
        header += [f"{g['label']} mean", f"{g['label']} plus_1sigma", f"{g['label']} minus_1sigma",
                   f"{g['label']} plus_sem", f"{g['label']} minus_sem", f"{g['label']} ci95_low",
                   f"{g['label']} ci95_high", f"{g['label']} n_effective"]
    diffs = comparison.get("group_differences") or []
    for d in diffs:
        header += [f"{d['label']} difference", f"{d['label']} se", f"{d['label']} ci95_low",
                   f"{d['label']} ci95_high"]
    if diffs:
        lines.append("# '<group> minus <first group>' columns: difference of the composite means, its standard error "
                     "and 95 % bootstrap interval (each group resampled on its own)"
                     + ("; in percent of the first group's geometric mean." if diffs[0].get("percent") else "."))
    budget = comparison.get("uncertainty_budget") or {}
    bkeys = [k for k in _BUDGET_COLUMNS if any(v is not None for v in budget.get(k) or [])]
    if bkeys:
        header += [f"budget_{k}" for k in bkeys]
        lines.append("# budget_* columns (uncertainty budget, equal weights unless inverse-variance weighting; "
                     + ("as 100 x the 1-sigma of ln(value), the percent of the value while small; " if budget.get("percent") else "")
                     + "over the profiles with a 1-sigma at the level): spread^2 = variability^2 + random_rms^2; "
                     "random_fraction = random_rms^2 / spread^2; mean_random = random error of the mean; "
                     "mean_systematic_independent / _correlated = systematic uncertainty of the mean when the profiles' "
                     "systematic errors are independent / shared.")
    ref = (comparison.get("reference") or {}).get("series")
    if ref:
        lines.append(f"# reference: {comparison['reference']['name']}; {comparison['reference']['citation']}")
        header.append(f"reference_{var_name}")
    header += cols
    with_sigma = [(c, p) for c, p in zip(cols, profiles) if p.get("interpolated_sigma")]
    header += [f"sigma_{c}" for c, _ in with_sigma]
    if with_sigma:
        lines.append("# sigma_* columns: each profile's 1-sigma uncertainty on the grid, archived or propagated by VEDA.")
    with_sys = [(c, p) for c, p in zip(cols, profiles) if p.get("interpolated_systematic")]
    header += [f"systematic_{c}" for c, _ in with_sys]
    if with_sys:
        lines.append("# systematic_* columns: each profile's systematic uncertainty on the grid (boundary temperature of "
                     "radio occultation retrievals), apart from sigma_*.")
    lines.append(",".join(_csv_field(h) for h in header))

    def at(seq, i):
        return seq[i] if seq and i < len(seq) else None
    n_level = comparison.get("profiles_per_level") or []
    for i, z in enumerate(grid):
        row = [f"{z:.6g}" if by_pressure else f"{z:.3f}"] + [_csv_num(at(comparison.get(k), i)) for k in
                              ("composite_mean", "composite_std", "composite_plus_1sigma", "composite_minus_1sigma",
                               "composite_sem", "composite_plus_sem", "composite_minus_sem",
                               "composite_ci95_low", "composite_ci95_high")]
        row.append(str(at(n_level, i)) if at(n_level, i) is not None else "")
        row.append(_csv_num(at(comparison.get("n_effective"), i)))
        for g in groups:
            row += [_csv_num(at(g["mean"], i)), _csv_num(at(g["plus_1sigma"], i)), _csv_num(at(g["minus_1sigma"], i)),
                    _csv_num(at(g.get("plus_sem"), i)), _csv_num(at(g.get("minus_sem"), i)),
                    _csv_num(at(g.get("ci95_low"), i)), _csv_num(at(g.get("ci95_high"), i)),
                    _csv_num(at(g.get("n_effective"), i))]
        for d in diffs:
            row += [_csv_num(at(d["difference"], i)), _csv_num(at(d["se"], i)), _csv_num(at(d["ci95_low"], i)),
                    _csv_num(at(d["ci95_high"], i))]
        row += [_csv_num(at(budget.get(k), i)) for k in bkeys]
        if ref:
            row.append(_csv_num(at(ref, i)))
        row += [_csv_num(at(p.get("interpolated_series"), i)) for p in profiles]
        row += [_csv_num(at(p.get("interpolated_sigma"), i)) for _, p in with_sigma]
        row += [_csv_num(at(p.get("interpolated_systematic"), i)) for _, p in with_sys]
        lines.append(",".join(row))

    return "\n".join(lines) + "\n"



def export_cross_section_to_csv(comparison: Dict[str, Any]) -> str:
    """The zonal-mean cross section of a comparison, one row per latitude band and level."""
    from ..core.registry import get_variable_info
    xs = comparison.get("cross_section") or {}
    var_name = comparison.get("variable_name", "variable")
    units = (get_variable_info(var_name) or {}).get("units", "")
    by_pressure = comparison.get("vertical") == "pressure"
    grid = comparison.get("grid_hpa", []) if by_pressure else comparison.get("grid_km", [])
    lines = [
        f"# VEDA zonal-mean cross section: body={comparison.get('body_name', '')}, variable={var_name}"
        + (f" [{units}]" if units else ""),
        f"# {comparison.get('profile_count', 0)} profiles in latitude bands {xs.get('width', 0):g} deg wide"
        + (f" ({xs['without_latitude']} without latitude left out)" if xs.get("without_latitude") else "")
        + f"; {comparison.get('averaging', '')}; sem = spread / sqrt(n_effective)"
        + (" in percent of the mean" if xs.get("sem_unit") == "%" else ""),
        f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA, doi:10.5281/zenodo.23215291), MIT License",
        ",".join(["latitude_center_deg", "pressure_hpa" if by_pressure else "altitude_km", f"mean_{var_name}",
                  "sem_pct" if xs.get("sem_unit") == "%" else "sem", "profiles"]),
    ]
    for b, c in enumerate(xs.get("latitude_centers", [])):
        for i, z in enumerate(grid):
            m = xs["mean"][b][i]
            if m is None:
                continue
            lines.append(",".join([f"{c:g}", f"{z:.6g}" if by_pressure else f"{z:.3f}", _csv_num(m),
                                   _csv_num(xs["sem"][b][i]), str(xs["profiles"][b][i])]))
    return "\n".join(lines) + "\n"
