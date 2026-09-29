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
from ..core.models import BodyInfo, ObservationProfile
from ..core.registry import get_body


def _gradient_nan_safe(z_km: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Compute dv/dz robustly handling non-finite values and non-monotonic or duplicate altitudes."""
    z = np.asarray(z_km, dtype=np.float64)
    val = np.asarray(v, dtype=np.float64)
    out = np.full(val.shape, np.nan, dtype=np.float64)
    ok = np.isfinite(z) & np.isfinite(val)
    if ok.sum() < 2:
        return out

    z_ok = z[ok]
    val_ok = val[ok]

    sort_order = np.argsort(z_ok)
    z_sorted = z_ok[sort_order].copy()
    val_sorted = val_ok[sort_order]

    # Guard against duplicate altitudes that could cause division by zero
    diffs = np.diff(z_sorted)
    if np.any(diffs <= 0):
        for j in range(1, len(z_sorted)):
            if z_sorted[j] <= z_sorted[j - 1]:
                z_sorted[j] = z_sorted[j - 1] + 1e-6

    grad_sorted = np.gradient(val_sorted, z_sorted)

    inv_order = np.empty_like(sort_order)
    inv_order[sort_order] = np.arange(len(sort_order))
    out[ok] = grad_sorted[inv_order]
    return out


def compute_atmospheric_diagnostics(
    profile: ObservationProfile,
    body: Optional[BodyInfo] = None,
) -> Dict[str, np.ndarray]:
    """Compute full suite of thermodynamic derived quantities for a profile."""
    derived: Dict[str, np.ndarray] = {}
    if body is None:
        body = get_body(profile.body_id)
    if body is None:
        return derived
    z = profile.altitude_km
    if z is None or z.size < 2:
        return derived

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

    # 2. Local gravitational acceleration with altitude g(z) = g0 * (R / (R + z))^2
    r_body = body.radius_km
    g0 = body.surface_gravity
    gz = g0 * (r_body / (r_body + np.clip(z, 0.0, None))) ** 2

    # 3. Scale Height H = R_spec * T / g(z) in km
    r_spec = body.gas_constant_r
    cp = body.isobaric_heat_capacity_cp
    with np.errstate(invalid="ignore", divide="ignore"):
        h_scale = (r_spec * t_k) / (gz * 1000.0)
        gamma = cp / max(cp - r_spec, 1.0) if cp > r_spec else 1.4
        cs = np.sqrt(gamma * r_spec * t_k)
    derived["scale_height"] = h_scale
    derived["speed_of_sound"] = cs

    # 4. Pressure and Potential Temperature
    p_hpa = profile.pressure_hpa
    if p_hpa is not None and p_hpa.size == z.size:
        # Poisson constant kappa = R / Cp
        kappa = r_spec / cp
        p_ref = body.reference_pressure_hpa

        with np.errstate(invalid="ignore", divide="ignore"):
            theta = t_k * (p_ref / np.where(p_hpa > 0, p_hpa, np.nan)) ** kappa
            # Mass density rho = P / (R * T) in kg/m^3 (P in Pa = hPa * 100)
            rho = (p_hpa * 100.0) / (r_spec * t_k)

        derived["potential_temperature"] = theta
        derived["dtheta_dz"] = _gradient_nan_safe(z, theta)
        derived["density"] = rho

        # Brunt-Vaisala frequency squared N^2 = (g / theta) * (d_theta / dz)
        # Or equivalently: N^2 = (g / T) * (dT/dz + g/Cp)
        # Note: z is in km, so dtdz is in K/km = 1e-3 K/m; gz is in m/s^2; Cp is in J/(kg K)
        dtdz_m = dtdz / 1000.0
        with np.errstate(invalid="ignore", divide="ignore"):
            n2 = (gz / t_k) * (dtdz_m + gz / cp)
            tau_b = np.where(n2 > 0, (2.0 * np.pi / np.sqrt(n2)) / 60.0, np.nan)
        derived["buoyancy_freq_sq"] = n2
        derived["buoyancy_period"] = tau_b

    # 5. Ionospheric VTEC & F2 peak diagnostics if electron density is present
    if profile.electron_density_cm3 is not None and profile.electron_density_cm3.size >= 2:
        try:
            from .advanced_science import compute_vtec
            vtec_res = compute_vtec(z, profile.electron_density_cm3)
            profile.raw_attributes["vtec_tecu"] = vtec_res.get("vtec_tecu")
            profile.raw_attributes["hmf2_km"] = vtec_res.get("peak_alt_km")
            profile.raw_attributes["nmf2_cm3"] = vtec_res.get("peak_density_cm3")
        except Exception:
            pass

    # 6. Tropopause, Gravity Waves, and Ionospheric Chapman Modeling
    try:
        from .wave_and_stability import detect_tropopause, extract_gravity_wave_activity, fit_chapman_ionosphere
        tropo = detect_tropopause(z, t_k)
        profile.raw_attributes.update(tropo)

        gw = extract_gravity_wave_activity(z, t_k, gz, derived.get("buoyancy_freq_sq"))
        if gw.get("t_prime_k"):
            derived["t_prime"] = np.array([np.nan if x is None else x for x in gw["t_prime_k"]])
            derived["wave_potential_energy"] = np.array([np.nan if x is None else x for x in gw["potential_energy_j_kg"]])
            profile.raw_attributes["gw_mean_ep_j_kg"] = gw.get("mean_potential_energy")
            profile.raw_attributes["gw_dominant_wavelength_km"] = gw.get("dominant_wavelength_km")

        if profile.electron_density_cm3 is not None and profile.electron_density_cm3.size >= 8:
            chap = fit_chapman_ionosphere(z, profile.electron_density_cm3)
            profile.raw_attributes["chapman_fit"] = chap
    except Exception:
        pass

    return derived


def compare_profiles_on_body(
    profiles: List[ObservationProfile],
    body: BodyInfo,
    altitude_step_km: float = 0.5,
    variable_name: str = "temperature_k",
) -> Dict[str, Any]:
    """Cross-compare multi-mission profiles for a target planetary body.

    Interpolates all profiles onto a uniform vertical grid and calculates
    multi-spacecraft composite mean, dispersion (+/- 1 sigma), and individual curves.
    """
    if not profiles:
        return {"grid_km": [], "composite_mean": [], "composite_std": [], "profiles": []}

    # Determine altitude span covering the observations
    valid_profiles = [p for p in profiles if p is not None]
    if not valid_profiles:
        return {"grid_km": [], "composite_mean": [], "composite_std": [], "profiles": []}

    all_z = [p.altitude_km for p in valid_profiles if p.altitude_km is not None and p.altitude_km.size > 0]
    if not all_z:
        return {"grid_km": [], "composite_mean": [], "composite_std": [], "profiles": []}

    z_mins = [float(np.nanmin(z)) for z in all_z if np.isfinite(z).any()]
    z_maxs = [float(np.nanmax(z)) for z in all_z if np.isfinite(z).any()]
    if not z_mins or not z_maxs:
        return {"grid_km": [], "composite_mean": [], "composite_std": [], "profiles": []}

    grid_lo = max(0.0, float(np.min(z_mins)))
    grid_hi = float(np.max(z_maxs))
    if grid_hi <= grid_lo:
        grid_hi = grid_lo + 10.0

    num_steps = int(round((grid_hi - grid_lo) / altitude_step_km)) + 1
    z_grid = np.linspace(grid_lo, grid_hi, max(num_steps, 2))

    interpolated_matrix = []
    profile_summaries = []

    for p in valid_profiles:
        # Extract target variable
        v = None
        if variable_name == "temperature_k":
            v = p.temperature_k
        elif variable_name == "temperature_c":
            v = p.temperature_c
        elif variable_name == "pressure_hpa":
            v = p.pressure_hpa
        elif variable_name == "refractivity":
            v = p.refractivity
        elif variable_name == "electron_density_cm3":
            v = p.electron_density_cm3
        elif variable_name in p.derived:
            v = p.derived[variable_name]

        if v is None or p.altitude_km is None or p.altitude_km.size < 2:
            continue

        z_p = p.altitude_km
        ok = np.isfinite(z_p) & np.isfinite(v)
        if ok.sum() < 2:
            continue

        z_clean = z_p[ok]
        v_clean = v[ok]
        sort_idx = np.argsort(z_clean)
        z_clean, v_clean = z_clean[sort_idx], v_clean[sort_idx]

        # Interpolate onto common body grid (never extrapolate beyond profile range)
        v_interp = np.interp(z_grid, z_clean, v_clean, left=np.nan, right=np.nan)
        interpolated_matrix.append(v_interp)

        profile_summaries.append({
            "observation_id": p.observation_id,
            "mission_id": p.mission_id,
            "instrument": p.instrument,
            "time_utc": p.time_utc,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "n_points": int(v_clean.size),
            "z_range_km": [round(float(np.min(z_clean)), 2), round(float(np.max(z_clean)), 2)],
            "interpolated_series": [None if not np.isfinite(x) else round(float(x), 4) for x in v_interp],
        })

    if not interpolated_matrix:
        return {"grid_km": [round(float(z), 2) for z in z_grid],
                "composite_mean": [], "composite_std": [], "profiles": []}

    mat = np.array(interpolated_matrix)  # shape: (n_profiles, n_grid)
    with np.errstate(invalid="ignore"):
        mean_v = np.nanmean(mat, axis=0)
        std_v = np.nanstd(mat, axis=0)

    return {
        "body_id": body.id,
        "body_name": body.name,
        "variable_name": variable_name,
        "grid_km": [round(float(z), 2) for z in z_grid],
        "composite_mean": [None if not np.isfinite(x) else round(float(x), 4) for x in mean_v],
        "composite_std": [None if not np.isfinite(x) else round(float(x), 4) for x in std_v],
        "composite_plus_1sigma": [None if not np.isfinite(m + s) else round(float(m + s), 4) for m, s in zip(mean_v, std_v)],
        "composite_minus_1sigma": [None if not np.isfinite(m - s) else round(float(m - s), 4) for m, s in zip(mean_v, std_v)],
        "profile_count": len(profile_summaries),
        "profiles": profile_summaries,
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
        lines.append(f"# Citation: {profile.provenance.doi_or_citation}")
    lines.append("# Data Availability: NASA PDS Atmospheres, ESA PSA, JAXA DARTS, and ISRO ISSDC PRADAN planetary science archives.")
    lines.append("# Software License: MIT License (Keshav Aggarwal, SPL, VSSC, ISRO)")

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


def export_comparison_to_csv(comparison: Dict[str, Any]) -> str:
    """Serialize multi-mission comparison data to CSV format."""
    body_name = comparison.get("body_name", "Body")
    var_name = comparison.get("variable_name", "variable")
    grid = comparison.get("grid_km", [])
    mean_v = comparison.get("composite_mean", [])
    std_v = comparison.get("composite_std", [])
    plus_sigma = comparison.get("composite_plus_1sigma", [])
    minus_sigma = comparison.get("composite_minus_1sigma", [])
    profiles = comparison.get("profiles", [])

    lines = [
        f"# VEDA Cross-Mission Comparative Analysis - Body: {body_name}, Variable: {var_name}",
        f"# Total Profiles: {len(profiles)}",
        "# Data Availability: NASA PDS Atmospheres, ESA PSA, JAXA DARTS, and ISRO ISSDC PRADAN planetary science archives.",
        "# Software License: MIT License (Keshav Aggarwal, SPL, VSSC, ISRO)",
    ]
    for p in profiles:
        lines.append(f"# Mission: {p.get('mission_id')}, Obs: {p.get('observation_id')}, Lat: {p.get('latitude')}, Lon: {p.get('longitude')}")

    header = ["altitude_km", f"composite_mean_{var_name}", "composite_std", "plus_1sigma", "minus_1sigma"]
    for p in profiles:
        header.append(f"{p.get('mission_id')}_{p.get('observation_id')}")
    lines.append(",".join(header))

    for i, z in enumerate(grid):
        row = [
            f"{z:.2f}",
            f"{mean_v[i]:.4f}" if i < len(mean_v) and mean_v[i] is not None else "",
            f"{std_v[i]:.4f}" if i < len(std_v) and std_v[i] is not None else "",
            f"{plus_sigma[i]:.4f}" if i < len(plus_sigma) and plus_sigma[i] is not None else "",
            f"{minus_sigma[i]:.4f}" if i < len(minus_sigma) and minus_sigma[i] is not None else "",
        ]
        for p in profiles:
            s = p.get("interpolated_series", [])
            val = s[i] if i < len(s) and s[i] is not None else ""
            row.append(f"{val:.4f}" if isinstance(val, (int, float)) else "")
        lines.append(",".join(row))

    return "\n".join(lines)

