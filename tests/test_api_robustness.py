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
    # the bundled Akatsuki profile has temperature and pressure (and so a scale height)
    for var in ("temperature_k", "pressure_hpa", "scale_height"):
        r = client.get(f"/api/veda/figure/publication?body_id=venus&variable={var}&dpi=72")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png", (var, r.text[:200])
    r = client.get("/api/veda/figure/publication?body_id=venus&variable=refractivity&dpi=72")
    assert r.status_code == 400 and "contain" in r.json()["detail"]
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


def test_requests_from_other_websites_are_refused(client):
    """A page of another website could make the browser send a form POST (settings,
    reset, indexing) or an <img> GET to the local API; those are refused, while VEDA's
    own page, a typed address and scripts (no browser headers) are served."""
    before = client.get("/api/meta").json()["settings"]
    form = {"content-type": "text/plain"}
    r = client.post("/api/settings", content=b'{"ui_theme": "light"}',
                    headers={**form, "origin": "https://evil.example", "sec-fetch-site": "cross-site"})
    assert r.status_code == 403
    # older browsers: no Sec-Fetch-Site, but an Origin that is not this server
    assert client.post("/api/settings/reset", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/settings/reset", headers={"origin": "null"}).status_code == 403
    assert client.get("/api/veda/bodies", headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert client.get("/api/veda/bodies", headers={"sec-fetch-site": "same-site"}).status_code == 403
    # a JSON body is required: a text/plain form post cannot set anything even without the headers
    assert client.post("/api/settings", content=b'{"ui_theme": "light"}', headers=form).status_code == 415
    assert client.get("/api/meta").json()["settings"] == before
    assert client.get("/api/veda/bodies", headers={"sec-fetch-site": "same-origin"}).status_code == 200
    assert client.get("/api/veda/bodies", headers={"sec-fetch-site": "none"}).status_code == 200
    assert client.post("/api/settings", json={}, headers={"origin": "http://testserver"}).status_code == 200
    # opening a folder is a POST, not a GET an <img> could trigger
    assert client.get("/api/reveal-folder?which=logs").status_code in (404, 405)


def test_corrupt_settings_file_is_repaired_on_load():
    SETTINGS_PATH.write_text(json.dumps({"ui_theme": 42, "ui_font_size": "huge", "plot_dpi": 600}),
                             encoding="utf-8")
    s = Settings.load()
    assert s.ui_theme == "dark" and s.ui_font_size == 14 and s.plot_dpi == 600
    SETTINGS.reset()
    SETTINGS.save()


def test_infinite_numbers_in_settings_are_rejected(client):
    """int(inf) raises OverflowError, not ValueError: {"plot_dpi": Infinity} gave a server
    error, and a settings.json holding 1e400 stopped VEDA from starting."""
    r = client.post("/api/settings", content=b'{"plot_dpi": Infinity}', headers={"content-type": "application/json"})
    assert r.status_code == 422 and "whole number" in r.json()["detail"]
    r = client.post("/api/settings", content=b'{"plot_dpi": NaN}', headers={"content-type": "application/json"})
    assert r.status_code == 422 and "whole number" in r.json()["detail"]
    SETTINGS_PATH.write_text('{"plot_dpi": 1e400, "ui_font_size": 16}', encoding="utf-8")
    s = Settings.load()
    assert s.plot_dpi == 300 and s.ui_font_size == 16
    SETTINGS.reset()
    SETTINGS.save()


def test_settings_that_cannot_be_saved_are_reported(client, monkeypatch, tmp_path):
    """Bug: a failed write of settings.json was ignored and the request answered 200."""
    import veda.config as config
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "missing-folder" / "settings.json")
    r = client.post("/api/settings", json={"plot_dpi": 600})
    assert r.status_code == 500 and "could not be saved" in r.json()["detail"]
    monkeypatch.undo()
    SETTINGS.reset()
    SETTINGS.save()


def test_oversized_requests_are_refused_before_reading(client, monkeypatch):
    """Uploads arrive whole in one JSON request; a request over the limit is refused from
    its Content-Length instead of being read into memory, and a comparison cannot list
    an unbounded number of observations."""
    import veda.api.app as app_module
    monkeypatch.setattr(app_module, "MAX_REQUEST_BYTES", 1000)
    r = _upload(client, "big.csv", "altitude,temperature\n" + "1,2\n" * 500)
    assert r.status_code == 413 and "larger than" in r.json()["detail"]
    monkeypatch.undo()
    many = [{"mission_id": "vex", "observation_id": str(i)} for i in range(5001)]
    assert client.post("/api/veda/compare/body/venus", json={"observations": many}).status_code == 422


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


def test_upload_names_with_folders_stay_in_the_upload_folder(client):
    """A file name with ../ (or a Windows path) is stored under its plain name inside the
    upload folder; nothing is written where the path points."""
    from veda.missions.uploads_adapter import UPLOAD_DIR
    good = "altitude,temperature\n0,300\n10,280\n20,260\n"
    for name in ("../../escaped.csv", "..\\..\\escaped.csv"):
        assert _upload(client, name, good).status_code == 200, name
        assert (UPLOAD_DIR / "escaped.csv" / "escaped.csv").is_file()
        for up in (UPLOAD_DIR.parent, UPLOAD_DIR.parent.parent, UPLOAD_DIR / "escaped.csv" / ".."):
            assert not (up / "escaped.csv").is_file()
    client.delete("/api/veda/uploads/escaped")


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


def test_uploaded_image_time_is_never_the_file_creation_date(client, tmp_path):
    """FITS DATE is when the file was written: the upload's answer showed it as the
    observation time, which the stored image (DATE-OBS only) did not have."""
    from astropy.io import fits as _fits
    f = tmp_path / "dated.fits"
    hdu = _fits.PrimaryHDU(np.ones((8, 8), dtype="float32"))
    hdu.header["DATE"] = "2026-01-01T00:00:00"
    hdu.writeto(f)
    r = _upload(client, "dated.fits", _b64(f), body_id="pluto")
    assert r.status_code == 200 and r.json()["time_utc"] == ""
    client.delete("/api/veda/uploads/dated")


@pytest.mark.parametrize("name", ["upper_case.FITS", "short_suffix.fts", "lower.fits"])
def test_uploaded_images_of_every_accepted_suffix_render(client, tmp_path, name):
    """Bug: only lower-case .fit/.fits were rendered, so accepted .FITS and .fts
    files loaded but their image gave 404."""
    from astropy.io import fits as _fits
    f = tmp_path / name
    _fits.PrimaryHDU((np.mgrid[0:32, 0:32][0] * 8.0).astype("float32")).writeto(f)
    r = _upload(client, name, _b64(f), body_id="pluto")
    assert r.status_code == 200 and r.json()["type"] == "image", r.text[:200]
    stem = name.rsplit(".", 1)[0]
    png = client.get(f"/api/veda/image/user_imported/{stem}/render")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    client.delete(f"/api/veda/uploads/{stem}")


def test_uploaded_profile_can_be_exported(client):
    r = _upload(client, "sounding.csv", "altitude,temperature\n0,300\n10,280\n20,260\n30,240\n")
    assert r.status_code == 200
    csv = client.get("/api/veda/export/profile/user_imported/sounding/csv")
    assert csv.status_code == 200 and "altitude" in csv.text.lower()


def test_failed_upload_keeps_the_earlier_good_one(client):
    """Bugs: a re-upload of a file that cannot be read deleted the good upload of the same
    name before reading it, and a failed obs.tab deleted the good obs.csv (same id)."""
    good = "altitude,temperature\n0,300\n10,280\n20,260\n30,240\n"
    assert _upload(client, "keepme.csv", good).status_code == 200
    assert _upload(client, "keepme.csv", "a;b;c\n1;2\nfoo;bar;baz\n").status_code == 422
    assert _upload(client, "keepme.tab", "1 2 3\n4 5\n").status_code == 422
    names = [u["filename"] for u in client.get("/api/veda/uploads").json()]
    assert "keepme.csv" in names and "keepme.tab" not in names
    assert client.get("/api/veda/export/profile/user_imported/keepme/csv").status_code == 200
    from veda.missions.uploads_adapter import UPLOAD_DIR
    assert not [d for d in UPLOAD_DIR.iterdir() if d.name.startswith(".staging-")]
    # a companion named like the primary file cannot replace it
    r = _upload(client, "twin.csv", good, companion_files=[{"filename": "twin.csv", "file_content": "x"}])
    assert r.status_code == 200 and r.json()["data"]["n_points"] == 4
    client.delete("/api/veda/uploads/keepme")
    client.delete("/api/veda/uploads/twin")
    # names the file system refuses are a bad request, not a server error
    assert _upload(client, "x" * 300 + ".csv", good).status_code == 400


def test_download_job_where_every_product_failed_is_failed(client, monkeypatch):
    """Bug: a download job always ended "completed" ("Downloaded 0 of 2") because its
    result, {"fetched": []}, was not empty."""
    import time as _time
    from veda.archives import catalog, net

    def fetch(dataset_id, product_id, *a, **k):
        if product_id == "good":
            return "x"
        raise net.ArchiveError("archive down")
    monkeypatch.setattr(catalog, "get_product", lambda ds, pid: {"product_id": pid})
    monkeypatch.setattr(catalog, "fetch_product", fetch)

    def run(pids):
        items = [{"dataset_id": "mex-m-mrs-5-occ", "product_id": p} for p in pids]
        job_id = client.post("/api/veda/archive/fetch", json={"items": items}).json()["job_id"]
        for _ in range(200):
            job = client.get(f"/api/veda/archive/jobs/{job_id}").json()
            if job["status"] != "running":
                return job
            _time.sleep(0.02)
        raise AssertionError("job did not finish")
    bad = run(["a", "b"])
    assert bad["status"] == "failed" and len(bad["errors"]) == 2 and "Downloaded 0 of 2" in bad["message"]
    mixed = run(["good", "b"])
    assert mixed["status"] == "completed" and mixed["result"]["fetched"] == ["good"] and len(mixed["errors"]) == 1


def test_product_transect_and_spectrum_validate_their_input(client, monkeypatch):
    """A band beyond the image (or non-numeric line ends) gave a server error (IndexError)
    in the product viewer's transect; it is now a 400 answer."""
    from veda.api import product_routes
    from veda.readers.product import open_product
    lbl = SAMPLES / "venus_akatsuki" / "uvi_20181105_080112_283_geo_v10.lbl"
    monkeypatch.setattr(product_routes, "_product", lambda ds, pid, confirm_large=True: open_product(str(lbl)))
    base = "/api/veda/product/x/y"
    ok = client.get(f"{base}/image/transect", params={"x0": 10, "y0": 10, "x1": 200, "y1": 300})
    assert ok.status_code == 200 and len(ok.json()["intensities"]) > 10
    r = client.get(f"{base}/image/transect", params={"x0": 10, "y0": 10, "x1": 200, "y1": 300, "band": 3})
    assert r.status_code == 400 and "band" in r.json()["detail"]
    assert client.get(f"{base}/image/transect", params={"x0": "nan", "y0": 10, "x1": 200, "y1": 300}).status_code == 400
    assert client.get(f"{base}/cube/spectrum", params={"line": 10, "sample": 10}).status_code == 200
    assert client.get(f"{base}/cube/spectrum", params={"line": 10**6, "sample": 10}).status_code == 400


def test_profile_failures_are_explained(client, monkeypatch):
    """Bug: an archive that could not be reached, or a product that could not be read,
    gave a bare 500 "Internal Server Error" when a profile was opened."""
    from veda.archives import net, profiles
    oid = "M32ICL2L04_AIX_040931105_60"

    def down(*a, **k):
        raise net.ArchiveError("Could not connect to archives.esac.esa.int. Check your internet connection.")
    monkeypatch.setattr(profiles, "load_profile_cached", down)
    r = client.get(f"/api/veda/profile/mex/{oid}")
    assert r.status_code == 502 and "internet connection" in r.json()["detail"]
    assert client.get(f"/api/veda/export/profile/mex/{oid}/csv").status_code == 502

    def corrupt(*a, **k):
        raise ValueError("C:/Users/x/cache/M32.TAB: no altitude or radius column")
    monkeypatch.setattr(profiles, "load_profile_cached", corrupt)
    r = client.get(f"/api/veda/profile/mex/{oid}")
    assert r.status_code == 422 and "no altitude" in r.json()["detail"] and "Users" not in r.json()["detail"]


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
    # dates are compared as text: anything but YYYY-MM-DD is refused, not misread
    assert client.get("/api/veda/archive/search?start=2020-01-01junk").status_code == 422
    for bad in ("2020-1-31", "2020-02-30", "31/01/2020"):
        r = client.post("/api/veda/compare/body/mars", json={"filter": {"start": bad, "download": False}})
        assert r.status_code == 422, bad
    r = client.post("/api/veda/export/compare/mars/profiles",
                    json={"filter": {"start": "2005-01-01", "end": "2004-01-01", "download": False}})
    assert r.status_code == 422 and "after the end" in r.json()["detail"]
    r = client.post("/api/veda/export/compare/mars/profiles", json={"group_by": "zodiac"})
    assert r.status_code == 422
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
    # a temperature figure of a Mars Express profile draws its systematic uncertainty too
    t = client.post("/api/veda/figure/publication?body_id=mars", json={**req, "variable": "temperature_k"})
    assert t.status_code == 200 and b"Systematic (boundary temperature)" in t.content
    assert b"Systematic" not in r.content or b"Systematic (boundary temperature)" in r.content


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
    assert mars["isobaric_heat_capacity_cp"] == 752.0 and mars["cp_model"].startswith("temperature-dependent")
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


def test_mission_details_say_what_kind_of_mission_it_is(client):
    """The mission page badge read mission_type from the details, which did not carry it,
    so New Horizons (a flyby) and the Mars landers and rovers were all shown as orbiters."""
    assert client.get("/api/veda/missions/new_horizons").json()["mission_type"] == "flyby"
    assert client.get("/api/veda/missions/mer").json()["mission_type"] == "rover"
    assert client.get("/api/veda/missions/mex").json()["mission_type"] == "orbiter"


def test_akatsuki_image_metadata_comes_from_the_file(client):
    """The UVI sample was shown with made-up defaults (0.05 s, 350,000 km, phase 45 deg);
    the file gives 0.5 s, 128,304 km and 23.23 deg (EXPOSURE, S_DISTAV, S_SSCPHA)."""
    # (the id the page sends: file names are case-sensitive on Linux)
    d = client.get("/api/veda/image/akatsuki/uvi_20181105_080112_283_geo_v10").json()
    assert d["exposure_seconds"] == 0.5
    assert d["target_distance_km"] == pytest.approx(128304.0)
    assert d["solar_phase_angle_deg"] == pytest.approx(23.2337)
    assert d["time_utc"] == "2018-11-05T08:01:12.369" and d["filter_name"] == "283 nm"


def test_comparison_candidates_come_from_data_sets_holding_the_variable():
    """Magellan's H2SO4/absorptivity profiles and Odyssey's densities hold no temperature,
    but were drawn as candidates for a temperature comparison, using up its budget."""
    from veda.archives.datasets import get_dataset
    from veda.missions.selection import provides
    h2so4 = get_dataset("mgn-v-rss-5-occ-prof-abs-h2so4-v1.0")
    ody = get_dataset("ody-m-accel-5-derived-v1.0")
    mex = get_dataset("mex-m-mrs-5-occ")
    assert not provides(h2so4, "temperature_k") and provides(h2so4, "h2so4_ppm")
    assert not provides(ody, "temperature_k") and not provides(ody, "density") and provides(ody, "density_measured")
    assert provides(mex, "temperature_k") and provides(mex, "density") and not provides(mex, "h2so4_ppm")


def test_comparison_csv_states_the_altitude_reference():
    """The comparison CSV said 'Altitude above the body's reference radius' for every
    comparison, including CRISM profiles above the local surface and probe profiles."""
    from veda.analysis.atmospheric import export_comparison_to_csv
    base = {"body_name": "Mars", "variable_name": "dust_mixing_ratio", "grid_km": [10.0], "altitude_step_km": 0.5,
            "composite_mean": [0.1], "composite_plus_1sigma": [None], "composite_minus_1sigma": [None]}
    prof = {"observation_id": "a", "mission_id": "mro", "interpolated_series": [0.1],
            "altitude_reference": "the local surface (CRISM limb retrieval levels)"}
    text = export_comparison_to_csv({**base, "profiles": [prof]})
    assert "# Altitude above the local surface (CRISM limb retrieval levels) (km), common grid every 0.5 km." in text
    line = next(x for x in text.splitlines() if x.startswith("# mro_a,"))
    assert line.endswith(", the local surface (CRISM limb retrieval levels)")       # its own column
    mixed = export_comparison_to_csv({**base, "profiles": [prof, {**prof, "observation_id": "b",
                                      "altitude_reference": "a sphere of radius 3389.5 km (from the radius column)"}]})
    assert "each profile's own reference" in mixed


def test_observation_ids_cannot_reach_files_outside_the_data_folder(client, tmp_path):
    """Observation ids come from the URL: an absolute path or ../ must not open a label or
    FITS file elsewhere on the computer (the Akatsuki adapter built paths from the id)."""
    import shutil
    src = SAMPLES / "venus_akatsuki"
    for f in src.iterdir():
        shutil.copy(f, tmp_path / f.name)
    stem = "rs_20160303_223100_udsc64_l4_ae_v10"
    img = "uvi_20181105_080112_283_geo_v10"
    assert client.get(f"/api/veda/profile/akatsuki/{stem}").status_code == 200       # the sample itself
    outside = tmp_path.as_posix()
    rel = "../" * 12 + outside.split(":", 1)[-1].lstrip("/")
    for oid in (f"{outside}/{stem}", f"{rel}/{stem}", f"..\\{stem}", "*", "rs_*"):
        assert client.get(f"/api/veda/profile/akatsuki/{oid}").status_code == 404, oid
        assert client.get(f"/api/veda/export/profile/akatsuki/{oid}/csv").status_code == 404, oid
    for oid in (f"{outside}/{img}", f"{rel}/{img}"):
        assert client.get(f"/api/veda/image/akatsuki/{oid}").status_code == 404, oid
        assert client.get(f"/api/veda/image/akatsuki/{oid}/render").status_code == 404, oid


def test_publication_figure_note_does_not_cover_the_axis_label(monkeypatch):
    """The altitude-reference note under the figure overlapped the x-axis label."""
    from matplotlib.figure import Figure
    from veda.api import routes
    from veda.core.registry import get_body
    seen = {}
    orig = Figure.savefig
    def keep(self, *a, **k):
        seen["fig"] = self
        return orig(self, *a, **k)
    monkeypatch.setattr(Figure, "savefig", keep)
    comp = {"grid_km": [50.0, 60.0, 70.0], "profile_count": 2, "composite_mean": [330.0, 260.0, 230.0],
            "profiles": [{"mission_id": "vex", "observation_id": "a", "interpolated_series": [330.0, 260.0, 230.0]},
                         {"mission_id": "akatsuki", "observation_id": "b", "interpolated_series": [331.0, 262.0, 229.0]}],
            "vertical_reference_warning": "Altitudes are measured from different references (AKATSUKI, VEX: the body's "
                                          "reference sphere; VEX: the Venus surface at the tangent point, as given by the "
                                          "SOIR team), so they are offset from each other."}
    routes._publication_figure(get_body("venus"), comp, "temperature_k", 100, "png")
    fig = seen["fig"]
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    r = FigureCanvasAgg(fig).get_renderer()
    label = fig.axes[0].xaxis.label.get_window_extent(r)
    note = fig.texts[0].get_window_extent(r)
    assert note.y1 < label.y0


def _label_rows(tab, cols):
    """Columns (1-based, whitespace-separated) of a bundled sample table."""
    rows = [line.split() for line in tab.read_text().splitlines() if line.strip()]
    return [np.array([float(r[c - 1]) for r in rows]) for c in cols]


def test_systematic_uncertainty_from_the_boundary_temperatures(client):
    """Mars Express and Akatsuki profiles are integrated down from three temperatures at
    the top; the systematic uncertainty is half the lower-upper difference, kept apart
    from the random 1-sigma, and carried into the derived quantities and the exports."""
    mex = client.get("/api/veda/archive/profile/mex-m-mrs-5-occ/M32ICL2L04_AIX_040931105_60").json()
    t_lo, t_hi = _label_rows(SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.TAB", (15, 19))
    sys_t = np.array([np.nan if v is None else v for v in mex["systematic"]["temperature_k"]])
    assert np.allclose(sys_t, np.abs(t_hi - t_lo) / 2, atol=1e-6)
    assert sys_t[0] == pytest.approx(35.0) and sys_t[-1] < 0.5      # 130/200 K at the top, ~0 near the ground
    assert mex["uncertainty"]["temperature_k"][0] == pytest.approx(10.0)  # the random 1-sigma stays as archived
    assert "lapse_rate" in mex["systematic"] and "density" in mex["systematic"]
    aka = client.get("/api/veda/archive/profile/vco-v-rs-5-occ-v1.0/rs_20160303_223100_udsc64_l4_ae_v10").json()
    t_lo, t_hi = _label_rows(SAMPLES / "venus_akatsuki" / "rs_20160303_223100_udsc64_l4_ae_v10.tab", (15, 19))
    sys_t = np.array([np.nan if v is None else v for v in aka["systematic"]["temperature_k"]])
    assert np.nanmax(np.abs(sys_t - np.abs(t_hi - t_lo) / 2)) < 1e-6 and np.nanmax(sys_t) == pytest.approx(30.05, abs=0.01)
    assert not aka["uncertainty"].get("temperature_k")                   # the archive's 1-sigma is -9.99 throughout
    from veda.archives.profiles import load_profile
    from veda.analysis.atmospheric import export_profile_to_csv
    text = export_profile_to_csv(load_profile("mex-m-mrs-5-occ", "M32ICL2L04_AIX_040931105_60"))
    header = next(line for line in text.splitlines() if line.startswith("altitude_km,"))
    assert "systematic_temperature_k" in header and "systematic_lapse_rate" in header and "sigma_temperature_k" in header
    comp = client.post("/api/veda/compare/body/mars", json={"observations": [
        {"mission_id": "mex", "observation_id": "M32ICL2L04_AIX_040931105_60"}], "variable": "temperature_k",
        "altitude_step_km": 1.0}).json()
    p = comp["profiles"][0]
    grid = np.asarray(comp["grid_km"])
    z = np.asarray(mex["altitude_km"], dtype=float)
    mex_sys = np.array([np.nan if v is None else v for v in mex["systematic"]["temperature_k"]])
    o = np.argsort(z)
    k = int(np.argmin(np.abs(grid - 40.0)))
    assert p["interpolated_systematic"][k] == pytest.approx(np.interp(grid[k], z[o], mex_sys[o]), rel=1e-3)


def test_number_density_uncertainty_of_radio_occultations(client):
    """Mars Express, MGS and MRO give the 1-sigma of the number density (SIGMA NUMBER
    DENSITY); the Mars Express one was skipped because the same table has LOWER / MEDIUM /
    UPPER variants of the other columns.  It is read now, and the temperature retrieved
    from the density gets a Monte Carlo 1-sigma."""
    mex = client.get("/api/veda/archive/profile/mex-m-mrs-5-occ/M32ICL2L04_AIX_040931105_60").json()
    n, s_n = _label_rows(SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.TAB", (21, 22))
    got = np.array([np.nan if v is None else v for v in mex["uncertainty"]["number_density_m3"]])
    np.testing.assert_allclose(got, s_n, rtol=1e-6)
    assert s_n[0] / n[0] == pytest.approx(0.0255, abs=1e-3)
    assert any(v is not None and v > 0 for v in mex["uncertainty"]["temperature_from_density"])
    assert mex["uncertainty"]["temperature_k"][0] == pytest.approx(10.0)       # the MEDIUM retrieval's, as before
