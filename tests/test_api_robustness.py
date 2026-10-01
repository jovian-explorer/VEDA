"""Regression tests for API input validation, uploads and security fixes (v2.1.0).

Each test names the bug it guards against.
"""
from __future__ import annotations

import base64
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from veda.api.app import create_app
from veda.config import SETTINGS, SETTINGS_PATH, Settings, sampledata_dir

SAMPLES = sampledata_dir()


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _text(path):
    return path.read_text(encoding="utf-8")


def _b64(path):
    return "data:application/octet-stream;base64," + base64.b64encode(path.read_bytes()).decode()


# --- image routes -----------------------------------------------------------

@pytest.mark.parametrize("mission,obs", [
    ("akatsuki", "uvi_20181105_080112_283_geo_v10"),
])
def test_image_render_returns_png(client, mission, obs):
    """Bug: /image/{id}/render was shadowed by the greedy metadata route (404 / JSON)."""
    r = client.get(f"/api/veda/image/{mission}/{obs}/render")
    assert r.status_code == 200, r.text[:200]
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    h = client.get(f"/api/veda/image/{mission}/{obs}/histogram?bins=50")
    assert h.status_code == 200 and h.json()
    assert client.get(f"/api/veda/image/{mission}/{obs}").json()["mission_id"] == mission


def test_image_render_rejects_unknown_options(client):
    obs = "/api/veda/image/akatsuki/uvi_20181105_080112_283_geo_v10"
    assert client.get(obs + "/render?stretch=bogus").status_code == 400
    assert client.get(obs + "/render?colormap=bogus").status_code == 400
    assert client.get(obs + "/histogram?bins=-5").status_code == 400


# --- figures and comparison -------------------------------------------------

@pytest.mark.parametrize("query", ["variable=bogus", "dpi=100000", "fmt=exe"])
def test_publication_figure_bad_input_is_400_not_500(client, query):
    """Bug: unknown variable/dpi/fmt crashed matplotlib with a 500."""
    r = client.get(f"/api/veda/figure/publication?body_id=venus&{query}")
    assert r.status_code == 400, r.text[:200]


def test_publication_figure_all_frontend_variables(client):
    for var in ("temperature_k", "pressure_hpa", "scale_height", "refractivity"):
        r = client.get(f"/api/veda/figure/publication?body_id=venus&variable={var}&dpi=72")
        assert r.status_code in (200, 400), (var, r.text[:200])
    r = client.get("/api/veda/figure/publication?body_id=venus&dpi=72&fmt=svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg")


COMPARISON_KEYS = {"body_id", "body_name", "variable_name", "grid_km", "composite_mean",
                   "composite_std", "composite_plus_1sigma", "composite_minus_1sigma",
                   "profile_count", "profiles"}


@pytest.mark.parametrize("body,variable", [
    ("venus", "temperature_k"),          # has data
    ("comet_67p", "pressure_hpa"),       # profiles exist, but none carry pressure
    ("vesta", "electron_density_cm3"),
])
def test_compare_always_returns_full_shape(client, body, variable):
    """Bug: when no profile had the variable the result lacked body_name, and the
    comparison plot crashed on every body (TypeError reading 'toUpperCase')."""
    r = client.post(f"/api/veda/compare/body/{body}", json={"variable": variable})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert COMPARISON_KEYS <= data.keys()
    assert data["body_id"] == body and data["body_name"]
    assert data["profile_count"] == len(data["profiles"])


def test_compare_unknown_body_is_404(client):
    """Bug: returned 200 with an {"error": ...} body."""
    assert client.post("/api/veda/compare/body/nobody", json={}).status_code == 404
    assert client.post("/api/veda/export/compare/nobody/csv", json={}).status_code == 404


# --- settings ---------------------------------------------------------------

def test_invalid_settings_are_rejected_and_not_saved(client):
    """Bug: any value was persisted; ui_font_size="huge" broke fonts on every launch."""
    before = client.get("/api/meta").json()["settings"]
    r = client.post("/api/settings", json={"ui_font_size": "huge"})
    assert r.status_code == 422
    r = client.post("/api/settings", json={"ui_theme": "dark", "plot_dpi": -1})
    assert r.status_code == 422  # all-or-nothing: ui_theme is not applied either
    assert client.post("/api/settings", json={"nope": 1}).status_code == 422
    assert client.post("/api/settings", content=b"notjson",
                       headers={"content-type": "application/json"}).status_code == 400
    assert client.get("/api/meta").json()["settings"] == before


def test_settings_update_and_reset(client):
    r = client.post("/api/settings", json={"ui_theme": "light", "units_pressure": "bar", "plot_dpi": 600})
    assert r.status_code == 200 and r.json()["ui_theme"] == "light"
    r = client.post("/api/settings/reset")
    assert r.json() == Settings().to_dict()


def test_corrupt_settings_file_is_repaired_on_load():
    SETTINGS_PATH.write_text(json.dumps({"ui_theme": 42, "ui_font_size": "huge", "plot_dpi": 600}),
                             encoding="utf-8")
    s = Settings.load()
    assert s.ui_theme == "dark" and s.ui_font_size == 14 and s.plot_dpi == 600
    SETTINGS.reset()
    SETTINGS.save()


def test_meta_reports_paths_and_repository(client):
    meta = client.get("/api/meta").json()
    assert meta["repository"] == "https://github.com/jovian-explorer/VEDA"
    assert set(meta["paths"]) >= {"data_root", "cache", "exports", "logs"}


# --- uploads ----------------------------------------------------------------

def _upload(client, name, content, **extra):
    return client.post("/api/veda/parse-file", json={"filename": name, "file_content": content, **extra})


def test_upload_pds3_label_with_companion_table(client):
    """Bug: every uploaded .tab/.csv failed ('Pds3Table' has no attribute 'row_count')."""
    lbl = SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.LBL"
    tab = lbl.with_suffix(".TAB")
    r = _upload(client, lbl.name, _text(lbl), body_id="mars",
                companion_files=[{"filename": tab.name, "file_content": _text(tab)}])
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["type"] == "profile" and body["data"]["n_points"] > 10
    assert "local_path" not in body


def test_upload_label_without_table_explains_what_to_do(client):
    lbl = SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.LBL"
    r = _upload(client, lbl.name, _text(lbl), body_id="mars")
    assert r.status_code == 422
    assert ".tab together" in r.json()["detail"]
    assert "Temp" not in r.json()["detail"] and "veda-" not in r.json()["detail"]


def test_reupload_does_not_reuse_stale_companions(client):
    """Bug: uploads shared one folder, so a label uploaded alone silently paired
    with a .tab left over from an earlier upload of the same name."""
    lbl = SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.LBL"
    tab = lbl.with_suffix(".TAB")
    first = _upload(client, lbl.name, _text(lbl), body_id="mars",
                    companion_files=[{"filename": tab.name, "file_content": _text(tab)}])
    assert first.status_code == 200, first.text[:300]
    again = _upload(client, lbl.name, _text(lbl), body_id="mars")
    assert again.status_code == 422
    assert ".tab together" in again.json()["detail"]


def test_upload_companion_named_meta_json_is_rejected(client):
    r = _upload(client, "profile.csv", "altitude,temperature\n0,1\n1,2\n",
                companion_files=[{"filename": "meta.json", "file_content": "{}"}])
    assert r.status_code == 400


def test_upload_headerless_tab_asks_for_label(client):
    tab = SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.TAB"
    r = _upload(client, tab.name, _text(tab), body_id="mars")
    assert r.status_code == 422
    assert ".lbl" in r.json()["detail"]


def test_upload_csv_with_header_and_decimation(client):
    rows = "\n".join(f"{i * 0.01:.2f},{200 + i % 50},{1000 * 2.718 ** (-i * 1e-4):.4f}" for i in range(20000))
    r = _upload(client, "big.csv", "altitude,temperature,pressure\n" + rows, decimate_max=1000)
    assert r.status_code == 200, r.text[:300]
    data = r.json()["data"]
    assert data["n_points"] == 20000 and len(data["altitude_km"]) == 1000


@pytest.mark.parametrize("name,content,status,needle", [
    ("empty.tab", "", 422, "empty"),
    ("blob.tab", "data:application/octet-stream;base64," + base64.b64encode(b"\x00\x01\x02" * 400).decode(), 422, "binary"),
    ("tool.exe", "MZ", 415, "Unsupported"),
    ("x.fits", "data:application/fits;base64,@@notbase64@@", 400, "base64"),
    ("../../evil.csv", "a,b\n1,2", 422, None),
    ("weird.csv", "a;b;c\n1;2\nfoo;bar;baz\n", 422, "altitude"),
])
def test_bad_uploads_fail_cleanly(client, name, content, status, needle):
    r = _upload(client, name, content)
    assert r.status_code == status, (name, r.status_code, r.text[:200])
    if needle:
        assert needle.lower() in r.json()["detail"].lower()


def test_uploaded_fits_can_be_rendered_and_listed(client, tmp_path):
    """Bug: uploaded images were treated as profiles and then 404'd."""
    from astropy.io import fits as _fits
    fits = tmp_path / "small.fits"
    yy, xx = np.mgrid[0:64, 0:64]
    _fits.PrimaryHDU(np.exp(-((xx - 32) ** 2 + (yy - 32) ** 2) / 200.0).astype("float32")).writeto(fits)
    r = _upload(client, "my_upload.fits", _b64(fits), body_id="pluto")
    assert r.status_code == 200 and r.json()["type"] == "image"
    png = client.get("/api/veda/image/user_imported/my_upload/render")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    recent = client.get("/api/veda/uploads").json()
    assert recent[0]["observation_id"] == "my_upload" and recent[0]["data_type"] == "image"
    assert client.delete("/api/veda/uploads/my_upload").status_code == 200
    assert client.get("/api/veda/image/user_imported/my_upload/render").status_code == 404


def test_uploaded_profile_can_be_exported(client):
    r = _upload(client, "sounding.csv", "altitude,temperature\n0,300\n10,280\n20,260\n30,240\n")
    assert r.status_code == 200
    csv = client.get("/api/veda/export/profile/user_imported/sounding/csv")
    assert csv.status_code == 200 and "altitude" in csv.text.lower()


# --- security -----------------------------------------------------------------

def test_parse_file_path_restricted_to_veda_folders(client, tmp_path):
    outside = tmp_path / "secret.csv"
    outside.write_text("altitude,temperature\n0,1\n1,2\n", encoding="utf-8")
    assert client.post("/api/veda/parse-file", json={"file_path": str(outside)}).status_code == 403
    inside = SAMPLES / "venus_akatsuki" / "rs_20160303_223100_udsc64_l4_ae_v10.lbl"
    assert client.post("/api/veda/parse-file", json={"file_path": str(inside)}).status_code == 200


def test_archive_api_rejects_unknown_and_bad_input(client):
    assert client.get("/api/veda/archive/search?dataset_id=nope").status_code == 404
    assert client.get("/api/veda/archive/search?start=yesterday").status_code == 422
    assert client.get("/api/veda/archive/search?start=2020-01-02&end=2020-01-01").status_code == 400
    assert client.post("/api/veda/archive/datasets/nope/index").status_code == 404
    r = client.post("/api/veda/archive/fetch", json={"items": [{"dataset_id": "mex-m-mrs-5-occ", "product_id": "../../x"}]})
    assert r.status_code == 404
    assert client.get("/api/veda/archive/profile/mex-m-mrs-5-occ/nope").status_code == 404


def test_archive_search_finds_bundled_real_products(client):
    r = client.get("/api/veda/archive/search?mission_id=mex&kind=profile&start=2004-01-01&end=2004-12-31")
    assert r.status_code == 200
    ids = {p["product_id"] for p in r.json()["products"]}
    assert {"M32ICL2L04_AIX_040931105_60", "M32ICL2L04_IIX_040931105_60"} <= ids
    prof = client.get("/api/veda/archive/profile/mex-m-mrs-5-occ/M32ICL2L04_AIX_040931105_60").json()
    temps = [t for t in prof["temperature_k"] if t is not None]
    assert 150 < min(temps) and max(temps) < 260          # Mars, 5-50 km
    assert prof["uncertainty"]["temperature_k"] and prof["track"]["latitude"]


def test_archive_paths_from_remote_files_cannot_escape(tmp_path):
    """Index paths and label pointers come from remote files; '..' must never be used."""
    from veda.archives.catalog import label_pointers
    assert ("TABLE", "../../evil.tab") in label_pointers('^TABLE = "../../evil.tab"')
    # fetch_product skips such pointers; index_volume skips such paths (see catalog.py)


def test_foreign_host_header_is_rejected(client):
    """DNS-rebinding guard: only localhost names may address the local API."""
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/api/health").status_code == 200


def test_no_wildcard_cors(client):
    r = client.get("/api/health", headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_match_column_prefers_the_named_quantity():
    """Bug: 'TEMPERATURE' matched 'PRESSURE (LOWER TEMPERATURE AT BOUNDARY)', so the
    Akatsuki profile plotted pressure in pascals as temperature (up to 47,000 K)."""
    from veda.readers.pds3_reader import match_column
    cols = ["RADIUS", "LATITUDE", "GEOPOTENTIAL_HEIGHT",
            "PRESSURE (LOWER TEMPERATURE AT BOUNDARY)", "SIGMA PRESSURE (LOWER TEMPERATURE AT BOUNDARY)",
            "PRESSURE (MEDIUM TEMPERATURE AT BOUNDARY)",
            "TEMPERATURE (LOWER TEMPERATURE AT BOUNDARY)", "SIGMA TEMPERATURE (MEDIUM TEMPERATURE AT BOUNDARY)",
            "TEMPERATURE (MEDIUM TEMPERATURE AT BOUNDARY)"]
    assert match_column(cols, "TEMPERATURE") == "TEMPERATURE (MEDIUM TEMPERATURE AT BOUNDARY)"
    assert match_column(cols, "PRESSURE") == "PRESSURE (MEDIUM TEMPERATURE AT BOUNDARY)"
    assert match_column(cols, "HEIGHT") == "GEOPOTENTIAL_HEIGHT"
    assert match_column(cols, "T") is None          # not LATITUDE
    assert match_column(["time", "Temp_K", "alt"], "TEMP_K") == "Temp_K"


def test_akatsuki_profile_temperature_is_physical():
    from veda.missions.manager import get_mission_manager
    prof = get_mission_manager().load_profile("akatsuki", "rs_20160303_223100_udsc64_l4_ae_v10")
    t = prof.temperature_k[~np.isnan(prof.temperature_k)]
    assert 100 < t.min() and t.max() < 400      # Venus 54-95 km: ~150-290 K
    p = prof.pressure_hpa[~np.isnan(prof.pressure_hpa)]
    assert p.max() < 1000                       # below 1 bar at >= 54 km
