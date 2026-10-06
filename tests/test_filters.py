"""Profile filters of a comparison: altitude coverage, vertical resolution, uncertainty,
data sets and instruments (missions/selection.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.core.models import ObservationProfile
from veda.missions import selection
from veda.missions.selection import ProfileFilter, quality_passes


def _prof(z0=40.0, z1=90.0, dz=0.5, sigma=1.0, oid="p"):
    z = np.arange(z0, z1 + 1e-9, dz)
    return ObservationProfile(observation_id=oid, mission_id="vex", body_id="venus", instrument="VeRa",
                              time_utc="2008-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                              temperature_k=np.full(z.size, 250.0),
                              uncertainty={} if sigma is None else {"temperature_k": np.full(z.size, sigma)})


def test_coverage_spacing_and_uncertainty_limits():
    p = _prof()
    assert quality_passes(p, ProfileFilter(), "temperature_k") == (True, "")
    assert quality_passes(p, ProfileFilter(cover_min_km=45, cover_max_km=85), "temperature_k")[0]
    assert quality_passes(p, ProfileFilter(cover_min_km=35), "temperature_k") == (False, "altitude range not covered")
    assert quality_passes(p, ProfileFilter(cover_max_km=95), "temperature_k") == (False, "altitude range not covered")
    assert quality_passes(p, ProfileFilter(max_spacing_km=0.5), "temperature_k")[0]
    assert quality_passes(p, ProfileFilter(max_spacing_km=0.2), "temperature_k") == (False, "levels too far apart")
    assert quality_passes(p, ProfileFilter(max_sigma=2.0), "temperature_k")[0]
    assert quality_passes(p, ProfileFilter(max_sigma=0.5), "temperature_k") == (False, "uncertainty above the limit")
    assert quality_passes(p, ProfileFilter(max_sigma_pct=0.5), "temperature_k")[0]            # 1 K of 250 K = 0.4 %
    assert quality_passes(p, ProfileFilter(max_sigma_pct=0.3), "temperature_k")[1] == "uncertainty above the limit"
    assert quality_passes(_prof(sigma=None), ProfileFilter(max_sigma=5.0), "temperature_k") == (False, "no uncertainty")
    assert quality_passes(p, ProfileFilter(cover_min_km=45), "electron_density_cm3") == (False, "variable missing")


def test_filters_are_described_and_need_a_larger_budget():
    f = ProfileFilter(cover_min_km=50, max_sigma_pct=2, datasets=["vex-vera-fsi-imamura"], instruments=["VeRa (Radio Science)"])
    d = f.describe()
    assert "covering 50 to ... km" in d and "1-sigma at most 2 %" in d
    assert any(x.startswith("data sets ") for x in d) and any(x.startswith("instruments ") for x in d)
    assert f.geometry_limits() and not ProfileFilter(datasets=["x"]).geometry_limits()


def test_data_set_and_instrument_choice_limits_the_candidates(monkeypatch):
    seen = {}

    def fake_candidates(ds_ids, f, variable, n):
        seen.setdefault("ids", []).append(list(ds_ids))
        return 0, []
    monkeypatch.setattr(selection, "_candidates", fake_candidates)
    monkeypatch.setattr(selection.catalog, "dataset_status", lambda ds: {"indexed_volumes": 1})
    selection.select_profiles(None, "venus", ["vex"], "temperature_k",
                              ProfileFilter(datasets=["vex-vera-fsi-imamura"], include_uploads=False))
    assert seen["ids"][-1] == ["vex-vera-fsi-imamura"]
    selection.select_profiles(None, "venus", ["vex"], "temperature_k",
                              ProfileFilter(instruments=["SPICAV-SOIR"], include_uploads=False))
    assert seen["ids"][-1] == ["vex-soir-co2-temperature"]


def test_filter_reaches_the_api_report_and_recipe(monkeypatch):
    from fastapi.testclient import TestClient
    from veda.api.app import create_app

    def fake_select(manager, body_id, mission_ids, variable, f):
        return [_prof(oid="a"), _prof(oid="b")], {"vex": {"in_date_range": 2, "tried": 2, "kept": 2, "left_out": {}, "failed": 0}}
    monkeypatch.setattr(selection, "select_profiles", fake_select)
    c = TestClient(create_app())
    req = {"variable": "temperature_k", "missions": ["vex"],
           "filter": {"cover_min_km": 45, "cover_max_km": 85, "max_spacing_km": 1, "max_sigma": 3}}
    r = c.post("/api/veda/compare/body/venus", json=req)
    assert r.status_code == 200
    assert "covering 45 to 85 km" in r.json()["selection_filters"]
    text = c.post("/api/veda/export/compare/venus/csv", json=req).text
    recipe = next(line for line in text.splitlines() if line.startswith("# recipe: "))
    assert '"cover_min_km":45' in recipe.replace(".0", "")
    bad = {**req, "filter": {"cover_min_km": 90, "cover_max_km": 50}}
    assert c.post("/api/veda/compare/body/venus", json=bad).status_code == 422
