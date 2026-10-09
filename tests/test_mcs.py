"""MRO Mars Climate Sounder profiles from the DDR files (archives/mcs.py).

The fixture is two rows (100 and 286) of the real file 2006120120_DDR (MROM_2004,
NASA PDS Atmospheres Node) with its label and format files, stored byte for byte."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

DATA = Path(__file__).parent / "data" / "mcs"
DS = "mro-m-mcs-5-ddr-v1.0"
FILE = {"dataset_id": DS, "product_id": "2006120120_DDR", "volume": "MROM_2004",
        "path": "DATA/2006/200612/20061201/2006120120_DDR.LBL", "start_time": "2006-12-01T20:00:24.914",
        "stop_time": "2006-12-01T23:58:33.742", "target": "MARS",
        "product_type": "MCS DDR file (about 300 profiles of T, P, dust and ice)", "kind": "table", "extra": "{}"}


@pytest.fixture()
def ddr_file():
    """The fixture file in the catalogue and in the download cache, as if downloaded."""
    from veda.archives import catalog
    label = catalog.local_label_path(DS, FILE["volume"], FILE["path"])
    label.parent.mkdir(parents=True, exist_ok=True)
    names = ["2006120120_DDR.LBL", "2006120120_DDR.TAB", "MCS_DDR1.FMT", "MCS_DDR2.FMT"]
    for n in names:
        shutil.copyfile(DATA / n, label.parent / n)
    label.with_name(label.name + ".complete").write_text("\n".join(names), encoding="utf-8")
    with catalog._db_lock, catalog._connect() as conn:
        conn.execute("INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                     ":start_time,:stop_time,:target,:product_type,:kind,:extra)", FILE)
    yield label
    with catalog._db_lock, catalog._connect() as conn:
        conn.execute("DELETE FROM products WHERE dataset_id=? AND product_id=?", (DS, FILE["product_id"]))


def test_each_row_of_a_ddr_file_is_a_profile(ddr_file):
    """Row 0 of the fixture (row 100 of the file): its level 13 in the file reads
    369.98 Pa, 215.304 +- 0.699 K, 1.052 km above the surface point, whose radius is
    3395.783 km; time, latitude, local time (0.148102 sol) and Ls from the header."""
    from veda.archives.catalog import get_product
    from veda.archives.profiles import load_profile
    prod = get_product(DS, "2006120120_DDR_P000")
    assert prod["kind"] == "profile" and prod["row"] == 0 and prod["file_product_id"] == "2006120120_DDR"
    assert get_product(DS, "2006120120_DDR_P0x1") is None
    p = load_profile(DS, "2006120120_DDR_P000")
    assert p.time_utc == "2006-12-01T21:20:02.883"
    assert p.latitude == pytest.approx(24.83611) and p.longitude == pytest.approx(-103.38962)
    assert p.raw_attributes["LST"] == pytest.approx(0.148102 * 24) and p.raw_attributes["LS"] == pytest.approx(143.88314)
    k = int(np.nanargmin(np.abs(p.pressure_hpa - 3.6998)))
    assert p.temperature_k[k] == pytest.approx(215.304) and p.uncertainty["temperature_k"][k] == pytest.approx(0.699)
    assert p.altitude_km[k] == pytest.approx(3395.783 + 1.052 - 3389.5, abs=1e-6)
    assert p.track["latitude"][k] == pytest.approx(23.687)
    assert k == 0 and np.isfinite(p.temperature_k).all()   # the levels at -9999 below the retrieval are left out
    # MCS altitudes are hydrostatic with GM/r^2: VEDA checks them with the same gravity
    assert p.raw_attributes["hydrostatic_max_pct"] < 0.15
    # dust and water-ice opacity per km with their 1-sigma: level 40 of the row reads
    # 3.5561e-06 +- 1.0834e-06 (dust) and 3.3927e-03 +- 7.1677e-05 (water ice)
    k40 = int(np.nanargmin(np.abs(p.pressure_hpa - 0.1266)))
    assert p.derived["dust_opacity_per_km"][k40] == pytest.approx(3.5561e-06)
    assert p.uncertainty["dust_opacity_per_km"][k40] == pytest.approx(1.0834e-06)
    assert p.derived["ice_opacity_per_km"][k40] == pytest.approx(3.3927e-03)
    assert p.uncertainty["ice_opacity_per_km"][k40] == pytest.approx(7.1677e-05)
    other = load_profile(DS, "2006120120_DDR_P001")
    assert other.latitude == pytest.approx(-28.76247)
    with pytest.raises(ValueError):
        load_profile(DS, "2006120120_DDR_P005")             # the fixture has two rows


def test_comparisons_take_mcs_profiles_from_the_files(ddr_file):
    """A filtered comparison reads the files of many profiles in the date range and keeps
    the rows whose geometry passes; the report counts the file."""
    from veda.missions.manager import get_mission_manager
    from veda.missions.selection import ProfileFilter
    f = ProfileFilter(start="2006-12-01", end="2006-12-02", per_mission=5, download=False, datasets=[DS],
                      lat_min=0, lat_max=60)
    comp = get_mission_manager().compare_on_body("mars", None, mission_ids=["mro"], variable_name="temperature_k",
                                                 selection=f, altitude_step_km=1.0)
    assert [p["observation_id"] for p in comp["profiles"]] == ["2006120120_DDR_P000"]       # 24.8 N, not 28.8 S
    r = comp["selection"]["mro"]
    assert r["kept"] == 1 and r["files_of_many_profiles"] == 1
    from veda.archives.datasets import get_dataset
    assert get_dataset(DS).to_dict()["has_profiles"] is True
    assert json.dumps(comp)                                   # serialisable for the window
    from veda.missions.selection import provides
    ds = get_dataset(DS)
    assert provides(ds, "temperature_k") and provides(ds, "dust_opacity_per_km") and not provides(ds, "dust_mixing_ratio")
    dust = get_mission_manager().compare_on_body("mars", [{"mission_id": "mro", "observation_id": "2006120120_DDR_P000"}],
                                                 variable_name="dust_opacity_per_km", altitude_step_km=1.0)
    assert dust["profile_count"] == 1 and any(v for v in dust["profiles"][0]["interpolated_series"] if v)
