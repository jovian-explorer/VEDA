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


@pytest.mark.parametrize("failure", ["cancelled", "shut down"])
def test_cpu_map_finishes_when_the_pool_is_replaced_meanwhile(monkeypatch, failure):
    """Bug: changing the number of workers shuts the old pool down with its queued work
    cancelled; a comparison using it then failed with CancelledError (a server error)."""
    from concurrent.futures import Future
    from veda import parallel

    class ReplacedPool:
        def submit(self, fn, *args):
            if failure == "shut down":
                raise RuntimeError("cannot schedule new futures after shutdown")
            f = Future()
            f.cancel()
            f.set_running_or_notify_cancel()      # as the executor does for cancelled work
            return f
    monkeypatch.setattr(parallel, "process_pool", lambda: ReplacedPool())
    assert parallel.cpu_map(pow, [(2, 3), (3, 2), (5, 0)]) == [8, 9, 1]


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


def test_comparison_csv_keeps_small_values_and_groups():
    from veda.analysis.atmospheric import export_comparison_to_csv
    z = np.arange(0.0, 20.0, 1.0)
    profs = []
    for oid, lat, scale in (("a", 5.0, 1.0), ("b", 10.0, 1.2), ("c", 70.0, 2.0)):
        p = _profile(oid, lat, 0.0)
        p.altitude_km = z
        p.temperature_k = None
        p.derived["density"] = 1e-7 * scale * np.exp(-z / 10.0)      # kg/m3, as in the Mars thermosphere
        profs.append(p)
    comp = compare_profiles_on_body(profs, get_body("venus"), 1.0, "density", group_by="latitude", group_width=30.0)
    text = export_comparison_to_csv(comp)
    rows = [l for l in text.splitlines() if not l.startswith("#")]
    header = rows[0].split(",")
    assert "Latitude 0 to 30 deg mean" in header and "profiles_at_level" in header
    first = dict(zip(header, rows[1].split(",")))
    assert float(first["composite_mean_density"]) == pytest.approx(1e-7 * (1.0 * 1.2 * 2.0) ** (1 / 3), rel=1e-4)
    assert float(first["Latitude 0 to 30 deg mean"]) == pytest.approx(1e-7 * 1.2 ** 0.5, rel=1e-4)
    assert "# vex_a, vex, VeRa, a, 2010-03-05T00:00:00, 5," in text


def test_grouped_publication_figure_renders():
    client = TestClient(create_app())
    r = client.post("/api/veda/figure/publication?body_id=venus",
                    json={"variable": "temperature_k", "group_by": "latitude", "dpi": 72, "fmt": "png"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png", r.text[:200]   # bundled sample


def test_long_profile_export_has_every_level_and_variable():
    from veda.analysis.atmospheric import export_profiles_long_csv
    a, b = _profile("a", 5.0, 0.0), _profile("b", 10.0, 2.0)
    a.pressure_hpa = 1e-3 * np.exp(-a.altitude_km / 5.0)
    a.uncertainty = {"temperature_k": np.full(a.altitude_km.size, 1.5)}
    a.track = {"sza": np.linspace(80.0, 90.0, a.altitude_km.size)}
    b.derived["scale_height"] = np.full(b.altitude_km.size, 15.0)
    text = export_profiles_long_csv([a, b], get_body("venus"))
    rows = [l.split(",") for l in text.splitlines() if not l.startswith("#")]
    header, data = rows[0], rows[1:]
    assert len(data) == a.altitude_km.size + b.altitude_km.size        # no interpolation, no lost levels
    for col in ("temperature_k", "pressure_hpa", "scale_height", "sigma_temperature_k", "level_sza_deg"):
        assert col in header
    first_a = dict(zip(header, data[0]))
    assert first_a["observation_id"] == "a" and float(first_a["pressure_hpa"]) == pytest.approx(1e-3)
    assert float(first_a["sigma_temperature_k"]) == 1.5 and float(first_a["level_sza_deg"]) == 80.0
    first_b = dict(zip(header, data[a.altitude_km.size]))
    assert first_b["pressure_hpa"] == "" and float(first_b["scale_height"]) == 15.0


def test_hand_picked_comparison_reads_archive_products_together(monkeypatch):
    """Hand-picked archive profiles go through load_profiles (the worker pool) in one
    batch, keep their order, and an unreadable one is left out instead of failing."""
    import veda.archives.profiles as profiles_mod
    from veda.core.models import ObservationProfile
    from veda.missions.archive_adapter import ArchiveMissionAdapter
    from veda.missions.manager import MissionManager

    keys = {"A": ("ds", "A"), "B": ("ds", "B"), "C": ("ds", "C")}
    monkeypatch.setattr(ArchiveMissionAdapter, "profile_key", lambda self, oid: keys.get(oid))
    calls = []

    def fake_load_profiles(pairs):
        calls.append(list(pairs))
        return [RuntimeError("unreadable") if pid == "B" else
                ObservationProfile(pid, "mex", "mars", "MaRS", "2004-01-01") for _, pid in pairs]
    monkeypatch.setattr(profiles_mod, "load_profiles", fake_load_profiles)
    mgr = MissionManager()
    got = mgr._load_hand_picked([{"mission_id": "mex", "observation_id": o} for o in ("C", "B", "A", "nope")])
    assert calls == [[("ds", "C"), ("ds", "B"), ("ds", "A")]]          # one batch
    assert [p.observation_id for p in got] == ["C", "A"]


def _mission_profiles(mission, t0, n, seed, pressure=False):
    rng = np.random.default_rng(seed)
    z = np.arange(0.0, 30.0, 1.0)
    out = []
    for i in range(n):
        t = t0 - 1.0 * z + rng.normal(0.0, 2.0)
        out.append(ObservationProfile(observation_id=f"{mission}{i}", mission_id=mission, body_id="mars", instrument="RS",
                                      time_utc="2005-01-01T00:00:00", latitude=0.0, longitude=0.0, altitude_km=z,
                                      temperature_k=t, pressure_hpa=(6.0 if mission == "mex" else 6.6) * np.exp(-z / 10.0)
                                      * np.exp(rng.normal(0.0, 0.02)) if pressure else None))
    return out


def test_difference_between_groups_with_its_interval():
    """MGS 5 K warmer than MEX, 20 profiles each with 2 K scatter: the difference, its
    standard error sqrt(s_a^2/n_a + s_b^2/n_b) and a 95 % bootstrap interval of about
    +-1.96 of it; pressure 10 % higher, as a percentage."""
    mars = get_body("mars")
    profs = _mission_profiles("mex", 200.0, 20, 1, True) + _mission_profiles("mgs", 205.0, 20, 2, True)
    comp = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="mission")
    d = comp["group_differences"]
    assert len(d) == 1 and d[0]["label"] == "MGS minus MEX" and d[0]["n"] == 20
    k = 10
    a = np.array([p.temperature_k[k] for p in profs[:20]])
    b = np.array([p.temperature_k[k] for p in profs[20:]])
    se = np.sqrt(a.var(ddof=1) / 20 + b.var(ddof=1) / 20)
    assert d[0]["difference"][k] == pytest.approx(b.mean() - a.mean(), rel=1e-4)
    assert d[0]["se"][k] == pytest.approx(se, rel=1e-3)
    lo, hi = d[0]["ci95_low"][k], d[0]["ci95_high"][k]
    assert lo < d[0]["difference"][k] < hi and (hi - lo) / 2 == pytest.approx(1.96 * se, rel=0.25)
    assert not d[0]["percent"]
    p = compare_profiles_on_body(profs, mars, altitude_step_km=1.0, group_by="mission", variable_name="pressure_hpa")
    dp = p["group_differences"][0]
    assert dp["percent"] and dp["difference"][k] == pytest.approx(10.0, abs=2.0)
    from veda.analysis.atmospheric import export_comparison_to_csv
    text = export_comparison_to_csv(comp)
    assert "MGS minus MEX difference" in text and "MGS minus MEX ci95_low" in text
    one = compare_profiles_on_body(profs[:20], mars, altitude_step_km=1.0, group_by="mission")
    assert one["group_differences"] == []


def test_group_by_mission_and_instrument():
    """One mission's instruments apart (MRO's MCS and radio occultations): two groups and
    their difference."""
    from veda.analysis.atmospheric import compare_profiles_on_body
    from veda.core.models import ObservationProfile
    from veda.core.registry import get_body
    z = np.arange(0.0, 30.0, 1.0)

    def prof(oid, instrument, t0):
        return ObservationProfile(observation_id=oid, mission_id="mro", body_id="mars", instrument=instrument,
                                  time_utc="2011-12-01T00:00:00", latitude=65.0, longitude=0.0, altitude_km=z,
                                  temperature_k=t0 - 1.5 * z)
    profs = [prof("a", "MCS (Mars Climate Sounder)", 200.0), prof("b", "MCS (Mars Climate Sounder)", 202.0),
             prof("c", "RSS (Radio Science)", 197.0), prof("d", "RSS (Radio Science)", 199.0)]
    comp = compare_profiles_on_body(profs, get_body("mars"), altitude_step_km=1.0, group_by="instrument")
    assert [g["label"] for g in comp["groups"]] == ["MRO MCS (Mars Climate Sounder)", "MRO RSS (Radio Science)"]
    d = comp["group_differences"][0]
    assert d["label"] == "MRO RSS (Radio Science) minus MRO MCS (Mars Climate Sounder)"
    assert d["difference"][10] == pytest.approx(-3.0)
