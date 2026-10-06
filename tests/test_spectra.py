"""Vertical wavenumber spectra of temperature perturbations (analysis/spectra.py)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.analysis.spectra import composite_spectrum, profile_spectrum


def test_a_single_wave_peaks_at_its_wavenumber_and_parseval_holds():
    z = np.arange(60.0, 90.0, 0.1)
    t = 230.0 - 1.0 * (z - 60) + 2.3 * np.sin(2 * np.pi * z / 3.0)
    s = profile_spectrum(z, t, 60.0, 90.0)
    assert s["m"][np.argmax(s["psd"])] == pytest.approx(1 / 3.0, rel=0.05)
    dm = s["m"][1] - s["m"][0]
    assert np.sum(s["psd"]) * dm == pytest.approx(s["variance"], rel=0.02)


def test_red_noise_slope_and_its_uncertainty():
    """Profiles whose perturbations have P ~ m^-3: the fitted slope is about -3, inside
    its bootstrap interval."""
    rng = np.random.default_rng(4)
    z = np.arange(50.0, 110.0, 0.2)
    n = z.size
    m = np.fft.rfftfreq(n, 0.2)
    specs = []
    for _ in range(25):
        amp = np.zeros(m.size)
        amp[1:] = m[1:] ** -1.5
        ph = rng.uniform(0, 2 * np.pi, m.size)
        x = np.fft.irfft(amp * np.exp(1j * ph) * rng.rayleigh(1.0, m.size), n)
        x *= 0.01 / x.std()
        specs.append(profile_spectrum(z, 200.0 * (1 + x), 50.0, 110.0))
    c = composite_spectrum(specs)
    assert c["n"] == 25 and c["slope"] == pytest.approx(-3.0, abs=0.35)
    lo, hi = c["slope_ci95"]
    assert lo < c["slope"] < hi
    assert all(a <= b for a, b in zip(c["ci95_low"], c["ci95_high"]))


def test_profiles_not_covering_the_layer_are_skipped():
    z = np.arange(60.0, 75.0, 0.5)
    assert profile_spectrum(z, 200 + 0 * z, 60.0, 90.0) is None
    assert composite_spectrum([])["n"] == 0


def test_spectra_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from veda.api.app import create_app
    from veda.core.models import ObservationProfile
    from veda.missions import manager as mgr
    z = np.arange(40.0, 100.0, 0.25)
    profs = [ObservationProfile(observation_id=f"p{i}", mission_id="vex", body_id="venus", instrument="VeRa",
                                time_utc="2008-01-01", latitude=0.0, longitude=0.0, altitude_km=z,
                                temperature_k=300 - 1.5 * (z - 40) + np.sin(z * (1 + 0.1 * i))) for i in range(4)]
    monkeypatch.setattr(mgr.MissionManager, "profiles_for_comparison", lambda self, *a, **k: (profs, None))
    c = TestClient(create_app())
    r = c.post("/api/veda/analysis/vertical-spectra/venus", json={"z_min": 50, "z_max": 90})
    assert r.status_code == 200 and r.json()["composite"]["n"] == 4
    t = c.post("/api/veda/analysis/vertical-spectra/venus", json={"z_min": 50, "z_max": 90, "csv": True})
    assert t.text.splitlines()[3].startswith("m_cycles_per_km,wavelength_km,mean_psd")
    assert c.post("/api/veda/analysis/vertical-spectra/venus", json={"z_min": 90, "z_max": 50}).status_code == 422
