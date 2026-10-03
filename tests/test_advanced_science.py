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
    assert r["composite_mean"][0] is None                            # ... and no "mean" either
    assert r["profiles_per_level"][0] == 1


# ---------------------------------------------------------------- dense and repeated altitudes

def test_gradient_with_repeated_altitudes_is_not_inflated():
    """Descending probes repeat altitudes; the old guard nudged them 1e-6 km apart, turning
    any difference into a gradient of order 1e6 K/km."""
    from veda.analysis.atmospheric import _gradient_nan_safe
    z = np.array([0.0, 1.0, 1.0, 2.0, 3.0])
    t = np.array([210.0, 208.0, 208.4, 206.0, 204.0])
    g = _gradient_nan_safe(z, t)
    assert np.all(np.abs(g) < 3.0)
    assert g[1] == g[2]                                  # one value per altitude


def test_gradient_of_dense_noisy_entry_data_resolves_100_m():
    from veda.analysis.atmospheric import _gradient_nan_safe
    rng = np.random.default_rng(0)
    z = np.arange(10.0, 40.0, 0.003)                     # 3 m sampling, as entry accelerometers
    t = 220.0 - 2.0 * z + rng.normal(0, 0.05, z.size)    # 0.05 K noise
    g = _gradient_nan_safe(z, t)
    inner = (z > 11) & (z < 39)
    assert np.median(g[inner]) == pytest.approx(-2.0, abs=0.02)
    assert np.percentile(np.abs(g[inner] + 2.0), 99) < 2.0    # adjacent-sample differences would give ~25 K/km


def test_non_positive_temperature_and_pressure_are_fill():
    import dataclasses
    from veda.archives.datasets import get_dataset
    from veda.archives.profiles import profile_from_label
    import os, tempfile, pathlib
    tmp = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get("VEDA_HOME")))
    rows = [(3400000.0, 200.0, 300.0), (3410000.0, 180.0, 100.0), (3500000.0, -1.0, -1.0)]
    (tmp / "p.tab").write_text("".join(f"{r:12.1f} {t:8.2f} {p:8.2f}\r\n" for r, t, p in rows), newline="")
    cols = [("RADIAL_DISTANCE", 1, 12, "METER"), ("TEMP", 14, 8, "KELVIN"), ("PRESS", 23, 8, "PASCAL")]
    body = "".join(f"OBJECT = COLUMN\nNAME = {n}\nDATA_TYPE = ASCII_REAL\nSTART_BYTE = {s}\nBYTES = {b}\nUNIT = {u}\n"
                   f"END_OBJECT = COLUMN\n" for n, s, b, u in cols)
    (tmp / "p.lbl").write_text(f"PDS_VERSION_ID = PDS3\nRECORD_TYPE = FIXED_LENGTH\nRECORD_BYTES = 32\n^TABLE = \"p.tab\"\n"
                               f"OBJECT = TABLE\nINTERCHANGE_FORMAT = ASCII\nROWS = 3\nCOLUMNS = 3\nROW_BYTES = 32\n{body}"
                               f"END_OBJECT = TABLE\nEND\n")
    ds = dataclasses.replace(get_dataset("phx-m-ase-5-edl-rdr-v1.0"), extra_variables={},
                             profile_columns={"radius": "RADIAL_DISTANCE", "temperature": "TEMP", "pressure": "PRESS"})
    prof = profile_from_label(ds, {"product_id": "p", "start_time": "2008-05-25T23:30:00", "volume": "v", "url": "",
                                   "product_type": "profile"}, tmp / "p.lbl")
    assert np.isnan(prof.temperature_k[2]) and np.isnan(prof.pressure_hpa[2])
    assert prof.temperature_k[0] == 200.0 and prof.pressure_hpa[0] == pytest.approx(3.0)


def test_gradient_with_altitude_jitter_after_touchdown():
    """VEGA 2: after landing the reconstructed altitude jitters by metres at constant T."""
    from veda.analysis.atmospheric import _gradient_nan_safe
    z = np.concatenate([np.arange(3.0, 0.0, -0.15), [0.00079, -0.00079, 0.00032, 0.00143, -0.00663, -0.00553]])
    t = np.concatenate([734.0 + 8.0 * (0.0 - np.arange(3.0, 0.0, -0.15)), np.full(6, 734.3)])
    g = _gradient_nan_safe(z, t)
    assert np.all(np.abs(g) < 12.0)                     # was ~1e4 K/km at the jitter
    assert np.median(g[:10]) == pytest.approx(-8.0, abs=0.01)


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_log_composite_falls_back_to_linear_for_every_profile(order):
    """One noisy (negative) electron density must switch the whole comparison to
    linear averaging, whatever the order of the profiles."""
    from veda.analysis.atmospheric import compare_profiles_on_body
    venus = get_body("venus")
    z = np.arange(100.0, 300.0, 1.0)
    clean = _profile("venus", z, None, ne=np.full(z.size, 1e4))
    noisy_ne = np.full(z.size, 1e4)
    noisy_ne[0] = -50.0
    noisy = _profile("venus", z, None, ne=noisy_ne)
    profs = [(clean, noisy)[i] for i in order]
    r = compare_profiles_on_body(profs, venus, altitude_step_km=1.0, variable_name="electron_density_cm3")
    assert r["averaging"].startswith("arithmetic")
    i = r["grid_km"].index(150.0)
    assert r["composite_mean"][i] == pytest.approx(1e4)
    assert all(p["interpolated_series"][i] == pytest.approx(1e4) for p in r["profiles"])


@pytest.mark.parametrize("body_id,lat,expected,tol", [
    ("jupiter", 0.0, 23.12, 0.05),     # NASA fact sheet: 23.12 m/s^2 at the 1-bar equator
    ("jupiter", 90.0, 27.0, 0.15),
    ("saturn", 0.0, 9.0, 0.1),
    ("saturn", 90.0, 12.1, 0.1),
])
def test_giant_planet_gravity_depends_on_latitude(body_id, lat, expected, tol):
    from veda.analysis.atmospheric import gravity_profile
    g, model = gravity_profile(get_body(body_id), np.array([0.0]), lat, "the 1-bar pressure level")
    assert g[0] == pytest.approx(expected, abs=tol)
    assert "effective gravity" in model


def test_gravity_falls_back_to_the_sphere():
    from veda.analysis.atmospheric import gravity_profile
    jup = get_body("jupiter")
    z = np.array([0.0, 500.0])
    np.testing.assert_allclose(gravity_profile(jup, z, None)[0], _g(jup, z))           # latitude unknown
    venus = get_body("venus")
    np.testing.assert_allclose(gravity_profile(venus, z, 45.0)[0], _g(venus, z))       # spherical body


def test_saturn_scale_height_uses_latitude_gravity():
    """An isothermal 140 K Saturn profile at 70 deg: H = R T / g with the local
    effective gravity, about 13 % less than with the global 10.44 m/s^2."""
    from veda.analysis.atmospheric import gravity_profile
    sat = get_body("saturn")
    z = np.linspace(0.0, 300.0, 61)
    p = _profile("saturn", z, np.full_like(z, 140.0))
    p.latitude = 70.0
    p.raw_attributes["ALTITUDE_REFERENCE"] = "the 1-bar level of Saturn along the surface normal"
    d = compute_atmospheric_diagnostics(p)
    g = gravity_profile(sat, z, 70.0, p.raw_attributes["ALTITUDE_REFERENCE"])[0]
    np.testing.assert_allclose(d["scale_height"], sat.gas_constant_r * 140.0 / (g * 1000.0), rtol=1e-12)
    assert d["scale_height"][0] < 0.9 * sat.gas_constant_r * 140.0 / (sat.surface_gravity * 1000.0)
    assert p.raw_attributes["gravity_model"].startswith("effective gravity at 70.0")


def test_saturn_composition_is_cassini_helium_and_constants_follow_from_it():
    """Saturn's He is 11 % by volume (Koskinen & Guerlet 2018), not Voyager's 3.25 %; the
    molar mass, gas constant and cp are computed from the composition (they were 2.07
    g/mol and 4016 J/(kg K), not even consistent with the old composition, 2.14 g/mol)."""
    sat = get_body("saturn")
    comp = sat.atmospheric_composition
    assert comp == {"H2": 88.55, "He": 11.0, "CH4": 0.45} and sum(comp.values()) == pytest.approx(100.0)
    molar = {"H2": 2.01588, "He": 4.002602, "CH4": 16.0425}
    mu = sum(comp[g] / 100.0 * molar[g] for g in comp)
    assert sat.mean_molecular_weight == pytest.approx(mu, abs=1e-4)
    assert sat.gas_constant_r == pytest.approx(8314.462618 / mu, abs=0.1)
    r = 8.314462618
    cp_molar = comp["H2"] / 100 * 3.5 * r + comp["He"] / 100 * 2.5 * r + comp["CH4"] / 100 * 33.258
    assert sat.isobaric_heat_capacity_cp == pytest.approx(cp_molar / (mu / 1000.0), abs=1.0)
    from veda.analysis.thermo import heat_capacity
    assert heat_capacity(sat, np.array([120.0]))[0] == sat.isobaric_heat_capacity_cp     # constant cp


def test_comparison_on_pressure_levels_lines_up_offset_references():
    """The same T(p) measured from two altitude references 50 km apart: on an altitude
    grid the two disagree, on a log-pressure grid they coincide."""
    from veda.analysis.atmospheric import compare_profiles_on_body, export_comparison_to_csv
    sat = get_body("saturn")
    z = np.linspace(0.0, 400.0, 401)
    p_hpa = 1000.0 * np.exp(-z / 45.0)
    t = 140.0 + 20.0 * np.sin(z / 60.0)
    a = _profile("saturn", z, t, p_hpa)
    b = _profile("saturn", z + 50.0, t, p_hpa)
    alt = compare_profiles_on_body([a, b], sat, altitude_step_km=2.0)
    assert np.nanmax([s or 0 for s in alt["composite_std"]]) > 5.0
    prs = compare_profiles_on_body([a, b], sat, variable_name="temperature_k", vertical="pressure",
                                   pressure_step_decades=0.05)
    assert prs["vertical"] == "pressure" and prs["grid_km"] == [] and prs["profile_count"] == 2
    assert prs["grid_hpa"][0] == pytest.approx(1000.0, rel=0.06)                 # bottom up, like altitude
    assert prs["grid_hpa"][-1] == pytest.approx(1000.0 * np.exp(-400.0 / 45.0), rel=0.15)
    assert np.diff(np.log10(prs["grid_hpa"])) == pytest.approx(-0.05, abs=1e-5)
    std = [s for s in prs["composite_std"] if s is not None]
    assert std and max(std) < 1e-6
    i = int(np.argmin(np.abs(np.array(prs["grid_hpa"]) - 100.0)))
    p_i = prs["grid_hpa"][i]
    assert prs["composite_mean"][i] == pytest.approx(140.0 + 20.0 * np.sin(45.0 * np.log(1000.0 / p_i) / 60.0), abs=0.05)
    csv = export_comparison_to_csv(prs)
    assert "uniform in log pressure" in csv and "\npressure_hpa,composite_mean_temperature_k" in csv


def test_pressure_comparison_skips_profiles_without_pressure_and_refuses_pressure_variable():
    from veda.analysis.atmospheric import compare_profiles_on_body
    mars = get_body("mars")
    z = np.linspace(0.0, 40.0, 41)
    with_p = _profile("mars", z, np.full_like(z, 200.0), 6.0 * np.exp(-z / 10.0))
    without_p = _profile("mars", z, np.full_like(z, 210.0))
    r = compare_profiles_on_body([with_p, without_p], mars, vertical="pressure")
    assert r["profile_count"] == 1
    assert "error" in compare_profiles_on_body([with_p], mars, variable_name="pressure_hpa", vertical="pressure")
    with pytest.raises(ValueError):
        compare_profiles_on_body([with_p], mars, vertical="theta")
