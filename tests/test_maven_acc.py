"""MAVEN accelerometer density profiles (PDS4 bundle maven_acc): pass legs, times, the
spheroid altitudes and the noise beyond each leg's usable part, on an archive file
(periapsis 3302, a deep dip of June 2016)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from veda.archives import catalog
from veda.archives.datasets import get_dataset
from veda.archives.profiles import profile_from_label
from veda.readers.pds4_reader import read_pds4_table

DATA = Path(__file__).parent / "data" / "maven_acc"
XML = DATA / "mvn_acc_l3_pro-acc-p03302_20160610_v02_r01.xml"
DS = get_dataset("maven-acc-profile")


def _leg(leg):
    prod = {"product_id": XML.stem + ("_IN" if leg == "inbound" else "_OUT"), "volume": "acc_bundle",
            "start_time": DS.time_from_filename(XML.name), "leg": leg,
            "url": DS.base_url + "acc_bundle/l3/2016/06/" + XML.name,
            "product_type": f"Density profile along the periapsis pass, {leg} leg"}
    return profile_from_label(DS, prod, XML)


def test_listing_walks_year_and_month_folders_and_splits_the_passes(monkeypatch):
    root = DS.base_url + "acc_bundle/"
    tree = {root + "l3/": ["2016", "2019"], root + "l3/2016/": ["06"], root + "l3/2019/": ["02"],
            root + "l3/2016/06/": [XML.name, XML.name[:-4] + ".tab", "collection_x.xml"],
            root + "l3/2019/02/": ["mvn_acc_l3_pro-acc-p08569_20190218_v02_r01.xml"]}
    monkeypatch.setattr(catalog.http, "list_directory", lambda url, pattern=None, dirs_only=False, login_url=None:
                        list(tree.get(url if url.endswith("/") else url + "/", [])))
    rows = catalog.index_pds4(DS, "acc_bundle")
    assert [r["product_id"] for r in rows] == [XML.stem + "_IN", XML.stem + "_OUT",
                                               "mvn_acc_l3_pro-acc-p08569_20190218_v02_r01_IN",
                                               "mvn_acc_l3_pro-acc-p08569_20190218_v02_r01_OUT"]
    assert rows[0]["path"] == "l3/2016/06/" + XML.name and rows[0]["start_time"] == "2016-06-10T00:00:00"
    assert rows[0]["kind"] == "profile" and json.loads(rows[1]["extra"])["LEG"] == "outbound"


def test_legs_take_the_periapsis_time_and_go_on_the_mars_sphere():
    inb, out = _leg("inbound"), _leg("outbound")
    # the label's start time (08:36:23) plus the 300 s before periapsis; the catalogue has the date only
    assert inb.time_utc.startswith("2016-06-10T08:41:23") and out.time_utc == inb.time_utc
    assert inb.altitude_km.size == 300 and out.altitude_km.size == 301
    # periapsis (the outbound leg's first level): 118.385 km above the spheroid at 34.581 deg
    # areodetic latitude is a radius of 3508.198 km and 34.276 deg planetocentric
    assert out.altitude_km[0] == pytest.approx(118.698, abs=1e-3)
    assert out.track["latitude"][0] == pytest.approx(34.276, abs=1e-3)
    assert out.track["lst"][0] == pytest.approx(5.33, abs=0.01)          # the file's true local solar time
    rho = out.derived["density_measured"]
    assert rho[0] == pytest.approx(5.065e-9) and out.uncertainty["density_measured"][0] == pytest.approx(4.9e-11)


def test_each_leg_ends_where_the_density_falls_below_twice_its_sigma():
    """The files run to 300 s from periapsis (200 km), where the 1-s density is noise about
    zero; going out from periapsis each leg stops at the first level below 2 sigma."""
    raw = read_pds4_table(str(XML)).columns
    t, d, s = raw["Seconds from Periapsis"], raw["1-SEC DENSITY"], raw["SIGMA 1-SEC DENSITY"]
    for leg, mask in (("inbound", t < 0), ("outbound", t >= 0)):
        p = _leg(leg)
        order = np.argsort(np.abs(t[mask]), kind="stable")
        weak = d[mask][order] < 2 * s[mask][order]
        kept = int(np.argmax(weak))
        rho = p.derived["density_measured"]
        assert np.isfinite(rho).sum() == kept and np.isfinite(rho[order[:kept]]).all()
        assert np.isfinite(p.uncertainty["density_measured"]).sum() == kept
        assert 140.0 < np.nanmax(np.where(np.isfinite(rho), p.altitude_km, np.nan)) < 165.0
        # a deep dip: the density falls by e^5 over the leg, enough for a temperature from it
        assert np.isfinite(p.derived["temperature_from_density"]).sum() > 100


def test_data_set_is_cited_and_listed_for_maven():
    from veda.citations import build, ref_text, references
    from veda.core.registry import get_mission
    assert DS.mission_id == "maven" and "mars" in DS.body_ids and DS.to_dict()["has_profiles"]
    assert DS.refs == ("zurek2015", "tolson2016data")
    refs = references()
    assert ref_text(refs["zurek2015"]).endswith("https://doi.org/10.1007/s11214-014-0095-x")
    assert ref_text(refs["tolson2016data"]).endswith("https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/MAVEN/acc_bundle/")
    assert [p["key"] for p in build([DS.id], [])["data"][0]["papers"]] == ["zurek2015", "tolson2016data"]
    assert "ACC" in [i.id for i in get_mission("maven").instruments]
