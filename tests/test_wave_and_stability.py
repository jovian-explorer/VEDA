"""Unit tests for VEDA Atmospheric Wave, Stability, and Chapman Ionosphere Module."""
import numpy as np
import pytest

from veda.analysis.wave_and_stability import (
    detect_tropopause,
    extract_gravity_wave_activity,
    fit_chapman_ionosphere,
    tropopause_for_body,
)
from veda.analysis.atmospheric import (
    compare_profiles_on_body,
    compute_atmospheric_diagnostics,
    export_comparison_to_csv,
    profile_diagnostics,
)
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def test_tropopause_detection_cpt_and_lrt():
    """Verify CPT and LRT tropopause detection on a synthetic troposphere-stratosphere profile."""
    # z from 0 to 30 km
    z_km = np.linspace(0.0, 30.0, 301)
    # Troposphere lapse rate: 6.5 K/km from 290 K at surface to 11 km (T = 218.5 K)
    # Isothermal / slight inversion in stratosphere above 11 km
    t_k = np.where(
        z_km <= 11.0,
        290.0 - 6.5 * z_km,
        218.5 + 1.2 * (z_km - 11.0)
    )

    res = detect_tropopause(z_km, t_k, min_alt_km=8.0, max_alt_km=20.0)
    assert res["cpt_alt_km"] is not None
    assert abs(res["cpt_alt_km"] - 11.0) < 0.2
    assert abs(res["cpt_temp_k"] - 218.5) < 1.0

    assert res["lrt_alt_km"] is not None
    assert abs(res["lrt_alt_km"] - 11.0) < 0.5


def test_gravity_wave_extraction():
    """Verify extraction of gravity wave temperature perturbation and potential energy."""
    z_km = np.linspace(15.0, 45.0, 301)
    # Smooth background: T_bar(z) ~ 220 + 2.0 * (z - 15)
    t_bar_synth = 220.0 + 2.0 * (z_km - 15.0)
    # Synthetic sinusoidal gravity wave with 4 km vertical wavelength and 3 K amplitude
    lambda_z_true = 4.0
    wave = 3.0 * np.sin(2.0 * np.pi * z_km / lambda_z_true)
    t_synth = t_bar_synth + wave
    gz = np.full(z_km.shape, 9.8)

    gw = extract_gravity_wave_activity(z_km, t_synth, gz, cutoff_wavelength_km=10.0)
    assert gw["mean_potential_energy"] > 0.0
    assert gw["dominant_wavelength_km"] is not None
    # Estimated vertical wavelength should be within 20% of true 4.0 km
    assert abs(gw["dominant_wavelength_km"] - lambda_z_true) <= 0.8


def test_chapman_ionosphere_fit():
    """Verify Chapman layer curve fitting recovers known peak density and altitude."""
    z_km = np.linspace(100.0, 500.0, 201)
    nm_true = 1.5e6  # cm^-3
    hm_true = 300.0  # km
    h_true = 50.0    # km

    # Chapman analytical function
    zeta = (z_km - hm_true) / h_true
    ne_synth = nm_true * np.exp(0.5 * (1.0 - zeta - np.exp(-zeta)))

    fit_res = fit_chapman_ionosphere(z_km, ne_synth)
    assert fit_res["nmf2_cm3"] is not None
    assert abs(fit_res["nmf2_cm3"] - nm_true) / nm_true < 0.05
    assert abs(fit_res["hmf2_km"] - hm_true) < 2.0
    assert fit_res["r_squared"] is not None and fit_res["r_squared"] > 0.98


def _titan_profile(obs="t1", descending=False):
    # HASI-like: 94 K at the surface, 70.4 K cold point at 44 km, warming above
    z = np.arange(0.0, 150.0, 0.5)
    t = np.minimum(np.where(z < 44, 94 - (94 - 70.4) * z / 44, 70.4 + 0.9 * (z - 44)), 170.0)
    p = 1467.0 * np.exp(-z / 20.0)
    if descending:
        z, t, p = z[::-1], t[::-1], p[::-1]
    return ObservationProfile(obs, "cassini", "titan", "RSS", "2005-01-14T12:00:00",
                              latitude=-10.0, altitude_km=z, temperature_k=t, pressure_hpa=p)


def test_tropopause_searched_where_the_body_has_one():
    prof = _titan_profile()
    compute_atmospheric_diagnostics(prof)
    d = profile_diagnostics(prof)
    assert d["cpt_alt_km"] == 44.0 and d["cpt_temp_k"] == pytest.approx(70.4)
    assert d["cpt_pressure_hpa"] == pytest.approx(1467.0 * np.exp(-44.0 / 20.0), rel=1e-3)

    # Venus: temperature falls through the mesosphere, no cold point is reported
    # (the old Earth window of 6-25 km returned the coldest level of the profile)
    z = np.arange(40.0, 90.0, 0.5)
    venus = ObservationProfile("v1", "vex", "venus", "VeRa", "2007-01-01", altitude_km=z, temperature_k=420 - 3.5 * (z - 40))
    compute_atmospheric_diagnostics(venus)
    assert profile_diagnostics(venus)["cpt_alt_km"] is None


def test_tropopause_needs_an_interior_minimum_and_pressure_on_giants():
    z = np.arange(30.0, 60.0, 0.5)                       # starts above Titan's cold point
    assert tropopause_for_body("titan", z, 70.4 + 0.9 * (z - 30))["cpt_alt_km"] is None
    zj = np.arange(-50.0, 200.0, 1.0)                    # Jupiter, altitude above 1 bar
    pj = 1000.0 * np.exp(-zj / 27.0)
    tj = np.where(pj > 100.0, 110 + 55 * np.log10(pj / 100.0), 110 + 20 * np.log10(100.0 / pj))
    res = tropopause_for_body("jupiter", zj, tj, pj)
    assert res["cpt_pressure_hpa"] == pytest.approx(100.0, rel=0.05)
    assert tropopause_for_body("jupiter", zj, tj)["cpt_alt_km"] is None   # needs pressure


def test_gravity_wave_output_follows_sample_order():
    z = np.arange(0.0, 60.0, 0.2)
    t = 250 - 2 * z + 3 * np.sin(2 * np.pi * z / 5)
    g = np.full_like(z, 3.7)
    up = np.array(extract_gravity_wave_activity(z, t, g)["t_prime_k"], dtype=float)
    down = np.array(extract_gravity_wave_activity(z[::-1], t[::-1], g)["t_prime_k"], dtype=float)
    np.testing.assert_allclose(down[::-1], up)


def test_ionosphere_diagnostics_without_temperature():
    z = np.arange(80.0, 300.0, 1.0)
    zeta = (z - 135.0) / 12.0
    ne = 1.5e5 * np.exp(0.5 * (1 - zeta - np.exp(-zeta)))
    prof = ObservationProfile("i1", "mex", "mars", "MaRS", "2008-01-01", altitude_km=z, electron_density_cm3=ne)
    compute_atmospheric_diagnostics(prof)
    d = profile_diagnostics(prof)
    assert d["ne_peak_alt_km"] == 135.0 and d["chapman_h_km"] == pytest.approx(12.0, abs=0.1)
    assert d["tec_tecu"] == pytest.approx(1e-7 * np.trapezoid(ne, z), rel=1e-3)


def test_comparison_carries_profile_diagnostics_to_csv():
    profs = [_titan_profile("a"), _titan_profile("b", descending=True)]
    for p in profs:
        compute_atmospheric_diagnostics(p)
    comp = compare_profiles_on_body(profs, get_body("titan"))
    assert "cpt_alt_km" in comp["diagnostic_labels"]
    assert all(s["diagnostics"]["cpt_alt_km"] == 44.0 for s in comp["profiles"])
    header = [line for line in export_comparison_to_csv(comp).splitlines() if line.startswith("# column,")][0]
    assert "cpt_alt_km" in header and "cpt_temp_k" in header
    row = [line for line in export_comparison_to_csv(comp).splitlines() if line.startswith("# cassini_a")][0]
    assert ", 44," in row


def _t_prime_amplitude(lam_km, cutoff_km=8.0):
    z = np.arange(40.0, 100.0, 0.2)
    t = 200.0 - (z - 40.0) + 2.0 * np.sin(2 * np.pi * z / lam_km)
    gw = extract_gravity_wave_activity(z, t, np.full_like(z, 8.87), cutoff_wavelength_km=cutoff_km)
    tp = np.array(gw["t_prime_k"], dtype=float)
    mid = (z > 55) & (z < 85)                       # away from the ends
    return np.sqrt(2.0) * np.nanstd(tp[mid]) / 2.0, gw


@pytest.mark.parametrize("lam,lo,hi", [(3.0, 0.98, 1.02), (5.0, 0.95, 1.02), (8.0, 0.4, 0.6), (12.0, 0.0, 0.05)])
def test_gravity_wave_cutoff_is_where_stated(lam, lo, hi):
    """Waves shorter than the cutoff stay in T' at full amplitude (no overshoot),
    longer ones go to the background, the cutoff wave is split about in half."""
    amp, _ = _t_prime_amplitude(lam)
    assert lo <= amp <= hi


def test_gravity_wave_smooth_background_leaves_no_perturbation():
    z = np.arange(40.0, 100.0, 0.2)
    t = 200.0 - (z - 40.0) + 0.01 * (z - 70.0) ** 2
    gw = extract_gravity_wave_activity(z, t, np.full_like(z, 8.87))
    assert np.nanmax(np.abs(np.array(gw["t_prime_k"], dtype=float))) < 0.01
    assert gw["dominant_wavelength_km"] is None


def test_wave_energy_uses_background_stability():
    """A 2 K, 3 km wave in a near-adiabatic Venus cloud layer makes the local N^2
    negative at some levels; E_p must stay near (g/N_bar)^2 (T'/T)^2 / 2 instead of
    exploding where the local N^2 was clipped to a tiny value."""
    from veda.analysis.atmospheric import compute_atmospheric_diagnostics
    from veda.core.models import ObservationProfile
    z = np.arange(50.0, 90.0, 0.2)
    t = np.where(z < 65, 260 - 8 * (z - 50), 140 - 3 * (z - 65)) + 2.0 * np.sin(2 * np.pi * z / 3.0)
    p = ObservationProfile("x", "vex", "venus", "VeRa", "2008-01-01", altitude_km=z, temperature_k=t)
    d = compute_atmospheric_diagnostics(p)
    assert np.nanmin(d["buoyancy_freq_sq"]) < 0                    # the case being tested
    ep = d["wave_potential_energy"]
    upper = (z > 70) & (z < 85)                                     # stable layer, away from the kink
    # N_bar^2 there: (g/T)(dT/dz + g/cp) with dT/dz = -3 K/km; E_p peaks at (g/N_bar)^2 (2 K / T)^2 / 2
    assert np.nanmax(ep[upper]) < 40.0
    assert np.nanmax(ep) < 200.0                                    # was 1860 J/kg


def test_failed_chapman_fit_reports_no_fit(monkeypatch):
    """Bug: when the fit did not converge, the measured peak was returned as the 'Chapman
    fit' peak density and altitude (shown as fit results in the altitude cut and CSV)."""
    from veda.analysis import wave_and_stability as ws

    def no_convergence(*a, **k):
        raise RuntimeError("Optimal parameters not found")
    monkeypatch.setattr(ws, "curve_fit", no_convergence)
    z = np.linspace(100.0, 500.0, 50)
    res = ws.fit_chapman_ionosphere(z, 1e5 * np.exp(-((z - 300.0) / 60.0) ** 2))
    assert res == {"nmf2_cm3": None, "hmf2_km": None, "scale_height_km": None, "r_squared": None}
