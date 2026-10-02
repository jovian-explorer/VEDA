"""Solar geometry computed from time and position, against values the archives publish."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from veda.analysis import solar_geometry as sg
from veda.archives.datasets import get_dataset
from veda.archives.profiles import _add_solar_geometry
from veda.core.models import ObservationProfile
from veda.missions.selection import ProfileFilter, passes, profile_geometry


# Mars Express MaRS "AIO" files (ESA PSA, MEX-M-MRS-5-OCC-9101-V2.0): time of the lowest
# sample at Mars, its latitude and east longitude, and the archive's subsolar point,
# Ls, local true solar time and solar zenith angle
MEX = [
    ("2004-05-18T15:08:04.584", 52.51, 271.95, 14.15, 196.66, 35.07, 17.02, 69.88),
]
# Venus Express VeRa 2014 (Gramigna et al. 2023, Zenodo 10.5281/zenodo.20056665):
# per-sample UTC, latitude, longitude, solar zenith angle and local solar time
VEX = [
    ("2014-01-20T06:12:11.625", -83.331604, 186.88183, 80.895424, 11.941667),
]


@pytest.mark.parametrize("t,lat,lon,sslat,sslon,ls,lst,sza", MEX)
def test_mars_matches_mars_express_geometry(t, lat, lon, sslat, sslon, ls, lst, sza):
    g = sg.solar_geometry("mars", t, lat, lon)
    assert g["subsolar_latitude"] == pytest.approx(sslat, abs=0.05)
    assert g["subsolar_longitude"] == pytest.approx(sslon, abs=0.05)
    assert g["ls"] == pytest.approx(ls, abs=0.05)
    assert g["lst"] == pytest.approx(lst, abs=0.01)          # 36 s of local time
    assert g["sza"] == pytest.approx(sza, abs=0.05)


@pytest.mark.parametrize("t,lat,lon,sza,lst", VEX)
def test_venus_matches_venus_express_geometry(t, lat, lon, sza, lst):
    # Venus rotates retrograde: local time runs the other way in longitude
    g = sg.solar_geometry("venus", t, lat, lon)
    assert g["sza"] == pytest.approx(sza, abs=0.05)
    assert g["lst"] == pytest.approx(lst, abs=0.01)


def test_mars_seasons_and_light_time():
    # Mars Year 27 northern spring equinox, 2004-03-05 (Piqueux et al. 2015 calendar)
    ls = sg.subsolar_point("mars", "2004-03-05T12:00:00")["ls"]
    assert (ls + 180.0) % 360.0 - 180.0 == pytest.approx(0.0, abs=0.5)
    assert abs(sg.subsolar_point("mars", "2004-03-05")["subsolar_latitude"]) < 0.5
    # Mars near conjunction in May 2004 (about 2.3 au) and close to Earth in August 2005
    assert 1050 < sg.light_time_s("mars", "2004-05-18T15:08:00") < 1200
    assert 250 < sg.light_time_s("mars", "2005-08-22T22:15:00") < 400


def test_unsupported_or_incomplete_input_gives_none():
    assert sg.solar_geometry("pluto", "2015-07-14T12:00:00", 0.0, 0.0) is None
    assert sg.solar_geometry("mars", "", 0.0, 0.0) is None
    assert sg.solar_geometry("mars", "2004-05-18T15:08:00", None, 10.0) is None


def _mex_profile(et_received, lat, lon):
    z = np.linspace(0.0, 40.0, et_received.size)
    return ObservationProfile(observation_id="x", mission_id="mex", body_id="mars", instrument="MaRS",
                              time_utc="2004-05-18T15:12:00", latitude=float(np.median(lat)),
                              longitude=float(np.median(lon)), altitude_km=z,
                              track={"latitude": lat, "longitude": lon, "et": et_received})


def test_profile_gets_geometry_and_measurement_time():
    # ground-received ephemeris seconds of the AIO example; the lowest level comes first
    et_at_mars = (np.datetime64("2004-05-18T15:08:04.584") - np.datetime64("2000-01-01T12:00:00")) \
        / np.timedelta64(1, "s") + 69.184
    lt = sg.light_time_s("mars", "2004-05-18T15:08:04")
    et = et_at_mars + lt + np.arange(5) * 1.0
    p = _mex_profile(et, np.full(5, 52.51), np.full(5, 271.95))
    _add_solar_geometry(p, get_dataset("mex-m-mrs-5-occ"))
    assert p.time_utc.startswith("2004-05-18T15:08:0")
    assert p.raw_attributes["LABEL_TIME"] == "2004-05-18T15:12:00"
    assert p.track["lst"][0] == pytest.approx(17.02, abs=0.01)
    geom = profile_geometry(p)
    assert geom["sza"] == pytest.approx(69.9, abs=0.1) and geom["ls"] == pytest.approx(35.07, abs=0.05)


def test_archive_geometry_is_kept_and_dates_alone_give_none():
    ds = dataclasses.replace(get_dataset("mex-m-mrs-5-occ"), times_earth_received=False)
    p = _mex_profile(np.full(3, np.nan), np.full(3, 10.0), np.full(3, 20.0))
    p.track = {"latitude": p.track["latitude"], "longitude": p.track["longitude"], "lst": np.full(3, 9.5)}
    _add_solar_geometry(p, ds)
    assert np.all(p.track["lst"] == 9.5) and "sza" in p.track     # archive value kept, SZA added
    q = _mex_profile(np.full(3, np.nan), np.full(3, 10.0), np.full(3, 20.0))
    q.time_utc = "2004-05-18"
    _add_solar_geometry(q, ds)
    assert "lst" not in q.track


def test_ls_filter_wraps_through_zero():
    f = ProfileFilter(ls_min=330.0, ls_max=30.0)
    assert passes({"latitude": 0.0, "lst": 12.0, "sza": 40.0, "ls": 350.0}, f)[0]
    assert passes({"latitude": 0.0, "lst": 12.0, "sza": 40.0, "ls": 10.0}, f)[0]
    ok, why = passes({"latitude": 0.0, "lst": 12.0, "sza": 40.0, "ls": 90.0}, f)
    assert not ok and "Ls" in why
    assert passes({"latitude": 0.0, "lst": 12.0, "sza": 40.0, "ls": None}, f) == (False, "solar longitude Ls unknown")


def test_mro_header_geometry_and_spacecraft_time(tmp_path):
    """MRO/MGS radio science layout: a one-row header table with the time at the spacecraft,
    Ls, local true solar time and zenith angle, then the profile (label times are Earth
    receive times)."""
    from veda.archives.profiles import profile_from_label
    hdr = "2008-08-01T19:33:11.169,106.80, 4.760,112.29"
    rows = ["3398734.8, 200.00, 500.00", "3399734.8, 195.00, 450.00", "3400734.8, 190.00, 400.00"]
    (tmp_path / "P.TPS").write_text("".join(f"{r:<48}\r\n" for r in [hdr] + rows), newline="")

    def col(name, start, nbytes, dtype="ASCII_REAL", unit=None):
        return (f"OBJECT = COLUMN\nNAME = \"{name}\"\nDATA_TYPE = {dtype}\nSTART_BYTE = {start}\nBYTES = {nbytes}\n"
                + (f"UNIT = {unit}\n" if unit else "") + "END_OBJECT = COLUMN\n")
    (tmp_path / "P.LBL").write_text(
        "PDS_VERSION_ID = PDS3\nRECORD_TYPE = FIXED_LENGTH\nRECORD_BYTES = 50\n"
        "^RSTP_HDR_TABLE = (\"P.TPS\",1)\n^RSTP_TABLE = (\"P.TPS\",2)\nSTART_TIME = 2008-08-01T19:45:03\n"
        "OBJECT = RSTP_HDR_TABLE\nINTERCHANGE_FORMAT = ASCII\nROWS = 1\nCOLUMNS = 4\nROW_BYTES = 50\n"
        + col("SPACECRAFT TIME", 1, 23, "TIME") + col("SOLAR LONGITUDE", 25, 6) + col("LOCAL TRUE SOLAR TIME OF OCCULTATION", 32, 6)
        + col("SOLAR ZENITH ANGLE", 39, 6) + "END_OBJECT = RSTP_HDR_TABLE\n"
        "OBJECT = RSTP_TABLE\nINTERCHANGE_FORMAT = ASCII\nROWS = 3\nCOLUMNS = 3\nROW_BYTES = 50\n"
        + col("RADIUS", 1, 9, unit="METER") + col("TEMPERATURE", 11, 7, unit="KELVIN") + col("PRESSURE", 19, 7, unit="PASCAL")
        + "END_OBJECT = RSTP_TABLE\nEND\n")
    prof = profile_from_label(get_dataset("mro-m-rss-5-tps-v1.0"),
                              {"product_id": "P", "start_time": "2008-08-01T19:45:03", "volume": "v", "url": "",
                               "product_type": "profile"}, tmp_path / "P.LBL")
    assert prof.time_utc == "2008-08-01T19:33:11.169" and prof.raw_attributes["LABEL_TIME"] == "2008-08-01T19:45:03"
    g = profile_geometry(prof)
    assert g["lst"] == 4.76 and g["sza"] == 112.29 and g["ls"] == 106.8      # the archive's values, not recomputed
