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


def _t_prof(oid, t0, n=41):
    z = np.arange(0.0, n * 1.0, 1.0)
    return ObservationProfile(observation_id=oid, mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="2005-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                              temperature_k=t0 + 0.5 * np.sin(z + len(oid)))


def test_outlier_screen_flags_and_optionally_leaves_out():
    from veda.analysis.atmospheric import compare_profiles_on_body, export_comparison_to_csv
    from veda.core.registry import get_body
    mars = get_body("mars")
    profs = [_t_prof(f"p{i}", 200.0 + i) for i in range(8)] + [_t_prof("hot", 260.0)]
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, outlier_z=3.5)
    scr = comp["outlier_screen"]
    assert scr["flagged"] == ["hot"] and not scr["left_out"] and comp["profile_count"] == 9
    hot = next(p for p in comp["profiles"] if p["observation_id"] == "hot")
    assert hot["outlier"]["flagged"] and hot["outlier"]["max_abs_z"] > 10
    assert not any(p["outlier"]["flagged"] for p in comp["profiles"] if p["observation_id"] != "hot")
    kept_mean = comp["composite_mean"][10]
    dropped = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, outlier_z=3.5, drop_outliers=True)
    assert dropped["profile_count"] == 8 and dropped["outlier_screen"]["left_out"]
    assert dropped["composite_mean"][10] < kept_mean - 5
    assert dropped["outlier_screen"]["left_out_profiles"][0]["observation_id"] == "hot"
    assert "# outlier screen: robust z > 3.5" in export_comparison_to_csv(dropped)
    assert compare_profiles_on_body(profs, mars, altitude_step_km=1.0)["outlier_screen"] is None


def test_outlier_screen_needs_enough_profiles():
    from veda.analysis.atmospheric import screen_outliers
    mat = np.array([[1.0, 1.0], [1.1, 1.2], [9.0, 9.0]])          # three profiles: too few to judge
    assert not any(f["flagged"] for f in screen_outliers(mat, 3.5))


def test_outlier_screen_within_groups():
    """Grouped by latitude, warm equatorial and cold polar profiles are judged within their
    own band: none is flagged, though against all profiles the minority band would be."""
    from veda.analysis.atmospheric import compare_profiles_on_body
    from veda.core.registry import get_body
    mars = get_body("mars")
    profs = []
    for i in range(6):
        a, b = _t_prof(f"eq{i}", 220.0 + i), _t_prof(f"po{i}", 160.0 + i)
        a.latitude, b.latitude = 5.0, 75.0
        profs += [a, b]
    profs += [_t_prof(f"x{i}", 221.0 + i) for i in range(6)]
    for p in profs[-6:]:
        p.latitude = 10.0
    grouped = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, outlier_z=3.5, group_by="latitude", group_width=30.0)
    assert grouped["outlier_screen"]["flagged"] == [] and grouped["outlier_screen"]["against"] == "own group"
    alone = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, outlier_z=3.5)
    assert sorted(alone["outlier_screen"]["flagged"]) == [f"po{i}" for i in range(6)]


def test_latitude_cross_section_with_errors():
    from veda.analysis.atmospheric import compare_profiles_on_body, export_cross_section_to_csv
    from veda.core.registry import get_body
    mars = get_body("mars")
    profs = []
    for i, (lat, t0) in enumerate([(-45, 180), (-42, 184), (5, 210), (8, 214), (2, 212), (70, 150), (None, 999)]):
        p = _t_prof(f"q{i}", float(t0))
        p.latitude = lat
        profs.append(p)
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, cross_section_width=30.0)
    xs = comp["cross_section"]
    assert xs["latitude_centers"] == [-45.0, 15.0, 75.0] and xs["without_latitude"] == 1
    k = 10
    vals = [p["interpolated_series"][k] for p in comp["profiles"][2:5]]
    assert xs["mean"][1][k] == pytest.approx(np.mean(vals), rel=1e-5)
    assert xs["sem"][1][k] == pytest.approx(np.std(vals, ddof=1) / np.sqrt(3), rel=1e-3)
    assert xs["profiles"][2][k] == 1 and xs["sem"][2][k] is None
    text = export_cross_section_to_csv(comp)
    assert text.splitlines()[3].startswith("latitude_center_deg,altitude_km,mean_temperature_k,sem,profiles")
    assert compare_profiles_on_body(profs, mars, altitude_step_km=1.0)["cross_section"] is None


def test_cross_section_endpoint():
    from fastapi.testclient import TestClient
    from veda.api.app import create_app
    c = TestClient(create_app())
    r = c.post("/api/veda/export/compare/venus/cross-section", json={"variable": "temperature_k"})
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert r.text.splitlines()[1].startswith("# recipe: ")
