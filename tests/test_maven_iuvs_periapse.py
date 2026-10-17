"""MAVEN IUVS periapse limb scans: one file, up to 12 profiles (archives/row_files.py),
against Evans et al. (2015).  The fixture is the real file of orbit 109 (18 October 2014)."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

DATA = Path(__file__).parent / "data" / "maven_iuvs"
DS = "maven-iuvs-periapse"
NAME = "mvn_iuv_l2_periapse-orbit00109_20141018T160558"
FILE = {"dataset_id": DS, "product_id": NAME, "volume": "iuvs_derived_bundle",
        "path": f"l2/limb/2014/10/{NAME}.xml", "start_time": "2014-10-18T16:05:58", "stop_time": "",
        "target": "MARS", "product_type": "IUVS periapse file", "kind": "table", "extra": "{}"}


@pytest.fixture()
def periapse_file():
    from veda.archives import catalog
    label = catalog.local_label_path(DS, FILE["volume"], FILE["path"])
    label.parent.mkdir(parents=True, exist_ok=True)
    names = [NAME + ".xml", NAME + "_v13_r01.fits"]
    for n in names:
        shutil.copyfile(DATA / n, label.parent / n)
    label.with_name(label.name + ".complete").write_text("\n".join(names), encoding="utf-8")
    with catalog._db_lock, catalog._connect() as conn:
        conn.execute("INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                     ":start_time,:stop_time,:target,:product_type,:kind,:extra)", FILE)
    yield label
    with catalog._db_lock, catalog._connect() as conn:
        conn.execute("DELETE FROM products WHERE dataset_id=? AND product_id=?", (DS, NAME))


def test_each_limb_scan_is_a_profile_as_published(periapse_file):
    """Evans et al. 2015 (GRL 42, 9040), the tenth scan of orbit 109: SZA 42.5 deg, 12 N,
    131 E, local time 14.2 h; CO2 at 170 km between 1 and 2.3e9 cm^-3 (their Figure 2a)."""
    from veda.archives.catalog import get_product
    from veda.archives.profiles import load_profile
    from veda.readers.iuvs_reader import read_file, valid_rows
    assert len(valid_rows(read_file(periapse_file))) == 11          # scan 5 was not retrieved
    prod = get_product(DS, NAME + "_P009")
    assert prod["kind"] == "profile" and prod["row"] == 9
    p = load_profile(DS, NAME + "_P009")
    assert p.raw_attributes["SZA"] == pytest.approx(42.46, abs=0.01)
    assert p.raw_attributes["LST"] == pytest.approx(14.20, abs=0.01)
    assert p.longitude == pytest.approx(129.07, abs=0.01)
    assert p.latitude == pytest.approx(12.26, abs=0.01)             # planetocentric (12.39 geodetic)
    # the archive's altitudes are above the ellipsoid; the 170.15 km level is at 175.93 km on VEDA's sphere here
    z = np.asarray(p.altitude_km)
    k = int(np.nanargmin(np.abs(z - 175.929)))
    assert p.derived["n_co2_m3"][k] == pytest.approx(1.6514e15, rel=1e-4)
    assert 1e15 < p.derived["n_co2_m3"][k] < 2.3e15
    assert p.temperature_k[k] == pytest.approx(313.29, abs=0.01)
    # N2 and O on their own altitudes; between their levels interpolated, never beyond
    n2 = np.asarray(p.derived["n_n2_m3"])
    assert np.isfinite(n2).sum() > 3 and z.size == 11 and np.isnan(n2[z < 129]).all()
    assert np.isfinite(p.derived["n_o_m3"]).sum() > 3
    assert np.isfinite(p.derived["temperature_from_density"]).any()
    with pytest.raises(ValueError):
        load_profile(DS, NAME + "_P005")
