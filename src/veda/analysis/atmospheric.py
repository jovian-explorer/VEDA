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
    # (altitudes below the reference level, e.g. the Hellas basin below the Mars reference sphere or the
    # Galileo probe below 1 bar, are valid: gravity is slightly larger there)
    gz = g0 * (r_body / np.maximum(r_body + z, 1e-3 * r_body)) ** 2

    # 3. Scale height H = R_spec T / g(z) (km) and speed of sound with cp(T)
    from .thermo import cp_model, heat_capacity
    r_spec = body.gas_constant_r
    cp_t = heat_capacity(body, t_k)                 # J/(kg K), temperature dependent for CO2/N2 atmospheres
    profile.raw_attributes["cp_model"] = cp_model(body)
    with np.errstate(invalid="ignore", divide="ignore"):
        h_scale = (r_spec * t_k) / (gz * 1000.0)
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
            # Mass density rho = P / (R * T) in kg/m^3 (P in Pa = hPa * 100)
            rho = (p_hpa * 100.0) / (r_spec * t_k)

        derived["potential_temperature"] = theta
        derived["dtheta_dz"] = _gradient_nan_safe(z, theta)
        derived["density"] = rho

    # 6. Ionospheric VTEC & F2 peak diagnostics if electron density is present
    if profile.electron_density_cm3 is not None and profile.electron_density_cm3.size >= 2:
        try:
            from .advanced_science import compute_vtec
            vtec_res = compute_vtec(z, profile.electron_density_cm3)
            profile.raw_attributes["vtec_tecu"] = vtec_res.get("vtec_tecu")
            profile.raw_attributes["hmf2_km"] = vtec_res.get("peak_alt_km")
            profile.raw_attributes["nmf2_cm3"] = vtec_res.get("peak_density_cm3")
        except Exception:
            pass

    # 7. Tropopause, Gravity Waves, and Ionospheric Chapman Modeling
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


# Variables compared in log space (they change by orders of magnitude with height)
LOG_VARIABLES = {"pressure_hpa", "density", "density_measured", "number_density_m3", "electron_density_cm3"}


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
        return _empty_comparison(body, variable_name)

    # Determine altitude span covering the observations
    valid_profiles = [p for p in profiles if p is not None]
    if not valid_profiles:
        return _empty_comparison(body, variable_name)

    all_z = [p.altitude_km for p in valid_profiles if p.altitude_km is not None and p.altitude_km.size > 0]
    if not all_z:
        return _empty_comparison(body, variable_name)

    z_mins = [float(np.nanmin(z)) for z in all_z if np.isfinite(z).any()]
    z_maxs = [float(np.nanmax(z)) for z in all_z if np.isfinite(z).any()]
    if not z_mins or not z_maxs:
        return _empty_comparison(body, variable_name)

    # Grid levels on whole multiples of the step (20.0, 20.5 km ...), covering every
    # profile; negative altitudes (below the reference level) are kept.
    grid_lo = np.ceil(float(np.min(z_mins)) / altitude_step_km - 1e-9) * altitude_step_km
    grid_hi = np.floor(float(np.max(z_maxs)) / altitude_step_km + 1e-9) * altitude_step_km
    if grid_hi <= grid_lo:
        grid_hi = grid_lo + altitude_step_km

    num_steps = int(round((grid_hi - grid_lo) / altitude_step_km)) + 1
    z_grid = np.round(grid_lo + altitude_step_km * np.arange(max(num_steps, 2)), 6)

    interpolated_matrix = []
    profile_summaries = []
    # Quantities that vary exponentially with height are interpolated and averaged in
    # log space (geometric mean, spread as a factor), when every value is positive.
    log_like = variable_name in LOG_VARIABLES

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
        if log_like and np.any(v_clean <= 0):
            log_like = False                  # e.g. noisy electron densities: fall back to linear

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
            "altitude_reference": (p.raw_attributes or {}).get("ALTITUDE_REFERENCE", ""),
            "interpolated_series": v_interp,
        })

    if not interpolated_matrix:
        return _empty_comparison(body, variable_name, [round(float(z), 2) for z in z_grid])

    mat = np.array(interpolated_matrix)  # shape: (n_profiles, n_grid)
    if log_like and len(interpolated_matrix) != len(profile_summaries):
        log_like = False
    n_per_level = np.sum(np.isfinite(mat), axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_f = np.nanmean(mat, axis=0)
            std_f = np.nanstd(mat, axis=0, ddof=1) if mat.shape[0] > 1 else np.full(mat.shape[1], np.nan)
    std_f = np.where(n_per_level >= 2, std_f, np.nan)        # no spread from a single profile
    if log_like:
        mean_v, lo_v, hi_v = np.exp(mean_f), np.exp(mean_f - std_f), np.exp(mean_f + std_f)
        std_v = np.full_like(mean_v, np.nan)                  # spread is a factor, see lo/hi
        for s in profile_summaries:
            s["interpolated_series"] = np.exp(s["interpolated_series"])
    else:
        mean_v, std_v = mean_f, std_f
        lo_v, hi_v = mean_f - std_f, mean_f + std_f
    for s in profile_summaries:
        s["interpolated_series"] = [None if not np.isfinite(x) else float(f"{x:.6g}")
                                    for x in s["interpolated_series"]]
    sig = (lambda x: None if not np.isfinite(x) else float(f"{x:.6g}"))

    return {
        "averaging": "geometric mean and 1-sigma factor (log space)" if log_like else "arithmetic mean and 1-sigma (sample)",
        "profiles_per_level": [int(n) for n in n_per_level],
        "vertical_reference_warning": _vertical_reference_warning(profile_summaries),
        "body_id": body.id,
        "body_name": body.name,
        "variable_name": variable_name,
        "grid_km": [round(float(z), 2) for z in z_grid],
        "composite_mean": [sig(x) for x in mean_v],
        "composite_std": [sig(x) for x in std_v],
        "composite_plus_1sigma": [sig(x) for x in hi_v],
        "composite_minus_1sigma": [sig(x) for x in lo_v],
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
        lines.append(f"# Source file: {profile.provenance.original_file} ({profile.provenance.product_level})")
        lines.append(f"# Citation: {profile.provenance.doi_or_citation}")
    lines.append("# Archived columns are as published, converted to the units in the header; other columns are derived by VEDA.")
    lines.append(f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA), MIT License")

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
        "# Profiles from the official mission archives (see each product for its source); mean and spread computed by VEDA.",
        f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA), MIT License",
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

