"""Automated verification tests for universal file ingestion and pipeline processing."""
from __future__ import annotations

from pathlib import Path
import pytest
from backend.veda.api.routes import ParseFileRequest, parse_generic_file_endpoint
from backend.veda.pipeline.archive_downloader import get_archive_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ingest_all_planetary_samples():
    """Verify that every authentic sample granule in sampledata/veda parses cleanly."""
    samples = [
        ("sampledata/veda/venus_akatsuki/rs_20160303_223100_udsc64_l4_ae_v10.tab", "venus", "profile"),
        ("sampledata/veda/venus_akatsuki/uvi_20181105_080112_283_geo_v10.fit", "venus", "image"),
        ("sampledata/veda/mars_mom/mom_menca_orbit_1200.tab", "mars", "profile"),
        ("sampledata/veda/mars_maven/maven_rs_orbit_1240.tab", "mars", "profile"),
        ("sampledata/veda/moon_chandrayaan2/ch2_dfrs_orbit_1420.tab", "moon", "profile"),
        ("sampledata/veda/moon_lro/lro_diviner_shackleton.tab", "moon", "profile"),
        ("sampledata/veda/jupiter_juno/juno_mwr_perijove_08.tab", "jupiter", "profile"),
        ("sampledata/veda/titan_cassini/cassini_rss_titan_t12.tab", "titan", "profile"),
        ("sampledata/veda/venus_express/vex_vera_0268_temp.tab", "venus", "profile"),
        ("sampledata/veda/pluto_new_horizons/nh_rex_pluto_ingress.tab", "pluto", "profile"),
        ("sampledata/veda/pluto_new_horizons/nh_lorri_pluto_approach.fits", "pluto", "image"),
        ("sampledata/veda/pluto_new_horizons/lor_0299059349_0x630_sci_full.jpg", "pluto", "image"),
    ]

    for rel_path, body_id, expected_type in samples:
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Sample granule missing: {rel_path}"

        req = ParseFileRequest(file_path=str(full_path), body_id=body_id)
        res = parse_generic_file_endpoint(req)

        assert res["type"] == expected_type, f"Expected {expected_type} for {rel_path}, got {res['type']}"
        assert res["body_id"] == body_id

        if expected_type == "profile":
            data = res["data"]
            assert data["n_points"] > 0
            assert "altitude_km" in data
            # Ensure derived thermodynamic products exist
            derived = data.get("derived", {})
            assert isinstance(derived, dict)
        else:
            assert res["shape"][0] > 0
            assert res["shape"][1] > 0
            assert "stats" in res
            assert "mean" in res["stats"]


def test_derived_thermodynamics_values():
    """Verify thermodynamic calculation values on ingested sample profile."""
    full_path = PROJECT_ROOT / "sampledata/veda/venus_express/vex_vera_0268_temp.tab"
    req = ParseFileRequest(file_path=str(full_path), body_id="venus")
    res = parse_generic_file_endpoint(req)

    data = res["data"]
    derived = data["derived"]
    assert "lapse_rate" in derived
    assert "potential_temperature" in derived
    assert "buoyancy_freq_sq" in derived

    # Verify potential temperature increases with height (stable atmosphere)
    theta = [x for x in derived["potential_temperature"] if x is not None]
    assert len(theta) > 10
    assert theta[-1] > theta[0]


def test_archive_pipeline_offline_download():
    """Verify archive downloader task fallback to bundled samples."""
    pipe = get_archive_pipeline()
    task = pipe.download_product(
        task_id="test_offline_mom_granule",
        remote_url="https://example.gov/mom_menca_orbit_1200.tab",
        mission_id="mom",
        body_id="mars",
        instrument="MENCA",
        filename="mom_menca_orbit_1200.tab",
    )
    assert task.status == "completed"
    assert task.progress_pct == 100.0
    assert Path(task.local_path).exists()
    assert Path(task.local_path).stat().st_size > 0


def test_parse_file_content_text_and_base64():
    """Verify ingestion of uploaded file contents directly via text and base64."""
    import base64

    # 1. Text content (CSV)
    csv_text = (
        "altitude_km,temperature_k,pressure_hpa\n"
        "10.0,280.5,800.0\n"
        "20.0,260.2,400.0\n"
        "30.0,240.1,200.0\n"
        "40.0,220.0,100.0\n"
    )
    req_text = ParseFileRequest(
        filename="custom_sounding.csv",
        file_content=csv_text,
        body_id="venus",
    )
    res_text = parse_generic_file_endpoint(req_text)
    assert res_text["type"] == "profile"
    assert res_text["data"]["n_points"] == 4
    assert res_text["data"]["temperature_k"] == [280.5, 260.2, 240.1, 220.0]
    assert len(res_text["data"]["derived"]["potential_temperature"]) == 4

    # 2. Base64 content (FITS file)
    fits_path = PROJECT_ROOT / "sampledata/veda/venus_akatsuki/uvi_20181105_080112_283_geo_v10.fit"
    with open(fits_path, "rb") as f:
        raw_bytes = f.read()
    b64_str = "data:application/octet-stream;base64," + base64.b64encode(raw_bytes).decode("ascii")

    req_b64 = ParseFileRequest(
        filename="uvi_geo.fit",
        file_content=b64_str,
        body_id="venus",
    )
    res_b64 = parse_generic_file_endpoint(req_b64)
    assert res_b64["type"] == "image"
    assert res_b64["shape"][0] > 0
    assert "stats" in res_b64
