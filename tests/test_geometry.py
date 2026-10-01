"""Geometry: SPICE kernel selection (offline). Geometry values themselves were
validated against the products (Akatsuki SZA/LST, Mars Express tangent radius)
when the module was written; that check needs ~150 MB of kernels, so it is not
run in CI."""
from __future__ import annotations

import datetime as dt

import pytest

from veda.geometry import kernels

# File names as served by DARTS and the ESA SPICE service (copied from their listings).
VCO = ["spkinfo.txt", "vco_2015_v01.bsp", "vco_2016_v01.bsp", "vco_2017_v01.bsp", "vco_de423_de430.bsp"]
MEX = ["MEX_ROB_040101_041231_003.BSP", "MEX_ROB_050101_051231_003.BSP", "MEX_ROB_130101_131231_001.BSP",
       "ORMF_031222_050328_00066.BSP", "ORMM__260801000000_01973.BSP", "ORMM_T19_260801000000_01973.BSP"]


@pytest.fixture
def listings(monkeypatch):
    def fake(url):
        return VCO if "darts" in url else MEX
    monkeypatch.setattr(kernels, "_listing", fake)


@pytest.mark.parametrize("mission,date,expected", [
    ("akatsuki", dt.date(2016, 3, 3), "vco_2016_v01.bsp"),
    ("mex", dt.date(2004, 4, 2), "MEX_ROB_040101_041231_003.BSP"),
    ("mex", dt.date(2013, 12, 31), "MEX_ROB_130101_131231_001.BSP"),
    ("mex", dt.date(2026, 8, 15), "ORMM__260801000000_01973.BSP"),
])
def test_spk_chosen_by_coverage_in_file_name(listings, mission, date, expected):
    assert kernels.mission_spk_for(mission, date).endswith("/" + expected)


def test_no_spk_for_uncovered_date(listings):
    assert kernels.mission_spk_for("akatsuki", dt.date(2030, 1, 1)) is None
    with pytest.raises(LookupError):
        kernels.plan("akatsuki", "venus", dt.date(2030, 1, 1))


def test_mars_needs_the_satellite_kernel(listings):
    names = [u.rsplit("/", 1)[1] for u in kernels.plan("mex", "mars", dt.date(2004, 4, 2)).urls]
    assert "mar099s.bsp" in names and "de440s.bsp" in names
    venus = [u.rsplit("/", 1)[1] for u in kernels.plan("akatsuki", "venus", dt.date(2016, 3, 3)).urls]
    assert "mar099s.bsp" not in venus
