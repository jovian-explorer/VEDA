"""Profiles from research data repositories (Zenodo, BIRA-IASB): Venus Express VeRa and SOIR."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

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


_SOIR_FIELDS = ["altitude", "pressure", "temperature", "total_density", "total_molar_mass", "err_pressure",
                "err_temperature", "err_total_density", "err_total_molar_mass"]


def _soir_votable(params, rows):
    """A SOIR w24 VOTable: one occultation, its time and place in PARAMs."""
    return ('<?xml version="1.0"?><VOTABLE xmlns="http://www.ivoa.net/xml/VOTable/v1.2"><RESOURCE><TABLE>'
            + "".join(f'<PARAM name="{k}" value="{v}" datatype="char"/>' for k, v in params.items())
            + "".join(f'<FIELD name="{f}" datatype="double" unit="u"/>' for f in _SOIR_FIELDS)
            + "<DATA><TABLEDATA>" + "".join("<TR>" + "".join(f"<TD>{v}</TD>" for v in r) + "</TR>" for r in rows)
            + "</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>")


def _soir_zip(tmp_path, monkeypatch, members):
    ds = get_dataset("vex-soir-co2-temperature")
    zf = tmp_path / "cox.zip"
    with zipfile.ZipFile(zf, "w") as z:
        for name, xml in members.items():
            z.writestr(name, xml)
    monkeypatch.setattr(repo, "_zip_path", lambda ds, progress=None: zf)
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    return ds


_GEO = {"latitude_120km": 85.0, "longitude_120km": 282.0, "local_time_min": 2.75, "local_time_max": 3.963,
        "solar_longitude_min": 65.355, "solar_longitude_max": 65.364, "time_min_calendar": "2006-05-12T01:30:36"}


def test_soir_w24_profiles_one_file_each(tmp_path, monkeypatch):
    """SOIR version w24: one VOTable per occultation (CO2_0/Orbit0021.1_CO2_0_w24.01.xml), the
    product ids those of w23 (soir_co2_orbit0021_1); the other molecules' files are not
    profiles of this data set; "(76+0j)", written in one file, is 76."""
    row = lambda alt, t: [alt, 0.1, t, 1e15, 43.44, 0.01, 5.0, 1e14, 0.0]          # noqa: E731
    ds = _soir_zip(tmp_path, monkeypatch, {
        "CO2_0/Orbit0021.1_CO2_0_w24.01.xml": _soir_votable(_GEO, [row(90, 170), row(100, 165), row(110, 160)]),
        "CO2_0/Orbit0039.2_CO2_0_w24.01.xml": _soir_votable(_GEO, [row("(76+0j)", 180), row(80, 181), row(84, 182)]),
        "CO_0/Orbit0021.1_CO_0_w24.01.xml": _soir_votable(_GEO, [row(90, 170)])})
    idx = repo.index_repository(ds)
    assert sorted(r["product_id"] for r in idx) == ["soir_co2_orbit0021_1", "soir_co2_orbit0039_2"]
    t = repo.read_normalised(tmp_path / "soir_co2_orbit0021_1.csv")
    assert t.columns["temperature"].tolist()[:2] == [170.0, 165.0]
    assert t.metadata["LATITUDE"] == 85.0 and t.metadata["LONGITUDE"] == 282.0
    assert t.metadata["LST"] == pytest.approx(3.3565) and t.metadata["START_TIME"].startswith("2006-05-12T01:30:36")
    assert repo.read_normalised(tmp_path / "soir_co2_orbit0039_2.csv").columns["altitude"][0] == 76.0


def test_soir_temperature_held_at_the_upper_boundary_is_masked(tmp_path, monkeypatch):
    """Profiles that repeat one temperature over their top 10 km (orbit 335: 226.19782 K from
    147 to 156 km; 172 of the 718 in w24): the retrieval's starting value, with p = n k T
    from it.  In the others only the top level holds it, with an uncertainty of about 1e-13 K."""
    temps = [228.4, 227.88327] + [226.19782] * 10

    def row(alt, t, err=5.0):
        n = 4.0e8 * 0.85 ** (alt - 145)
        return [alt, n * 1e6 * 1.380649e-23 * t / 100.0, t, n, 43.0, 1e-10, err, n / 20, 0.1]
    ds = _soir_zip(tmp_path, monkeypatch, {
        "CO2_0/Orbit0335.1_CO2_0_w24.01.xml": _soir_votable(_GEO, [row(145 + i, t) for i, t in enumerate(temps)]),
        "CO2_0/Orbit0336.1_CO2_0_w24.01.xml": _soir_votable(
            _GEO, [row(120 + i, 180.0 + i, 1.1e-13 if i == 4 else 6.0) for i in range(5)])})
    stale = tmp_path / "soir_co2_orbit0335_1.csv"
    stale.write_text("# START_TIME=2007-04-17\naltitude [km],temperature [K]\n156,226.19782\n")
    t = repo.read_normalised(repo.fetch_repository_product(ds, {"product_id": "soir_co2_orbit0335_1"}))
    assert t.columns["temperature"][:2].tolist() == [228.4, 227.88327]
    for c in ("temperature", "err_temperature", "pressure", "err_pressure"):
        assert np.isnan(t.columns[c][2:]).all(), c
    assert np.isfinite(t.columns["total_density"]).all()
    t = repo.read_normalised(tmp_path / "soir_co2_orbit0336_1.csv")
    assert np.isfinite(t.columns["temperature"][:4]).all() and np.isnan(t.columns["temperature"][4])
    assert np.isnan(t.columns["pressure"][4]) and np.isfinite(t.columns["total_density"][4])


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


def test_repository_zip_download_reports_its_progress(tmp_path, monkeypatch):
    """Indexing a repository data set downloads its zip (the 38 MB SOIR file) with no
    progress shown: the callback was dropped on the way to the download."""
    seen = []
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    monkeypatch.setattr(repo, "_zenodo_files", lambda record: [{"key": get_dataset("vex-vera-gramigna2023").repository["zip"], "size": 1, "url": "https://example.org/x.zip"}])
    monkeypatch.setattr(repo.http, "download", lambda url, dest, progress=None: seen.append(progress) or dest)
    ds = get_dataset("vex-vera-gramigna2023")
    calls = []
    cb = lambda *a: calls.append(a)                         # noqa: E731
    repo._zip_path(ds, cb)
    # the download reports (bytes, total); the indexing callback takes (done, total, what):
    # passed as it was, the first index of a zip data set failed with a TypeError
    seen.pop()(5, 10)
    assert calls == [(5, 10, f"downloading {ds.repository['zip']}")]
    from veda.archives.datasets import DATASETS
    crism = next(d for d in DATASETS if (d.repository or {}).get("kind") == "csv_split")

    def stop(url, dest, progress=None):
        seen.append(progress)
        raise RuntimeError("stop here")
    monkeypatch.setattr(repo, "_download", stop)
    with pytest.raises(RuntimeError):
        repo._index_csv_split(crism, cb)
    assert seen == [cb]


def _juno(tmp_path, monkeypatch, ds_id, name):
    ds = get_dataset(ds_id)
    src = Path(__file__).parent / "data" / "juno_ro" / name
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    return ds, src


def test_juno_occultation_profiles_coffin_et_al(tmp_path, monkeypatch):
    """Coffin et al. (2025): seven profiles of four occultations, four ingress and three
    egress, all on the dawn limb.  ELECDEN is in m^-3 (the readme says cm^-3): the PJ53
    ingress peak, 1.35e11, is the 1.28e5 cm^-3 at 625 km of Caruso et al.'s file within 6 %."""
    from veda.archives.profiles import profile_from_label
    ds, src = _juno(tmp_path, monkeypatch, "juno-ro-coffin2025", "PJ053N_EDP_V01.CSV")
    monkeypatch.setattr(repo, "_download", lambda url, dest, progress=None: src)
    names = ["PJ053N", "PJ053X", "PJ054N", "PJ060N", "PJ060X", "PJ062N", "PJ062X"]
    monkeypatch.setattr(repo, "_zenodo_files", lambda record: [{"key": f"{n}_EDP_V01.CSV", "url": f"https://x/{n}"} for n in names]
                        + [{"key": "ZenodoReadme.pdf", "url": "https://x/r"}])
    rows = repo._index_zenodo_files(ds)
    assert len(rows) == 7 and sum("ingress" in r["product_type"] for r in rows) == 4
    assert all(r["start_time"] for r in rows)
    prod = {**rows[0], "url": "", "extra": json.loads(rows[0]["extra"])}
    p = profile_from_label(ds, prod, repo.fetch_repository_product(ds, prod))
    assert p.time_utc.startswith("2023-07-31T09:07:5")
    assert (p.latitude, p.longitude) == pytest.approx((41.08, 254.14))
    ne, z = np.asarray(p.electron_density_cm3), np.asarray(p.altitude_km)
    k = int(np.nanargmax(ne))
    assert ne[k] == pytest.approx(1.35e5, rel=0.01) and z[k] == pytest.approx(617, abs=5)
    assert 5.5 < float(np.nanmedian(p.track["lst"])) < 7.0                 # dawn


def test_juno_occultation_profiles_caruso_et_al(tmp_path, monkeypatch):
    """Two columns, no time or place: from the occultation table, 1000 km up."""
    import zipfile
    from veda.archives.profiles import profile_from_label
    ds, src = _juno(tmp_path, monkeypatch, "juno-ro-caruso2026", "PJ53I_Ne.txt")
    zf = tmp_path / ds.repository["zip"]
    with zipfile.ZipFile(zf, "w") as z:
        z.write(src, "PJ53I_Ne.txt")
    monkeypatch.setattr(repo, "_zip_path", lambda ds, progress=None: zf)
    rows = repo._index_zenodo_zip(ds)
    assert [r["start_time"] for r in rows] == ["2023-07-31T09:07:57"]
    prod = {**rows[0], "url": "", "extra": json.loads(rows[0]["extra"])}
    p = profile_from_label(ds, prod, repo.fetch_repository_product(ds, prod))
    assert (p.latitude, p.longitude) == pytest.approx((41.08, 254.14))
    ne, z = np.asarray(p.electron_density_cm3), np.asarray(p.altitude_km)
    k = int(np.nanargmax(ne))
    assert ne[k] == pytest.approx(1.28e5, rel=0.01) and z[k] == pytest.approx(625, abs=5)
    assert 6.0 < p.raw_attributes["LST"] < 7.0


def test_bytes_repr_times_are_read():
    assert repo._parse_time("b'2023 JUL 31 08:56:16.074515'") == "2023-07-31T08:56:16.074"


def test_nomad_profiles_from_a_tar_archive(tmp_path, monkeypatch):
    """Lopez-Valverde et al. (2023) NOMAD scans: one text file per scan in a .tar.xz; the
    header's ranges give the place (east longitude: VEDA's local time and solar zenith angle
    at it are those of the terminator a solar occultation sees, 16.8 h against the file's
    17.0 h, 88.7 deg); levels where the averaging kernel is under 0.01 are the first guess."""
    import tarfile
    from veda.archives.profiles import profile_from_label
    ds = get_dataset("tgo-nomad-so-lopezvalverde2023")
    name = "TPcorrected_20180423_204351_1p0a_SO_A_I_149_.dat"
    tz = tmp_path / ds.repository["zip"]
    with tarfile.open(tz, "w:xz") as t:
        t.add(Path(__file__).parent / "data" / "tgo_nomad" / name, f"Year1_3ndRun_allTPfiles/{name}")
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    rows = repo._index_zenodo_zip(ds)
    assert len(rows) == 1 and rows[0]["start_time"] == "2018-04-23T20:43:51" and "ingress" in rows[0]["product_type"]
    prod = {**rows[0], "url": "", "extra": json.loads(rows[0]["extra"])}
    p = profile_from_label(ds, prod, repo.fetch_repository_product(ds, prod))
    assert (p.latitude, p.longitude) == pytest.approx((-64.93, 221.91), abs=0.01)
    z, t = np.asarray(p.altitude_km), np.asarray(p.temperature_k, dtype=float)
    ok = np.isfinite(t)
    assert z[ok].min() == 24.0 and z[ok].max() == 100.0
    assert t[z == 30.0][0] == pytest.approx(166.69) and p.pressure_hpa[z == 30.0][0] == pytest.approx(0.1768)
    assert p.raw_attributes["LS"] == pytest.approx(p.raw_attributes["LS_FILE"], abs=0.02)     # 164.2
    from veda.analysis.solar_geometry import solar_geometry
    g = solar_geometry("mars", p.time_utc, p.latitude, p.longitude)
    assert g["lst"] == pytest.approx(16.8, abs=0.1) and g["sza"] == pytest.approx(88.7, abs=0.2)


def _acs(tmp_path, monkeypatch, ds_id, name):
    ds = get_dataset(ds_id)
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    monkeypatch.setattr(repo, "_zip_path", lambda ds, progress=None: Path(__file__).parent / "data" / "tgo_acs" / name)
    return ds


def test_acs_mir_profiles_placed_from_the_observation_list(tmp_path, monkeypatch):
    """Belyaev et al. (2022), Mendeley Data: files found by orbit and hemisphere in the
    observation list (orbit 2229: 24 May 2018, Ls 181.12, 83.51 N 94.95 E, 6.38 h); an orbit
    with two northern occultations in the list (3321) cannot be told apart and is left out.
    VEDA's temperatures from the CO2 density agree with the team's below 140 km."""
    from veda.archives.profiles import profile_from_label
    ds = _acs(tmp_path, monkeypatch, "tgo-acs-mir-belyaev2022", "acs_mir_excerpt.zip")
    rows = {r["product_id"]: r for r in repo._index_zenodo_zip(ds)}
    assert sorted(rows) == ["acs_mir_002229_NORTHERN_1", "acs_mir_002302_SOUTHERN_2"]
    r = rows["acs_mir_002229_NORTHERN_1"]
    assert r["start_time"] == "2018-05-24"
    prod = {**r, "url": "", "extra": json.loads(r["extra"])}
    p = profile_from_label(ds, prod, repo.fetch_repository_product(ds, prod))
    assert (p.latitude, p.longitude) == pytest.approx((83.51, 94.95)) and p.raw_attributes["LST"] == 6.38
    assert p.raw_attributes["LS"] == 181.12 and p.raw_attributes["MESOPAUSE_KM"] == 89.2
    z, t = np.asarray(p.altitude_km), np.asarray(p.temperature_k, float)
    m = (z > 60) & (z < 140)
    assert abs(np.nanmedian(np.asarray(p.derived["temperature_from_density"])[m] - t[m])) < 5.0


def test_acs_nir_files_of_three_kinds_dated_from_ls(tmp_path, monkeypatch):
    """Fedorova et al. (2022): water, temperature and aerosol files of one occultation, each
    with its own columns; the list gives Ls 163.3 of Mars year 34 and no date: 22 April 2018
    (Belyaev et al.'s list dates the same orbits to within a day)."""
    from veda.archives.profiles import profile_from_label
    ds = _acs(tmp_path, monkeypatch, "tgo-acs-nir-fedorova2022", "acs_nir_excerpt.zip")
    rows = {r["product_id"]: r for r in repo._index_zenodo_zip(ds)}
    assert sorted(rows) == ["acs_nir_001833_2_H2O_S", "acs_nir_001833_2_Temperature", "acs_nir_001833_2_aerosol_extinction"]
    assert {r["start_time"] for r in rows.values()} == {"2018-04-22"}
    get = lambda pid: profile_from_label(ds, {**rows[pid], "url": "", "extra": json.loads(rows[pid]["extra"])},  # noqa: E731
                                         repo.fetch_repository_product(ds, {**rows[pid], "extra": json.loads(rows[pid]["extra"])}))
    w = get("acs_nir_001833_2_H2O_S")
    assert w.derived["h2o_ppm"][0] == 2.9 and w.derived["saturation_ratio"][0] == pytest.approx(4.592e-3)
    assert (w.latitude, w.longitude) == pytest.approx((79.5, 246.0)) and w.raw_attributes["MARS_YEAR"] == 34
    assert get("acs_nir_001833_2_Temperature").temperature_k[0] == 125.2
    assert get("acs_nir_001833_2_aerosol_extinction").derived["aerosol_extinction_km"][0] == pytest.approx(4.466e-3)


def _archive(tmp_path, monkeypatch, ds_id, members, kind):
    """A one-file copy of a data set's archive (zip or tar) made from tests/data/tgo_nomad."""
    import tarfile
    ds = get_dataset(ds_id)
    src = Path(__file__).parent / "data" / "tgo_nomad"
    a = tmp_path / ds.repository["zip"]
    if kind == "zip":
        with zipfile.ZipFile(a, "w") as z:
            for arc, name in members:
                z.write(src / name, arc)
    else:
        with tarfile.open(a, "w") as t:
            for arc, name in members:
                t.add(src / name, arc)
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    return ds


def _one(ds):
    from veda.archives.profiles import profile_from_label
    rows = repo._index_zenodo_zip(ds)
    assert len(rows) == 1
    prod = {**rows[0], "url": "", "extra": json.loads(rows[0]["extra"])}
    return rows[0], profile_from_label(ds, prod, repo.fetch_repository_product(ds, prod))


def test_nomad_trompet_profiles_east_longitude_and_hydrostatic_temperatures(tmp_path, monkeypatch):
    """Trompet et al. (2023): per-level latitude, longitude and local time; the longitudes
    are east (VEDA's local time at them and the file's time agrees with the file's), and the
    team's temperatures are hydrostatic from the CO2 density, as VEDA's own (44.01 g/mol)."""
    from veda.analysis.solar_geometry import solar_geometry
    name = "20200909_234948_1p0a_SO_A_E_148.dat"
    ds = _archive(tmp_path, monkeypatch, "tgo-nomad-so-trompet2023", [(f"Trompet_JGR2022/{name}", name)], "zip")
    row, p = _one(ds)
    assert row["start_time"] == "2020-09-09T23:49:48" and "egress" in row["product_type"]
    g = solar_geometry("mars", p.time_utc, p.latitude, p.longitude)
    assert abs(((g["lst"] - np.nanmedian(p.track["lst"]) + 12) % 24) - 12) < 0.5
    z, t = np.asarray(p.altitude_km), np.asarray(p.temperature_k, float)
    m = z < np.nanmax(z) - 10                      # below the top boundary of both integrations
    assert abs(np.nanmedian(np.asarray(p.derived["temperature_from_density"])[m] - t[m])) < 6.0


def test_nomad_order_165_and_brines_water_profiles(tmp_path, monkeypatch):
    """Order 165 (Trompet 2026): local time before latitude and longitude in its columns,
    profiles at 140-190 km.  Brines et al. (2026): place from "# Label: value" header lines in
    a plain tar."""
    name = "20181130_205230_1p0a_SO_A_E_165.dat"
    ds = _archive(tmp_path, monkeypatch, "tgo-nomad-so165-trompet2026", [(f"Trompet_2026_NOMADSO165/{name}", name)], "tar")
    _, p = _one(ds)
    assert 140 < np.nanmin(p.altitude_km) and np.nanmax(p.altitude_km) < 200
    assert np.nanmedian(p.track["lst"]) == pytest.approx(7.4, abs=0.1) and np.nanmedian(p.track["latitude"]) == pytest.approx(41.0, abs=0.3)
    name = "20180421_202111_1p0a_SO_A_E_134-168.dat"
    ds = _archive(tmp_path, monkeypatch, "tgo-nomad-so-h2o-brines2026", [(name, name)], "tar")
    _, w = _one(ds)
    assert (w.latitude, w.longitude) == (78.94, 2.93) and w.raw_attributes["LST"] == 3.32
    assert w.altitude_km[0] == 20.0 and w.derived["h2o_ppm"][0] == pytest.approx(0.3781)


def test_nomad_aoki_water_profiles_from_csv(tmp_path, monkeypatch):
    """Aoki et al. (2022): one comma-separated file per scan and order with a header line,
    place and local time at each level.  The archive holds the paper's 5,472 profiles (and
    one empty file); after Ls 180 water is above NOMAD's detection limit (~1e9 cm^-3) at 70 km."""
    name = "20180623_075629_1p0a_SO_A_E_134.csv"
    ds = _archive(tmp_path, monkeypatch, "tgo-nomad-so-h2o-aoki2022", [(f"archive/{name}", name)], "zip")
    row, p = _one(ds)
    assert row["start_time"] == "2018-06-23T07:56:29" and "egress" in row["product_type"]
    k = int(np.argmin(np.abs(np.asarray(p.altitude_km) - 70.0)))
    assert p.derived["h2o_ppm"][k] == pytest.approx(59.8946) and p.derived["h2o_cm3"][k] == pytest.approx(1.8727e10)
    assert p.derived["h2o_cm3"][k] > 1e9
    assert p.track["latitude"][0] == pytest.approx(-73.3439) and p.track["lst"][0] == pytest.approx(19.8064)


def test_downloads_report_indexing_progress_with_three_arguments(tmp_path, monkeypatch):
    """The indexing progress is (done, total, what), the download's (bytes, total): the CRISM
    tables (csv_split) passed the indexing callback to the download and stopped with a TypeError."""
    def fake_download(url, dest, progress=None, **kw):
        progress(5, 10)
        Path(dest).write_text("x", encoding="utf-8")
        return dest
    monkeypatch.setattr(repo.http, "download", fake_download)
    seen = []
    repo._download("https://example.org/t.csv", tmp_path / "t.csv", progress=lambda d, t, what: seen.append((d, t, what)))
    assert seen == [(5, 10, "downloading t.csv")]


def test_nomad_uvis_aerosol_blocks_of_one_text_file(tmp_path, monkeypatch):
    """Flimon et al. (2025): one text file of 10,519 blocks (the paper's 10,519 processed
    occultations), each the scan's name, latitude, east longitude, Ls and local time, then
    its levels.  The excerpt holds the archive's first two blocks."""
    from veda.analysis.solar_geometry import solar_geometry
    from veda.archives.profiles import profile_from_label
    ds = get_dataset("tgo-nomad-uvis-aerosol-flimon2025")
    src = Path(__file__).parent / "data" / "tgo_nomad" / "uvis_paper_excerpt.txt"
    (tmp_path / "uvis_paper.txt").write_bytes(src.read_bytes())
    monkeypatch.setattr(repo, "_cache_dir", lambda ds: tmp_path)
    rows = repo.index_repository(ds)
    assert [r["product_id"] for r in rows] == ["20190101_045959_1p0a_UVIS_I", "20190101_074215_1p0a_UVIS_E"]
    assert rows[1]["start_time"] == "2019-01-01T07:42:15" and "egress" in rows[1]["product_type"]
    (tmp_path / "20190101_074215_1p0a_UVIS_E.csv").unlink()          # written again when asked for
    prod = {**rows[1], "url": "", "extra": json.loads(rows[1]["extra"])}
    p = profile_from_label(ds, prod, repo.fetch_repository_product(ds, prod))
    assert len(p.altitude_km) == 19 and p.altitude_km[0] == pytest.approx(38.198435)
    assert p.derived["aerosol_extinction_km"][-1] == pytest.approx(0.018713965)
    assert p.uncertainty["aerosol_extinction_km"][-1] == pytest.approx(0.0052025406)
    assert (p.latitude, p.raw_attributes["LST"]) == (pytest.approx(-71.1535), pytest.approx(1.6325))
    # the longitudes are east: the local time computed there agrees with the file's
    assert solar_geometry("mars", rows[1]["start_time"], p.latitude, p.longitude)["lst"] == pytest.approx(1.63, abs=0.3)
