"""Coincident pairs between groups of compared profiles (analysis/coincidence.py)."""
from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from veda.analysis.atmospheric import compare_profiles_on_body, export_comparison_to_csv
from veda.analysis.coincidence import DEFAULT_TOLERANCES, match_pairs, separations
from veda.api.app import create_app
from veda.core.models import ObservationProfile
from veda.core.registry import get_body

MCS, RSS = "MCS (Mars Climate Sounder)", "RSS (Radio Science)"


def _s(t, lat, lon=None, lst=None):
    return {"time_utc": t, "latitude": lat, "longitude": lon, "lst": lst}


def test_separations_wrap_longitude_and_local_time():
    sep = separations(_s("2011-12-01T23:30:00Z", 60.0, 359.0, 23.5), _s("2011-12-02T00:30:00", 62.5, 1.0, 0.5))
    assert sep == pytest.approx({"hours": 1.0, "lat": 2.5, "lon": 2.0, "lst": 1.0})
    assert separations(_s("", 0.0), _s("2011-12-01T00:00:00", 0.0))["hours"] is None


def test_pairs_are_closest_first_and_independent():
    """Each profile is in one pair at most, the closest pairs first; a pair outside a
    tolerance is not made; a criterion is skipped for a profile without that quantity, but
    time and latitude are always needed."""
    a = [_s("2011-12-01T00:00:00", 60.0, 10.0, 3.0), _s("2011-12-01T06:00:00", 60.0, 10.0, 3.0)]
    b = [_s("2011-12-01T00:10:00", 60.5, 10.0, 3.0),      # closest to a0
         _s("2011-12-01T00:20:00", 61.0, 10.0, 3.0),      # closer to a0 too, but a0 is taken: a1
         _s("2011-12-01T00:05:00", 70.0, 10.0, 3.0)]      # 10 deg of latitude away: no pair
    assert [(i, j) for i, j, _ in match_pairs(a, b, DEFAULT_TOLERANCES)] == [(0, 0), (1, 1)]
    assert [(i, j) for i, j, _ in match_pairs(a, b, {**DEFAULT_TOLERANCES, "hours": 1.0})] == [(0, 0)]
    no_lon = [_s("2011-12-01T00:00:00", 0.0)]
    assert len(match_pairs(no_lon, [_s("2011-12-01T01:00:00", 1.0, 200.0, 12.0)], DEFAULT_TOLERANCES)) == 1
    assert match_pairs(no_lon, [_s("", 0.0, 0.0, 0.0)], DEFAULT_TOLERANCES) == []


def _pair_profiles():
    """Eight coincident MCS and RSS profiles over two months at latitudes 60 to 74 deg,
    whose atmosphere differs by up to 28 K from one pair to the next; RSS reads 2 K warmer
    (+-0.3 K of noise) and 10 % higher pressure.  Three more RSS profiles, a month after
    any MCS profile and 15 K colder, change the RSS climatology but have no partner."""
    z = np.arange(0.0, 40.0, 1.0)

    def prof(oid, instrument, day, hour, lat, t0, p0):
        return ObservationProfile(observation_id=oid, mission_id="mro", body_id="mars", instrument=instrument,
                                  time_utc=f"2011-12-{day:02d}T{hour:02d}:00:00", latitude=lat, longitude=30.0,
                                  altitude_km=z, temperature_k=t0 - 1.5 * z, pressure_hpa=p0 * np.exp(-z / 10.0))
    out = []
    for i in range(8):
        t0, p0 = 190.0 + 4.0 * i, 6.0 + 0.2 * i
        out.append(prof(f"m{i}", MCS, 1 + 2 * i, 3, 60.0 + 2 * i, t0, p0))
        out.append(prof(f"r{i}", RSS, 1 + 2 * i, 4, 60.5 + 2 * i, t0 + 2.0 + (0.3 if i % 2 else -0.3), 1.1 * p0))
    for i in range(3):
        out.append(prof(f"x{i}", RSS, 25 + i, 3, 62.0, 180.0, 6.0))
    return out


def test_coincident_pairs_recover_the_offset_that_sampling_hides():
    mars, profs = get_body("mars"), _pair_profiles()
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="instrument", coincidence={})
    d = comp["coincident_differences"][0]
    assert d["label"] == f"MRO {RSS} minus MRO {MCS}" and d["reference_group"] == f"MRO {MCS}"
    assert d["n_pairs"] == 8 and {(p["first"], p["other"]) for p in d["pairs"]} == {(f"m{i}", f"r{i}") for i in range(8)}
    assert d["pairs"][0]["hours"] == pytest.approx(1.0) and d["pairs"][0]["lat"] == pytest.approx(0.5)
    k = 10
    assert d["difference"][k] == pytest.approx(2.0, abs=1e-6)
    assert d["se"][k] == pytest.approx(0.3 * np.sqrt(8 / 7) / np.sqrt(8), rel=1e-3)
    assert d["ci95_low"][k] < 2.0 < d["ci95_high"][k] and d["ci95_high"][k] - d["ci95_low"][k] < 0.6
    assert d["pairs_per_level"][k] == 8 and len(d["pair_series"]) == 8 and not d["percent"]
    # the climatologies differ by much more: the unpaired cold profiles pull the RSS mean down
    g = comp["group_differences"][0]
    assert g["difference"][k] < -3.0 and g["se"][k] > 2.0
    # log-averaged variables: in percent of the first group
    p = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="instrument", coincidence={},
                                 variable_name="pressure_hpa")["coincident_differences"][0]
    assert p["percent"] and p["difference"][k] == pytest.approx(10.0, abs=1e-6) and p["se"][k] == pytest.approx(0.0, abs=1e-9)
    # tighter tolerances: no pair (the partners are an hour apart); not grouped or not asked: nothing
    none = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="instrument",
                                    coincidence={"hours": 0.5})["coincident_differences"][0]
    assert none["n_pairs"] == 0 and none["difference"] == []
    assert compare_profiles_on_body(profs, mars, altitude_step_km=1.0, coincidence={})["coincident_differences"] == []
    assert compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="instrument")["coincident_differences"] == []
    text = export_comparison_to_csv(comp)
    assert f"MRO {RSS} minus MRO {MCS} pairs difference" in text and "pairs at level" in text
    assert "# coincident pairs" in text and "8 pairs within 12 h" in text and "m0/r0" in text


def test_api_takes_tolerances_and_the_recipe_keeps_them():
    client = TestClient(create_app())
    base = {"missions": ["mex"], "variable": "temperature_k", "group_by": "latitude",
            "filter": {"start": "2004-04-01", "end": "2004-04-03", "download": False}}
    r = client.post("/api/veda/compare/body/mars", json={**base, "coincidence": {"hours": 6}})
    assert r.status_code == 200 and "coincident_differences" in r.json()
    for bad in ({"hours": 0}, {"lat": -1}, {"lst": 13}):
        assert client.post("/api/veda/compare/body/mars", json={**base, "coincidence": bad}).status_code == 422
    csv = client.post("/api/veda/export/compare/mars/csv", json={**base, "coincidence": {"hours": 6}}).text
    recipe = json.loads(next(l for l in csv.splitlines() if l.startswith("# recipe: "))[len("# recipe: "):])
    assert recipe["coincidence"] == {**DEFAULT_TOLERANCES, "hours": 6.0}
