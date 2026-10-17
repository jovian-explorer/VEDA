"""MAVEN IUVS stellar occultation profiles (FITS, PDS4) against Groller et al. (2018)."""
from pathlib import Path

import numpy as np
import pytest

from veda.archives.datasets import get_dataset
from veda.archives.profiles import profile_from_label

DATA = Path(__file__).parent / "data" / "maven_iuvs"
XML = DATA / "mvn_iuv_l2_occultation-orbit02848_20160317T124025.xml"
DS = get_dataset("maven-iuvs-occultation")


def _profile():
    prod = {"product_id": XML.stem, "volume": "iuvs_derived_bundle",
            "start_time": DS.time_from_filename(XML.name),
            "url": DS.base_url + "iuvs_derived_bundle/l2/occultation/2016/03/" + XML.name,
            "product_type": DS.classify(XML.name)[0]}
    return profile_from_label(DS, prod, XML)


def test_iuvs_occultation_of_orbit_2848_as_published():
    """gamma1 Vel, 17 March 2016 12:40:25 (orbit 02848).  Groller et al. 2018, Table 3, at the
    half light point: longitude 236.45, latitude -5.76 (planetographic), Ls 123.82, SZA 150.91,
    LT 22.28 h.  Section 4.2: at Ls ~124 the ozone peak is "slightly smaller" than the ~2e9 cm^-3
    of Ls ~63 and "centered at ~30 km"."""
    p = _profile()
    assert DS.classify(XML.name)[1] == "profile"
    assert p.time_utc.startswith("2016-03-17T12:40:25")
    assert p.longitude % 360 == pytest.approx(236.45, abs=0.01)
    assert p.latitude == pytest.approx(-5.70, abs=0.01)          # planetocentric (-5.76 planetographic)
    assert p.raw_attributes["SOLAR_LONGITUDE"] == pytest.approx(123.82, abs=0.01)
    assert p.raw_attributes["REPRESENTATIVE_POINT"]["sza"] == pytest.approx(150.91, abs=0.01)
    assert p.raw_attributes["REPRESENTATIVE_POINT"]["lst"] == pytest.approx(22.28, abs=0.01)
    z = np.asarray(p.altitude_km)
    o3 = np.asarray(p.derived["n_o3_m3"]) / 1e6                  # cm^-3
    k = int(np.nanargmax(o3))
    assert 25 < z[k] < 35 and 0.5e9 < o3[k] < 2e9                # 8.9e8 cm^-3 at 27.4 km
    # CO2: the main density, cm^-3 -> m^-3 with its 1-sigma; pressure Pa -> hPa
    n = np.asarray(p.derived["number_density_m3"])
    assert n[6] == pytest.approx(4.035e21, rel=1e-3)
    assert p.uncertainty["number_density_m3"][6] == pytest.approx(3.821e20, rel=1e-3)
    assert np.asarray(p.pressure_hpa)[6] == pytest.approx(0.1268, rel=1e-3)
    assert np.asarray(p.temperature_k)[6] == pytest.approx(227.4, abs=0.1)
    assert np.nanmax(p.derived["n_o2_m3"]) == pytest.approx(2.34e15, rel=1e-3)
