"""Real-gas compressibility of Titan's troposphere (analysis/realgas.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis.realgas import compressibility, second_virial
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def test_second_virial_coefficient_of_nitrogen():
    """The Tsonopoulos correlation against tabulated values for N2 (about -160 cm^3/mol at
    100 K, -35 at 200 K): within 5 % where Titan's troposphere is."""
    b = second_virial(np.array([100.0, 200.0]), {"N2": 1.0}) * 1e6
    assert b[0] == pytest.approx(-160.0, rel=0.05)
    assert b[1] == pytest.approx(-35.2, rel=0.06)
    assert compressibility(get_body("mars"), np.array([200.0]), np.array([6.0])) is None      # ideal elsewhere


def test_titan_troposphere_is_treated_as_a_real_gas():
    """A Titan profile hydrostatic with p = Z n k T (Z = 0.96 at the surface): with the
    real gas the hydrostatic check finds no departure, the mass density is n m (the ideal
    gas gave 4 % less) and the temperature retrieved from the density is the profile's."""
    from veda.analysis.atmospheric import compute_atmospheric_diagnostics, gravity_profile
    titan = get_body("titan")
    z = np.arange(0.0, 60.01, 0.5)
    t = np.where(z < 40, 94.0 - 0.65 * z, 68.0 + 0.0 * z)
    g, _ = gravity_profile(titan, z, None, "")
    r = titan.gas_constant_r
    # integrate dp/dz = -p g / (Z R T) with Z(T, p) by small steps
    p = np.empty(z.size)
    p[0] = 1.467e5
    for i in range(1, z.size):
        pi = p[i - 1]
        for _ in range(3):
            zm = compressibility(titan, np.array([0.5 * (t[i] + t[i - 1])]), np.array([0.5 * (pi + p[i - 1]) / 100]))[0]
            pi = p[i - 1] * np.exp(-0.5 * (g[i] + g[i - 1]) * 500.0 / (zm * r * 0.5 * (t[i] + t[i - 1])))
        p[i] = pi
    zc = compressibility(titan, t, p / 100.0)
    assert zc[0] == pytest.approx(0.962, abs=0.004)
    n = p / (zc * 1.380649e-23 * t)
    prof = ObservationProfile(observation_id="ti", mission_id="cassini", body_id="titan", instrument="RSS",
                              time_utc="2006-03-19T00:00:00", altitude_km=z, temperature_k=t, pressure_hpa=p / 100.0)
    prof.derived["number_density_m3"] = n
    prof.derived.update(compute_atmospheric_diagnostics(prof, titan))
    assert prof.raw_attributes["hydrostatic_max_pct"] < 0.05
    np.testing.assert_allclose(prof.derived["density"], n * 1.380649e-23 / r, rtol=1e-6)
    np.testing.assert_allclose(prof.derived["temperature_from_density"][:60], t[:60], rtol=2e-3)
    assert "real gas" in prof.raw_attributes["equation_of_state"]
