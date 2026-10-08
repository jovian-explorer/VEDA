"""CO2 frost point and the margin of a temperature profile above it (analysis/condensation.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis.atmospheric import compute_atmospheric_diagnostics, profile_diagnostics
from veda.analysis.condensation import co2_condensation_temperature, co2_volume_fraction
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def test_frost_point_formula():
    """James et al. (1992) as in Greve et al. (2010, eq. 7): 700 Pa gives 148.7 K."""
    assert co2_condensation_temperature(7.0, 1.0) == pytest.approx(148.69, abs=0.01)
    # colder at lower pressure; the CO2 partial pressure counts (Mars: 95.1 % CO2)
    tc = co2_condensation_temperature(np.array([6.1, 0.1, 1e-3]), co2_volume_fraction(get_body("mars")))
    assert tc[0] > tc[1] > tc[2] and tc[0] == pytest.approx(3182.48 / (23.3494 - np.log(6.1 * 0.951)))
    assert co2_volume_fraction(get_body("mars")) == pytest.approx(0.951)
    assert co2_volume_fraction(get_body("jupiter")) is None
    assert np.isnan(co2_condensation_temperature(-1.0, 0.95))


def _mars_polar_night(dt_cold=-2.0):
    """A polar-night profile that touches the frost point 2 K below it at 8 km."""
    mars = get_body("mars")
    z = np.arange(0.0, 30.0, 0.5)
    p = 6.0 * np.exp(-z / 9.0)
    tc = co2_condensation_temperature(p, 0.951)
    t = tc + 8.0 + (dt_cold - 8.0) * np.exp(-((z - 8.0) / 1.5) ** 2)
    prof = ObservationProfile(observation_id="pn", mission_id="mgs", body_id="mars", instrument="RS",
                              time_utc="1999-05-01T00:00:00", latitude=-80.0, longitude=0.0, altitude_km=z,
                              temperature_k=t, pressure_hpa=p,
                              uncertainty={"temperature_k": np.full(z.size, 1.0), "pressure_hpa": 0.01 * p})
    prof.derived = compute_atmospheric_diagnostics(prof, mars)
    return prof, tc


def test_margin_above_the_frost_point_with_its_uncertainty():
    prof, tc = _mars_polar_night()
    np.testing.assert_allclose(prof.derived["co2_condensation_temperature"], tc, rtol=1e-12)
    margin = prof.derived["t_minus_co2_condensation"]
    np.testing.assert_allclose(margin, prof.temperature_k - tc, rtol=1e-12)
    d = profile_diagnostics(prof)
    assert d["co2_margin_min_k"] == pytest.approx(np.min(margin), abs=0.01) and d["co2_margin_min_k"] < 0
    assert d["co2_margin_min_km"] == pytest.approx(8.0, abs=0.5)
    # sigma: T's 1 K and the frost point's from 1 % in p: T_c^2 / b * 0.01
    k = int(np.argmin(margin))
    s_tc = tc[k] ** 2 / 3182.48 * 0.01
    assert prof.uncertainty["co2_condensation_temperature"][k] == pytest.approx(s_tc, rel=1e-6)
    assert d["co2_margin_min_sigma_k"] == pytest.approx(np.hypot(1.0, s_tc), abs=0.01)


def test_no_frost_point_without_co2_or_pressure():
    jup = get_body("jupiter")
    z = np.arange(0.0, 50.0, 1.0)
    prof = ObservationProfile(observation_id="j", mission_id="galileo", body_id="jupiter", instrument="ASI",
                              time_utc="1995-12-07T00:00:00", latitude=6.5, longitude=0.0, altitude_km=z,
                              temperature_k=170.0 - z, pressure_hpa=1000 * np.exp(-z / 25.0))
    assert "t_minus_co2_condensation" not in compute_atmospheric_diagnostics(prof, jup)
    prof, _ = _mars_polar_night()
    prof.pressure_hpa = None
    prof.derived = compute_atmospheric_diagnostics(prof, get_body("mars"))
    assert "t_minus_co2_condensation" not in prof.derived
