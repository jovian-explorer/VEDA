"""Scientific checks of VEDA's derived quantities against analytic cases.

Each test builds a profile whose answer is known in closed form, using the
body's own constants (gravity falling with altitude, R_specific, cp(T)).
"""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis.advanced_science import TECU_CONVERSION_FACTOR, compute_vtec
from veda.analysis.atmospheric import compute_atmospheric_diagnostics
from veda.analysis.thermo import heat_capacity
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def _profile(body_id, z, t, p=None, ne=None):
    return ObservationProfile(observation_id="test", mission_id="test", body_id=body_id, instrument="test",
                              time_utc="2016-01-01T00:00:00", altitude_km=np.asarray(z, float),
                              temperature_k=None if t is None else np.asarray(t, float),
                              pressure_hpa=None if p is None else np.asarray(p, float),
                              electron_density_cm3=None if ne is None else np.asarray(ne, float))


def _g(body, z):
    return body.surface_gravity * (body.radius_km / (body.radius_km + z)) ** 2


# ---------------------------------------------------------------- heat capacity

@pytest.mark.parametrize("body_id,t,expected,tol", [
    ("mars", 200.0, 739.5, 3.0),     # CO2/N2/Ar mixture at 200 K
    ("venus", 300.0, 850.0, 5.0),    # matches the classical 850 J/(kg K) near 300 K
    ("venus", 735.0, 1140.0, 15.0),  # deep atmosphere: cp rises with T
    ("titan", 94.0, 1025.0, 5.0),    # N2 + CH4, nearly constant
])
def test_cp_of_temperature(body_id, t, expected, tol):
    assert heat_capacity(get_body(body_id), np.array([t]))[0] == pytest.approx(expected, abs=tol)


def test_constant_cp_for_other_bodies():
    jup = get_body("jupiter")
    assert heat_capacity(jup, np.array([165.0]))[0] == jup.isobaric_heat_capacity_cp


# ---------------------------------------------------------------- isothermal atmosphere

def test_isothermal_mars_scale_height_stability_density():
    mars = get_body("mars")
    z = np.linspace(0.0, 40.0, 81)
    t = np.full_like(z, 200.0)
    g = _g(mars, z)
    # hydrostatic pressure for an isothermal layer with g(z)
    h_km = mars.gas_constant_r * 200.0 / (g * 1000.0)
    p = 6.1 * np.exp(-np.concatenate([[0.0], np.cumsum(np.diff(z) / (0.5 * (h_km[1:] + h_km[:-1])))]))
    prof = _profile("mars", z, t, p)
    d = compute_atmospheric_diagnostics(prof, mars)
    np.testing.assert_allclose(d["scale_height"], h_km, rtol=1e-9)
    cp = heat_capacity(mars, t)
    np.testing.assert_allclose(d["buoyancy_freq_sq"], g ** 2 / (cp * 200.0), rtol=1e-6)
    np.testing.assert_allclose(d["dry_adiabatic_lapse_rate"], g / cp * 1000.0, rtol=1e-9)
    np.testing.assert_allclose(d["density"], p * 100.0 / (mars.gas_constant_r * 200.0), rtol=1e-12)
    np.testing.assert_allclose(d["lapse_rate"], 0.0, atol=1e-9)
    gamma = cp / (cp - mars.gas_constant_r)
    np.testing.assert_allclose(d["speed_of_sound"], np.sqrt(gamma * mars.gas_constant_r * 200.0), rtol=1e-9)
    assert prof.raw_attributes["cp_model"].startswith("temperature-dependent")


def test_potential_temperature_equals_temperature_at_reference_pressure():
    venus = get_body("venus")
    z = np.array([0.0, 1.0, 2.0])
    p = np.array([venus.reference_pressure_hpa, 0.9 * venus.reference_pressure_hpa, 0.8 * venus.reference_pressure_hpa])
    d = compute_atmospheric_diagnostics(_profile("venus", z, [735.0, 727.0, 719.0], p), venus)
    assert d["potential_temperature"][0] == pytest.approx(735.0, rel=1e-12)
    assert d["potential_temperature"][2] > 719.0          # lower pressure: theta > T


# ---------------------------------------------------------------- dry adiabat

def test_dry_adiabat_has_neutral_stability_with_variable_cp():
    """dT/dz = -g/cp(T) integrated through the deep Venus atmosphere gives N^2 = 0."""
    venus = get_body("venus")
    z = np.linspace(0.0, 30.0, 3001)
    t = np.empty_like(z)
    t[0] = 735.0
    for i in range(1, z.size):
        dz = (z[i] - z[i - 1]) * 1000.0
        g_mid = _g(venus, 0.5 * (z[i] + z[i - 1]))
        k1 = -g_mid / heat_capacity(venus, np.array([t[i - 1]]))[0]
        k2 = -g_mid / heat_capacity(venus, np.array([t[i - 1] + k1 * dz]))[0]
        t[i] = t[i - 1] + 0.5 * (k1 + k2) * dz
    d = compute_atmospheric_diagnostics(_profile("venus", z, t), venus)
    n2 = d["buoyancy_freq_sq"][5:-5]
    assert np.nanmax(np.abs(n2)) < 2e-7           # vs ~1e-4 s^-2 for a stable layer
    # with a constant cp of 850 J/(kg K) the same profile would look unstable by ~25 %
    assert np.nanmean(d["dry_adiabatic_lapse_rate"][:100]) == pytest.approx(8.87 / heat_capacity(venus, np.array([735.0]))[0] * 1000, rel=0.01)


def test_stability_without_pressure_column():
    """N^2 needs only temperature; profiles without pressure still get it."""
    d = compute_atmospheric_diagnostics(_profile("mars", [0, 1, 2, 3], [210, 208, 206, 204]), get_body("mars"))
    assert "buoyancy_freq_sq" in d and np.isfinite(d["buoyancy_freq_sq"]).all()
    assert "potential_temperature" not in d


# ---------------------------------------------------------------- ionosphere

def test_chapman_layer_total_electron_content():
    hm, nm, h = 320.0, 1.2e6, 60.0
    z = np.linspace(150.0, 650.0, 501)
    x = (z - hm) / h
    ne = nm * np.exp(1.0 - x - np.exp(-x))
    r = compute_vtec(z, ne)
    assert r["peak_density_cm3"] == pytest.approx(nm, rel=1e-3)
    assert r["peak_alt_km"] == pytest.approx(hm, rel=1e-3)
    # analytic integral over all heights: 1e-7 * Nm * H * e = 19.57 TECU
    assert r["vtec_tecu"] == pytest.approx(TECU_CONVERSION_FACTOR * nm * h * np.e, rel=1e-2)


def test_tec_clamps_negative_noise_and_handles_short_input():
    r = compute_vtec(np.array([100.0, 200.0, 300.0, 400.0]), np.array([-500.0, 1e5, 2e5, -100.0]))
    assert r["vtec_tecu"] > 0 and r["peak_alt_km"] == 300.0
    assert np.isnan(compute_vtec(np.array([200.0]), np.array([1e5]))["vtec_tecu"])
    assert np.isnan(compute_vtec(np.array([np.nan, np.nan]), np.array([np.nan, np.nan]))["vtec_tecu"])


def test_descending_and_duplicate_altitudes():
    z = np.array([300.0, 250.0, 250.0, 200.0, 150.0])
    ne = np.array([1e5, 2e5, 2e5, 1.5e5, 5e4])
    r = compute_vtec(z, ne)
    assert r["alt_min_km"] == 150.0 and r["alt_max_km"] == 300.0 and r["vtec_tecu"] > 0


# ---------------------------------------------------------------- multi-profile comparison

def test_comparison_pressure_is_averaged_in_log_space():
    from veda.analysis.atmospheric import compare_profiles_on_body
    mars = get_body("mars")
    z = np.linspace(0.0, 40.0, 41)
    a = _profile("mars", z, np.full_like(z, 200.0), 6.0 * np.exp(-z / 10.0))
    b = _profile("mars", z, np.full_like(z, 220.0), 6.0 * np.exp(-z / 12.0))
    r = compare_profiles_on_body([a, b], mars, altitude_step_km=1.0, variable_name="pressure_hpa")
    assert r["averaging"].startswith("geometric")
    i = r["grid_km"].index(30.0)
    pa, pb = 6.0 * np.exp(-3.0), 6.0 * np.exp(-2.5)
    assert r["composite_mean"][i] == pytest.approx(np.sqrt(pa * pb), rel=1e-6)
    assert r["composite_minus_1sigma"][i] < r["composite_mean"][i] < r["composite_plus_1sigma"][i]
    # each interpolated profile stays exponential between grid points
    assert r["profiles"][0]["interpolated_series"][i] == pytest.approx(pa, rel=1e-5)   # 6 significant figures


def test_comparison_keeps_negative_altitudes_and_does_not_bridge_gaps():
    from veda.analysis.atmospheric import compare_profiles_on_body
    mars = get_body("mars")
    z = np.concatenate([np.arange(-4.0, 10.0, 1.0), np.arange(30.0, 40.0, 1.0)])     # gap 9..30 km
    p = _profile("mars", z, 210.0 - z)
    r = compare_profiles_on_body([p], mars, altitude_step_km=1.0)
    assert r["grid_km"][0] == -4.0
    series = r["profiles"][0]["interpolated_series"]
    assert series[r["grid_km"].index(-4.0)] == pytest.approx(214.0)
    assert series[r["grid_km"].index(20.0)] is None                  # inside the gap
    assert r["composite_plus_1sigma"][0] is None                     # one profile: no spread
    assert r["profiles_per_level"][0] == 1
