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


# Rows of temperature_fsi_060827i-1.dat (Zenodo 4621070, ingress 2006-08-27, latitude 18), every
# 0.25 km from 44 to 62 km, as in the file: radius, altitude (km), T (K), p (Pa), n (m^-3).
_FSI_060827I = (
    "6095.800000 44.000000 6.863049e+02 1.522359e+05 1.606623e+25\n"
    "6096.050000 44.250000 6.748847e+02 1.497027e+05 1.606623e+25\n"
    "6096.300000 44.500000 6.634654e+02 1.471697e+05 1.606623e+25\n"
    "6096.550000 44.750000 6.520470e+02 1.446368e+05 1.606623e+25\n"
    "6096.800000 45.000000 6.406296e+02 1.421042e+05 1.606623e+25\n"
    "6097.050000 45.250000 6.292131e+02 1.395718e+05 1.606623e+25\n"
    "6097.300000 45.500000 6.177976e+02 1.370396e+05 1.606623e+25\n"
    "6097.550000 45.750000 6.063829e+02 1.345076e+05 1.606623e+25\n"
    "6097.800000 46.000000 5.949693e+02 1.319759e+05 1.606623e+25\n"
    "6098.050000 46.250000 5.835565e+02 1.294443e+05 1.606623e+25\n"
    "6098.300000 46.500000 5.743606e+02 1.269167e+05 1.600472e+25\n"
    "6098.550000 46.750000 5.689902e+02 1.244157e+05 1.583741e+25\n"
    "6098.800000 47.000000 5.661547e+02 1.219484e+05 1.560108e+25\n"
    "6099.050000 47.250000 5.609707e+02 1.195026e+05 1.542947e+25\n"
    "6099.300000 47.500000 5.473190e+02 1.170622e+05 1.549137e+25\n"
    "6099.550000 47.750000 5.414848e+02 1.146341e+05 1.533351e+25\n"
    "6099.800000 48.000000 5.368966e+02 1.122309e+05 1.514035e+25\n"
    "6100.050000 48.250000 5.319857e+02 1.098520e+05 1.495622e+25\n"
    "6100.300000 48.500000 5.210621e+02 1.074954e+05 1.494219e+25\n"
    "6100.550000 48.750000 5.119800e+02 1.051479e+05 1.487515e+25\n"
    "6100.800000 49.000000 5.084307e+02 1.028314e+05 1.464899e+25\n"
    "6101.050000 49.250000 5.029248e+02 1.005375e+05 1.447902e+25\n"
    "6101.300000 49.500000 4.943801e+02 9.827424e+04 1.439768e+25\n"
    "6101.550000 49.750000 4.834058e+02 9.601104e+04 1.438544e+25\n"
    "6101.800000 50.000000 4.779987e+02 9.377173e+04 1.420886e+25\n"
    "6102.050000 50.250000 4.722092e+02 9.154346e+04 1.404128e+25\n"
    "6102.300000 50.500000 4.613531e+02 8.934644e+04 1.402677e+25\n"
    "6102.550000 50.750000 4.597266e+02 8.716558e+04 1.373280e+25\n"
    "6102.800000 51.000000 4.529571e+02 8.500221e+04 1.359212e+25\n"
    "6103.050000 51.250000 4.470366e+02 8.286064e+04 1.342515e+25\n"
    "6103.300000 51.500000 4.297112e+02 8.073839e+04 1.360872e+25\n"
    "6103.550000 51.750000 4.242221e+02 7.861791e+04 1.342277e+25\n"
    "6103.800000 52.000000 4.196576e+02 7.652418e+04 1.320740e+25\n"
    "6104.050000 52.250000 4.098730e+02 7.446571e+04 1.315894e+25\n"
    "6104.300000 52.500000 3.996805e+02 7.240944e+04 1.312188e+25\n"
    "6104.550000 52.750000 3.916482e+02 7.035170e+04 1.301045e+25\n"
    "6104.800000 53.000000 3.811262e+02 6.830895e+04 1.298143e+25\n"
    "6105.050000 53.250000 3.727951e+02 6.628187e+04 1.287770e+25\n"
    "6105.300000 53.500000 3.655539e+02 6.427746e+04 1.273565e+25\n"
    "6105.550000 53.750000 3.488970e+02 6.227288e+04 1.292753e+25\n"
    "6105.800000 54.000000 3.425714e+02 6.026278e+04 1.274125e+25\n"
    "6106.050000 54.250000 3.252940e+02 5.823992e+04 1.296757e+25\n"
    "6106.300000 54.500000 3.141049e+02 5.621715e+04 1.296307e+25\n"
    "6106.550000 54.750000 3.073914e+02 5.419031e+04 1.276861e+25\n"
    "6106.800000 55.000000 3.037150e+02 5.220874e+04 1.245062e+25\n"
    "6107.050000 55.250000 3.008427e+02 5.027936e+04 1.210498e+25\n"
    "6107.300000 55.500000 2.984211e+02 4.840581e+04 1.174849e+25\n"
    "6107.550000 55.750000 2.958590e+02 4.658769e+04 1.140513e+25\n"
    "6107.800000 56.000000 2.933556e+02 4.482325e+04 1.106682e+25\n"
    "6108.050000 56.250000 2.907541e+02 4.311086e+04 1.073927e+25\n"
    "6108.300000 56.500000 2.881170e+02 4.144943e+04 1.041990e+25\n"
    "6108.550000 56.750000 2.855460e+02 3.983770e+04 1.010490e+25\n"
    "6108.800000 57.000000 2.828783e+02 3.827522e+04 9.800133e+24\n"
    "6109.050000 57.250000 2.801847e+02 3.675996e+04 9.502644e+24\n"
    "6109.300000 57.500000 2.776623e+02 3.529178e+04 9.205991e+24\n"
    "6109.550000 57.750000 2.751571e+02 3.386937e+04 8.915391e+24\n"
    "6109.800000 58.000000 2.726392e+02 3.249235e+04 8.631906e+24\n"
    "6110.050000 58.250000 2.701542e+02 3.115953e+04 8.353972e+24\n"
    "6110.300000 58.500000 2.675801e+02 2.986922e+04 8.085073e+24\n"
    "6110.550000 58.750000 2.664009e+02 2.862371e+04 7.782232e+24\n"
    "6110.800000 59.000000 2.671951e+02 2.742946e+04 7.435372e+24\n"
    "6111.050000 59.250000 2.660468e+02 2.628517e+04 7.155939e+24\n"
    "6111.300000 59.500000 2.656734e+02 2.518482e+04 6.866014e+24\n"
    "6111.550000 59.750000 2.641685e+02 2.412812e+04 6.615403e+24\n"
    "6111.800000 60.000000 2.624806e+02 2.310894e+04 6.376711e+24\n"
    "6112.050000 60.250000 2.610410e+02 2.212764e+04 6.139602e+24\n"
    "6112.300000 60.500000 2.591844e+02 2.118195e+04 5.919309e+24\n"
    "6112.550000 60.750000 2.573995e+02 2.027064e+04 5.703923e+24\n"
    "6112.800000 61.000000 2.559901e+02 1.939326e+04 5.487085e+24\n"
    "6113.050000 61.250000 2.547330e+02 1.854959e+04 5.274279e+24\n"
    "6113.300000 61.500000 2.533181e+02 1.773860e+04 5.071856e+24\n"
    "6113.550000 61.750000 2.519342e+02 1.695893e+04 4.875569e+24\n"
    "6113.800000 62.000000 2.506805e+02 1.620964e+04 4.683459e+24\n"
)


def test_fsi_levels_above_the_padding_where_density_flattens_are_masked(tmp_path, monkeypatch):
    """n is constant up to 46.43 km; above it, to about 54.5 km, it still falls far too slowly
    (to 1.25e25 at 55 km from 1.6e25), so T stays at 400-580 K (399.7 K at 52.5 km, where other
    profiles give about 320 K) with lapse rates of 30-40 K/km."""
    ds = get_dataset("vex-vera-fsi-imamura")
    src = tmp_path / "temperature_fsi_060827i-1.src"
    src.write_text(_FSI_060827I)
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    monkeypatch.setattr(repo, "_download", lambda url, dest, progress=None: src)
    prod = {"product_id": "temperature_fsi_060827i-1", "path": "https://zenodo.org/x", "start_time": "2006-08-27",
            "extra": {"LATITUDE": 18.0}}
    stale = tmp_path / "temperature_fsi_060827i-1.csv"
    stale.write_text("# START_TIME=2006-08-27\nRADIUS [km],TEMPERATURE [K]\n6098.3,399.7\n")
    t = repo.read_normalised(repo.fetch_repository_product(ds, prod))     # an older cached CSV is rewritten
    z, temp = t.columns["ALTITUDE"], t.columns["TEMPERATURE"]
    kept = np.isfinite(temp)
    assert 54.0 < z[kept].min() < 55.0
    assert np.isnan(t.columns["NUMBER_DENSITY"][~kept]).all() and np.isnan(t.columns["PRESSURE"][~kept]).all()
    assert temp[kept].max() < 320.0 and kept[z >= 55].all()
    np.testing.assert_allclose(temp[z == 60.0], 262.5, atol=0.1)          # levels above are untouched


def test_unstable_bottom_masking_keeps_an_adiabatic_profile():
    z = np.arange(44.0, 70.0, 0.1)
    t = 380.0 - 10.0 * (z - 44.0)                                          # about the dry adiabat
    cols = {"ALTITUDE": z, "TEMPERATURE": t.copy()}
    repo._mask_unstable_bottom(cols, "TEMPERATURE", "ALTITUDE", 15.0, [])
    assert np.isfinite(cols["TEMPERATURE"]).all()


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
