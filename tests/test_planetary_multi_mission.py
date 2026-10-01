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
    """Real bundled profiles load through the mission manager (Akatsuki, Mars Express)."""
    mgr = get_mission_manager()
    for mission, body, t_range in (("akatsuki", "venus", (100, 450)), ("mex", "mars", (120, 260))):
        obs = [o for o in mgr.discover_by_mission(mission, body_id=body)
               if o.get("data_type") == "profile" and "atmosphere" in o["product"]]
        assert obs, mission
        prof = mgr.load_profile(mission, obs[-1]["observation_id"])
        t = prof.temperature_k[np.isfinite(prof.temperature_k)]
        assert prof.body_id == body and len(prof.altitude_km) > 50
        assert t_range[0] < t.min() and t.max() < t_range[1], (mission, t.min(), t.max())
        assert prof.provenance.archive_url.startswith("https://")


# ===========================================================================
# 4. CROSS-MISSION COMPOSITE & UNIFORM GRID INTERPOLATION
# ===========================================================================

def test_cross_compare_variable_switching():
    """Composite statistics across two profiles of one body, for T and P."""
    import copy
    mgr = get_mission_manager()
    ak_obs = [o for o in mgr.discover_by_mission("akatsuki", body_id="venus") if o.get("data_type") == "profile"]
    a = mgr.load_profile("akatsuki", ak_obs[0]["observation_id"])
    # Test input: a second profile made by offsetting the real one by +5 K.
    b = copy.deepcopy(a)
    b.observation_id += "_offset"
    b.temperature_k = a.temperature_k + 5.0
    venus_body = get_body("venus")
    for var in ["temperature_k", "pressure_hpa"]:
        res = compare_profiles_on_body([a, b], venus_body, altitude_step_km=1.0, variable_name=var)
        assert res["variable_name"] == var and res["profile_count"] == 2
        assert len(res["composite_mean"]) == len(res["grid_km"]) == len(res["composite_plus_1sigma"])
        for mean_val, minus_val, plus_val in zip(res["composite_mean"], res["composite_minus_1sigma"], res["composite_plus_1sigma"]):
            if None not in (mean_val, minus_val, plus_val):
                assert minus_val <= mean_val <= plus_val
    t = compare_profiles_on_body([a, b], venus_body, altitude_step_km=1.0, variable_name="temperature_k")
    spread = [s for s in t["composite_std"] if s is not None]
    assert spread and abs(np.median(spread) - 2.5) < 0.2      # std of x and x+5 is 2.5


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

def test_no_mission_returns_fabricated_observations():
    """Regression: missions used to return formula-generated profiles presented as
    archive data. Every observation must now trace to a real archive product."""
    mgr = get_mission_manager()
    for mid in MISSIONS:
        for obs in mgr.discover_by_mission(mid, limit=500):
            if obs.get("data_type") == "image":
                continue
            assert obs.get("dataset_id"), (mid, obs)
            assert str(obs.get("archive_source", "")).startswith("https://"), (mid, obs)
    # MOM and Chandrayaan-2 data need an ISSDC login, so nothing is listed until downloaded.
    assert mgr.discover_by_mission("mom") == [] and mgr.discover_by_mission("chandrayaan2") == []
