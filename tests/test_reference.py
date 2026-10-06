"""Published reference atmospheres (analysis/reference.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis.atmospheric import compare_profiles_on_body, export_comparison_to_csv
from veda.analysis.reference import reference_on_pressure, reference_profile
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def test_venus_reference_values_and_interpolation():
    """VIRA mean values: 735.3 K and 92.1 bar at the surface, 350.5 K and 1.07 bar at 50 km."""
    t = reference_profile("venus", "temperature_k", [0.0, 50.0, 55.0, 200.0])
    assert t[0] == pytest.approx(735.3) and t[1] == pytest.approx(350.5)
    assert t[2] == pytest.approx((350.5 + 262.8) / 2) and np.isnan(t[3])
    p = reference_profile("venus", "pressure_hpa", [50.0, 55.0])
    assert p[0] == pytest.approx(1070.0) and p[1] == pytest.approx(np.sqrt(1070.0 * 236.0))
    venus = get_body("venus")
    h = reference_profile("venus", "scale_height", [50.0])[0]
    assert h == pytest.approx(venus.gas_constant_r * 350.5 / (8.87 * (6051.8 / 6101.8) ** 2 * 1000), rel=1e-6)
    assert reference_profile("jupiter", "temperature_k", [10.0]) is None
    tp = reference_on_pressure("venus", "temperature_k", [1070.0])
    assert tp[0] == pytest.approx(350.5, rel=1e-3)


def test_reference_in_a_comparison_and_its_csv():
    z = np.arange(45.0, 90.0, 1.0)
    venus = get_body("venus")
    profs = [ObservationProfile(observation_id=f"p{i}", mission_id="vex", body_id="venus", instrument="VeRa",
                                time_utc="2008-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                                temperature_k=reference_profile("venus", "temperature_k", z) + i) for i in range(3)]
    comp = compare_profiles_on_body(profs, venus, altitude_step_km=1.0, reference=True)
    ref = comp["reference"]
    assert "Venus-GRAM" in ref["name"] and len(ref["series"]) == len(comp["grid_km"])
    k = comp["grid_km"].index(50.0)
    assert ref["series"][k] == pytest.approx(350.5) and comp["composite_mean"][k] == pytest.approx(351.5)
    text = export_comparison_to_csv(comp)
    assert "reference_temperature_k" in text and "# reference: Venus-GRAM" in text
    assert compare_profiles_on_body(profs, venus, altitude_step_km=1.0)["reference"] is None
    assert compare_profiles_on_body(profs, get_body("jupiter"), altitude_step_km=1.0, reference=True)["reference"] is None


def test_mars_reference_is_hydrostatic_for_geometric_heights():
    """Mars-GRAM 2024 global average (Aviary table): its pressures follow from its
    temperatures with g falling as 1/r^2 (geometric heights), not with a constant g
    (geopotential heights, as the table's docstring says): within 3 % to 80 km against 20 % off."""
    from veda.analysis.reference import MARS_GRAM_2024
    mars = get_body("mars")
    t = np.array(MARS_GRAM_2024, dtype=float)
    z, temp, p, rho = t[:, 0], t[:, 1], t[:, 2], t[:, 3]
    r_spec = p * 100 / (rho * temp)
    assert np.median(r_spec) == pytest.approx(mars.gas_constant_r, rel=0.01)
    def integrate(g):
        f = g / (np.median(r_spec) * temp)
        return p[0] * np.exp(np.concatenate([[0.0], np.cumsum(-0.5 * (f[1:] + f[:-1]) * np.diff(z) * 1000)]))
    geometric = integrate(mars.surface_gravity * (mars.radius_km / (mars.radius_km + z)) ** 2)
    constant = integrate(np.full(z.size, mars.surface_gravity))
    assert np.max(np.abs(geometric / p - 1)) < 0.03
    assert abs(constant[-1] / p[-1] - 1) > 0.15
    assert reference_profile("mars", "temperature_k", [20.0])[0] == pytest.approx(188.3)
    assert reference_on_pressure("mars", "temperature_k", [0.947])[0] == pytest.approx(188.3, rel=1e-3)


def test_mars_reference_on_comparisons_notes_the_areoid():
    mars = get_body("mars")
    z = np.arange(0.0, 40.0, 1.0)
    profs = [ObservationProfile(observation_id=f"m{i}", mission_id="mex", body_id="mars", instrument="MaRS",
                                time_utc="2006-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                                temperature_k=reference_profile("mars", "temperature_k", z) + i,
                                pressure_hpa=reference_profile("mars", "pressure_hpa", z)) for i in range(3)]
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, reference=True)
    assert "Mars-GRAM 2024" in comp["reference"]["name"] and "areoid" in comp["reference"]["altitude_note"]
    on_p = compare_profiles_on_body(profs, mars, vertical="pressure", reference=True)
    ref = np.array([np.nan if v is None else v for v in on_p["reference"]["series"]])
    mean = np.array([np.nan if v is None else v for v in on_p["composite_mean"]])
    both = np.isfinite(ref) & np.isfinite(mean)
    assert both.sum() > 20 and np.allclose(mean[both] - ref[both], 1.0, atol=0.6)
