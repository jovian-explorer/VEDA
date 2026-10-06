"""Uncertainties of derived quantities from the archived 1-sigma values (analysis/uncertainty.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis import uncertainty as unc
from veda.analysis.atmospheric import (_gradient_nan_safe, compare_profiles_on_body, compute_atmospheric_diagnostics,
                                       export_comparison_to_csv, export_profile_to_csv)
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def _mars_profile(dz=0.5, sigma_t=1.0, sigma_p_rel=0.01, oid="p1", seed=7):
    """A smooth profile plus independent errors of the stated size (as a profile whose
    errors are independent looks: the scatter between levels matches the 1-sigma)."""
    mars = get_body("mars")
    rng = np.random.default_rng(seed)
    z = np.arange(0.0, 40.0 + 1e-9, dz)
    t = 210.0 - 1.5 * z + 3.0 * np.sin(z / 3.0) + rng.normal(0.0, sigma_t, z.size)
    h = mars.gas_constant_r * 200.0 / mars.surface_gravity / 1000.0
    p = 6.1 * np.exp(-z / h) * (1.0 + rng.normal(0.0, sigma_p_rel, z.size))
    prof = ObservationProfile(observation_id=oid, mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="2005-01-01T00:00:00", latitude=10.0, longitude=20.0,
                              altitude_km=z, temperature_k=t, pressure_hpa=p,
                              uncertainty={"temperature_k": np.full(z.size, sigma_t), "pressure_hpa": p * sigma_p_rel})
    prof.derived = compute_atmospheric_diagnostics(prof, mars)
    return prof, mars


def test_single_level_quantities_follow_the_analytic_formulas():
    prof, mars = _mars_profile()
    t, p, u = prof.temperature_k, prof.pressure_hpa, prof.uncertainty
    np.testing.assert_allclose(u["scale_height"], prof.derived["scale_height"] / t, rtol=1e-9)
    np.testing.assert_allclose(u["density"], prof.derived["density"] * np.sqrt((1 / t) ** 2 + 0.01 ** 2), rtol=1e-9)
    kappa = mars.gas_constant_r / mars.isobaric_heat_capacity_cp
    np.testing.assert_allclose(u["potential_temperature"],
                               prof.derived["potential_temperature"] * np.sqrt((1 / t) ** 2 + (kappa * 0.01) ** 2), rtol=1e-9)
    np.testing.assert_allclose(u["speed_of_sound"], prof.derived["speed_of_sound"] / (2 * t), rtol=1e-9)


def test_lapse_rate_uncertainty_matches_central_differences_of_independent_errors():
    """Central difference over 2 dz of independent errors sigma: sigma sqrt(2) / (2 dz)."""
    prof, _ = _mars_profile(dz=0.5, sigma_t=1.0)
    s = prof.uncertainty["lapse_rate"][1:-1]
    expected = np.sqrt(2.0) / (2 * 0.5)
    assert np.median(s) == pytest.approx(expected, rel=0.08)
    assert "buoyancy_freq_sq" in prof.uncertainty and "dtheta_dz" in prof.uncertainty


def test_correlated_errors_make_derivatives_more_certain():
    prof, mars = _mars_profile(dz=0.5, sigma_t=1.0)
    corr = unc.propagate(prof, mars, prof.derived, mars.surface_gravity * np.ones(prof.altitude_km.size), corr_km=5.0)
    assert np.median(corr["lapse_rate"][1:-1]) < 0.3 * np.sqrt(2.0)
    np.testing.assert_allclose(corr["scale_height"], prof.derived["scale_height"] / prof.temperature_k, rtol=1e-9)


def test_gradient_operator_is_the_gradient_used_for_the_values():
    rng = np.random.default_rng(1)
    z = np.sort(rng.uniform(0, 30, 300))
    z[50] = z[51]                                   # a repeated altitude
    z[100:110] = z[100] + np.arange(10) * 0.004     # samples closer than the 50 m minimum half window
    v = np.cos(z) + rng.normal(0, 0.1, z.size)
    v[7] = np.nan
    ok = np.isfinite(v)
    op = unc.gradient_operator(z, ok)
    np.testing.assert_allclose(op @ v[ok], _gradient_nan_safe(z, v)[ok], rtol=1e-10, atol=1e-12)


def test_temperature_from_density_uncertainty():
    """A 2 % independent density error gives about 2 % in T near the bottom (p there is an
    integral over many levels, so T = p / (rho R) carries the error of rho), and less at the
    top, where T is the boundary temperature fitted to the top 20 % of the levels."""
    mars = get_body("mars")
    z = np.arange(90.0, 160.0, 0.5)
    rho = 1e-7 * np.exp(-(z - 90.0) / 8.0) * np.exp(np.random.default_rng(3).normal(0.0, 0.02, z.size))
    prof = ObservationProfile(observation_id="acc", mission_id="mro", body_id="mars", instrument="ACC",
                              time_utc="2006-05-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                              uncertainty={"density_measured": 0.02 * rho})
    prof.derived["density_measured"] = rho
    prof.derived.update(compute_atmospheric_diagnostics(prof, mars))
    t, s = prof.derived["temperature_from_density"], prof.uncertainty["temperature_from_density"]
    assert s[0] / t[0] == pytest.approx(0.02, rel=0.25)
    assert 0 < s[-1] / t[-1] < 0.02 and np.isfinite(s).all()
    assert "pressure_from_density" in prof.uncertainty


def test_uncertainties_reach_the_comparison_and_the_exports():
    a, mars = _mars_profile(oid="a")
    b, _ = _mars_profile(oid="b", sigma_t=2.0)
    comp = compare_profiles_on_body([a, b], mars, altitude_step_km=1.0, variable_name="scale_height")
    sig = comp["profiles"][1]["interpolated_sigma"]
    h = comp["profiles"][1]["interpolated_series"]
    assert sig[10] == pytest.approx(2.0 * h[10] / np.interp(comp["grid_km"][10], b.altitude_km, b.temperature_k), rel=1e-3)
    text = export_comparison_to_csv(comp)
    header = next(line for line in text.splitlines() if line.startswith("altitude_km,"))
    assert "sigma_mex_a" in header and "sigma_mex_b" in header
    one = export_profile_to_csv(a)
    assert "sigma_scale_height" in one and "sigma_lapse_rate" in one


def test_profiles_without_uncertainties_get_none():
    prof, mars = _mars_profile()
    prof.uncertainty = {}
    prof.derived = compute_atmospheric_diagnostics(prof, mars)
    assert prof.uncertainty == {}


def _flat(oid, t0, sigma, n=41):
    z = np.arange(0.0, n * 1.0, 1.0)
    return ObservationProfile(observation_id=oid, mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="2005-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                              temperature_k=np.full(n, t0), uncertainty={"temperature_k": np.full(n, sigma)})


def test_composite_standard_error_and_effective_number():
    mars = get_body("mars")
    profs = [_flat("a", 200.0, 1.0), _flat("b", 210.0, 1.0), _flat("c", 220.0, 1.0), _flat("d", 230.0, 1.0)]
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0)
    s = np.std([200, 210, 220, 230], ddof=1)
    assert comp["composite_sem"][5] == pytest.approx(s / 2.0, rel=1e-5)
    assert comp["n_effective"][5] == 4.0
    assert comp["composite_plus_sem"][5] == pytest.approx(215.0 + s / 2.0, rel=1e-6)
    assert comp["weighting"] == "equal"


def test_inverse_variance_weighting():
    """Weights 1/sigma^2: 200 +- 1 and 230 +- 3 give (200 + 230 / 9) / (1 + 1 / 9) = 203 K;
    n_eff = (1 + 1/9)^2 / (1 + 1/81) = 1.22."""
    mars = get_body("mars")
    profs = [_flat("a", 200.0, 1.0), _flat("b", 230.0, 3.0)]
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, weighting="inverse_variance")
    assert comp["composite_mean"][3] == pytest.approx(203.0, rel=1e-6)
    assert comp["n_effective"][3] == pytest.approx((1 + 1 / 9) ** 2 / (1 + 1 / 81), abs=0.01)
    assert "inverse-variance" in comp["averaging"]
    text = export_comparison_to_csv(comp)
    assert "composite_sem" in text and "n_effective" in text
    nosig = [_flat("a", 200.0, 1.0), _flat("b", 230.0, 3.0)]
    for pr in nosig:
        pr.uncertainty = {}
    assert "error" in compare_profiles_on_body(nosig, mars, altitude_step_km=1.0, weighting="inverse_variance")


def test_inverse_variance_in_log_space_uses_relative_errors():
    mars = get_body("mars")
    z = np.arange(0.0, 20.0, 1.0)
    profs = []
    for oid, p0, rel in (("a", 6.0, 0.01), ("b", 7.0, 0.10)):
        p = p0 * np.exp(-z / 11.0)
        profs.append(ObservationProfile(observation_id=oid, mission_id="mex", body_id="mars", instrument="MaRS",
                                        time_utc="2005-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                                        pressure_hpa=p, uncertainty={"pressure_hpa": rel * p}))
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, variable_name="pressure_hpa",
                                    weighting="inverse_variance")
    w = np.array([1 / 0.01 ** 2, 1 / 0.10 ** 2])
    expected = np.exp((w[0] * np.log(6.0) + w[1] * np.log(7.0)) / w.sum())
    assert comp["composite_mean"][0] == pytest.approx(expected, rel=1e-5)


def test_bootstrap_interval_of_the_mean():
    """For many profiles drawn from a normal distribution the 95 % bootstrap interval is
    close to mean +- 1.96 SEM; it is reproducible, and it follows the weights."""
    mars = get_body("mars")
    rng = np.random.default_rng(3)
    temps = rng.normal(200.0, 10.0, 80)
    profs = [_flat(f"p{i}", t, 1.0) for i, t in enumerate(temps)]
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0)
    m, sem = comp["composite_mean"][5], comp["composite_sem"][5]
    assert comp["composite_ci95_low"][5] == pytest.approx(m - 1.96 * sem, abs=0.35 * sem)
    assert comp["composite_ci95_high"][5] == pytest.approx(m + 1.96 * sem, abs=0.35 * sem)
    again = compare_profiles_on_body(profs, mars, altitude_step_km=1.0)
    assert again["composite_ci95_low"] == comp["composite_ci95_low"]
    assert "ci95_low" in export_comparison_to_csv(comp)


def test_bootstrap_interval_of_group_means_and_skewed_samples():
    mars = get_body("mars")
    temps = [200.0] * 9 + [260.0]                  # one warm outlier: the interval is skewed
    profs = [_flat(f"p{i}", t, 1.0) for i, t in enumerate(temps)]
    for i, pr in enumerate(profs):
        pr.latitude = 10.0 if i < 5 else 50.0
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="latitude", group_width=30.0)
    m = comp["composite_mean"][5]
    assert comp["composite_ci95_high"][5] - m > m - comp["composite_ci95_low"][5]
    g = [x for x in comp["groups"] if not x.get("ungrouped")]
    assert g[0]["ci95_low"][5] == pytest.approx(200.0) and g[0]["ci95_high"][5] == pytest.approx(200.0)
    assert g[1]["ci95_high"][5] > g[1]["ci95_low"][5]


def test_batched_density_retrieval_equals_the_single_one():
    from veda.analysis.hydrostatic import temperature_from_density, temperature_from_density_draws
    rng = np.random.default_rng(5)
    z = np.arange(90.0, 160.0, 0.5)
    rho = 1e-7 * np.exp(-(z - 90.0) / 8.0) * (1 + 0.05 * rng.standard_normal(z.size))
    g = 3.7 * (3389.5 / (3389.5 + z)) ** 2
    sig = 0.03 * rho
    one = temperature_from_density(z, rho, g, 191.2, rho_sigma=sig)
    many = temperature_from_density_draws(z, np.vstack([rho, rho * 1.01]), g, 191.2, rho_sigma=sig)
    np.testing.assert_allclose(many["temperature_k"][0], one["temperature_k"], rtol=1e-9)
    np.testing.assert_allclose(many["pressure_pa"][0], one["pressure_pa"], rtol=1e-9)
    np.testing.assert_allclose(many["temperature_k"][1], one["temperature_k"], rtol=1e-9)   # a constant factor cancels


def test_noise_level_of_the_hydrostatic_check():
    """A hydrostatic profile with 1 % independent pressure errors: the median departure
    expected from the errors alone is about 0.67 % (median of |N(0, 1 %)|), the largest
    a few percent; with 0.1 % errors both are ten times smaller."""
    levels = {}
    for rel in (0.01, 0.001):
        prof, mars = _mars_profile(dz=0.5, sigma_t=1e-6, sigma_p_rel=rel)
        a = prof.raw_attributes
        levels[rel] = (a["hydrostatic_noise_median_pct"], a["hydrostatic_noise_max_pct"])
    assert levels[0.01][0] == pytest.approx(0.67, rel=0.25)
    assert levels[0.001][0] == pytest.approx(levels[0.01][0] / 10, rel=0.1)
    assert 1.5 < levels[0.01][1] < 6.0


def test_layer_mean_sigma_counts_the_correlation_made_by_interpolation():
    """Grid values interpolated between the same two levels share their errors: the
    comparison gives each profile a correlation length so that the 1-sigma of a layer
    mean (Altitude cut) matches the exact propagation A C A^T."""
    mars = get_body("mars")
    z = np.arange(0.0, 40.0 + 1e-9, 2.0)
    s = 0.5 + 0.05 * z
    prof = ObservationProfile(observation_id="c", mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="2005-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                              temperature_k=200.0 - z + np.random.default_rng(5).normal(0.0, s),
                              uncertainty={"temperature_k": s})
    comp = compare_profiles_on_body([prof], mars, altitude_step_km=0.25, variable_name="temperature_k")
    p = comp["profiles"][0]
    big_l = p["sigma_correlation_km"]
    l_levels = unc.error_correlation_from_scatter(z, prof.temperature_k, s)
    assert l_levels < 1.0                                   # independent errors: about none
    assert big_l == pytest.approx(np.hypot(l_levels, 2.0 / np.sqrt(3.0)), rel=1e-3)
    grid = np.asarray(comp["grid_km"], dtype=float)
    sg = np.array([np.nan if v is None else v for v in p["interpolated_sigma"]])
    k = np.clip(np.searchsorted(z, grid, side="right") - 1, 0, z.size - 2)
    w = (grid - z[k]) / (z[k + 1] - z[k])
    a = np.zeros((grid.size, z.size))
    a[np.arange(grid.size), k] = 1 - w
    a[np.arange(grid.size), k + 1] = w
    exact_cov = a @ (np.outer(s, s) * np.exp(-(z[:, None] - z[None, :]) ** 2 / (2 * max(l_levels, 1e-9) ** 2))) @ a.T
    assert np.allclose(sg, np.sqrt(np.diag(exact_cov)), rtol=1e-3)      # midway: s / sqrt(2), not s
    for lo, hi in ((10.0, 15.0), (20.0, 30.0)):
        sl = (grid >= lo) & (grid <= hi)
        m = sl.sum()
        exact = np.sqrt(exact_cov[np.ix_(sl, sl)].sum()) / m
        gz, ss = grid[sl], sg[sl]
        r = np.exp(-(gz[:, None] - gz[None, :]) ** 2 / (2 * big_l ** 2))
        model = np.sqrt(ss @ r @ ss) / m                     # what the Altitude cut computes
        independent = np.sqrt(np.sum(ss ** 2)) / m
        assert model == pytest.approx(exact, rel=0.15)
        assert independent < 0.6 * exact


def _correlated_noise(z, length, sigma, seed):
    rng = np.random.default_rng(seed)
    c = np.exp(-(z[:, None] - z[None, :]) ** 2 / (2 * length ** 2)) + 1e-10 * np.eye(z.size)
    return np.linalg.cholesky(c) @ rng.standard_normal(z.size) * sigma


def test_error_correlation_found_from_the_scatter_of_the_values():
    """Independent errors: no correlation length; Gaussian-correlated errors: their length;
    a smooth profile with large error bars: errors that cannot be independent."""
    z = np.arange(0.0, 60.0, 0.25)
    s = np.full(z.size, 2.0)
    smooth = 200.0 - z
    found_indep = [unc.error_correlation_from_scatter(z, smooth + np.random.default_rng(k).normal(0, 2.0, z.size), s)
                   for k in range(10)]
    assert np.median(found_indep) < 0.25 * 0.5                # below half the spacing: no effect
    for length in (0.5, 1.0, 2.0):
        found = [unc.error_correlation_from_scatter(z, smooth + _correlated_noise(z, length, 2.0, k), s)
                 for k in range(10)]
        assert np.median(found) == pytest.approx(length, rel=0.2)
    assert unc.error_correlation_from_scatter(z, smooth, s) > 10.0
    assert unc.error_correlation_from_scatter(z[:8], smooth[:8], s[:8]) == 0.0     # too few levels to say


def test_correlation_lowers_the_sigma_of_differences_and_raises_that_of_sums():
    """The same profile with its errors correlated over 3 km (scatter smaller than the error
    bars): lapse rate and the temperature from density get smaller, the pressure integrated
    from density larger than with independent errors."""
    mars = get_body("mars")
    z = np.arange(90.0, 160.0, 0.5)
    base = 1e-7 * np.exp(-(z - 90.0) / 8.0)
    out = {}
    for name, noise in (("indep", np.random.default_rng(3).normal(0.0, 0.02, z.size)),
                        ("corr", _correlated_noise(z, 3.0, 0.02, 3))):
        prof = ObservationProfile(observation_id=name, mission_id="mro", body_id="mars", instrument="ACC",
                                  time_utc="2006-05-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                                  uncertainty={"density_measured": 0.02 * base})
        prof.derived["density_measured"] = base * np.exp(noise)
        prof.derived.update(compute_atmospheric_diagnostics(prof, mars))
        out[name] = (prof.uncertainty, prof.raw_attributes["error_correlation_density_km"])
    assert out["indep"][1] < 0.5 and out["corr"][1] == pytest.approx(3.0, rel=0.3)
    mid = slice(20, 100)
    assert np.median(out["corr"][0]["temperature_from_density"][mid]) < 0.9 * np.median(out["indep"][0]["temperature_from_density"][mid])
    assert np.median(out["corr"][0]["pressure_from_density"][mid] / out["indep"][0]["pressure_from_density"][mid]) > 1.3

    t_ind, _ = _mars_profile(dz=0.5, sigma_t=1.0, oid="i")
    t_cor, _ = _mars_profile(dz=0.5, sigma_t=1e-9, oid="c")
    t_cor.temperature_k = t_cor.temperature_k + _correlated_noise(t_cor.altitude_km, 3.0, 1.0, 4)
    t_cor.uncertainty = {"temperature_k": np.ones(t_cor.altitude_km.size), "pressure_hpa": t_cor.uncertainty["pressure_hpa"]}
    t_cor.derived = compute_atmospheric_diagnostics(t_cor, mars)
    assert np.median(t_cor.uncertainty["lapse_rate"]) < 0.3 * np.median(t_ind.uncertainty["lapse_rate"])
