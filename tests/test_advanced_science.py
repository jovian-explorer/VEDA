"""Unit tests for VEDA Advanced Planetary Atmospheric & Ionospheric Science Module.

Verifies:
- Known physical benchmarks (isothermal atmosphere, dry adiabatic, Chapman ionospheric layer, scintillation events)
- Automatic unit conversion (Celsius vs. Kelvin)
- Monotonicity, non-uniform altitude grids, and descending occultation profiles
- Resilience to NaNs, infinite values, negative pressures, and boundary edge cases
- Planetary gravity scaling across Solar System targets

Author: Keshav Aggarwal (SPL / VSSC, ISRO)
Date: 2026-09-20
"""

import math
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))
sys.path.insert(0, str(ROOT_DIR / "backend" / "veda" / "analysis"))

from advanced_science import (
    C_P,
    G_0,
    KAPPA,
    P_REF,
    TECU_CONVERSION_FACTOR,
    classify_scintillation,
    compute_brunt_vaisala,
    compute_potential_temperature,
    compute_vtec,
)


class TestPotentialTemperature:
    """Tests for compute_potential_temperature."""

    def test_reference_pressure(self):
        """At P_ref (1000 hPa), theta must equal T."""
        temps_k = np.array([250.0, 273.15, 300.0])
        press_hpa = np.array([1000.0, 1000.0, 1000.0])
        theta = compute_potential_temperature(temps_k, press_hpa)
        np.testing.assert_allclose(theta, temps_k, rtol=1e-6)

    def test_celsius_auto_detection(self):
        """Celsius temperatures (mean < 100) must convert accurately to Kelvin."""
        temps_c = np.array([-50.0, -20.0, 0.0, 25.0])
        press_hpa = np.array([500.0, 700.0, 850.0, 1000.0])
        
        theta_from_c = compute_potential_temperature(temps_c, press_hpa)
        theta_from_k = compute_potential_temperature(temps_c + 273.15, press_hpa)
        
        np.testing.assert_allclose(theta_from_c, theta_from_k, rtol=1e-6)

    def test_compression_warming(self):
        """Parcel brought adiabatically from lower pressure (aloft) to 1000 hPa warms."""
        t_high = 220.0  # K at 200 hPa
        p_high = 200.0  # hPa
        theta = compute_potential_temperature(np.array([t_high]), np.array([p_high]))
        # Expected: 220 * (1000/200)^0.285743...
        expected = t_high * ((1000.0 / 200.0) ** KAPPA)
        assert pytest.approx(theta[0], rel=1e-5) == expected
        assert theta[0] > t_high

    def test_invalid_pressures_and_temperatures(self):
        """Negative or zero pressures and temperatures must result in NaN without crashing."""
        temps = np.array([280.0, -10.0, 250.0, np.nan, 290.0])
        # Note: If -10 is interpreted as C, it's 263.15 K. Let's test non-physical values.
        press = np.array([0.0, -50.0, 500.0, 800.0, np.nan])
        
        theta = compute_potential_temperature(temps, press)
        assert np.isnan(theta[0])  # P = 0
        assert np.isnan(theta[1])  # P < 0
        assert np.isfinite(theta[2])  # Valid
        assert np.isnan(theta[3])  # T is NaN
        assert np.isnan(theta[4])  # P is NaN

    def test_empty_and_mismatched_inputs(self):
        """Verify empty array handling and shape validation."""
        empty_res = compute_potential_temperature(np.array([]), np.array([]))
        assert len(empty_res) == 0

        with pytest.raises(ValueError):
            compute_potential_temperature(np.array([250.0, 260.0]), np.array([1000.0]))


class TestBruntVaisala:
    """Tests for compute_brunt_vaisala buoyancy frequency squared."""

    def test_dry_adiabatic_neutral_stability(self):
        """In a neutrally stable dry atmosphere, theta is constant, so N^2 = 0."""
        alt_km = np.linspace(0.0, 10.0, 101)
        theta_k = np.full_like(alt_km, 300.0)  # constant theta
        n2 = compute_brunt_vaisala(alt_km, theta_k, smooth_window=1)
        # Interior points should have N^2 = 0
        np.testing.assert_allclose(n2, 0.0, atol=1e-12)

    def test_isothermal_atmosphere_analytical(self):
        """In an isothermal atmosphere (T0 = const), N^2 = g_0^2 / (c_p * T0)."""
        t0 = 250.0  # Kelvin
        scale_height_m = (287.0578 * t0) / G_0  # H ~ 7317 m
        
        alt_km = np.linspace(10.0, 25.0, 151)
        alt_m = alt_km * 1000.0
        # For isothermal: theta(z) = T0 * exp(kappa * z / H) = T0 * exp(g0 * z / (cp * T0))
        theta_k = t0 * np.exp((G_0 * alt_m) / (C_P * t0))
        
        n2 = compute_brunt_vaisala(alt_km, theta_k, smooth_window=1)
        analytical_n2 = (G_0 ** 2) / (C_P * t0)  # ~ 3.829e-4 s^-2
        
        # Check interior points (avoiding numerical edge difference boundary effects)
        np.testing.assert_allclose(n2[10:-10], analytical_n2, rtol=1e-3)

    def test_typical_atmospheric_magnitudes(self):
        """Typical stratospheric stability is ~ 4e-4 to 6e-4 s^-2."""
        alt_km = np.array([15.0, 16.0, 17.0, 18.0, 19.0, 20.0])
        # Theta increasing at ~ 15 K/km in stratosphere
        theta_k = np.array([380.0, 395.0, 410.0, 425.0, 440.0, 455.0])
        n2 = compute_brunt_vaisala(alt_km, theta_k, smooth_window=1)
        # dtheta/dz = 15 K / 1000 m = 0.015 K/m.
        # N^2 ~ (9.80665 / 410) * 0.015 ~ 3.58e-4 s^-2
        assert np.all(n2[1:-1] > 3.0e-4)
        assert np.all(n2[1:-1] < 5.0e-4)

    def test_descending_occultation_profile(self):
        """Occultations often sample downwards (descending altitude)."""
        alt_asc = np.linspace(5.0, 25.0, 50)
        th_asc = 300.0 + 5.0 * (alt_asc - 5.0)  # Linear increase
        n2_asc = compute_brunt_vaisala(alt_asc, th_asc, smooth_window=1)
        
        # Reverse order
        alt_desc = alt_asc[::-1]
        th_desc = th_asc[::-1]
        n2_desc = compute_brunt_vaisala(alt_desc, th_desc, smooth_window=1)
        
        # Results reversed should match ascending results
        np.testing.assert_allclose(n2_desc[::-1], n2_asc, rtol=1e-5)

    def test_nan_resilience(self):
        """Isolated NaNs must not corrupt entire profile calculation."""
        alt_km = np.linspace(0.0, 10.0, 21)
        theta_k = 300.0 + 3.0 * alt_km
        theta_k[5] = np.nan
        theta_k[15] = np.nan
        
        n2 = compute_brunt_vaisala(alt_km, theta_k, smooth_window=1)
        assert np.isnan(n2[5])
        assert np.isnan(n2[15])
        assert np.isfinite(n2[0])
        assert np.isfinite(n2[10])
        assert np.isfinite(n2[20])


class TestVTEC:
    """Tests for compute_vtec ionospheric integration."""

    def test_chapman_layer_integration(self):
        """Verify integration and peak detection on a synthetic Chapman-like layer."""
        hm_f2 = 320.0  # km (peak altitude)
        nm_f2 = 1.2e6  # el/cm^3 (peak density)
        h_iono = 60.0  # km (scale height)

        alt_km = np.linspace(150.0, 650.0, 501)
        z_norm = (alt_km - hm_f2) / h_iono
        ne = nm_f2 * np.exp(1.0 - z_norm - np.exp(-z_norm))

        res = compute_vtec(alt_km, ne)
        
        # Peak parameters
        assert pytest.approx(res["peak_density_cm3"], rel=1e-3) == nm_f2
        assert pytest.approx(res["peak_alt_km"], rel=1e-3) == hm_f2
        assert pytest.approx(res["alt_min_km"], rel=1e-3) == 150.0
        assert pytest.approx(res["alt_max_km"], rel=1e-3) == 650.0
        
        # Chapman analytical integral over infinite limits for Ne = Nm * exp(1 - z_norm - exp(-z_norm)):
        # integral(exp(1 - xi - exp(-xi)) dxi) = e * integral(e^-u du) = e ~ 2.71828.
        # Total TEC = 10^-7 * Nm * H * e = 10^-7 * 1.2e6 * 60 * 2.71828 = 19.57 TECU.
        # Over the [150, 650] km bounds (capturing > 99% of total ionosphere), VTEC is ~ 19.49 TECU.
        assert 19.0 < res["vtec_tecu"] < 20.0
        assert pytest.approx(res["vtec_tecu"], rel=1e-2) == 19.57

    def test_zero_and_negative_density_clamping(self):
        """Retrieved negative densities (noise artifacts) must be clamped to 0."""
        alt_km = np.array([100.0, 200.0, 300.0, 400.0])
        ne = np.array([-500.0, 1e5, 2e5, -100.0])
        
        res = compute_vtec(alt_km, ne)
        assert res["vtec_tecu"] > 0.0
        assert res["peak_density_cm3"] == 2e5
        assert res["peak_alt_km"] == 300.0

    def test_insufficient_points(self):
        """Arrays with < 2 valid points must return NaN without exception."""
        res_empty = compute_vtec(np.array([]), np.array([]))
        assert np.isnan(res_empty["vtec_tecu"])

        res_single = compute_vtec(np.array([200.0]), np.array([1e5]))
        assert np.isnan(res_single["vtec_tecu"])


class TestScintillation:
    """Tests for classify_scintillation."""

    def test_quiet_scintillation(self):
        """Low S4 profile (<0.3) should be classified as quiet."""
        s4 = np.array([0.05, 0.12, 0.18, 0.08, 0.15])
        res = classify_scintillation(s4)
        assert res["category"] == "quiet"
        assert res["s4_max"] == pytest.approx(0.18)
        assert res["fraction_moderate"] == 0.0
        assert res["fraction_strong"] == 0.0
        assert res["event_count"] == 0

    def test_moderate_scintillation(self):
        """Max S4 in [0.3, 0.6) should be classified as moderate."""
        s4 = np.array([0.1, 0.25, 0.45, 0.35, 0.2, 0.1])
        res = classify_scintillation(s4)
        assert res["category"] == "moderate"
        assert res["s4_max"] == pytest.approx(0.45)
        assert pytest.approx(res["fraction_moderate"]) == 2 / 6
        assert res["fraction_strong"] == 0.0
        assert res["event_count"] == 1  # single contiguous event

    def test_severe_scintillation_multiple_events(self):
        """S4 exceeding 0.6 classified as severe; multiple bursts counted correctly."""
        # Event 1: [0.75, 0.85], Quiet: [0.1], Event 2: [0.35, 0.65], Quiet: [0.05]
        s4 = np.array([0.1, 0.75, 0.85, 0.1, 0.35, 0.65, 0.05])
        res = classify_scintillation(s4)
        assert res["category"] == "severe"
        assert res["s4_max"] == pytest.approx(0.85)
        assert res["event_count"] == 2
        assert pytest.approx(res["fraction_moderate"]) == 4 / 7
        assert pytest.approx(res["fraction_strong"]) == 3 / 7

    def test_nan_and_negative_filtering(self):
        """Scintillation calculation must safely ignore NaNs and negatives."""
        s4 = np.array([np.nan, -0.2, 0.1, 0.4, np.nan, 0.2])
        res = classify_scintillation(s4)
        assert res["category"] == "moderate"
        assert res["s4_max"] == pytest.approx(0.4)
        assert pytest.approx(res["s4_mean"]) == (0.1 + 0.4 + 0.2) / 3
        assert res["event_count"] == 1

    def test_edge_scintillation_bursts(self):
        """Events starting at index 0 and finishing at the final index."""
        s4 = np.array([0.7, 0.8, 0.1, 0.1, 0.9])
        res = classify_scintillation(s4)
        assert res["category"] == "severe"
        assert res["event_count"] == 2  # indices 0-1, and index 4

    def test_all_nans(self):
        """All NaN inputs should yield unknown category and NaN values."""
        s4 = np.array([np.nan, np.nan])
        res = classify_scintillation(s4)
        assert res["category"] == "unknown"
        assert np.isnan(res["s4_max"])
        assert res["event_count"] == 0


class TestEdgeAndNonUniformCases:
    """Additional edge cases across the suite."""

    def test_non_uniform_altitude_brunt_vaisala(self):
        """Radio occultation geometric grid with non-uniform delta_z."""
        alt_km = np.array([2.0, 2.2, 2.5, 3.0, 3.8, 5.0])
        theta_k = 290.0 + 4.0 * (alt_km - 2.0)
        n2 = compute_brunt_vaisala(alt_km, theta_k, smooth_window=1)
        assert len(n2) == len(alt_km)
        assert np.all(np.isfinite(n2))
        assert np.all(n2 > 0.0)

    def test_duplicate_altitudes_handling(self):
        """Duplicate altitudes in RO profiles should not divide by zero."""
        alt_km = np.array([10.0, 10.0, 11.0, 12.0, 12.0, 13.0])
        theta_k = np.array([300.0, 300.0, 305.0, 310.0, 310.0, 315.0])
        n2 = compute_brunt_vaisala(alt_km, theta_k, smooth_window=1)
        assert len(n2) == len(alt_km)
        assert np.all(np.isfinite(n2))

    def test_all_nan_arrays(self):
        """Verify behavior when entire profiles are missing (all NaN)."""
        nan_arr = np.full(10, np.nan)
        
        theta = compute_potential_temperature(nan_arr, nan_arr)
        assert np.all(np.isnan(theta))

        n2 = compute_brunt_vaisala(nan_arr, nan_arr)
        assert np.all(np.isnan(n2))

        vtec = compute_vtec(nan_arr, nan_arr)
        assert np.isnan(vtec["vtec_tecu"])

    def test_custom_planetary_gravity_brunt_vaisala(self):
        """Verify Brunt-Vaisala calculation scales linearly with planetary gravity."""
        z = np.linspace(10.0, 50.0, 41)
        theta = 300.0 + 2.0 * z

        n2_earth = compute_brunt_vaisala(z, theta, smooth_window=1, gravity_ms2=9.80665)
        n2_mars = compute_brunt_vaisala(z, theta, smooth_window=1, gravity_ms2=3.72)

        valid = np.isfinite(n2_earth) & np.isfinite(n2_mars)
        ratio = n2_mars[valid] / n2_earth[valid]
        np.testing.assert_allclose(ratio, 3.72 / 9.80665, rtol=1e-5)

    def test_atmospheric_gradient_with_duplicates_and_descending(self):
        """Verify robust gradient calculation on non-monotonic and duplicate coordinate grids."""
        from veda.analysis.atmospheric import _gradient_nan_safe
        z = np.array([50.0, 40.0, 30.0, 30.0, 20.0, 10.0])
        t = np.array([250.0, 260.0, 270.0, 270.0, 280.0, 290.0])

        grad = _gradient_nan_safe(z, t)
        assert grad.shape == z.shape
        assert np.all(np.isfinite(grad))
        # Lapse rate dT/dz is negative (-1.0 K/km) since T decreases with altitude
        assert np.all(grad < 0.0)

    def test_chapman_extreme_altitudes_no_overflow(self):
        """Verify Chapman layer fit avoids numerical exponential overflow on wide altitude grids."""
        from veda.analysis.wave_and_stability import fit_chapman_ionosphere
        z = np.linspace(50.0, 800.0, 100)
        # Theoretical Chapman profile with Nm = 1e5, hm = 300 km, H = 50 km
        zeta = (z - 300.0) / 50.0
        ne = 1e5 * np.exp(0.5 * (1.0 - zeta - np.exp(-zeta)))

        fit = fit_chapman_ionosphere(z, ne)
        assert fit["nmf2_cm3"] is not None
        assert abs(fit["nmf2_cm3"] - 1e5) < 5000.0
        assert fit["hmf2_km"] is not None
        assert abs(fit["hmf2_km"] - 300.0) < 5.0
        assert fit["r_squared"] is not None and fit["r_squared"] > 0.98

