"""Live archive services, SPICE kernel selection and the citation builder (offline parts)."""
from __future__ import annotations

import datetime as dt

import pytest

from veda.archives import services
from veda.archives.datasets import DATASETS, get_dataset
from veda.geometry import kernels


def test_every_mission_has_data_sets_and_live_ones_have_references():
    missions = {d.mission_id for d in DATASETS}
    for m in ("akatsuki", "vex", "mex", "mgs", "maven", "mro", "juno", "galileo", "cassini", "new_horizons",
              "messenger", "magellan", "pvo", "lro", "dawn", "rosetta", "bepicolombo", "mom", "chandrayaan2"):
        assert m in missions, m
    live = [d for d in DATASETS if d.service]
    assert len(live) > 80
    assert all(d.refs for d in live)
    assert len({d.id for d in DATASETS}) == len(DATASETS)          # unique ids


def test_psa_product_type_and_julian_dates():
    assert services._psa_type("MEX-M-ASPERA3-2-EDR-ELS-EXT1-V1.0", "2") == "ASPERA3 EDR ELS (level 2)"
    d = dt.datetime(2009, 6, 17, 12)
    assert services._from_jd(services._jd(d)).startswith("2009-06-17T12:00")
    assert services._iso(["1965-01-01T00:00:00Z"]) == ""             # registry placeholder time


def test_live_window_cache(tmp_path, monkeypatch):
    import sqlite3
    import threading
    db = tmp_path / "c.sqlite"

    def connect():
        from veda.archives.catalog import _ClosingConnection
        c = sqlite3.connect(db, factory=_ClosingConnection)
        c.execute("CREATE TABLE IF NOT EXISTS products (dataset_id, product_id, volume, path, start_time, "
                  "stop_time, target, product_type, kind, extra, PRIMARY KEY (dataset_id, product_id))")
        return c
    calls = []

    def fake(q, t0, t1, limit):
        calls.append((t0, t1))
        return [{"product_id": "P1", "volume": "V", "path": "https://x/y/P1.LBL", "start_time": "2009-06-17T01:00:00",
                 "stop_time": "", "target": "MARS", "product_type": "T (level 2)", "extra": {}}], 1
    monkeypatch.setitem(services.QUERIES, "psa_tap", fake)
    ds = get_dataset("psa-mex-aspera3")
    lock = threading.Lock()
    r1 = services.search_window(ds, "2009-06-17", "2009-06-17", connect, lock)
    r2 = services.search_window(ds, "2009-06-17", "2009-06-17", connect, lock)
    assert r1["listed"] == 1 and not r1["cached"] and r2["cached"] and len(calls) == 1
    with pytest.raises(services.ServiceError):
        services.search_window(ds, "2009-06-18", "2009-06-17", connect, lock)


@pytest.mark.parametrize("code,expected", [
    ("090617", dt.date(2009, 6, 17)), ("20090617", dt.date(2009, 6, 17)), ("09168", dt.date(2009, 6, 17)),
    ("2009168", dt.date(2009, 6, 17)), ("100101000000", dt.date(2010, 1, 1)), ("2009-06-17", dt.date(2009, 6, 17)),
])
def test_kernel_date_codes(code, expected):
    assert kernels._date(code) == expected


def test_range_source_returns_boundary_files(monkeypatch):
    src = kernels.Source("https://x/", "range", r"^200128RU_SCPSE_(?P<start>\d{5})_(?P<end>\d{5})\.bsp$")
    monkeypatch.setattr(kernels, "_listing", lambda url: ["200128RU_SCPSE_09153_09168.bsp",
                                                         "200128RU_SCPSE_09168_09184.bsp", "other.bsp"])
    urls = kernels._from_source(src, dt.date(2009, 6, 17))
    assert set(u.rsplit("/", 1)[1] for u in urls) == {"200128RU_SCPSE_09153_09168.bsp", "200128RU_SCPSE_09168_09184.bsp"}
    assert kernels._from_source(src, dt.date(2009, 6, 20)) == ["https://x/200128RU_SCPSE_09168_09184.bsp"]


def test_next_and_fixed_sources(monkeypatch):
    monkeypatch.setattr(kernels, "_listing", lambda url: ["ORVV_T19_100101000000_00287.BSP", "ORVV_T19_100201000000_00290.BSP"])
    nxt = kernels.Source("https://v/", "next", r"^ORVV_T19_(?P<start>\d{12})_\d{5}\.BSP$")
    assert kernels._from_source(nxt, dt.date(2010, 1, 15))[0].endswith("ORVV_T19_100101000000_00287.BSP")
    assert kernels._from_source(nxt, dt.date(2010, 2, 3))[0].endswith("ORVV_T19_100201000000_00290.BSP")
    fixed = kernels.MISSION_SPICE["magellan"].sources[0]
    assert kernels._from_source(fixed, dt.date(1991, 10, 5))[0].endswith("CYCLE2.BSP")
    assert kernels._from_source(fixed, dt.date(1995, 1, 1)) == []


def test_body_kernels_cover_non_de440s_targets():
    for body in ("mars", "pluto", "ceres", "vesta", "comet_67p"):
        assert kernels.base_plan(body).urls[-1] != kernels.GENERIC[-1]


def test_citations_follow_usage():
    from veda.citations import build
    r = build(["vco-v-rs-5-occ-v1.0", "psa-mex-spicam"], ["geometry", "figure_export"],
              {"psa-mex-spicam": ["MEX-M-SPI-2-UVEDR-RAWXMARS-EXT1-V1.0"]})
    keys = {p["key"] for d in r["data"] for p in d["papers"]}
    assert {"imamura2017", "bertaux2006"} <= keys
    assert any("SPICE" in f["title"] for f in r["features"])
    assert "@software{Aggarwal_VEDA_2026" in r["bibtex"] and "@article{acton1996" in r["bibtex"]
    assert "JAXA" in r["statement"] and "ESA" in r["statement"] and "NAIF" in r["statement"]
    spicam = next(d for d in r["data"] if d["dataset_id"] == "psa-mex-spicam")
    assert spicam["archive_ids"] == ["MEX-M-SPI-2-UVEDR-RAWXMARS-EXT1-V1.0"]


def test_agu_article_numbers_replace_doi_suffix_pages():
    from veda.citations import references, ref_text
    assert "E10S90" in ref_text(references()["bertaux2006"])


def test_index_rows_path_filename_and_long_paths():
    from veda.archives import catalog
    ds = get_dataset("mro-m-mcs-5-ddr-v1.0")
    row = catalog._index_row(ds, "MROM_2001", "https://x/", {"PATH": "2006/200609/20060924",
                                                              "FILENAME": "2006092416_DDR.TAB",
                                                              "START_TIME": "2006-09-24T16:40:38.836"})
    assert row["path"] == "DATA/2006/200609/20060924/2006092416_DDR.LBL"
    assert row["start_time"].startswith("2006-09-24T16:40")
    p = catalog.local_label_path("psa-mex-pfs", "V", "https://archives.esac.esa.int/psa/ftp/" + "A" * 200 + "/X.LBL")
    assert p.name == "X.LBL" and len(str(p.relative_to(catalog.PRODUCT_ROOT))) < 60


# ---------------------------------------------------------------- large product files

class _FakeResponse:
    def __init__(self, body: bytes, length: int):
        self.headers = {"Content-Length": str(length)}
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size):
        yield self._body

    def close(self):
        self.closed = True


def test_download_refuses_files_over_the_limit_before_writing(tmp_path, monkeypatch):
    from veda.archives import net
    resp = _FakeResponse(b"x" * 10, 1_200_000_000)
    monkeypatch.setattr(net, "get", lambda url, **kw: resp)
    with pytest.raises(net.TooLarge) as exc:
        net.download("https://example.org/UVS.FIT", tmp_path / "UVS.FIT", max_bytes=250_000_000)
    assert exc.value.size_bytes == 1_200_000_000 and resp.closed
    assert not (tmp_path / "UVS.FIT").exists() and not list(tmp_path.glob("*.part"))
    small = _FakeResponse(b"abc", 3)
    monkeypatch.setattr(net, "get", lambda url, **kw: small)
    assert net.download("https://example.org/a.dat", tmp_path / "a.dat", max_bytes=250).read_bytes() == b"abc"


def test_simultaneous_downloads_of_one_file_do_not_collide(tmp_path, monkeypatch):
    """Two products in one folder share a format file; downloading both at once wrote one
    .part file from two threads and one of them failed with a PermissionError."""
    import threading
    import time
    from veda.archives import net

    class Slow:
        headers = {"Content-Length": "40"}

        def iter_content(self, chunk_size):
            for _ in range(4):
                time.sleep(0.03)
                yield b"x" * 10

        def close(self):
            pass
    monkeypatch.setattr(net, "get", lambda url, **kw: Slow())
    dest = tmp_path / "MORS.FMT"
    errors = []

    def fetch(delay):
        time.sleep(delay)
        try:
            net.download("https://example.org/MORS.FMT", dest)
        except Exception as exc:          # noqa: BLE001 - any failure is the bug
            errors.append(exc)
    threads = [threading.Thread(target=fetch, args=(d,)) for d in (0, 0.01, 0.05)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert dest.read_bytes() == b"x" * 40 and not list(tmp_path.glob("*.part"))


def test_structure_answers_413_with_the_size_until_confirmed(monkeypatch):
    from fastapi.testclient import TestClient
    from veda.api import product_routes
    from veda.api.app import create_app
    from veda.archives import net
    seen = []

    def fake_fetch(ds, pid, progress=None, max_bytes=None):
        seen.append(max_bytes)
        if max_bytes is not None:
            raise net.TooLarge("UVS.FIT", 1_200_000_000)
        raise net.ArchiveError("stop here")

    monkeypatch.setattr(product_routes.catalog, "get_product", lambda ds, pid: {"volume": "", "path": ""})
    monkeypatch.setattr(product_routes.catalog, "fetch_product", fake_fetch)
    c = TestClient(create_app())
    r = c.get("/api/veda/product/pds-juno-uvs/x/structure")
    assert r.status_code == 413 and r.json()["detail"]["size_bytes"] == 1_200_000_000
    assert c.get("/api/veda/product/pds-juno-uvs/x/structure", params={"confirm_large": True}).status_code == 502
    assert seen[0] == 250_000_000 and seen[1] is None


def test_refused_server_is_reported_as_refused_not_missing(monkeypatch):
    from veda.archives import catalog, net
    ds = get_dataset("pds-galileo-radioscience")
    url = "https://pds-rings.seti.org/pds4/bundles/gll.rss/x/g1/p.xml"
    monkeypatch.setattr(catalog, "get_product", lambda d, p: {"volume": "", "path": url})

    def refuse(u, dest, **kw):
        raise net.ArchiveError("pds-rings.seti.org refused the request (HTTP 403).")
    monkeypatch.setattr(net, "download", refuse)
    with pytest.raises(net.ArchiveError, match="HTTP 403"):
        catalog.fetch_product(ds.id, "p")

    def too_big(u, dest, **kw):
        raise net.TooLarge("p.fit", 900_000_000)
    monkeypatch.setattr(net, "download", too_big)
    with pytest.raises(net.TooLarge):
        catalog.fetch_product(ds.id, "p", max_bytes=1000)


def test_download_progress_is_visible_while_a_product_downloads(monkeypatch):
    from fastapi.testclient import TestClient
    from veda.api import product_routes
    from veda.api.app import create_app
    from veda.archives import net
    seen = {}

    def fake_fetch(ds, pid, progress=None, max_bytes=None):
        progress(3_000_000, 12_000_000)
        seen["during"] = product_routes.progress(ds, pid)
        raise net.ArchiveError("stop here")

    monkeypatch.setattr(product_routes.catalog, "get_product", lambda ds, pid: {"volume": "", "path": ""})
    monkeypatch.setattr(product_routes.catalog, "fetch_product", fake_fetch)
    c = TestClient(create_app())
    c.get("/api/veda/product/pds-lro-diviner/x/structure")
    assert seen["during"] == {"active": True, "done": 3_000_000, "total": 12_000_000}
    assert c.get("/api/veda/product/pds-lro-diviner/x/progress").json()["active"] is False


def test_ftp_fallback_only_for_mirrored_hosts_and_not_for_missing_files(tmp_path, monkeypatch):
    from veda.archives import net
    calls = []

    def https_fails(msg):
        def f(url, dest, *a, **kw):
            raise net.ArchiveError(msg)
        return f

    def ftp_ok(url, dest, *a, **kw):
        calls.append(url)
        dest.write_bytes(b"ok")
        return dest
    monkeypatch.setattr(net, "_ftp_download", ftp_ok)
    monkeypatch.setattr(net, "_https_download", https_fails("pds-atmospheres.nmsu.edu refused the request (HTTP 503)."))
    net.download("https://pds-atmospheres.nmsu.edu/PDS/data/mg_2401/data/mgn_abs.lbl", tmp_path / "a.lbl")
    assert calls == ["ftp://pds-atmospheres.nmsu.edu/PDS/data/mg_2401/data/mgn_abs.lbl"]
    monkeypatch.setattr(net, "_https_download", https_fails("pds-atmospheres.nmsu.edu does not have /x (HTTP 404)."))
    with pytest.raises(net.ArchiveError, match="404"):
        net.download("https://pds-atmospheres.nmsu.edu/x", tmp_path / "x")
    monkeypatch.setattr(net, "_https_download", https_fails("pds-rings.seti.org refused the request (HTTP 503)."))
    with pytest.raises(net.ArchiveError):
        net.download("https://pds-rings.seti.org/pds4/x.xml", tmp_path / "y")     # no FTP there
    assert len(calls) == 1


def test_busy_server_403_is_retried(monkeypatch):
    from veda.archives import net
    codes = iter([403, 403, 200])

    class R:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            pass

    class S:
        def get(self, *a, **kw):
            return R(next(codes))
    monkeypatch.setattr(net, "session", lambda: S())
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    assert net.get("https://pds-rings.seti.org/pds4/bundles/gll.rss/").status_code == 200


def test_product_falls_back_to_a_mirror_archive(monkeypatch, tmp_path):
    """MEX MaRS volumes are at ESA PSA and, renamed, at the PDS Geosciences Node."""
    from veda.archives import catalog, net
    monkeypatch.setattr(catalog, "PRODUCT_ROOT", tmp_path)   # files from earlier runs are not reused
    ds = get_dataset("mex-m-mrs-5-occ")
    monkeypatch.setattr(catalog, "get_product", lambda d, p: {
        "volume": "MEX-M-MRS-5-OCC-9124-V1.0", "path": "DATA/DOY_126/LEVEL04/P.TAB"})
    urls = []

    def download(url, dest, **kw):
        urls.append(url)
        if "esac.esa.int" in url:
            raise net.ArchiveError("archives.esac.esa.int refused the request (HTTP 503).")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("1,2\n")
        return dest
    monkeypatch.setattr(net, "download", download)
    path = catalog.fetch_product(ds.id, "p")
    assert path.is_file()
    assert urls[-1] == "https://pds-geosciences.wustl.edu/mex/mex-m-mrs-5-occ-v1/mexmrs_9124/DATA/DOY_126/LEVEL04/P.TAB"
    assert any("esac.esa.int" in u for u in urls[:-1])          # the primary was tried first


def test_fetch_skips_optional_docs_and_is_not_repeated(monkeypatch, tmp_path):
    """Opening a downloaded product used to retry its missing description texts on every
    open (MEX MaRS: ~20 s of requests to a slow server each time)."""
    from veda.archives import catalog, net
    monkeypatch.setattr(catalog, "PRODUCT_ROOT", tmp_path)
    ds = get_dataset("mex-m-mrs-5-occ")
    monkeypatch.setattr(catalog, "get_product", lambda d, p: {"volume": "MEX-M-MRS-5-OCC-9124-V1.0",
                                                              "path": "DATA/X/LEVEL04/T1.LBL"})
    calls = []
    label = 'PDS_VERSION_ID = PDS3\n^ATM_TABLE = "T1.TAB"\n^ATM_INFO = "T1.TXT"\n^INSTRUMENT_DESC = "MARS_DESC.TXT"\nEND\n'

    def download(url, dest, **kw):
        calls.append(url.rsplit("/", 1)[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(label if url.endswith(".LBL") else "1,2\n")
        return dest
    monkeypatch.setattr(net, "download", download)
    catalog.fetch_product(ds.id, "t1")
    assert calls == ["T1.LBL", "T1.TAB"]             # no description texts
    catalog.fetch_product(ds.id, "t1")
    assert calls == ["T1.LBL", "T1.TAB"]             # nothing asked for again
    p = catalog.local_label_path(ds.id, "MEX-M-MRS-5-OCC-9124-V1.0", "DATA/X/LEVEL04/T1.LBL")
    (p.parent / "T1.TAB").unlink()                   # part of the cache cleared
    catalog.fetch_product(ds.id, "t1")
    assert calls[-1] == "T1.TAB"


def test_kernel_sizes_unknown_when_offline_or_unanswered(monkeypatch):
    """Bug: the size check bypassed Settings > Network and cached failures as 0 bytes, so
    kernels of unknown size counted as within the automatic download limit."""
    from veda.archives import net
    from veda.config import SETTINGS
    calls = []

    class Resp:
        def __init__(self, n):
            self.headers = {"Content-Length": str(n)} if n else {}

        def raise_for_status(self):
            pass

    class Session:
        def head(self, url, **kw):
            calls.append(url)
            if "down" in url:
                raise net.requests.ConnectionError("no route")
            return Resp(2 * 1048576)
    monkeypatch.setattr(net, "session", lambda: Session())
    monkeypatch.setattr(kernels, "_size_cache", {})
    monkeypatch.setattr(SETTINGS, "network_enabled", False)
    assert kernels.remote_size("https://x/a.bsp") is None and not calls
    monkeypatch.setattr(SETTINGS, "network_enabled", True)
    assert kernels.remote_size("https://down/b.bsp") is None
    assert kernels.remote_size("https://down/b.bsp") is None and calls.count("https://down/b.bsp") == 2
    assert kernels.total_mb(["https://x/a.bsp", "https://down/b.bsp"]) is None
    assert kernels.total_mb(["https://x/a.bsp", "https://x/c.bsp"]) == 4.0
    kernels.remote_size("https://x/a.bsp")
    assert calls.count("https://x/a.bsp") == 1                         # known sizes are cached


def _flaky_server(data: bytes, cut_every: int, ranges: bool = True):
    """A local HTTP server that closes the connection after ``cut_every`` bytes of each
    answer; with ``ranges`` it answers Range requests (206) as archives that allow
    resuming do."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            start = 0
            rng = self.headers.get("Range")
            if rng and ranges:
                start = int(rng.split("=")[1].split("-")[0])
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
            else:
                self.send_response(200)
            self.send_header("Content-Length", str(len(data) - start))
            self.end_headers()
            self.wfile.write(data[start:start + cut_every])
            self.wfile.flush()
            self.close_connection = True

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_broken_downloads_are_continued_where_they_stopped(tmp_path, monkeypatch):
    from veda.archives import net
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    monkeypatch.setattr(net, "_session", None)            # an own session, closed below (its pooled sockets)
    data = bytes(range(256)) * 4000                       # 1 MB, cut every 300 kB
    srv = _flaky_server(data, 300_000)
    try:
        out = net.download(f"http://127.0.0.1:{srv.server_address[1]}/f.zip", tmp_path / "f.zip")
        assert out.read_bytes() == data
    finally:
        srv.shutdown()
        srv.server_close()
    srv = _flaky_server(data, 300_000, ranges=False)      # a server that cannot resume
    try:
        with pytest.raises(net.ArchiveError):
            net.download(f"http://127.0.0.1:{srv.server_address[1]}/g.zip", tmp_path / "g.zip")
        assert not (tmp_path / "g.zip").exists() and not list(tmp_path.glob("*.part*"))
    finally:
        srv.shutdown()
        srv.server_close()
        net.session().close()


def test_method_papers_for_the_derived_quantities_and_references():
    """The Cite panel names the papers behind the reference atmospheres, the CO2 frost
    point, Mars' gravity field and Titan's real gas when they were used; NASA technical
    memoranda are cited with their NTRS address."""
    from veda.citations import build
    out = build([], ["venus_reference", "mars_reference", "co2_frost_point", "mars_gravity", "titan_real_gas"])
    methods = next(f for f in out["features"] if f["title"] == "Methods")
    keys = [i["key"] for i in methods["items"]]
    assert keys == ["justh2021", "seiff1985", "justh2024", "james1992", "greve2010", "konopliv2016", "tsonopoulos1974", "gillis1996"]
    texts = {i["key"]: i["text"] for i in methods["items"]}
    assert texts["justh2021"].endswith("https://ntrs.nasa.gov/citations/20210022168")
    assert "https://doi.org/10.1016/j.icarus.2016.02.052" in texts["konopliv2016"]
    assert "@techreport{justh2024" in out["bibtex"] and "@incollection{james1992" in out["bibtex"]
    assert "url      = {https://ntrs.nasa.gov/citations/20240012934}" in out["bibtex"]


def test_dataset_citations_follow_their_registry_records():
    """Checked against DataCite and Crossref (2026-10): authors, year and title as registered."""
    from veda.citations import references
    refs = references()
    soir = refs["bira2020soir"]
    assert soir["authors"][0] == "Vandaele, A. C." and soir["year"] == 2017
    assert refs["kliore2014data"]["year"] == 2019 and refs["koskinen2018data"]["year"] == 2019
    assert refs["karatekin2020data"]["authors"] == ["Karatekin, O."]
    assert refs["holsteinrathlou2015data"]["authors"][0] == "Withers, P."
    assert refs["johnson1992"]["title"] == "Space science reviews volume on Galileo Mission overview"


def test_venus_potential_temperature_cites_its_cp_fit():
    from veda.citations import FEATURE_REFS, ref_text, references
    assert FEATURE_REFS["venus_potential_temperature"] == ["lebonnois2010"]
    assert "115(E6), E06006" in ref_text(references()["lebonnois2010"])


def test_profile_view_records_the_method_papers_of_what_it_shows():
    """Opening a profile lists the papers behind its derived quantities in Cite: before, only
    gravity, the real gas and the frost point were recorded there, not Venus' potential
    temperature, the giant planets' hydrogen cp or the gravity-wave energy."""
    from pathlib import Path
    from veda.citations import FEATURE_REFS
    js = (Path(__file__).resolve().parents[1] / "src" / "veda" / "frontend" / "js" / "veda_app.js").read_text(encoding="utf-8")
    assert "['co2_condensation_temperature', 'potential_temperature', 'buoyancy_freq_sq', 'wave_potential_energy']" in js
    for feature in ("venus_potential_temperature", "giant_planet_cp", "gravity_waves"):
        assert f"recordFeature('{feature}')" in js and FEATURE_REFS[feature]


def test_downloads_remove_parts_left_by_a_killed_process(tmp_path):
    """A download in a process that was killed leaves its .part file behind for good."""
    import os
    import time
    from veda.archives import net
    dest = tmp_path / "mar099s.bsp"
    stale = tmp_path / "mar099s.bsp.16800-22696.part"
    fresh = tmp_path / "mar099s.bsp.17000-1.part"
    other = tmp_path / "de440s.bsp.16800-22696.part"
    for f in (stale, fresh, other):
        f.write_bytes(b"x")
    old = time.time() - 2 * net.STALE_PART_S
    os.utime(stale, (old, old))
    os.utime(other, (old, old))
    net._part_path(dest)
    assert not stale.exists() and fresh.exists() and other.exists()     # only this file's old parts


def test_pds_search_refused_for_a_long_window_is_split(monkeypatch):
    """The PDS Registry answers HTTP 503 to a day of MRO CRISM or MAVEN IUVS products; six
    hours work.  The live search found nothing for those instruments."""
    import datetime as dt
    calls = []

    def window(q, t0, t1, limit):
        calls.append(t1 - t0)
        if t1 - t0 > dt.timedelta(hours=6):
            raise services.ServiceError("The archive search service did not answer (pds.nasa.gov refused the request (HTTP 503).)")
        return [{"product_id": t0.isoformat()}], 1
    monkeypatch.setattr(services, "_query_pds_window", window)
    rows, total = services.query_pds({}, dt.datetime(2012, 1, 1), dt.datetime(2012, 1, 2), 100)
    assert total == 4 and len(rows) == 4 and rows[0]["product_id"] == "2012-01-01T00:00:00"
    monkeypatch.setattr(services, "_query_pds_window",
                        lambda *a: (_ for _ in ()).throw(services.ServiceError("HTTP 500")))
    with pytest.raises(services.ServiceError):                # other errors are not split
        services.query_pds({}, dt.datetime(2012, 1, 1), dt.datetime(2012, 1, 2), 100)


def test_occultation_geometry_against_spice_with_real_kernels(monkeypatch):
    """With the generic kernels on this computer (else skipped): the sub-Earth point is
    where the planet-fixed direction to Earth points (it was taken two light times back,
    3.9 deg of longitude off on Mars in April 2004), and tangent altitudes are above the
    body's reference radius.  Phobos stands in for the spacecraft."""
    import os
    from pathlib import Path
    import numpy as np
    import spiceypy as sp
    from veda.geometry import compute
    src = Path(os.environ.get("LOCALAPPDATA", "")) / "VEDA" / "cache" / "spice"
    names = ("naif0012.tls", "pck00011.tpc", "de440s.bsp", "mar099s.bsp")
    if not all((src / n).is_file() for n in names):
        pytest.skip("generic SPICE kernels not on this computer")
    monkeypatch.setattr(kernels, "KERNEL_DIR", src)
    plan = kernels.KernelPlan(urls=[f"https://x/{n}" for n in names])
    compute._furnsh(plan)
    mid = sp.str2et("2004-04-02T11:44:14")
    g = compute.observation_geometry(plan, 401, "mars", np.array([mid - 30.0, mid, mid + 30.0]))
    pl, lt = sp.spkpos("499", mid, "J2000", "CN", "399")
    _, lon, lat = sp.reclat(sp.pxform("J2000", "IAU_MARS", mid - lt) @ (-pl))
    assert g["subearth"]["lon"] == pytest.approx(np.degrees(lon) % 360, abs=0.01)
    assert g["subearth"]["lat"] == pytest.approx(np.degrees(lat), abs=0.01)
    assert g["reference_radius_km"] == 3389.5


def test_galileo_probe_track_from_its_own_spk(monkeypatch):
    """The Galileo probe's own SPK (NAIF -344, s960730a.bsp) puts it at 6.53 N, 4.94 W at
    the data set's entry time 22:04:44; the mission catalogue (gp_0001 MISSION.CAT) gives
    the entry point as 6.54 N, 4.46 W (0.5 deg apart: about 12 s along the 47 km/s entry
    track).  The kernel ends at 22:05:59, before the descent.  Skipped without the kernels."""
    import os
    from pathlib import Path
    from veda.archives.datasets import get_dataset
    from veda.geometry import compute
    src = Path(os.environ.get("LOCALAPPDATA", "")) / "VEDA" / "cache" / "spice"
    ds = get_dataset("gp-j-entry-v1.0")
    names = ("naif0012.tls", "pck00011.tpc", "de440s.bsp", ds.probe_spk[1].rsplit("/", 1)[1])
    if not all((src / n).is_file() for n in names):
        pytest.skip("SPICE kernels not on this computer")
    monkeypatch.setattr(kernels, "KERNEL_DIR", src)
    plan = kernels.KernelPlan(urls=[f"https://x/{n}" for n in names])
    t = compute.probe_track(plan, ds.probe_spk[0], "jupiter", ds.fixed_time)
    i = min(range(len(t["utc"])), key=lambda k: abs(dt.datetime.fromisoformat(t["utc"][k]) -
                                                     dt.datetime(1995, 12, 7, 22, 4, 44)))
    assert t["lat"][i] == pytest.approx(6.54, abs=0.05)
    assert (360.0 - t["lon"][i]) == pytest.approx(4.46, abs=0.6)
    assert t["utc"][-1] <= "1995-12-07T22:05:59"
