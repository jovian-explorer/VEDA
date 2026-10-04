"""Profiles from research data repositories (Zenodo, BIRA-IASB): Venus Express VeRa and SOIR."""
from __future__ import annotations

import io
import zipfile

import numpy as np
import pytest

from veda.archives import repositories as repo
from veda.archives.datasets import get_dataset


def test_normalised_csv_round_trip(tmp_path):
    p = repo.write_normalised(tmp_path / "x.csv", {"START_TIME": "2014-02-17T03:47:57", "LATITUDE": 84.5},
                              [("RADIUS", "km"), ("TEMPERATURE", "K")], [(6100.0, 250.0), (6110.0, float("nan"))])
    t = repo.read_normalised(p)
    assert t.metadata == {"START_TIME": "2014-02-17T03:47:57", "LATITUDE": 84.5}
    assert t.units == {"RADIUS": "km", "TEMPERATURE": "K"}
    np.testing.assert_allclose(t.columns["RADIUS"], [6100.0, 6110.0])
    assert np.isnan(t.columns["TEMPERATURE"][1])


def test_constant_number_density_padding_is_masked():
    """FSI files hold n constant below the lowest valid level; T computed there is nonsense."""
    n = np.array([2.4e25] * 6 + [2.1e25, 1.2e25, 6.4e24])
    cols = {"NUMBER_DENSITY": n.copy(), "TEMPERATURE": np.array([797.0, 700, 600, 520, 450, 400, 349.5, 301.9, 251.0])}
    repo._mask_constant_runs(cols, "NUMBER_DENSITY", ["TEMPERATURE"])
    assert np.isnan(cols["TEMPERATURE"][:6]).all() and cols["TEMPERATURE"][6] == 349.5


@pytest.mark.parametrize("text,iso", [
    ("17-Feb-2014 03:47:57.625000 (UTC)", "2014-02-17T03:47:57.625"),
    ("2453867.562916917", "2006-05-12T01:30:36.021"),
    ("2010-12-14T02:01:11", "2010-12-14T02:01:11.000"),
    ("not a time", ""),
])
def test_time_parsing(text, iso):
    assert repo._parse_time(text) == iso


def test_zip_of_profiles_with_header_lines(tmp_path, monkeypatch):
    ds = get_dataset("vex-vera-gramigna2023")
    rows = ["ID\tutc_table\tVar3\tVar4\tVar5\tVar6\tVar7\tVar8\tVar9\tVar10\tVar11\ttime_table",
            "1\t17-Feb-2014 03:47:57.625000 (UTC)\t4.4588e+08\t6148.78\t84.47\t37.56\t4.6e-06\t6.9\t170.0\t2.94e+21\t95.59\t03:40:21",
            "2\t17-Feb-2014 03:47:57.875000 (UTC)\t4.4588e+08\t6111.80\t84.40\t37.60\t1.0e-03\t22000.0\t250.0\t6.4e+24\t95.60\t03:40:19"]
    zf = tmp_path / "g.zip"
    with zipfile.ZipFile(zf, "w") as z:
        z.writestr("d/VEX_RO_2014_DOY048_INGRESS.txt.txt", "\n".join(rows))
        z.writestr("d/readme.lbl.txt", "not a profile")
    monkeypatch.setattr(repo, "_zip_path", lambda ds, progress=None: zf)
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    idx = repo.index_repository(ds)
    assert [r["product_id"] for r in idx] == ["VEX_RO_2014_DOY048_INGRESS"]
    assert idx[0]["start_time"].startswith("2014-02-17T03:47:57") and idx[0]["kind"] == "profile"
    csv = repo.fetch_repository_product(ds, {**idx[0], "extra": {}})
    t = repo.read_normalised(csv)
    assert t.columns["TEMPERATURE"].tolist() == [170.0, 250.0]           # header line skipped
    assert t.columns["LOCAL_SOLAR_TIME"][0] == pytest.approx(3 + 40 / 60 + 21 / 3600)


def test_votable_split_into_profiles(tmp_path, monkeypatch):
    ds = get_dataset("vex-soir-co2-temperature")
    fields = ["orbit", "case", "longitude_min", "longitude_max", "latitude_min", "latitude_max", "solar_longitude_min",
              "solar_longitude_max", "local_time_min", "local_time_max", "time_JDUTC_min", "time_JDUTC_max", "altitude",
              "pressure", "err_pressure", "temperature", "err_temperature", "total_density", "err_total_density"]
    def tr(orbit, case, alt, t):
        vals = [orbit, case, 280, 300, 85, 87, 65, 65.1, 2.75, 3.96, 2453867.5629, 2453867.5684, alt, 0.1, 0.01, t, 5.0, 1e15, 1e14]
        return "<TR>" + "".join(f"<TD>{v}</TD>" for v in vals) + "</TR>"
    xml = ('<?xml version="1.0"?><VOTABLE xmlns="http://www.ivoa.net/xml/VOTable/v1.2"><RESOURCE><TABLE>'
           + "".join(f'<FIELD name="{f}" datatype="double" unit="u"/>' for f in fields)
           + "<DATA><TABLEDATA>" + tr(21, 1, 90, 170) + tr(21, 1, 100, 165) + tr(39, 2, 95, 180) + "</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>")
    zf = tmp_path / "co2.zip"
    with zipfile.ZipFile(zf, "w") as z:
        z.writestr("SOIRProfiles_CO2_0.xml", xml)
    monkeypatch.setattr(repo, "_zip_path", lambda ds, progress=None: zf)
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    idx = repo.index_repository(ds)
    assert sorted(r["product_id"] for r in idx) == ["soir_co2_orbit0021_1", "soir_co2_orbit0039_2"]
    t = repo.read_normalised(tmp_path / "soir_co2_orbit0021_1.csv")
    assert t.columns["temperature"].tolist() == [170.0, 165.0]
    assert t.metadata["LATITUDE"] == 86.0 and t.metadata["START_TIME"].startswith("2006-05-12T01:30")


def test_crism_limb_aerosol_tables_split_into_dated_profiles(tmp_path, monkeypatch):
    """CRISM limb aerosol profiles (PDS Atmospheres, mro-crism_atmos-db): one table, rows of
    real profiles copied from the archive files.  A profile is dated from its Mars year and
    Ls (the labels' start dates, 2009-07-11 and 2010-12-06, are those of the first rows),
    longitudes are given positive west, and -999 is missing."""
    smith = ("29 , 301 ,   -86.98 ,   222.00 ,     0.20 ,   0.032646 ,   0.011556 ,     2.43\n"
             "29 , 301 ,   -86.98 ,   222.00 ,     0.40 ,   0.056285 ,   0.011920 ,     4.83\n"
             "31 , 102 ,    86.37 ,   218.54 ,     5.80 ,   0.001000 ,   0.006376 ,    51.86\n")
    guz = ("Mars Year,Solar Longitude,Latitude,West Longitude,Height (km),Ice Mixing Ratio,Ice Effective Radius,"
           "Ice Effective Radius Error,Dust Mixing Ratio,Dust Effective Radius,Dust Effective Radius Error,Observation\n"
           "30,193.456,25.8266,300.0559,13.133411,-999,-999,-999,0.346091,0.986737,0.219891,LMB00002BE1_05\n"
           "30,193.456,25.8266,300.0559,15.18378,-999,-999,-999,0.294713,0.992004,0.22155,LMB00002BE1_05\n"
           "30,318.954,20.4294,298.7216,13.330383,0.017372,-999,-999,0.292013,1.019826,0.220488,LMB00002C02_07\n")
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    s = get_dataset("mro-crism-smith2013-aerosol")
    (tmp_path / s.repository["url"].rsplit("/", 1)[-1]).write_text(smith, encoding="utf-8")
    idx = {r["product_id"]: r for r in repo.index_repository(s)}
    assert sorted(idx) == ["crism_smith2013_29_301_m86p98_222p00", "crism_smith2013_31_102_86p37_218p54"]
    first = idx["crism_smith2013_29_301_m86p98_222p00"]
    assert first["start_time"] == "2009-07-10" and first["kind"] == "profile"   # Ls 301 of MY 29, date only
    assert idx["crism_smith2013_31_102_86p37_218p54"]["start_time"] == "2012-04-26"   # the label's stop date
    t = repo.read_normalised(repo.fetch_repository_product(s, {**first, "extra": {}}))
    assert t.metadata["LONGITUDE"] == pytest.approx(138.0) and t.metadata["LS"] == 301.0
    assert t.columns["HEIGHT_KM"].tolist() == [2.43, 4.83] and t.columns["DUST_MIXING_RATIO"][0] == 0.032646

    g = get_dataset("mro-crism-guzewich-aerosol")
    (tmp_path / g.repository["url"].rsplit("/", 1)[-1]).write_text(guz, encoding="utf-8")
    idx = {r["product_id"]: r for r in repo.index_repository(g)}
    assert sorted(idx) == ["crism_guzewich_LMB00002BE1_05", "crism_guzewich_LMB00002C02_07"]
    assert idx["crism_guzewich_LMB00002BE1_05"]["start_time"] == "2010-12-06"
    t = repo.read_normalised(repo.fetch_repository_product(g, {**idx["crism_guzewich_LMB00002BE1_05"], "extra": {}}))
    assert np.isnan(t.columns["ICE_MIXING_RATIO"]).all()                      # -999
    assert t.columns["DUST_EFFECTIVE_RADIUS"].tolist() == [0.986737, 0.992004]
    assert t.metadata["OBSERVATION_NAME"] == "LMB00002BE1_05" and t.metadata["LONGITUDE"] == pytest.approx(59.9441)


def test_mars_time_from_ls_inverts_the_computed_season():
    from veda.analysis.solar_geometry import mars_time_from_ls, subsolar_point
    assert mars_time_from_ls(34, 0.0).startswith("2017-05-05")       # Mars year 34 began 2017-05-05
    assert mars_time_from_ls(36, 0.0).startswith("2021-02-07")
    t = mars_time_from_ls(33, 317.435059)
    assert t.startswith("2017-02-14") and subsolar_point("mars", t)["ls"] == pytest.approx(317.435, abs=0.01)
