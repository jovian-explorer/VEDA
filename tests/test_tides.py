"""Harmonic fits of altitude cuts against local time or longitude (analysis/tides.py)."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from veda.analysis.tides import harmonic_fit


def test_diurnal_and_semidiurnal_tide_recovered():
    """T = 180 + 12 cos(w (t - 15 h)) + 5 cos(2 w (t - 3 h)): amplitudes and the local
    times of the maxima come back, the semidiurnal one in [0, 12) h."""
    t = np.linspace(0.0, 24.0, 40, endpoint=False)
    w = 2 * np.pi / 24.0
    y = 180.0 + 12.0 * np.cos(w * (t - 15.0)) + 5.0 * np.cos(2 * w * (t - 3.0))
    r = harmonic_fit(t + 48.0, y, 24.0, 2)                        # local times beyond 24 h wrap
    d1, d2 = r["components"]
    assert r["mean"] == pytest.approx(180.0)
    assert d1["amplitude"] == pytest.approx(12.0) and d1["x_of_max"] == pytest.approx(15.0)
    assert d2["amplitude"] == pytest.approx(5.0) and d2["x_of_max"] == pytest.approx(3.0)
    assert r["r_squared"] == pytest.approx(1.0) and r["residual_rms"] < 1e-9
    assert r["max_gap"] == pytest.approx(0.6)
    assert len(r["curve_x"]) == len(r["curve_y"]) and r["curve_x"][-1] == 24.0


def test_uncertainties_match_the_scatter_of_noisy_fits():
    """The 1-sigma amplitude and phase from the covariance agree with the spread of fits
    to many noisy realisations (within 15 %)."""
    rng = np.random.default_rng(3)
    x = rng.uniform(0, 360, 30)
    truth = 1.0 + 0.3 * np.cos(np.radians(3 * (x - 40.0)))          # wave-3 in longitude
    fits = [harmonic_fit(x, truth + 0.1 * rng.standard_normal(x.size), 360.0, 3, bootstrap=False) for _ in range(400)]
    amps = np.array([f["components"][2]["amplitude"] for f in fits])
    maxima = np.array([f["components"][2]["x_of_max"] for f in fits])
    assert amps.mean() == pytest.approx(0.3, abs=0.01)
    assert np.median([f["components"][2]["amplitude_sigma"] for f in fits]) == pytest.approx(amps.std(), rel=0.15)
    assert maxima.mean() == pytest.approx(40.0, abs=1.0)
    assert np.median([f["components"][2]["x_of_max_sigma"] for f in fits]) == pytest.approx(maxima.std(), rel=0.15)


def test_log_fit_gives_relative_amplitudes():
    """Densities are fitted as ln rho: a 20 % wave (in ln) is 20 % amplitude, the mean is
    the geometric mean, and non-positive values are left out."""
    t = np.linspace(0, 24, 25)
    rho = 3e-9 * np.exp(0.2 * np.cos(2 * np.pi * (t - 6.0) / 24.0))
    rho[3] = 0.0
    r = harmonic_fit(t, rho, 24.0, 1, log=True)
    assert r["n_points"] == 24
    assert r["components"][0]["amplitude"] == pytest.approx(20.0, rel=1e-6)
    assert r["components"][0]["x_of_max"] == pytest.approx(6.0)
    assert r["mean"] == pytest.approx(3e-9, rel=1e-6)
    assert max(r["curve_y"]) == pytest.approx(3e-9 * np.exp(0.2), rel=1e-3)


def test_too_few_or_degenerate_points_are_refused():
    with pytest.raises(ValueError, match="at least 6 points"):
        harmonic_fit([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], 24.0, 2)
    with pytest.raises(ValueError, match="do not constrain"):
        harmonic_fit([3.0] * 10, np.arange(10.0), 24.0, 1)        # all at one local time
    with pytest.raises(ValueError):
        harmonic_fit([1, 2], [1, 2, 3], 24.0, 1)


def test_harmonic_fit_endpoint():
    from veda.api.app import create_app
    client = TestClient(create_app())
    t = list(np.linspace(0, 24, 12, endpoint=False))
    y = [200 + 10 * np.cos(2 * np.pi * (v - 14) / 24) for v in t]
    r = client.post("/api/veda/analysis/harmonic-fit", json={"x": t + [None], "y": y + [5.0], "period": 24, "harmonics": 1})
    assert r.status_code == 200
    c = r.json()["components"][0]
    assert c["amplitude"] == pytest.approx(10.0) and c["x_of_max"] == pytest.approx(14.0)
    bad = client.post("/api/veda/analysis/harmonic-fit", json={"x": [1, 2, 3], "y": [1, 2, 3], "period": 24, "harmonics": 1})
    assert bad.status_code == 400 and "points" in bad.json()["detail"]
    assert client.post("/api/veda/analysis/harmonic-fit", json={"x": [1], "y": [1, 2]}).status_code == 400


def test_weighted_fit_with_point_uncertainties():
    """Points with known 1-sigma: the weighted fit trusts the precise ones; when the scatter
    matches the errors the reduced chi-square is about 1 and the amplitude uncertainty is
    the one from the errors alone."""
    rng = np.random.default_rng(7)
    t = rng.uniform(0, 24, 60)
    sig = np.where(np.arange(60) % 2 == 0, 0.5, 5.0)
    y = 200.0 + 8.0 * np.cos(2 * np.pi / 24 * (t - 14.0)) + sig * rng.standard_normal(60)
    r = harmonic_fit(t, y, 24.0, 1, y_sigma=sig, bootstrap=False)
    assert r["weighted"] and 0.6 < r["reduced_chi_square"] < 1.5
    d = r["components"][0]
    assert d["amplitude"] == pytest.approx(8.0, abs=0.5)
    precise = harmonic_fit(t[::2], y[::2], 24.0, 1, y_sigma=sig[::2], bootstrap=False)["components"][0]
    assert d["amplitude_sigma"] < precise["amplitude_sigma"] * 1.05            # the noisy points add a little
    unweighted = harmonic_fit(t, y, 24.0, 1, bootstrap=False)["components"][0]
    assert d["amplitude_sigma"] < 0.5 * unweighted["amplitude_sigma"]


def test_bootstrap_intervals_of_amplitude_and_phase():
    rng = np.random.default_rng(11)
    t = rng.uniform(0, 24, 80)
    y = 180.0 + 10.0 * np.cos(2 * np.pi / 24 * (t - 0.5)) + 2.0 * rng.standard_normal(80)   # maximum near midnight
    r = harmonic_fit(t, y, 24.0, 1)
    d = r["components"][0]
    lo, hi = d["amplitude_ci95"]
    assert lo < d["amplitude"] < hi
    assert (hi - lo) / 2 == pytest.approx(1.96 * d["amplitude_sigma"], rel=0.3)
    xlo, xhi = d["x_of_max_ci95"]                     # around the circle: not split at 0 / 24 h
    assert xlo < xhi and xhi - xlo < 2.0
    assert (xhi - xlo) / 2 == pytest.approx(1.96 * d["x_of_max_sigma"], rel=0.3)
    assert r["bootstrap_draws"] > 900
