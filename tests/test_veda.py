"""Comprehensive verification test suite for VEDA Planetary Science Platform.

Validates:
- Mission & Body registry physical parameters & mission classifications (Orbiter vs Flyby)
- PDS3 table reader on real JAXA Akatsuki Level 4 radio science data
- FITS astronomical image reader & contrast stretch algorithms
- Planetary thermodynamic analysis (lapse rate, theta, N^2, scale height)
- Cross-mission comparative analysis with multi-spacecraft composites & +/- 1 sigma envelopes
- FastAPI VEDA endpoints and export formats (CSV / JSON)
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pytest

# Ensure backend package is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from veda.api.routes import (
    platform_info,
    explore_by_body,
    compare_missions_on_body,
    get_observation_profile,
    export_compare_csv,
    discover_remote_products,
    list_local_cached_products,
    generate_publication_figure,
    CrossCompareRequest,
)
from veda.core.registry import BODIES, MISSIONS, get_body, get_mission, list_bodies, list_missions, get_missions_for_body
from veda.readers.pds3_reader import read_pds3_table
from veda.readers.fits_reader import (
    apply_contrast_stretch,
    compute_image_histogram,
    extract_photometric_transect,
    render_to_png,
)
from veda.analysis.atmospheric import (
    compute_atmospheric_diagnostics,
    compare_profiles_on_body,
    export_profile_to_csv,
    export_comparison_to_csv,
)
from veda.missions.manager import get_mission_manager


# ===========================================================================
# 1. REGISTRY & METADATA TESTS
# ===========================================================================

def test_registry_bodies_physics():
    """Verify all bodies have physical constants for thermodynamics."""
    assert len(BODIES) >= 10
    required_bodies = ["venus", "earth", "mars", "jupiter", "saturn", "titan", "pluto", "mercury", "moon", "ceres", "vesta", "comet_67p"]
    for bid in required_bodies:
        assert bid in BODIES, f"Missing body: {bid}"
        b = BODIES[bid]
        assert b.radius_km > 0
        assert b.surface_gravity > 0 or bid == "comet_67p"
        assert b.gas_constant_r > 0
        assert b.isobaric_heat_capacity_cp > 0


def test_registry_mission_classification():
    """Verify distinction between Orbiters, Flybys, and Constellations."""
    assert MISSIONS["new_horizons"].mission_type == "flyby"
    assert MISSIONS["new_horizons"].target_encounters.get("pluto") == "flyby"
    assert MISSIONS["cosmic2"].mission_type == "constellation"
    assert MISSIONS["akatsuki"].mission_type == "orbiter"
    assert MISSIONS["juno"].mission_type == "orbiter"
    assert MISSIONS["cassini"].mission_type == "orbiter"
    assert MISSIONS["bepicolombo"].target_encounters.get("venus") == "flyby"
    assert MISSIONS["bepicolombo"].target_encounters.get("mercury") == "orbiter"


def test_get_missions_for_body():
    """Verify Venus lists multiple observing missions with encounter classifications."""
    venus_missions = get_missions_for_body("venus")
    ids = [m["id"] for m in venus_missions]
    assert "akatsuki" in ids
    assert "vex" in ids
    assert "bepicolombo" in ids
    for m in venus_missions:
        if m["id"] == "bepicolombo":
            assert m["encounter_type"] == "flyby"


# ===========================================================================
# 2. PDS3 READER TEST (REAL AKATSUKI L4 FILE)
# ===========================================================================

def test_pds3_reader_akatsuki_l4():
    """Verify reading authentic JAXA Akatsuki Level 4 radio science file."""
    lbl_file = ROOT_DIR / "sampledata" / "veda" / "venus_akatsuki" / "rs_20160303_223100_udsc64_l4_ae_v10.lbl"
    if not lbl_file.exists():
        pytest.skip("Akatsuki sample file not present")
    table = read_pds3_table(lbl_file)
    assert len(table.columns) > 0
    assert len(table.metadata) > 0
    radius = table.series("RADIUS")
    assert radius is not None
    assert radius.size > 50
    geo_h = table.series("GEOPOTENTIAL_HEIGHT")
    assert geo_h is not None
    assert geo_h.size > 50
    temp = table.series("TEMPERATURE")
    assert temp is not None
    assert temp.size > 50


# ===========================================================================
# 3. FITS READER & CONTRAST STRETCH TESTS
# ===========================================================================

def test_fits_zscale_and_transect():
    """Verify astronomical ZScale interval and 1D line slice."""
    # Create synthetic astronomical image array with faint source and bright peak
    np.random.seed(42)
    img = np.random.normal(loc=100.0, scale=15.0, size=(128, 128)).astype(np.float32)
    img[60:68, 60:68] += 800.0  # simulated star/feature

    stretched = apply_contrast_stretch(img, stretch_method="zscale")
    assert stretched.min() >= 0.0
    assert stretched.max() <= 1.0

    # Test PNG rendering with various stretches
    for stretch in ["zscale", "percentile", "linear", "log", "sqrt", "asinh", "histeq"]:
        png = render_to_png(img, stretch_method=stretch, colormap="inferno")
        assert len(png) > 100
        assert png.startswith(b"\x89PNG")

    # Test 1D transect
    transect = extract_photometric_transect(img, x0=10, y0=64, x1=100, y1=64, num_samples=50)
    assert "intensities" in transect
    assert len(transect["intensities"]) == 50
    assert "distances_pixels" in transect
    assert len(transect["distances_pixels"]) == 50

    # Test histogram
    hist = compute_image_histogram(img, num_bins=50)
    assert len(hist["counts"]) == 50
    assert len(hist["cdf"]) == 50


# ===========================================================================
# 4. PLANETARY THERMODYNAMICS & CROSS-MISSION COMPARISON
# ===========================================================================

def test_venus_cross_mission_comparison():
    """Verify comparing Akatsuki and Venus Express profiles on Venus."""
    mgr = get_mission_manager()
    ak_obs = mgr.discover_by_mission("akatsuki", body_id="venus")
    vex_obs = mgr.discover_by_mission("vex", body_id="venus")
    assert len(ak_obs) > 0
    assert len(vex_obs) > 0

    ak_prof = mgr.load_profile("akatsuki", ak_obs[0]["observation_id"])
    vex_prof = mgr.load_profile("vex", vex_obs[0]["observation_id"])
    assert ak_prof is not None
    assert vex_prof is not None

    venus_body = get_body("venus")
    res = compare_profiles_on_body([ak_prof, vex_prof], venus_body, altitude_step_km=1.0, variable_name="temperature_k")
    assert res["body_id"] == "venus"
    assert res["profile_count"] == 2
    assert len(res["grid_km"]) > 10
    assert len(res["composite_mean"]) == len(res["grid_km"])
    assert len(res["composite_plus_1sigma"]) == len(res["grid_km"])

    # Check that each profile includes its interpolated series
    for p in res["profiles"]:
        assert "interpolated_series" in p
        assert len(p["interpolated_series"]) == len(res["grid_km"])

    # Test CSV export of comparison
    csv_text = export_comparison_to_csv(res)
    assert "composite_mean_temperature_k" in csv_text
    assert "akatsuki" in csv_text or "vex" in csv_text


def test_profile_csv_export():
    """Verify single profile export to CSV with provenance metadata."""
    mgr = get_mission_manager()
    vex_prof = mgr.load_profile("vex", "vex-vera-orbit-0268-ingress")
    assert vex_prof is not None
    csv_text = export_profile_to_csv(vex_prof)
    assert "# VEDA Scientific Data Export" in csv_text
    assert "altitude_km,temperature_k" in csv_text
    assert "potential_temperature" in csv_text


# ===========================================================================
# 5. FASTAPI REST API VERIFICATION
# ===========================================================================

def test_api_platform_info():
    data = platform_info()
    assert "VEDA" in data["title"]
    assert data["missions_count"] >= 15


def test_api_explore_body():
    data = explore_by_body("venus")
    assert data["body_id"] == "venus"
    assert data["observations_count"] >= 2


def test_api_compare_body():
    req = CrossCompareRequest(missions=["akatsuki", "vex"], variable="temperature_k")
    data = compare_missions_on_body("venus", req)
    assert data["body_id"] == "venus"
    assert data["profile_count"] >= 2
    assert len(data["composite_mean"]) > 0


def test_api_profile_data():
    data = get_observation_profile("vex", "vex-vera-orbit-0268-ingress")
    assert data["mission_id"] == "vex"
    assert "altitude_km" in data
    assert "temperature_k" in data
    assert "provenance" in data


def test_api_export_compare_csv():
    req = CrossCompareRequest(missions=["akatsuki", "vex"], variable="temperature_k")
    resp = export_compare_csv("venus", req)
    assert resp.media_type == "text/csv"
    assert "composite_mean_temperature_k" in resp.body.decode()


def test_api_archive_discovery():
    data = discover_remote_products("akatsuki", body_id="venus")
    assert data["mission_id"] == "akatsuki"
    assert data["total_available"] >= 1
    assert any("darts" in p["archive"].lower() for p in data["products"])


def test_api_archive_local_cache():
    local_items = list_local_cached_products()
    assert isinstance(local_items, list)


def test_api_publication_figure_generator():
    resp = generate_publication_figure("venus", variable="temperature_k", missions="akatsuki,vex", dpi=150, fmt="png")
    assert resp.media_type == "image/png"
    assert resp.body.startswith(b"\x89PNG")
    assert len(resp.body) > 10000

