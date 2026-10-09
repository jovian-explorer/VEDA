"""MAVEN ROSE electron density profiles (PDS4 bundle maven.rose.derived) on an archive file
of 23 August 2016, cut to every fourth level (the header record and label are as archived)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from veda.archives import catalog
from veda.archives.datasets import get_dataset
from veda.archives.profiles import profile_from_label
from veda.missions.selection import profile_geometry
from veda.readers.pds4_reader import read_pds4_table

XML = Path(__file__).parent / "data" / "maven_rose" / "mvn_rse_l3_edp_20160823T192357_v01_r01.xml"
DS = get_dataset("maven-rose-edp")


def _profile():
    prod = {"product_id": XML.stem, "volume": "maven-rose-derived", "start_time": DS.time_from_filename(XML.name),
            "url": DS.base_url + "maven-rose-derived/data/edp/2016/08/" + XML.name,
            "product_type": "Ionospheric electron density profile"}
    return profile_from_label(DS, prod, XML)


def test_listing_walks_year_and_month_folders(monkeypatch):
    root = DS.base_url + "maven-rose-derived/"
    tree = {root + "data/edp/": ["2016"], root + "data/edp/2016/": ["08"],
            root + "data/edp/2016/08/": [XML.name, XML.name[:-4] + ".tab", "collection_x.xml"]}
    monkeypatch.setattr(catalog.http, "list_directory", lambda url, pattern=None, dirs_only=False, login_url=None:
                        list(tree.get(url if url.endswith("/") else url + "/", [])))
    rows = catalog.index_pds4(DS, "maven-rose-derived")
    assert [r["product_id"] for r in rows] == [XML.stem]
    assert rows[0]["start_time"] == "2016-08-23T19:23:57" and rows[0]["kind"] == "profile"


def test_profile_takes_the_archive_values_and_its_representative_point():
    """Time and place where the ray passes 3550 km from the centre of Mars (UTCTIME3550,
    AREOCENTRICLAT3550 ...), not the medians along a ray path that runs to 1000 km; the
    electron density in cm^-3 from NELEC (m^-3) on VEDA's 3389.5 km sphere."""
    p, raw = _profile(), read_pds4_table(str(XML))
    c = raw.columns
    assert p.time_utc == "2016-08-23T19:31:10.448"
    assert (p.latitude, p.longitude) == (pytest.approx(-76.57413), pytest.approx(81.59944))
    geo = profile_geometry(p)
    assert geo["lst"] == pytest.approx(12.70306) and geo["sza"] == pytest.approx(64.74959)
    np.testing.assert_allclose(p.altitude_km, c["RADIUS"] - 3389.5)
    ne, s = p.electron_density_cm3, p.uncertainty["electron_density_cm3"]
    ok = np.isfinite(ne)
    np.testing.assert_allclose(ne[ok], c["NELEC"][ok] / 1e6)
    np.testing.assert_allclose(s[ok], c["SNELEC"][ok] / 1e6)
    k = int(np.nanargmax(ne))
    # the dayside peak: 1.086e5 cm^-3 at 133.9 km in the full file (1.084e5 at this file's levels)
    assert ne[k] == pytest.approx(np.nanmax(c["NELEC"]) / 1e6) and 1.08e5 < ne[k] < 1.09e5
    assert 130.0 < p.altitude_km[k] < 140.0


def _expected_range(raw):
    """The kept part, from the archive values: above the highest level below 100 km with a
    density below -3 sigma, and below the first level above the peak under 2 sigma."""
    z, ne, s = raw.columns["RADIUS"] - 3389.5, raw.columns["NELEC"], raw.columns["SNELEC"]
    bottom = z[(ne < -3 * s) & (z < 100.0)].max()
    k = int(np.argmax(ne))
    above = np.where(z > z[k])[0]                          # rows go up in radius (SIS)
    top = z[above[int(np.argmax(ne[above] < 2 * s[above]))]]
    return z, ne, bottom, top


def test_neutral_atmosphere_and_topside_noise_are_left_out():
    """ROSE takes all refraction as plasma's, so below about 80 km the neutral atmosphere
    gives large negative densities (SIS): up to the highest level below 100 km where the
    density is below -3 sigma the profile is left out.  Above its peak it ends at the first
    level under 2 sigma (the file runs to 1100 km, into the noise)."""
    p, raw = _profile(), read_pds4_table(str(XML))
    z, ne_raw, bottom, top = _expected_range(raw)
    assert 60.0 < bottom < 100.0 and ne_raw[z <= bottom].min() < -1e11          # m^-3: far below the noise
    assert 200.0 < top < 500.0 and z.max() > 1000.0
    ne, s = p.electron_density_cm3, p.uncertainty["electron_density_cm3"]
    kept = (z > bottom) & (z < top)
    assert np.isfinite(ne[kept]).all() and np.isnan(ne[~kept]).all() and np.isnan(s[~kept]).all()


def test_a_profile_without_a_peak_above_the_noise_is_left_out():
    from veda.archives.profiles import _without_topside_noise
    z = np.arange(100.0, 400.0, 10.0)
    ne, s = np.full(z.size, 1e3), np.full(z.size, 1e3)    # nightside: everything within 2 sigma
    out, so = _without_topside_noise(z, ne, s, 2.0)
    assert np.isnan(out).all() and np.isnan(so).all()
    ne[5] = 5e3                                            # a peak at 150 km, 5 sigma
    out, _ = _without_topside_noise(z, ne, s, 2.0)
    assert np.isfinite(out[:6]).all() and np.isnan(out[6:]).all()
    # an occultation starting at 640 km, above the ionosphere: the largest of its noisy
    # levels (4 sigma here) is no peak
    z2 = np.arange(640.0, 2300.0, 1.0)
    ne2 = np.random.default_rng(1).normal(0.0, 1e3, z2.size)
    ne2[100] = 4e3
    assert np.isnan(_without_topside_noise(z2, ne2, np.full(z2.size, 1e3), 2.0)[0]).all()


def test_data_set_references():
    from veda.citations import ref_text, references
    assert DS.mission_id == "maven" and DS.to_dict()["has_profiles"] and DS.doi == "10.17189/1517630"
    assert DS.refs == ("withers2020rose", "withers2020radiosci", "withers2017rosedata")
    refs = references()
    assert ref_text(refs["withers2017rosedata"]).endswith("https://doi.org/10.17189/1517630")
    assert ref_text(refs["withers2020rose"]).endswith("https://doi.org/10.1007/s11214-020-00687-6")
