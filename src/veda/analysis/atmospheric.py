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
    _ionosphere_diagnostics(profile, z)

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

    # 6. Cold-point tropopause (where the body has one) and gravity waves
    try:
        from .wave_and_stability import extract_gravity_wave_activity, tropopause_for_body
        profile.raw_attributes.update(tropopause_for_body(body.id, z, t_k, p_hpa))

        gw = extract_gravity_wave_activity(z, t_k, gz, derived.get("buoyancy_freq_sq"))
        if gw.get("t_prime_k"):
            derived["t_prime"] = np.array([np.nan if x is None else x for x in gw["t_prime_k"]])
            derived["wave_potential_energy"] = np.array([np.nan if x is None else x for x in gw["potential_energy_j_kg"]])
            profile.raw_attributes["gw_mean_ep_j_kg"] = gw.get("mean_potential_energy")
            profile.raw_attributes["gw_dominant_wavelength_km"] = gw.get("dominant_wavelength_km")
    except Exception:
        pass

    return derived


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
PROFILE_DIAGNOSTICS: Dict[str, Tuple[str, str]] = {
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


def _group_composites(mat: np.ndarray, summaries: List[Dict[str, Any]], log_like: bool, by: str,
                      width: float, sig) -> List[Dict[str, Any]]:
    """Composite mean and spread of each group of profiles (climatology bins).  Same rules
    as the overall composite: the spread where two or more of the group's profiles
    overlap, the mean where at least half of them (and at least one) do."""
    import warnings
    keys = [_group_key(s, by, width) for s in summaries]
    out = []
    for key in sorted({k for k in keys if k is not None}, key=lambda k: k[0]):
        idx = [i for i, k in enumerate(keys) if k == key]
        sub = mat[idx]
        n = np.sum(np.isfinite(sub), axis=0)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(sub, axis=0)
            s = np.nanstd(sub, axis=0, ddof=1) if len(idx) > 1 else np.full(sub.shape[1], np.nan)
        s = np.where(n >= 2, s, np.nan)
        m = np.where(n >= max(1, int(np.ceil(0.5 * len(idx)))), m, np.nan)
        if log_like:
            mean, lo, hi = np.exp(m), np.exp(m - s), np.exp(m + s)
        else:
            mean, lo, hi = m, m - s, m + s
        out.append({"label": key[1], "n": len(idx), "observation_ids": [summaries[i]["observation_id"] for i in idx],
                    "mean": [sig(x) for x in mean], "plus_1sigma": [sig(x) for x in hi],
                    "minus_1sigma": [sig(x) for x in lo], "profiles_per_level": [int(x) for x in n]})
    unknown = sum(1 for k in keys if k is None)
    if unknown:
        out.append({"label": f"{unknown} profile{'s' if unknown > 1 else ''} without {by}", "n": unknown,
                    "observation_ids": [summaries[i]["observation_id"] for i, k in enumerate(keys) if k is None],
                    "mean": [], "plus_1sigma": [], "minus_1sigma": [], "profiles_per_level": [], "ungrouped": True})
    return out


# Variables compared in log space (they change by orders of magnitude with height)
LOG_VARIABLES = {"pressure_hpa", "density", "density_measured", "number_density_m3", "electron_density_cm3"}


def _compared_variable(p: ObservationProfile, variable_name: str) -> Optional[np.ndarray]:
    """The values of ``variable_name`` in profile ``p`` (archived or derived), or None."""
    if variable_name in ("temperature_k", "temperature_c", "pressure_hpa", "refractivity", "electron_density_cm3"):
        v = getattr(p, variable_name)
    else:
        v = p.derived.get(variable_name)
    return None if v is None else np.asarray(v, dtype=float)


def compare_profiles_on_body(
    profiles: List[ObservationProfile],
    body: BodyInfo,
    altitude_step_km: float = 0.5,
    variable_name: str = "temperature_k",
    group_by: str = "",
    group_width: float = 0.0,
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
    # log space (geometric mean, spread as a factor) when every value of every profile
    # is positive.  This is decided before any profile is interpolated: deciding it
    # profile by profile mixed log and linear values in one composite.
    log_like = variable_name in LOG_VARIABLES and not any(
        np.any(v[np.isfinite(v)] <= 0)
        for v in (_compared_variable(p, variable_name) for p in valid_profiles) if v is not None)

    for p in valid_profiles:
        v = _compared_variable(p, variable_name)

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
            # the mission a loaded file comes from, as the user said (for legends and colours)
            "mission_label": (p.raw_attributes or {}).get("SOURCE_MISSION") or p.mission_id,
            **{k: v for k, v in _geom(p).items() if k in ("lst", "sza", "ls")},
            "diagnostics": {k: v for k, v in profile_diagnostics(p).items() if v is not None},
            "interpolated_series": v_interp,
        })

    if not interpolated_matrix:
        return _empty_comparison(body, variable_name, [round(float(z), 2) for z in z_grid])

    mat = np.array(interpolated_matrix)  # shape: (n_profiles, n_grid)
    n_per_level = np.sum(np.isfinite(mat), axis=0)
    mean_min = max(2, int(np.ceil(0.5 * len(interpolated_matrix))))
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
    groups = _group_composites(mat, profile_summaries, log_like, group_by, group_width, sig) if group_by else []

    return {
        "group_by": group_by or "",
        "group_width": group_width,
        "groups": groups,
        "averaging": "geometric mean and 1-sigma factor (log space)" if log_like else "arithmetic mean and 1-sigma (sample)",
        "profiles_per_level": [int(n) for n in n_per_level],
        "vertical_reference_warning": _vertical_reference_warning(profile_summaries),
        "body_id": body.id,
        "body_name": body.name,
        "variable_name": variable_name,
        "grid_km": [round(float(z), 2) for z in z_grid],
        # The mean of whichever profiles reach a level jumps where that number changes
        # (one profile alone is just that profile), so it is given only where at least
        # two profiles and at least half of them overlap; profiles_per_level says how many.
        "composite_mean": [sig(x) if n >= mean_min else None for x, n in zip(mean_v, n_per_level)],
        "composite_std": [sig(x) for x in std_v],
        "composite_plus_1sigma": [sig(x) for x in hi_v],
        "composite_minus_1sigma": [sig(x) for x in lo_v],
        "profile_count": len(profile_summaries),
        "profiles": profile_summaries,
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
    track_cols = [k for k in _TRACK if any(k in (p.track or {}) for p in profiles)]

    lines = [
        f"# VEDA profiles at their archived levels (long format): {len(profiles)} profiles"
        + (f", body={body.name}" if body else ""),
        "# One row per profile and level. Archived quantities are as published, converted to the units in the column names;",
        "# the other quantities are derived by VEDA (see the User Guide). sigma_* columns are 1-sigma uncertainties.",
        "# altitude_km is above the body's reference radius; profile_* columns are each profile's header values,",
        "# level_* columns the position of each level along the ray path where the archive gives it.",
        f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA), MIT License",
    ]
    from ..core.registry import get_variable_info
    extra_units = {"dtheta_dz": "K/km", "number_density_m3": "m^-3"}
    unit_of = (lambda k: (get_variable_info(k) or {}).get("units") or extra_units.get(k))
    units = [f"{k}={unit_of(k)}" for k in var_cols if unit_of(k)]
    if units:
        lines.append("# units: " + "; ".join(units) + " (sigma_* as their quantity)")
    for p in profiles:
        if p.provenance:
            lines.append(f"# {p.observation_id}: {p.provenance.archive_source}, {p.provenance.original_file}"
                         + (f", {p.provenance.doi_or_citation}" if p.provenance.doi_or_citation else ""))
    header = (["mission", "instrument", "observation_id", "time_utc", "profile_latitude_deg", "profile_longitude_deg",
               "profile_lst_h", "profile_sza_deg", "profile_ls_deg", "altitude_km"]
              + var_cols + [f"sigma_{k}" for k in sigma_cols]
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
        cols += [arr((p.track or {}).get(k), n) for k in track_cols]
        for i in range(n):
            if not np.isfinite(z[i]):
                continue
            lines.append(",".join(fixed + [f"{z[i]:.4f}"] + [_csv_num(c[i]) if c is not None else "" for c in cols]))
    return "\n".join(lines) + "\n"


def export_comparison_to_csv(comparison: Dict[str, Any]) -> str:
    """The comparison as on screen: gridded composite, group composites and every
    profile, with a header describing each profile (time, position, geometry)."""
    from ..core.registry import get_variable_info
    body_name = comparison.get("body_name", "Body")
    var_name = comparison.get("variable_name", "variable")
    units = (get_variable_info(var_name) or {}).get("units", "")
    grid = comparison.get("grid_km", [])
    profiles = comparison.get("profiles", [])
    # group labels in plain ASCII ("Latitude 0 to 30 deg"): spreadsheets misread the degree sign
    groups = [{**g, "label": g["label"].replace("°", " deg")}
              for g in comparison.get("groups") or [] if not g.get("ungrouped") and g.get("mean")]

    lines = [
        f"# VEDA comparison: body={body_name}, variable={var_name}" + (f" [{units}]" if units else ""),
        f"# profiles={len(profiles)}, averaging={comparison.get('averaging', '')}"
        + (f", grouped by {comparison.get('group_by')}" if groups else ""),
        "# Profiles from the official mission archives (see each product for its source); means and spreads computed by VEDA.",
        "# Altitude above the body's reference radius (km)."
        + (f" Note: {comparison['vertical_reference_warning']}" if comparison.get("vertical_reference_warning") else ""),
        f"# Processed with VEDA {__version__} (https://github.com/jovian-explorer/VEDA), MIT License",
    ]
    diag_keys = list(comparison.get("diagnostic_labels") or {})
    lines.append("# column, mission, instrument, observation, time_utc, latitude_deg, longitude_deg, lst_h, sza_deg, ls_deg"
                 + "".join(f", {k}" for k in diag_keys))
    cols = []
    for p in profiles:
        col = f"{p.get('mission_label') or p.get('mission_id')}_{p.get('observation_id')}"
        cols.append(col)
        lines.append("# " + ", ".join(_csv_field(x) for x in (
            col, p.get("mission_label") or p.get("mission_id"), p.get("instrument"), p.get("observation_id"),
            p.get("time_utc"), _csv_num(p.get("latitude")), _csv_num(p.get("longitude")),
            _csv_num(p.get("lst")), _csv_num(p.get("sza")), _csv_num(p.get("ls")),
            *(_csv_num((p.get("diagnostics") or {}).get(k)) for k in diag_keys))))
    for g in groups:
        lines.append(f"# group {_csv_field(g['label'])}: n={g['n']}, profiles={' '.join(g['observation_ids'])}")

    header = ["altitude_km", f"composite_mean_{var_name}", "composite_std", "plus_1sigma", "minus_1sigma", "profiles_at_level"]
    for g in groups:
        header += [f"{g['label']} mean", f"{g['label']} plus_1sigma", f"{g['label']} minus_1sigma"]
    header += cols
    lines.append(",".join(_csv_field(h) for h in header))

    def at(seq, i):
        return seq[i] if seq and i < len(seq) else None
    n_level = comparison.get("profiles_per_level") or []
    for i, z in enumerate(grid):
        row = [f"{z:.3f}"] + [_csv_num(at(comparison.get(k), i)) for k in
                              ("composite_mean", "composite_std", "composite_plus_1sigma", "composite_minus_1sigma")]
        row.append(str(at(n_level, i)) if at(n_level, i) is not None else "")
        for g in groups:
            row += [_csv_num(at(g["mean"], i)), _csv_num(at(g["plus_1sigma"], i)), _csv_num(at(g["minus_1sigma"], i))]
        row += [_csv_num(at(p.get("interpolated_series"), i)) for p in profiles]
        lines.append(",".join(row))

    return "\n".join(lines) + "\n"

