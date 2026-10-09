"""Error-weighted vertical smoothing with propagated uncertainties (analysis/smoothing.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis.smoothing import apply_weights, smooth_on_grid
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


@pytest.mark.parametrize("corr_km", [0.0, 0.3, 1.0])
def test_smoothed_sigma_matches_monte_carlo(corr_km):
    """The 1-sigma of the smoothed values, sum_jk a_ij a_ik sigma_j sigma_k r(z_j - z_k), is
    the scatter of smoothed noise drawn with that correlation (to the 3 % that 3000 draws
    allow), at the ends of the profile too."""
    rng = np.random.default_rng(7)
    step, n = 0.1, 240
    z = np.arange(n) * step
    sig = 1.0 + 0.5 * np.sin(z / 3.0) ** 2
    lag = z[:, None] - z[None, :]
    r = np.exp(-lag ** 2 / (2 * corr_km ** 2)) if corr_km > 0 else np.eye(n)
    chol = np.linalg.cholesky(r * sig[:, None] * sig[None, :] + 1e-12 * np.eye(n))
    draws = (chol @ rng.standard_normal((n, 3000))).T
    out = smooth_on_grid(np.zeros(n), sig, step, 1.0, corr_km)
    smoothed = np.array([apply_weights(d, out["weights"], out["offsets"]) for d in draws])
    np.testing.assert_allclose(out["sigma"], smoothed.std(axis=0), rtol=0.06)
    assert np.median(out["sigma"][20:-20] / sig[20:-20]) < (0.5 if corr_km == 0 else 0.98)


def test_smoothing_keeps_constant_and_linear_profiles_and_weights_by_errors():
    z = np.arange(0.0, 20.0, 0.25)
    flat = smooth_on_grid(np.full(z.size, 200.0), np.full(z.size, 2.0), 0.25, 2.0)
    np.testing.assert_allclose(flat["values"], 200.0)
    line = smooth_on_grid(150.0 + 3.0 * z, None, 0.25, 2.0)
    assert line["sigma"] is None
    np.testing.assert_allclose(line["values"][12:-12], (150.0 + 3.0 * z)[12:-12])
    # one bad level with a large error hardly moves its neighbourhood
    x = np.full(z.size, 200.0)
    s = np.full(z.size, 1.0)
    x[40], s[40] = 260.0, 30.0
    weighted = smooth_on_grid(x, s, 0.25, 2.0)["values"][40]
    plain = smooth_on_grid(x, None, 0.25, 2.0)["values"][40]
    assert weighted - 200.0 < 0.1 < 5.0 < plain - 200.0


def _noisy(oid, t0, n=81, seed=0):
    z = np.arange(0.0, n * 0.25, 0.25)
    rng = np.random.default_rng(seed)
    sigma = np.full(n, 2.0)
    t = t0 + 0.5 * z + sigma * rng.standard_normal(n)
    return ObservationProfile(observation_id=oid, mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="2005-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                              temperature_k=t, uncertainty={"temperature_k": sigma},
                              systematic={"temperature_k": np.full(n, 3.0)})


def _with_pressure(p):
    p.pressure_hpa = 6.0 * np.exp(-np.asarray(p.altitude_km) / 11.0)
    return p


def test_comparison_smooths_each_profile_and_propagates_its_uncertainty():
    from veda.analysis.atmospheric import compare_profiles_on_body, export_comparison_to_csv
    mars = get_body("mars")
    profs = [_noisy("a", 200.0, seed=1), _noisy("b", 205.0, seed=2), _noisy("c", 210.0, seed=3)]
    raw = compare_profiles_on_body(profs, mars, altitude_step_km=0.25)
    smo = compare_profiles_on_body(profs, mars, altitude_step_km=0.25, smoothing_km=2.0)
    assert smo["smoothing_km"] == 2.0 and "smoothed to 2 km" in smo["averaging"]
    k = 40
    s_raw = raw["profiles"][0]["interpolated_sigma"][k]
    s_smo = smo["profiles"][0]["interpolated_sigma"][k]
    assert s_raw == pytest.approx(2.0, rel=1e-3)
    assert s_smo < 0.6 * s_raw                         # the errors' correlation counted, not 1/sqrt(window)
    assert smo["profiles"][0]["sigma_correlation_km"] > 1.0
    # the scatter about the straight profile falls, the systematic uncertainty stays 3 K
    resid = lambda c: np.nanstd(np.array(c["profiles"][0]["interpolated_series"][12:-12], float)
                                - (200.0 + 0.5 * np.array(c["grid_km"][12:-12])))
    assert resid(smo) < 0.5 * resid(raw)
    assert smo["profiles"][0]["interpolated_systematic"][k] == pytest.approx(3.0, rel=1e-6)
    assert "# each profile smoothed to 2 km" in export_comparison_to_csv(smo)
    on_pressure = compare_profiles_on_body([_with_pressure(p) for p in profs], mars, vertical="pressure", smoothing_km=2.0)
    assert "not smoothed" in on_pressure["averaging"] and not on_pressure["smoothing_km"]
    too_fine = compare_profiles_on_body(profs, mars, altitude_step_km=0.01, smoothing_km=2.0)
    assert "grid step of at least" in too_fine.get("error", "")


def test_correlation_length_matched_at_the_smoothing_scale():
    """Errors correlated over L = 1 km: their level-to-level scatter allows a much shorter
    length, which would make smoothing look far more effective than it is.  The length at
    which the error model gives the profile's own residual about its smoothed version
    comes back near 1 km, and the smoothed 1-sigma with it is the Monte Carlo one."""
    from veda.analysis.smoothing import matched_correlation_km
    rng = np.random.default_rng(11)
    step, n = 0.25, 240
    z = np.arange(n) * step
    sig = np.full(n, 2.0)
    chol = np.linalg.cholesky(4.0 * np.exp(-(z[:, None] - z[None, :]) ** 2 / 2.0) + 1e-10 * np.eye(n))
    found = [matched_correlation_km(200.0 + 0.3 * z + chol @ rng.standard_normal(n), sig, step, 2.0, 0.1)
             for _ in range(15)]
    assert 0.85 < np.median(found) < 1.2
    draws = (chol @ rng.standard_normal((n, 2000))).T
    out = smooth_on_grid(np.zeros(n), sig, step, 2.0, float(np.median(found)))
    mc = np.array([apply_weights(d, out["weights"], out["offsets"]) for d in draws]).std(axis=0)
    assert out["sigma"][120] == pytest.approx(mc[120], rel=0.08)
    assert smooth_on_grid(np.zeros(n), sig, step, 2.0, 0.1)["sigma"][120] < 0.5 * mc[120]   # the short length
