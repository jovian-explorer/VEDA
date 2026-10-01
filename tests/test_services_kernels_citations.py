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
        c = sqlite3.connect(db)
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
