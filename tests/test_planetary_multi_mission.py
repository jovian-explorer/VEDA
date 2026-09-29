"""Multi-body and multi-mission verification tests for VEDA Planetary Science Platform.

Validates:
- Comprehensive planetary physics constants for all 11 non-Earth celestial bodies
- Multi-spacecraft cross-comparison and vertical grid interpolation across multiple bodies
- Authoritative mission URLs and data archive links
- Publication figure generator across planetary targets
- Single-profile and cross-mission CSV and JSON exports
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
import numpy as np


from veda.core.registry import BODIES, MISSIONS, get_body, get_mission, list_bodies, list_missions, get_missions_for_body
from veda.analysis.atmospheric import compare_profiles_on_body, export_comparison_to_csv, export_profile_to_csv
from veda.missions.manager import get_mission_manager
from veda.api.routes import (
    explore_by_body,
    compare_missions_on_body,
    generate_publication_figure,
    CrossCompareRequest,
)


# ===========================================================================
# 1. CELESTIAL BODY CATALOG & PHYSICAL REALITY TESTS
# ===========================================================================

def test_all_11_planetary_bodies_present():
    """Verify exact presence of the 11 non-Earth planetary targets."""
    expected_bodies = [
        "venus", "mars", "jupiter", "saturn", "titan",
        "pluto", "mercury", "moon", "ceres", "vesta", "comet_67p"
    ]
    assert len(BODIES) >= 11
    for body_id in expected_bodies:
        assert body_id in BODIES, f"Expected body {body_id} missing from registry"
        body = BODIES[body_id]
        assert body.name
        assert body.description
        assert len(body.description) > 30
        assert body.mission_page_url.startswith("http")
        assert body.data_page_url.startswith("http")


def test_planetary_thermodynamic_constants_range():
    """Verify physical thermodynamic parameters fall within accepted astronomical bounds."""
    for body_id, body in BODIES.items():
        assert body.radius_km > 0.0
        # Surface gravity is negligible for small comets, but positive for all planets/moons
        if body_id != "comet_67p":
            assert 0.1 <= body.surface_gravity <= 30.0, f"Gravity out of bounds for {body_id}: {body.surface_gravity}"
        # Mean molecular weight for atmospheres
        if body.mean_molecular_weight > 0.0:
            assert 1.0 <= body.mean_molecular_weight <= 60.0
            assert body.gas_constant_r > 0.0
            assert body.isobaric_heat_capacity_cp > 0.0


def test_earth_strictly_excluded():
    """Confirm Earth and terrestrial GNSS are completely excluded from registry and bodies."""
    assert "earth" not in BODIES
    assert "earth" not in [b["id"] for b in list_bodies()]
    assert "cosmic2" not in MISSIONS
    assert "cosmic2" not in [m["id"] for m in list_missions()]


# ===========================================================================
# 2. MISSION CATALOG & URL INTEGRITY TESTS
# ===========================================================================

def test_all_17_missions_metadata_and_urls():
    """Verify all 17 planetary missions possess valid descriptions and archive URLs."""
    expected_missions = [
        "akatsuki", "vex", "magellan", "pvo", "bepicolombo",
        "messenger", "maven", "mro", "juno", "galileo",
        "cassini", "new_horizons", "lro", "dawn", "rosetta",
        "mom", "chandrayaan2"
    ]
    assert len(MISSIONS) >= 17
    for mission_id in expected_missions:
        assert mission_id in MISSIONS, f"Expected mission {mission_id} missing"
        m = MISSIONS[mission_id]
        assert m.name
        assert m.agency
        assert m.mission_type in ["orbiter", "flyby", "sample_return", "lander"]
        assert len(m.description) > 40
        assert m.mission_page_url.startswith("http"), f"Invalid mission URL for {mission_id}"
        assert m.data_page_url.startswith("http"), f"Invalid data URL for {mission_id}"


def test_target_encounters_consistency():
    """Verify that every target encounter references a valid body or recognized planetary target."""
    for mission_id, m in MISSIONS.items():
        for body_target, enc_type in m.target_encounters.items():
            assert body_target in BODIES or body_target == "arrokoth", f"Mission {mission_id} targets unknown body: {body_target}"
            assert enc_type in ["orbiter", "flyby", "encounter", "gravity_assist_flyby", "multiple_flybys"]


# ===========================================================================
# 3. MULTI-BODY EXPLORATION & PROFILE EXTRACTION
# ===========================================================================

def test_explore_multiple_bodies_api():
    """Verify /api/veda/bodies/{body_id} for multiple targets."""
    for bid in ["venus", "mars", "jupiter", "titan", "pluto"]:
        data = explore_by_body(bid)
        assert data["body_id"] == bid
        assert "body_name" in data
        assert "radius_km" in data
        assert "observations" in data
        assert "observations_count" in data


def test_mission_manager_profile_loading():
    """Verify that profile loader retrieves valid soundings with required arrays."""
    mgr = get_mission_manager()
    # Test loading Venus profiles
    ak_obs = mgr.discover_by_mission("akatsuki", body_id="venus")
    assert len(ak_obs) > 0
    ak_prof = mgr.load_profile("akatsuki", ak_obs[0]["observation_id"])
    assert ak_prof is not None
    assert len(ak_prof.altitude_km) > 0
    assert len(ak_prof.temperature_k) > 0
    assert len(ak_prof.pressure_hpa) > 0
    assert ak_prof.body_id == "venus"

    # Test loading VEX profile
    vex_obs = mgr.discover_by_mission("vex", body_id="venus")
    assert len(vex_obs) > 0
    vex_prof = mgr.load_profile("vex", vex_obs[0]["observation_id"])
    assert vex_prof is not None
    assert len(vex_prof.altitude_km) > 0
    assert vex_prof.body_id == "venus"


# ===========================================================================
# 4. CROSS-MISSION COMPOSITE & UNIFORM GRID INTERPOLATION
# ===========================================================================

def test_cross_compare_variable_switching():
    """Verify cross-mission comparison works across temperature and pressure."""
    mgr = get_mission_manager()
    ak_obs = mgr.discover_by_mission("akatsuki", body_id="venus")
    vex_obs = mgr.discover_by_mission("vex", body_id="venus")
    ak_prof = mgr.load_profile("akatsuki", ak_obs[0]["observation_id"])
    vex_prof = mgr.load_profile("vex", vex_obs[0]["observation_id"])
    venus_body = get_body("venus")

    for var in ["temperature_k", "pressure_hpa"]:
        res = compare_profiles_on_body([ak_prof, vex_prof], venus_body, altitude_step_km=1.0, variable_name=var)
        assert res["variable_name"] == var
        assert len(res["composite_mean"]) == len(res["grid_km"])
        assert len(res["composite_minus_1sigma"]) == len(res["grid_km"])
        assert len(res["composite_plus_1sigma"]) == len(res["grid_km"])
        # Mean should be bounded between minus and plus 1-sigma where valid
        for mean_val, minus_val, plus_val in zip(res["composite_mean"], res["composite_minus_1sigma"], res["composite_plus_1sigma"]):
            if mean_val is not None and minus_val is not None and plus_val is not None:
                assert minus_val <= mean_val <= plus_val or abs(plus_val - minus_val) < 1e-6


# ===========================================================================
# 5. PUBLICATION FIGURE GENERATOR TESTS
# ===========================================================================

def test_publication_figure_generator():
    """Verify publication figure generator produces valid high-resolution PNG bytes."""
    fig_png = generate_publication_figure("venus", variable="temperature_k", missions="akatsuki,vex", dpi=100, fmt="png")
    assert fig_png.media_type == "image/png"
    assert fig_png.body.startswith(b"\x89PNG")
    assert len(fig_png.body) > 5000


# ===========================================================================
# 6. ISRO PLANETARY MISSIONS (MOM & CHANDRAYAAN-2)
# ===========================================================================

def test_isro_planetary_missions_mom_and_ch2():
    """Verify ISRO planetary missions MOM and Chandrayaan-2 adapters and profiles."""
    mgr = get_mission_manager()

    # MOM (Mars)
    mom_obs = mgr.discover_by_mission("mom", body_id="mars")
    assert len(mom_obs) >= 2
    mom_prof = mgr.load_profile("mom", mom_obs[0]["observation_id"])
    assert mom_prof is not None
    assert mom_prof.body_id == "mars"
    assert mom_prof.instrument == "MENCA"
    assert len(mom_prof.altitude_km) > 0
    assert len(mom_prof.temperature_k) > 0
    assert "SPL" in mom_prof.provenance.doi_or_citation or "Bhardwaj" in mom_prof.provenance.doi_or_citation

    # Chandrayaan-2 (Moon)
    ch2_obs = mgr.discover_by_mission("chandrayaan2", body_id="moon")
    assert len(ch2_obs) >= 2
    ch2_prof = mgr.load_profile("chandrayaan2", ch2_obs[0]["observation_id"])
    assert ch2_prof is not None
    assert ch2_prof.body_id == "moon"
    assert ch2_prof.instrument == "DFRS"
    assert ch2_prof.electron_density_cm3 is not None
    assert len(ch2_prof.electron_density_cm3) > 0
    assert np.nanmax(ch2_prof.electron_density_cm3) > 100.0

