"""Mars Express MaRS L4 ionosphere profiles: valid range of the electron densities.

The profiles run from the surface to 1000-5800 km. The team's ^ION_INFO text gives the
lowest valid radius (MEX-MRS-RIU-IS-3050, item 16: where the X-band density first rises
above -3 sigma going up from the neutral atmosphere, copied into the differential Doppler
products); above the peak the densities end in noise.
"""
import numpy as np

from veda.archives.datasets import get_dataset

R_MARS = 3389.5
INFO = """ Profile file name                                  :  "ION.TAB"
 Noise level of the profile              [10^6/m^3] :     1000.00
 Upper noise level altitude                    [km] :    3640.000
 Lower noise level altitude                    [km] :    3470.000
 Lowest valid altitude of ionospheric profile  [km] :    {low}
 Fresnel radius at lowest valid altitude       [km] :        0.51
"""


def _product(tmp_path, z, ne, sigma, low=None):
    """A MaRS L4 ionosphere product (label, table and, if ``low``, its ^ION_INFO text)."""
    rows = "".join(f"{R_MARS + a:9.3f} {b:11.2f} {sigma:11.2f}\r\n" for a, b in zip(z, ne))
    (tmp_path / "ION.TAB").write_text(rows, newline="")
    if low is not None:
        (tmp_path / "ION.TXT").write_text(INFO.format(low=low))
    cols = [("RADIUS", 1, 9, "KILOMETER"), ("ELECTRON NUMBER DENSITY", 11, 11, "10^6 PER CUBIC METER"),
            ("NOISE LEVEL ELECTRON NUMBER DENSITY", 23, 11, "10^6 PER CUBIC METER")]
    body = "".join(f'  OBJECT = COLUMN\n    NAME = "{n}"\n    DATA_TYPE = ASCII_REAL\n    START_BYTE = {s}\n'
                   f'    BYTES = {b}\n    UNIT = "{u}"\n  END_OBJECT = COLUMN\n' for n, s, b, u in cols)
    (tmp_path / "ION.LBL").write_text(f"""PDS_VERSION_ID = PDS3
^ION_INFO = "ION.TXT"
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 35
FILE_RECORDS = {len(z)}
^ION_TABLE = "ION.TAB"
OBJECT = ION_TABLE
  INTERCHANGE_FORMAT = ASCII
  ROWS = {len(z)}
  COLUMNS = 3
  ROW_BYTES = 35
{body}END_OBJECT = ION_TABLE
END
""")
    return tmp_path / "ION.LBL"


def _layer(z):
    """An alpha-Chapman layer (1e5 cm^-3 at 130 km, H 10 km) over 1000 cm^-3 noise of mean zero,
    with the neutral atmosphere's negative densities below 50 km (an X-band profile)."""
    x = (z - 130.0) / 10.0
    ne = 1e5 * np.exp(0.5 * (1.0 - x - np.exp(-x))) + 1000.0 * np.where(np.arange(z.size) % 2 == 0, 0.5, -0.5)
    return np.where(z < 50.0, -2e4 * np.exp((50.0 - z) / 8.0), ne)


def _read(lbl):
    from veda.archives.profiles import profile_from_label
    prod = {"product_id": "ION", "start_time": "2004-05-22T06:00:00", "volume": "MEX-M-MRS-5-OCC-9101-V1.0",
            "url": "", "product_type": "L4 ionosphere electron density profile"}
    prof = profile_from_label(get_dataset("mex-m-mrs-5-occ"), prod, lbl)
    ne = np.asarray(prof.electron_density_cm3, float)
    kept = np.asarray(prof.altitude_km, float)[np.isfinite(ne)]
    return prof, kept


def test_densities_below_the_teams_lowest_valid_radius_are_left_out(tmp_path):
    z = np.arange(0.0, 1000.0, 1.0)
    ne = _layer(z)
    prof, kept = _read(_product(tmp_path, z, ne, 1000.0, low=f"{R_MARS + 70.0:.3f}"))
    # the team's value (70 km) holds even though the densities at 50-70 km are above -3 sigma
    assert kept.min() == 70.0
    # the topside ends below the first level above the peak under 2 sigma (2000 cm^-3), not at 1000 km
    weak = z[(z > 130.0) & (ne < 2000.0)][0]
    assert kept.max() == weak - 1.0 and 200.0 < weak < 230.0
    assert prof.raw_attributes["hmf2_km"] == 130.0
    s = np.asarray(prof.uncertainty["electron_density_cm3"], float)
    assert np.isnan(s[np.asarray(prof.altitude_km) < 70.0]).all()


def test_without_the_teams_value_the_neutral_region_is_found_from_the_densities(tmp_path):
    z = np.arange(0.0, 1000.0, 1.0)
    ne = _layer(z)
    # no text (older products have no ^ION_INFO file), or the default value: the highest level
    # under 100 km with a density below -3 sigma (49 km) and those below it are left out
    for low in (None, "-9999.999"):
        sub = tmp_path / str(low)
        sub.mkdir()
        _, kept = _read(_product(sub, z, ne, 1000.0, low=low))
        assert kept.min() == 50.0, low


def test_the_ionosphere_info_text_is_downloaded_once(monkeypatch, tmp_path):
    """The ^ION_INFO text is fetched with the product (other description texts are not), also
    for a product downloaded before VEDA read it, and one the archive lacks is not asked again."""
    from veda.archives import catalog, net
    monkeypatch.setattr(catalog, "PRODUCT_ROOT", tmp_path)
    ds = get_dataset("mex-m-mrs-5-occ")
    monkeypatch.setattr(catalog, "get_product", lambda d, p: {"volume": "MEX-M-MRS-5-OCC-9101-V1.0",
                                                              "path": f"DATA/X/LEVEL04/{p.upper()}.LBL"})
    calls, absent = [], set()

    def download(url, dest, **kw):
        name = url.rsplit("/", 1)[-1]
        calls.append(name)
        if name in absent:
            raise net.ArchiveError(f"the archive does not have {name} (HTTP 404).")
        dest.parent.mkdir(parents=True, exist_ok=True)
        stem = name.split(".")[0]
        dest.write_text(f'PDS_VERSION_ID = PDS3\n^ION_INFO = "{stem}.TXT"\n^ION_TABLE = "{stem}.TAB"\n'
                        f'^INSTRUMENT_DESC = "MARS_DESC.TXT"\nEND\n' if name.endswith(".LBL") else "1\n")
        return dest
    monkeypatch.setattr(net, "download", download)
    catalog.fetch_product(ds.id, "i1")
    assert calls == ["I1.LBL", "I1.TXT", "I1.TAB"]
    catalog.fetch_product(ds.id, "i1")
    assert len(calls) == 3                               # nothing asked for again
    # downloaded before: the marker lists the label and table only
    label = catalog.local_label_path(ds.id, "MEX-M-MRS-5-OCC-9101-V1.0", "DATA/X/LEVEL04/I1.LBL")
    (label.parent / "I1.TXT").unlink()
    (label.parent / "I1.LBL.complete").write_text("I1.LBL\nI1.TAB")
    catalog.fetch_product(ds.id, "i1")
    assert calls[3:] == ["I1.TXT"]
    # not in the archive: looked for next to the label only (as written and in lower case), then remembered
    absent.update({"I2.TXT", "i2.txt"})
    catalog.fetch_product(ds.id, "i2")
    assert calls[4] == "I2.LBL" and calls[-1] == "I2.TAB" and set(calls[5:-1]) == {"I2.TXT", "i2.txt"}
    n = len(calls)
    catalog.fetch_product(ds.id, "i2")
    assert len(calls) == n
