"""Hydrostatic temperature retrieval from density profiles (analysis/hydrostatic.py)."""
from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from veda.analysis.hydrostatic import temperature_from_density
from veda.core.models import ObservationProfile
from veda.core.registry import get_body

R_MARS = 191.2


def _g(z):
    return 3.71 * (3389.5 / (3389.5 + z)) ** 2


def _atmosphere(temp, z):
    """Density (kg/m^3) of a hydrostatic Mars atmosphere with temperature temp(z), z in km."""
    sol = solve_ivp(lambda zz, y: -_g(zz) * 1000.0 / (R_MARS * temp(zz)), [z[0], z[-1]], [0.0],
                    dense_output=True, rtol=1e-12, atol=1e-12)
    return np.exp(sol.sol(z)[0]) / (R_MARS * temp(z))


def test_isothermal_atmosphere_recovered_exactly():
    """The top is fitted against the geopotential, so an isothermal atmosphere comes back
    at its temperature everywhere although g changes by 6 % over the profile."""
    z = np.arange(80.0, 180.01, 0.5)
    rho = _atmosphere(lambda zz: 200.0 + 0 * zz, z)
    r = temperature_from_density(z, rho, _g(z), R_MARS)
    np.testing.assert_allclose(r["temperature_k"], 200.0, atol=1e-3)
    assert r["top_temperature_k"] == pytest.approx(200.0, abs=1e-3) and r["top_km"] == 180.0
    np.testing.assert_allclose(r["pressure_pa"], rho * R_MARS * 200.0, rtol=1e-6)


def test_wavy_profile_recovered_below_the_boundary_region():
    """A non-isothermal top gives a wrong boundary temperature, whose error decays by e
    every scale height (about 10 km here): two scale heights down the profile is good to
    a few tenths of a kelvin, unsorted levels and missing values included."""
    temp = (lambda zz: 150.0 + (zz - 100.0) + 15.0 * np.sin(2 * np.pi * zz / 12.0))
    z = np.arange(80.0, 180.01, 0.5)
    rho = _atmosphere(temp, z)
    order = np.random.default_rng(0).permutation(z.size)
    zz, rr = z[order], rho[order].copy()
    rr[5] = np.nan
    r = temperature_from_density(zz, rr, _g(zz), R_MARS)
    err = r["temperature_k"] - temp(zz)
    assert np.isnan(r["temperature_k"][5])
    low = zz < 140.0
    assert np.nanmax(np.abs(err[low])) < 1.6
    assert np.nanmax(np.abs(err[zz < 120.0])) < 0.1
    assert abs(r["top_temperature_k"] - temp(180.0)) > 5.0          # the boundary itself is off


def test_given_top_temperature_and_too_short_profiles():
    z = np.arange(100.0, 150.01, 1.0)
    rho = _atmosphere(lambda zz: 180.0 + 0 * zz, z)
    r = temperature_from_density(z, rho, _g(z), R_MARS, t_top=180.0)
    np.testing.assert_allclose(r["temperature_k"], 180.0, atol=1e-3)
    short = temperature_from_density(z[:3], rho[:3], _g(z[:3]), R_MARS)
    assert short["top_temperature_k"] is None and np.isnan(short["temperature_k"]).all()
    rising = temperature_from_density(z, rho[::-1], _g(z), R_MARS)          # density growing upwards
    assert rising["top_temperature_k"] is None


def test_profiles_with_a_number_density_get_hydrostatic_temperature():
    """Diagnostics add temperature and pressure from a measured number density
    (rho = n k_B / R): the SOIR case, checked against the archived temperatures."""
    from veda.analysis.atmospheric import compute_atmospheric_diagnostics
    venus = get_body("venus")
    z = np.arange(80.0, 130.01, 1.0)
    g = venus.surface_gravity * (venus.radius_km / (venus.radius_km + z)) ** 2
    sol = solve_ivp(lambda zz, y: -np.interp(zz, z, g) * 1000.0 / (venus.gas_constant_r * 170.0), [80, 130], [0.0],
                    dense_output=True, rtol=1e-12, atol=1e-12)
    rho = np.exp(sol.sol(z)[0]) * 1e-4
    prof = ObservationProfile(observation_id="x", mission_id="vex", body_id="venus", instrument="SOIR",
                              time_utc="", latitude=None, longitude=None, altitude_km=z)
    prof.derived["number_density_m3"] = rho * venus.gas_constant_r / 1.380649e-23
    d = compute_atmospheric_diagnostics(prof, venus)
    np.testing.assert_allclose(d["temperature_from_density"], 170.0, atol=0.01)
    np.testing.assert_allclose(d["pressure_from_density"], rho * venus.gas_constant_r * 170.0 / 100.0, rtol=1e-4)
    assert prof.raw_attributes["hydrostatic_top_km"] == 130.0


def test_hydrostatic_variables_come_from_density_data_sets():
    from veda.archives.datasets import get_dataset
    from veda.missions.selection import provides
    for ds_id in ("mro-m-accel-5-profile-v1.0", "ody-m-accel-5-derived-v1.0", "vex-soir-co2-temperature",
                  "phx-m-ase-5-edl-rdr-v1.0"):
        assert provides(get_dataset(ds_id), "temperature_from_density")
    assert not provides(get_dataset("hp-ssa-hasi-2-3-4-mission-v1.1"), "temperature_from_density")
