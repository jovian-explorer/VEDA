"""Unit tests for VEDA Atmospheric Wave, Stability, and Chapman Ionosphere Module."""
import numpy as np
import pytest

from veda.analysis.wave_and_stability import (
    detect_tropopause,
    extract_gravity_wave_activity,
    fit_chapman_ionosphere,
)


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
