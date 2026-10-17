"""MAVEN NGIMS density profiles (PDS4 bundle ngims_bundle): pass legs, periapsis time,
species on one time grid and density values on an archive file (periapsis pass 108, Oct 2014),
copied unchanged from the PDS Atmospheres Node (l2/2014/10)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from veda.archives import catalog
from veda.archives.datasets import get_dataset
from veda.archives.profiles import profile_from_label

DATA = Path(__file__).parent / "data" / "maven_ngims"
XML = DATA / "mvn_ngi_l2_csn-abund-14015_20141018T100458_v08_r01.xml"
DS = get_dataset("maven-ngims-l2")


def _leg(leg: str):
    prod = {
        "product_id": XML.stem + ("_IN" if leg == "inbound" else "_OUT"),
        "volume": "ngims_bundle",
        "start_time": DS.time_from_filename(XML.name),
        "leg": leg,
        "url": DS.base_url + "ngims_bundle/l2/2014/10/" + XML.name,
        "product_type": f"Neutral gas density profile along the periapsis pass, {leg} leg",
    }
    return profile_from_label(DS, prod, XML)


def test_ngims_bundle_indexing_walks_folders_and_splits_passes(monkeypatch):
    root = DS.base_url + "ngims_bundle/"
    tree = {
        root + "l2/": ["2014"],
        root + "l2/2014/": ["10"],
        root + "l2/2014/10/": [XML.name, XML.name[:-4] + ".csv", "collection_ngims_l2.xml"],
    }
    monkeypatch.setattr(
        catalog.http,
        "list_directory",
        lambda url, pattern=None, dirs_only=False, login_url=None: list(
            tree.get(url if url.endswith("/") else url + "/", [])
        ),
    )
    rows = catalog.index_pds4(DS, "ngims_bundle")
    assert [r["product_id"] for r in rows] == [XML.stem + "_IN", XML.stem + "_OUT"]
    assert rows[0]["path"] == "l2/2014/10/" + XML.name
    assert rows[0]["start_time"] == "2014-10-18T10:04:58"
    assert rows[0]["kind"] == "profile"
    assert json.loads(rows[0]["extra"])["LEG"] == "inbound"
    assert json.loads(rows[1]["extra"])["LEG"] == "outbound"


def test_ngims_legs_split_at_periapsis():
    inb, outb = _leg("inbound"), _leg("outbound")
    # Both legs take the periapsis time (11:38:54 UTC)
    assert inb.time_utc == "2014-10-18T11:38:54"
    assert outb.time_utc == inb.time_utc
    assert np.all(np.diff(inb.altitude_km) <= 0) and np.all(np.diff(outb.altitude_km) >= 0)
    assert inb.altitude_km[-1] == pytest.approx(184.9852, abs=1e-3)
    assert outb.altitude_km[0] == pytest.approx(184.985, abs=1e-3)
    # CO2 (the main species), particles/cc -> m^-3; PRECISION is a percent error
    n = np.asarray(inb.derived["number_density_m3"])
    assert np.nanmax(n) == pytest.approx(6.88e15, rel=0.01)
    k = int(np.nanargmax(n))
    assert inb.uncertainty["number_density_m3"][k] < 0.05 * n[k]
    # every outbound CO2 and N2 sample of this pass is flagged UR, "unreliable, data not
    # useable for science" (NGIMS SIS 8.3.10): not used; Ar and He outbound are kept
    assert "number_density_m3" not in outb.derived or np.isnan(outb.derived["number_density_m3"]).all()
    assert np.isnan(outb.derived.get("n_n2_m3", np.array([np.nan]))).all()
    assert outb.derived["n_ar_m3"][0] == pytest.approx(1.85e14, rel=0.01)
    assert np.nanmax(inb.derived["n_n2_m3"]) > 1e14
    assert outb.track["latitude"][0] == pytest.approx(42.28, abs=0.05)
    assert outb.track["longitude"][0] == pytest.approx(-153.84, abs=0.05)


def test_ngims_co2_scale_height_as_the_teams_level_3_fit():
    """The team's Level-3 product for the same pass (mvn_ngi_l3_res-sht-14015, orbit 108):
    CO2 scale height 11.43 +- 1.40 km from a fit of ln(density) against altitude, and
    201 +- 25 K.  The usable inbound CO2 levels (185-285 km) of the Level-2 file give the
    same within its error; VEDA's hydrostatic temperature from them, the same."""
    inb = _leg("inbound")
    z, n = np.asarray(inb.altitude_km), np.asarray(inb.derived["number_density_m3"])
    ok = np.isfinite(n) & (n > 0)
    h = -1.0 / np.polyfit(z[ok], np.log(n[ok]), 1)[0]
    assert h == pytest.approx(11.43, abs=1.40) and h == pytest.approx(11.64, abs=0.05)
    t = np.asarray(inb.derived["temperature_from_density"])
    assert np.nanmedian(t[ok]) == pytest.approx(201, abs=25)


def test_ion_files_are_not_neutral_profiles():
    assert DS.classify("mvn_ngi_l2_ion-abund-14015_20141018T100458_v08_r01.xml")[1] == "other"
