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


def test_hydrostatic_consistency_flags_inconsistent_pressures():
    """An exactly hydrostatic profile departs by nothing; a 10 % pressure error at one level
    shows there, at its altitude, and leaves the other levels (the median) at zero; a
    wrong altitude scale is seen everywhere."""
    from veda.analysis.hydrostatic import hydrostatic_consistency
    temp = (lambda zz: 210.0 - 0.8 * (zz - 0.0))
    z = np.arange(0.0, 60.01, 0.5)
    rho = _atmosphere(temp, z)
    p_hpa = rho * R_MARS * temp(z) / 100.0
    good = hydrostatic_consistency(z, p_hpa, temp(z), _g(z), R_MARS)
    assert good["hydrostatic_max_pct"] < 0.01
    bad = p_hpa.copy()
    bad[40] *= 1.1
    r = hydrostatic_consistency(z, bad, temp(z), _g(z), R_MARS)
    assert r["hydrostatic_max_pct"] == pytest.approx(10.0, abs=0.05) and r["hydrostatic_max_km"] == z[40]
    assert r["hydrostatic_median_pct"] < 0.01
    stretched = hydrostatic_consistency(z * 1.05, p_hpa, temp(z), _g(z), R_MARS)
    assert stretched["hydrostatic_max_pct"] > 10.0
    assert hydrostatic_consistency(z[:2], p_hpa[:2], temp(z[:2]), _g(z[:2]), R_MARS)["hydrostatic_max_pct"] is None


def test_profiles_with_temperature_and_pressure_report_their_hydrostatic_balance():
    from veda.analysis.atmospheric import compute_atmospheric_diagnostics, profile_diagnostics
    mars = get_body("mars")
    temp = (lambda zz: 200.0 + 0 * zz)
    z = np.arange(0.0, 40.01, 1.0)
    g = mars.surface_gravity * (mars.radius_km / (mars.radius_km + z)) ** 2
    p = 6.1 * np.exp(-np.concatenate([[0.0], np.cumsum(0.5 * (g[1:] + g[:-1]) * 1000.0)]) / (mars.gas_constant_r * 200.0))
    prof = ObservationProfile(observation_id="x", mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="", altitude_km=z, temperature_k=temp(z), pressure_hpa=p)
    prof.derived.update(compute_atmospheric_diagnostics(prof, mars))
    d = profile_diagnostics(prof)
    assert d["hydrostatic_max_pct"] < 1e-6 and d["hydrostatic_median_pct"] < 1e-6


def test_temperature_from_the_density_of_one_gas_uses_its_molar_mass():
    """Cassini UVIS gives the H2 density of Saturn's thermosphere: an isothermal 450 K H2
    profile must come back at 450 K, not 14 % higher with the bulk molar mass."""
    from veda.analysis.atmospheric import compute_atmospheric_diagnostics, gravity_profile
    from veda.core.models import ObservationProfile
    from veda.core.registry import get_body
    saturn = get_body("saturn")
    z = np.arange(800.0, 2000.0, 10.0)
    ref = "the 1-bar level of Saturn along the surface normal"
    g, _ = gravity_profile(saturn, z, 0.0, ref)
    r_h2 = 8314.46 / 2.01588
    h = r_h2 * 450.0 / g                                     # m, local scale height
    n = 1e17 * np.exp(-np.concatenate([[0.0], np.cumsum(np.diff(z) * 1000 / (0.5 * (h[1:] + h[:-1])))]))
    for mu, expected in ((2.01588, 450.0), (None, 450.0 * 8314.46 / saturn.gas_constant_r / 2.01588)):
        prof = ObservationProfile(observation_id="u", mission_id="cassini", body_id="saturn", instrument="UVIS",
                                  time_utc="2017-07-14T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                                  raw_attributes={"ALTITUDE_REFERENCE": ref, **({"DENSITY_MOLAR_MASS": mu} if mu else {})})
        prof.derived["number_density_m3"] = n
        t = compute_atmospheric_diagnostics(prof, saturn)["temperature_from_density"]
        assert np.nanmedian(t[:60]) == pytest.approx(expected, rel=0.01)
