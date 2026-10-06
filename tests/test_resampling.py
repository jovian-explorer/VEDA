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
