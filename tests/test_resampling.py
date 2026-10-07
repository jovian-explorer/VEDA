"""Bootstrap statistics of the points of an altitude cut (analysis/resampling.py)."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from veda.analysis.resampling import bootstrap_statistics


def test_mean_standard_error_and_bootstrap_intervals():
    rng = np.random.default_rng(2)
    v = rng.normal(150.0, 12.0, 200)
    r = bootstrap_statistics(v)
    assert r["n"] == 200 and r["mean"] == pytest.approx(v.mean())
    assert r["sem"] == pytest.approx(v.std(ddof=1) / np.sqrt(200))
    lo, hi = r["mean_ci95"]
    assert (hi - lo) / 2 == pytest.approx(1.96 * r["sem"], rel=0.15)
    assert r["median_ci95"][0] < r["median"] < r["median_ci95"][1]


def test_log_statistics_and_groups():
    v = [1e-8, 2e-8, 4e-8, 8e-8, np.nan, -1.0]
    r = bootstrap_statistics(v, log=True, groups=["a", "a", "b", "b", "b", "b"])
    assert r["n"] == 4 and r["mean"] == pytest.approx(np.exp(np.mean(np.log([1e-8, 2e-8, 4e-8, 8e-8]))))
    a, b = r["groups"]
    assert a["label"] == "a" and a["n"] == 2 and b["n"] == 2
    assert b["mean"] == pytest.approx(np.sqrt(4e-8 * 8e-8))
    single = bootstrap_statistics([3.0])
    assert single["mean"] == 3.0 and single["sem"] is None and single["mean_ci95"] is None


def test_point_statistics_endpoint():
    from veda.api.app import create_app
    c = TestClient(create_app())
    r = c.post("/api/veda/analysis/point-statistics", json={"values": [1, 2, 3, None, 5], "groups": ["x"] * 5})
    assert r.status_code == 200 and r.json()["n"] == 4
    assert c.post("/api/veda/analysis/point-statistics", json={"values": [1, 2], "groups": ["x"]}).status_code == 400


def test_correlation_and_regression_with_intervals():
    from veda.analysis.resampling import correlation
    rng = np.random.default_rng(9)
    x = rng.uniform(0, 10, 120)
    y = 3.0 + 0.5 * x + rng.normal(0, 1.0, x.size)
    r = correlation(x, y)
    assert r["n"] == 120 and r["slope"] == pytest.approx(0.5, abs=0.06)
    lo, hi = r["pearson_ci95"]
    assert lo < r["pearson_r"] < hi and r["p_value"] < 1e-10
    blo, bhi = r["slope_ci95_bootstrap"]
    tlo, thi = r["slope_ci95_t"]
    assert blo < 0.5 < bhi and tlo < 0.5 < thi
    assert (bhi - blo) == pytest.approx(thi - tlo, rel=0.3)
    assert r["spearman_ci95"][0] < r["spearman_rho"] < r["spearman_ci95"][1]


def test_correlation_on_log_axes_and_refusals():
    from veda.analysis.resampling import correlation
    x = np.array([1.0, 2.0, 4.0, 8.0, 16.0, -1.0])
    y = 5.0 * x ** 2
    r = correlation(x, y, log_x=True, log_y=True)
    assert r["n"] == 5 and r["slope"] == pytest.approx(2.0) and r["pearson_r"] == pytest.approx(1.0)
    assert r["line_y"][1] == pytest.approx(5.0 * 16.0 ** 2)
    with pytest.raises(ValueError):
        correlation([1, 2, 3], [1, 2, 3])
    with pytest.raises(ValueError):
        correlation([1, 1, 1, 1, 1], [1, 2, 3, 4, 5])


def test_binned_statistics_along_x():
    """Means in bins along x with bootstrap intervals; circular x (local time) wraps."""
    from veda.analysis.resampling import binned_statistics
    rng = np.random.default_rng(2)
    x = rng.uniform(0, 24, 400)
    y = 200 + 10 * np.cos(2 * np.pi * x / 24) + rng.normal(0, 2, 400)
    r = binned_statistics(np.r_[x, 24.5], np.r_[y, 1000.0], 3.0, period=24.0)
    assert [b["x_low"] for b in r["bins"]] == [0, 3, 6, 9, 12, 15, 18, 21]
    first = r["bins"][0]
    sel = np.r_[y[(x >= 0) & (x < 3)], 1000.0]                     # 24.5 h is 0.5 h
    assert first["n"] == sel.size and first["mean"] == pytest.approx(sel.mean())
    assert first["x_mean"] == pytest.approx(np.r_[x[x < 3], 0.5].mean())
    b = r["bins"][4]
    assert b["mean_ci95"][0] < b["mean"] < b["mean_ci95"][1]
    assert b["mean"] == pytest.approx(200 + 10 * np.cos(2 * np.pi * 13.5 / 24), abs=1.5)
    lat = binned_statistics([-75, -10, 5, 44, 46], [1, 2, 3, 4, 5], 30.0)

    assert [(b["x_low"], b["n"]) for b in lat["bins"]] == [(-90.0, 1), (-30.0, 1), (0.0, 1), (30.0, 2)]
    assert lat["bins"][0]["mean_ci95"] is None
    with pytest.raises(ValueError):
        binned_statistics([1, 2], [1], 1.0)
