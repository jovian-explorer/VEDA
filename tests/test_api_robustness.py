"""Regression tests for API input validation, uploads and security fixes.

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


def test_upload_pds4_label_with_its_table(client):
    """ISSDC (and MAVEN, NH, ...) products are PDS4: an .xml label with a .csv/.tab table."""
    xml = SAMPLES / "titan_cassini_rss" / "s19tioc2006078_0107_n_sx_14_titan_edp_v01_r00.xml"
    csv_ = xml.with_suffix(".csv")
    r = _upload(client, xml.name, _text(xml), body_id="titan",
                companion_files=[{"filename": csv_.name, "file_content": _text(csv_)}])
    assert r.status_code == 200, r.text[:300]
    assert r.json()["type"] == "profile"
    alone = _upload(client, xml.name, _text(xml), body_id="titan")
    assert alone.status_code == 422 and "not loaded with the label" in alone.json()["detail"]


def test_bundled_cassini_titan_profile_is_real_pds4(client):
    prof = client.get("/api/veda/archive/profile/corss_occul_el_dens/s19tioc2006078_0107_n_sx_14_titan_edp_v01_r00").json()
    ne = [v for v in prof["electron_density_cm3"] if v is not None]
    assert 800 < max(ne) < 5000                       # Titan ionospheric peak, cm^-3
    assert prof["uncertainty"]["electron_density_cm3"] and prof["track"]["sza"]


# ---------------------------------------------------------------- choosing profiles to compare

def test_selection_geometry_rules():
    from veda.missions.selection import ProfileFilter, passes, spread_order
    f = ProfileFilter(lat_min=50, lat_max=90, lst_min=22, lst_max=2)          # local time wraps midnight
    assert passes({"latitude": 60.0, "lst": 23.5, "sza": None}, f) == (True, "")
    assert passes({"latitude": 60.0, "lst": 1.0, "sza": None}, f) == (True, "")
    assert passes({"latitude": 60.0, "lst": 12.0, "sza": None}, f)[1] == "local time outside the range"
    assert passes({"latitude": 10.0, "lst": 23.0, "sza": None}, f)[1] == "latitude outside the range"
    assert passes({"latitude": 60.0, "lst": None, "sza": None}, f)[1] == "local time unknown"
    assert passes({"latitude": None, "lst": None, "sza": None}, ProfileFilter()) == (True, "")
    for n in (1, 2, 7, 33):
        order = spread_order(n)
        assert sorted(order) == list(range(n))
        if n > 2:
            assert order[:2] == [0, n - 1]              # the first picks span the whole range


def test_comparison_filters_by_date_and_latitude(client):
    sample = "M32ICL2L04_AIX_040931105_60"
    lat = client.get(f"/api/veda/archive/profile/mex-m-mrs-5-occ/{sample}").json()["latitude"]
    base = {"missions": ["mex"], "variable": "temperature_k"}
    inside = client.post("/api/veda/compare/body/mars", json={**base, "filter": {
        "start": "2004-04-01", "end": "2004-04-03", "lat_min": lat - 1, "lat_max": lat + 1, "download": False}}).json()
    assert sample in [p["observation_id"] for p in inside["profiles"]]
    # each compared profile names its archive data set, for the Cite panel
    assert {p["dataset_id"] for p in inside["profiles"]} == {"mex-m-mrs-5-occ"}
    assert inside["selection"]["mex"]["kept"] >= 1
    # only the bundled samples are catalogued: the archive itself is not indexed, and the
    # report says so (it counted the samples as an index)
    assert inside["selection"]["mex"]["not_indexed"] == ["mex-m-mrs-5-occ"]
    outside = client.post("/api/veda/compare/body/mars", json={**base, "filter": {
        "start": "2004-04-01", "end": "2004-04-03", "lat_min": lat + 5, "lat_max": lat + 10, "download": False}}).json()
    assert outside["profile_count"] == 0
    assert outside["selection"]["mex"]["left_out"].get("latitude outside the range", 0) >= 1
    later = client.post("/api/veda/compare/body/mars", json={**base, "filter": {"start": "2030-01-01", "download": False}}).json()
    assert later["selection"]["mex"]["in_date_range"] == 0
    bad = client.post("/api/veda/compare/body/mars", json={**base, "filter": {"start": "2005-01-01", "end": "2004-01-01"}})
    assert bad.status_code == 422
    assert client.post("/api/veda/compare/body/mars", json={**base, "filter": {"lat_min": 95}}).status_code == 422


def test_publication_figure_uses_the_compared_profiles(client):
    """The figure used to be redrawn from one default profile per mission, ignoring the
    hand-picked profiles and filters behind the plot on screen."""
    req = {"observations": [{"mission_id": "mex", "observation_id": "M32ICL2L04_AIX_040931105_60"}],
           "variable": "pressure_hpa", "dpi": 72, "fmt": "svg"}
    r = client.post("/api/veda/figure/publication?body_id=mars", json=req)
    assert r.status_code == 200 and b"<svg" in r.content[:400]
    assert b"1 profile" in r.content and b"2004-04-02" in r.content        # title: count and date
    csv = client.post("/api/veda/export/compare/mars/csv", json={k: v for k, v in req.items() if k not in ("dpi", "fmt")})
    assert csv.status_code == 200 and "M32ICL2L04_AIX_040931105_60" in csv.text


def test_table_x_range_selects_rows_before_decimation(client):
    base = "/api/veda/product/mex-m-mrs-5-occ/M32ICL2L04_AIX_040931105_60/table"
    full = client.get(base, params={"x": "UTC TIME", "y": ["TEMPERATURE (MEDIUM BOUNDARY CONDITION)"]}).json()
    times = full["x"]["values"]
    assert full["rows"] == 354 and full["x_range"] is None          # all rows (the last two were once lost)
    lo, hi = times[100], times[199]
    part = client.get(base, params={"x": "UTC TIME", "y": ["TEMPERATURE (MEDIUM BOUNDARY CONDITION)"], "x_min": lo.replace("T", " "), "x_max": hi}).json()
    assert part["rows"] == 100 and part["rows_total"] == 354
    assert part["x"]["values"][0] == lo and part["x"]["values"][-1] == hi
    assert part["series"][0]["values"] == full["series"][0]["values"][100:200]
    rows = client.get(base, params={"x": "__row__", "y": ["TEMPERATURE (MEDIUM BOUNDARY CONDITION)"], "x_min": "11", "x_max": "20"}).json()
    assert rows["x"]["values"] == list(range(11, 21))
    assert client.get(base, params={"x": "__row__", "y": ["TEMPERATURE (MEDIUM BOUNDARY CONDITION)"], "x_min": "abc"}).status_code == 400


# ---------------------------------------------------------------- loading files with column roles

def test_pressure_label_units_hpa_is_not_pascal():
    """"PA" in "HPA" used to divide hPa columns by 100."""
    from veda.pipeline.ingest import unit_from_label
    assert unit_from_label("pressure", "HPA") == "hPa"
    assert unit_from_label("pressure", "MILLIBAR") == "mbar"
    assert unit_from_label("pressure", "PASCAL") == "Pa"
    assert unit_from_label("pressure", "BAR") == "bar"
    assert unit_from_label("temperature", "DEGREE CELSIUS") == "C"
    assert unit_from_label("altitude", "M") == "m"


def test_fill_values_in_text_tables_are_missing_not_celsius(tmp_path):
    """-999 in a Kelvin temperature column made the load dialog (and the guessed load)
    take the column for degrees Celsius, adding 273 K to every level."""
    from veda.core.registry import get_body
    from veda.pipeline.ingest import build_profile, suggest_roles
    from veda.readers.pds3_reader import read_any_table
    f = tmp_path / "fill.csv"
    f.write_text("altitude_km,temperature,pressure\n40,350,1000\n50,300,-999\n60,250,100\n"
                 "70,-9999,30\n80,200,1e36\n")
    roles = suggest_roles(read_any_table(str(f)))
    assert roles["TEMPERATURE"]["unit"] == "K"
    for r in (roles, None):
        prof, _ = build_profile(f, get_body("venus"), roles=r)
        assert prof.temperature_k[0] == pytest.approx(350.0) and np.isnan(prof.temperature_k[3])
        assert np.isnan(prof.pressure_hpa[1]) and np.isnan(prof.pressure_hpa[4])


def test_headerless_file_loaded_with_chosen_roles_units_and_mission(client):
    # radius in metres, temperature in C, pressure in Pa, no header
    rows = "\n".join(f"{(6051.8 + z) * 1000:.1f} {t:.2f} {p:.3f}"
                     for z, t, p in ((50, 76.8, 100000.0), (60, -18.0, 23000.0), (70, -45.0, 3500.0)))
    pv = client.post("/api/veda/upload/preview", json={"filename": "venus_ro.txt", "file_content": rows}).json()
    assert pv["type"] == "table" and len(pv["columns"]) == 3
    cols = [c["name"] for c in pv["columns"]]
    roles = {cols[0]: {"role": "radius", "unit": "m"}, cols[1]: {"role": "temperature", "unit": "C"},
             cols[2]: {"role": "pressure", "unit": "Pa"}}
    r = client.post("/api/veda/parse-file", json={"filename": "venus_ro.txt", "file_content": rows, "body_id": "venus",
                                                  "source_mission": "vex", "instrument": "VeRa",
                                                  "time_utc": "2014-02-17T03:47:57", "roles": roles})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["altitude_km"][0] == pytest.approx(50.0, abs=1e-6)
    assert d["temperature_k"][0] == pytest.approx(349.95)
    assert d["pressure_hpa"][0] == pytest.approx(1000.0)
    assert d["time_utc"] == "2014-02-17T03:47:57" and "VeRa" in d["instrument"]
    items = client.get("/api/veda/uploads").json()
    it = next(i for i in items if i["observation_id"] == "venus_ro")
    assert it["source_mission"] == "vex" and it["roles"][cols[1]]["unit"] == "C"
    again = client.get("/api/veda/profile/user_imported/venus_ro").json()        # rebuilt with the same roles
    assert again["temperature_k"][0] == pytest.approx(349.95)
    comp = client.post("/api/veda/compare/body/venus", json={"missions": [], "variable": "temperature_k",
                                                             "filter": {"start": "2014-02-01", "end": "2014-03-01", "download": False}}).json()
    assert any(p["observation_id"] == "venus_ro" and p["mission_label"] == "vex" for p in comp["profiles"])


def test_load_rejects_bad_roles_and_does_not_invent_a_time(client):
    rows = "10 200 5\n20 190 2\n30 180 1"
    bad = client.post("/api/veda/parse-file", json={"filename": "x.txt", "file_content": rows, "body_id": "mars",
                                                    "roles": {"COL_1": {"role": "temperature", "unit": "K"}}})
    assert bad.status_code == 422 and "altitude or radius" in bad.json()["detail"]
    wrong_unit = client.post("/api/veda/parse-file", json={"filename": "x.txt", "file_content": rows, "body_id": "mars",
                                                           "roles": {"COL_1": {"role": "altitude", "unit": "furlong"}}})
    assert wrong_unit.status_code == 422
    ok = client.post("/api/veda/parse-file", json={"filename": "x.txt", "file_content": rows, "body_id": "mars",
                                                   "roles": {"COL_1": {"role": "altitude", "unit": "km"},
                                                             "COL_2": {"role": "temperature", "unit": "K"}}}).json()
    assert ok["data"]["time_utc"] == ""                     # was a made-up 2026-01-01T12:00:00Z


def test_loaded_mass_density_profile_is_compared_as_measured_density(client):
    """A file holding only a mass density (an accelerometer or entry profile) can be loaded:
    there was no mass density column role, so such files could not be read at all."""
    text = "alt,RHO [kg/km**3],RHO_SIGMA\n100,20.0,1.0\n110,6.0,0.4\n120,2.0,0.2\n"
    pv = client.post("/api/veda/upload/preview", json={"filename": "acc.csv", "file_content": text}).json()
    sug = pv["suggested_roles"]
    alt, rho, srho = [c["name"] for c in pv["columns"]]
    assert sug[rho]["role"] == "mass_density" and sug[rho]["unit"] == "kg/km3"      # name and label unit
    assert sug[srho] == {"role": "mass_density_sigma", "unit": "kg/km3"}     # its quantity's unit
    roles = {alt: {"role": "altitude", "unit": "km"}, rho: {"role": "mass_density", "unit": "kg/km3"},
             srho: {"role": "mass_density_sigma", "unit": "kg/km3"}}
    r = client.post("/api/veda/parse-file", json={"filename": "acc.csv", "file_content": text, "body_id": "mars",
                                                  "roles": roles})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["derived"]["density_measured"][0] == pytest.approx(2.0e-8)
    assert d["uncertainty"]["density_measured"][0] == pytest.approx(1.0e-9)
    from veda.pipeline.ingest import unit_from_label
    assert unit_from_label("mass_density", "kg/km**3") == "kg/km3"
    assert unit_from_label("mass_density", "KG/M**3") == "kg/m3" and unit_from_label("mass_density", "g/cm^3") == "g/cm3"


def test_comparison_altitude_step_is_chosen_by_the_user(client):
    base = {"missions": ["mex"], "variable": "temperature_k",
            "filter": {"start": "2004-04-01", "end": "2004-04-03", "download": False}}
    default = client.post("/api/veda/compare/body/mars", json=base).json()
    assert default["profile_count"] >= 1 and default["altitude_step_km"] == 0.5
    fine = client.post("/api/veda/compare/body/mars", json={**base, "altitude_step_km": 0.1}).json()
    assert fine["altitude_step_km"] == 0.1
    assert np.allclose(np.diff(fine["grid_km"]), 0.1)
    assert len(fine["grid_km"]) > 4 * len(default["grid_km"])
    csv = client.post("/api/veda/export/compare/mars/csv", json={**base, "altitude_step_km": 0.1}).text
    assert "common grid every 0.1 km" in csv
    too_fine = client.post("/api/veda/compare/body/mars", json={**base, "altitude_step_km": 0.001})
    assert too_fine.status_code == 422                       # below the 0.01 km minimum


def test_comparison_grid_size_is_bounded():
    from veda.analysis.atmospheric import MAX_GRID_LEVELS, compare_profiles_on_body
    from veda.core.models import ObservationProfile
    from veda.core.registry import get_body
    z = np.linspace(0.0, 5000.0, 50)
    p = ObservationProfile("s", "cassini", "saturn", "UVIS", "2010-01-01", altitude_km=z, temperature_k=np.full(50, 400.0))
    r = compare_profiles_on_body([p], get_body("saturn"), altitude_step_km=0.01)
    assert "choose a step of at least" in r["error"] and r["profile_count"] == 0
    assert compare_profiles_on_body([p], get_body("saturn"), altitude_step_km=0.5).get("error") is None
    assert 5000.0 / 0.5 + 1 <= MAX_GRID_LEVELS


def test_comparison_on_pressure_levels_through_the_api(client):
    base = {"missions": ["mex"], "variable": "temperature_k", "vertical": "pressure",
            "filter": {"start": "2004-04-01", "end": "2004-04-03", "download": False}}
    r = client.post("/api/veda/compare/body/mars", json=base)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["profile_count"] >= 1 and d["grid_hpa"] and d["grid_km"] == []
    assert client.post("/api/veda/export/compare/mars/csv", json=base).text.count("\npressure_hpa,") == 1
    fig = client.post("/api/veda/figure/publication?body_id=mars", json={**base, "dpi": 100, "fmt": "png"})
    assert fig.status_code == 200 and fig.headers["content-type"] == "image/png"
    assert client.post("/api/veda/compare/body/mars", json={**base, "variable": "pressure_hpa"}).status_code == 400
    assert client.post("/api/veda/compare/body/mars", json={**base, "vertical": "theta"}).status_code == 422


def test_comparison_csv_carries_a_recipe_that_redoes_it(client):
    req = {"missions": ["mex"], "variable": "temperature_k", "altitude_step_km": 1.0, "group_by": "latitude",
           "filter": {"start": "2004-04-01", "end": "2004-04-03", "download": False}}
    first = client.post("/api/veda/compare/body/mars", json=req).json()
    csv = client.post("/api/veda/export/compare/mars/csv", json=req).text
    line = next(l for l in csv.splitlines() if l.startswith("# recipe: "))
    recipe = json.loads(line[len("# recipe: "):])
    assert recipe["veda_recipe"] == 1 and recipe["body_id"] == "mars" and recipe["altitude_step_km"] == 1.0
    assert [o["observation_id"] for o in recipe["observations"]] == [p["observation_id"] for p in first["profiles"]]
    again = client.post(f"/api/veda/compare/body/{recipe['body_id']}", json=recipe).json()   # the recipe is a request
    assert [p["observation_id"] for p in again["profiles"]] == [p["observation_id"] for p in first["profiles"]]
    assert again["composite_mean"] == first["composite_mean"] and again["grid_km"] == first["grid_km"]


def test_body_details_carry_molar_mass_and_heat_capacity(client):
    """The body banner shows mu and cp (USAGE says so); cp is marked as a reference
    value where derived quantities use cp(T)."""
    mars = client.get("/api/veda/bodies/mars").json()
    assert mars["mean_molecular_weight"] == pytest.approx(43.487)
    assert mars["isobaric_heat_capacity_cp"] == 830.0 and mars["cp_model"].startswith("temperature-dependent")
    assert client.get("/api/veda/bodies/saturn").json()["cp_model"] == "constant"


def test_data_licenses_panel_names_every_mission_with_data():
    """Data & Licenses lists, per archive, the missions VEDA reads from it; the lists were
    written by hand and missed Odyssey, the Mars landers, VEGA and the research repositories."""
    from veda.archives.datasets import DATASETS
    from veda.core.registry import DATA_LICENSES, DATA_PORTALS
    listed = {m for p in DATA_PORTALS for m in p["missions"]}
    assert {ds.mission_id for ds in DATASETS} <= listed
    repo = next(p for p in DATA_PORTALS if p["id"] == "research_repositories")
    assert "vex" in repo["missions"] and "cc_by_4" in DATA_LICENSES
