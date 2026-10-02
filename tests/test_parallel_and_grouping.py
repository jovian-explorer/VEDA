"""Worker-pool helpers, the performance settings and grouped (climatology) composites."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from veda import parallel
from veda.analysis.atmospheric import GROUPINGS, compare_profiles_on_body
from veda.api.app import create_app
from veda.config import SETTINGS, Settings
from veda.core.models import ObservationProfile
from veda.core.registry import get_body


def _square(x):
    if x < 0:
        raise ValueError("negative")
    return x * x


@pytest.fixture
def workers():
    saved = SETTINGS.cpu_workers

    def set_(n):
        SETTINGS.cpu_workers = n
    yield set_
    SETTINGS.cpu_workers = saved
    parallel.shutdown()


def test_cpu_map_serial_keeps_order_and_returns_exceptions(workers):
    workers(1)
    out = parallel.cpu_map(_square, [(3,), (-1,), (5,)])
    assert out[0] == 9 and out[2] == 25 and isinstance(out[1], ValueError)
    assert parallel.process_pool() is None


def test_cpu_map_pool_matches_serial(workers):
    workers(2)
    args = [(i,) for i in range(-2, 20)]
    out = parallel.cpu_map(_square, args)
    assert [o for o in out if not isinstance(o, Exception)] == [i * i for i in range(0, 20)]
    assert sum(isinstance(o, ValueError) for o in out) == 2


def test_thread_map_reports_progress():
    seen = []
    out = parallel.thread_map(_square, [(i,) for i in range(6)], workers=3, on_done=lambda i, r: seen.append(i))
    assert out == [i * i for i in range(6)] and sorted(seen) == list(range(6))


@pytest.mark.parametrize("key,bad", [("cpu_workers", 0), ("cpu_workers", 65), ("cpu_workers", 2.5),
                                     ("download_workers", 0), ("download_workers", 17)])
def test_performance_settings_are_validated(key, bad):
    with pytest.raises(ValueError):
        Settings.validate(key, bad)
    assert Settings.validate(key, 4) == 4


def test_meta_reports_cpu_count():
    meta = TestClient(create_app()).get("/api/meta").json()
    assert meta["system"]["cpu_count"] >= 1


def _profile(oid, lat, t_offset, time="2010-03-05T00:00:00"):
    z = np.arange(0.0, 50.0, 1.0)
    return ObservationProfile(observation_id=oid, mission_id="vex", body_id="venus", instrument="VeRa",
                              time_utc=time, altitude_km=z, temperature_k=250.0 - z + t_offset,
                              latitude=lat)


def test_grouped_composites_by_latitude():
    profs = [_profile("a", 5.0, 0.0), _profile("b", 10.0, 2.0), _profile("c", 70.0, 10.0), _profile("d", None, 0.0)]
    res = compare_profiles_on_body(profs, get_body("venus"), 1.0, "temperature_k", group_by="latitude", group_width=30.0)
    groups = {g["label"]: g for g in res["groups"]}
    assert set(groups) == {"Latitude 0 to 30°", "Latitude 60 to 90°", "1 profile without latitude"}
    low = groups["Latitude 0 to 30°"]
    assert low["n"] == 2 and sorted(low["observation_ids"]) == ["a", "b"]
    k = res["grid_km"].index(10.0)
    assert low["mean"][k] == pytest.approx(241.0)          # (240 + 242) / 2
    assert groups["Latitude 60 to 90°"]["mean"][k] == pytest.approx(250.0)
    assert groups["1 profile without latitude"]["ungrouped"]


def test_grouping_by_month_of_year_merges_years():
    profs = [_profile("a", 0.0, 0.0, "2008-07-01T00:00:00"), _profile("b", 0.0, 0.0, "2012-07-20T00:00:00"),
             _profile("c", 0.0, 0.0, "2012-01-02T00:00:00")]
    res = compare_profiles_on_body(profs, get_body("venus"), 1.0, "temperature_k", group_by="month_of_year")
    assert [(g["label"], g["n"]) for g in res["groups"]] == [("Jan", 1), ("Jul", 2)]


def test_unknown_grouping_is_rejected_by_the_api():
    client = TestClient(create_app())
    assert "month_of_year" in GROUPINGS
    r = client.post("/api/veda/compare/body/venus", json={"variable": "temperature_k", "group_by": "zodiac"})
    assert r.status_code in (400, 422)
