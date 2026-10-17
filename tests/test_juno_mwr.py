"""Juno MWR ammonia and water by latitude (JNOMWR_2100): one profile per latitude column,
on pressure levels only, against Li et al. (2020).  The fixture is the archive's four
files (abundance and 1-sigma of NH3 and H2O), unchanged."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

DATA = Path(__file__).parent / "data" / "juno_mwr"
DS = "jno-mwr-nh3-h2o"
STEM = "MWR{s}{k}2016240070004_R00548_V01"


def _row(s):
    pid = STEM.format(s=s, k="A")
    return {"dataset_id": DS, "product_id": pid, "volume": "JNOMWR_2100",
            "path": f"DATA/{s}-DISTRIBUTION/{pid}.LBL", "start_time": "2016-08-27T07:00:04.844",
            "stop_time": "2018-04-01T13:59:59.299", "target": "JUPITER", "product_type": f"MWR {s}",
            "kind": "table", "extra": "{}"}


@pytest.fixture()
def mwr_files():
    from veda.archives import catalog
    rows = [_row("NH3"), _row("H2O")]
    for r, s in zip(rows, ("NH3", "H2O")):
        label = catalog.local_label_path(DS, r["volume"], r["path"])
        label.parent.mkdir(parents=True, exist_ok=True)
        names = []
        for k in ("A", "U"):
            for ext in (".LBL", ".CSV"):
                n = STEM.format(s=s, k=k) + ext
                shutil.copyfile(DATA / n, label.parent / n)
                names.append(n)
        label.with_name(label.name + ".complete").write_text("\n".join(names[:2]), encoding="utf-8")
        with catalog._db_lock, catalog._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                         ":start_time,:stop_time,:target,:product_type,:kind,:extra)", r)
    yield rows
    with catalog._db_lock, catalog._connect() as conn:
        conn.execute("DELETE FROM products WHERE dataset_id=?", (DS,))


def test_equatorial_ammonia_and_water_as_published(mwr_files):
    """Li et al. 2020 (Nature Astronomy 4, 609), equatorial zone (0-4 N): ammonia 351 +- 22
    ppm and water 2.5 (+2.2 -1.6) x 10^3 ppm in the deep atmosphere.  The archive's columns
    at 1.5 N and 3.9 N, at 100 bar: 353 +- 33 ppm and 2556 +- 2272 ppm."""
    from veda.archives.profiles import load_profile
    nh3 = load_profile(DS, STEM.format(s="NH3", k="A") + "_P019")
    assert nh3.latitude == pytest.approx(1.5) and nh3.longitude is None
    assert np.isnan(nh3.altitude_km).all()                       # pressure levels only
    p = np.asarray(nh3.pressure_hpa)
    k = int(np.argmin(np.abs(p - 100e3)))
    assert nh3.derived["nh3_ppm"][k] == pytest.approx(353.2, abs=0.1)
    assert nh3.derived["nh3_ppm"][k] == pytest.approx(351, abs=22)
    assert nh3.uncertainty["nh3_ppm"][k] == pytest.approx(33.0, abs=0.1)
    h2o = load_profile(DS, STEM.format(s="H2O", k="A") + "_P020")
    assert h2o.latitude == pytest.approx(3.9)
    assert h2o.derived["h2o_ppm"][k] == pytest.approx(2556.2, abs=0.1)
    assert h2o.uncertainty["h2o_ppm"][k] == pytest.approx(2272.2, abs=0.1)
    with pytest.raises(ValueError):                              # no water retrieved at 0.9 S
        load_profile(DS, STEM.format(s="H2O", k="A") + "_P018")


def test_pressure_only_profiles_compare_on_pressure(mwr_files):
    from veda.missions.manager import get_mission_manager
    from veda.missions.selection import ProfileFilter
    f = ProfileFilter(start="2016-01-01", end="2019-01-01", per_mission=10, download=False, datasets=[DS],
                      lat_min=-5, lat_max=5)
    m = get_mission_manager()
    comp = m.compare_on_body("jupiter", None, mission_ids=["juno"], variable_name="nh3_ppm", selection=f,
                             vertical="pressure")
    assert comp["profile_count"] == 4 and comp["selection"]["juno"]["files_of_many_profiles"] == 2
    by_alt = m.compare_on_body("jupiter", None, mission_ids=["juno"], variable_name="nh3_ppm", selection=f)
    assert by_alt["profile_count"] == 0 and "pressure levels only" in by_alt["error"]
