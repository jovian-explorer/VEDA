"""Archive engine: index parsing, pointers, times and units (offline, no network)."""
from __future__ import annotations

import numpy as np
import pytest

from veda.archives.catalog import _normalise_time, label_pointers
from veda.archives.datasets import DATASETS, get_dataset
from veda.archives.pds3_index import parse_index
from veda.archives.profiles import _scale, _to_hpa, _to_per_cm3
from veda.readers.pds3_reader import match_column, parse_pds3_label


def _label(columns, extra=""):
    cols = "".join(
        f"  OBJECT = COLUMN\n    NAME = {n}\n    DATA_TYPE = CHARACTER\n    START_BYTE = {s}\n"
        f"    BYTES = {b}\n  END_OBJECT = COLUMN\n" for n, s, b in columns)
    return f"PDS_VERSION_ID = PDS3\n{extra}OBJECT = INDEX_TABLE\n{cols}END_OBJECT = INDEX_TABLE\nEND\n"


def test_index_csv_wins_over_wrong_byte_widths():
    """DARTS declares TARGET_NAME as 3 bytes for "VENUS"; byte slicing shifted the
    orbit number into ','. Clean quoted CSV is parsed as CSV instead."""
    lbl = _label([("FILE_SPECIFICATION_NAME", 2, 20), ("TARGET_NAME", 25, 3), ("ORBIT_NUMBER", 30, 2)])
    tab = '"data/l4/a_v10.lbl","VENUS", 9\r\n"data/l4/b_v10.lbl","VENUS",11\r\n'
    rows = parse_index(lbl, tab)
    assert [r["TARGET_NAME"] for r in rows] == ["VENUS", "VENUS"]
    assert [r["ORBIT_NUMBER"] for r in rows] == ["9", "11"]


def test_comment_marker_inside_quotes_keeps_columns():
    """INDEXED_FILE_NAME = {"BCK/*.LBL"} was read as a comment opener and every
    column definition after it was dropped."""
    lbl = _label([("FILE_SPECIFICATION_NAME", 2, 16), ("PRODUCT_ID", 21, 8)],
                 extra='INDEXED_FILE_NAME = {"BCK/*.LBL","ION/*.LBL"}\n')
    _, cols = parse_pds3_label(lbl)
    assert [c.name for c in cols] == ["FILE_SPECIFICATION_NAME", "PRODUCT_ID"]


def test_wrapped_column_names_are_joined():
    lbl = ('OBJECT = COLUMN\n  NAME = "SIGMA PRESSURE (LOWER TEMPERATURE AT\n           BOUNDARY)"\n'
           '  START_BYTE = 1\n  BYTES = 5\nEND_OBJECT = COLUMN\n')
    _, cols = parse_pds3_label(lbl)
    assert cols[0].name == "SIGMA PRESSURE (LOWER TEMPERATURE AT BOUNDARY)"


def test_header_row_inside_index_is_dropped():
    lbl = _label([("VOLUME_ID", 2, 11), ("FILE_SPECIFICATION_NAME", 16, 20)])
    tab = '"VOLUME_ID","FILE_SPECIFICATION_NAME"\n"JNOMWR_0000","DATA/EDR/X.LBL"\n'
    rows = parse_index(lbl, tab)
    assert len(rows) == 1 and rows[0]["VOLUME_ID"] == "JNOMWR_0000"


def test_day_of_year_times_become_calendar_dates():
    assert _normalise_time("2014-001T00:00:02.820") == "2014-01-01T00:00:02.820"
    assert _normalise_time("2016-240T10:00:00") == "2016-08-27T10:00:00"
    assert _normalise_time("2016-03-03T23:17:09.324Z") == "2016-03-03T23:17:09.324"
    assert _normalise_time("UNK") == ""


def test_mars_express_time_comes_from_file_name_not_creation_time():
    ds = get_dataset("mex-m-mrs-5-occ")
    assert ds.time_from_filename("M65RSR0L04_AIX_041601543_60.LBL") == "2004-06-08T15:43:00"
    assert ds.time_from_filename("M65TNFXL04_AIX_221300544_60.LBL") == "2022-05-10T05:44:00"
    assert ds.classify("M32ICL2L04_IIX_040931105_60.LBL") == ("L4 ionosphere electron density profile", "profile")


def test_label_pointers():
    txt = ('^ATM_DATA_TABLE = ("rs_x_l4_ae_v10.tab", 1)\n^STRUCTURE = "INDEX.FMT"\n'
           '^DESCRIPTION = "MARS_DESC.TXT"\n')
    assert label_pointers(txt) == [("ATM_DATA_TABLE", "rs_x_l4_ae_v10.tab"), ("STRUCTURE", "INDEX.FMT"),
                                   ("DESCRIPTION", "MARS_DESC.TXT")]


def test_density_and_pressure_units():
    """'10^6 PER CUBIC METER' is cm^-3; 'CUBIC METER' must not be read as 'CM'."""
    two = np.array([2.0])
    assert _scale("10^6 PER CUBIC METER") == 1e6
    assert _to_per_cm3(two, "10^6 PER CUBIC METER")[0] == 2.0
    assert _to_per_cm3(two, "1 PER CUBIC METER")[0] == 2e-6
    assert _to_per_cm3(two, "PER CUBIC CENTIMETER")[0] == 2.0
    assert _to_hpa(two, "PASCAL")[0] == 0.02
    assert _to_hpa(two, "BAR")[0] == 2000.0
    assert _to_hpa(two, "MBAR")[0] == 2.0


def test_column_names_with_spaces_or_underscores_match():
    assert match_column(["EPHEMERIS SECONDS"], "EPHEMERIS_SECONDS") == "EPHEMERIS SECONDS"
    assert match_column(["ELECTRON NUMBER DENSITY", "NOISE LEVEL ELECTRON NUMBER DENSITY"],
                        "ELECTRON NUMBER DENSITY") == "ELECTRON NUMBER DENSITY"


def test_dataset_registry_is_well_formed():
    ids = [d.id for d in DATASETS]
    assert len(ids) == len(set(ids))
    for d in DATASETS:
        assert d.base_url.startswith("https://") and d.base_url.endswith("/")
        assert d.body_ids and d.mission_id and d.instrument


def test_label_value_on_next_line_and_quoted_equals():
    """Magellan labels: 'DESCRIPTION =' with the text on the next line, and a quoted SQL
    query whose continuation line starts with '='. The table used to be swallowed."""
    from veda.readers.pds3_reader import parse_pds3_tables
    lbl = ('^TABLE = "X.DAT"\nDESCRIPTION =\n  "query WHERE (ORBIT_NUMBER\n  = 3212 OR ORBIT_NUMBER = 3213)"\n'
           'OBJECT = TABLE\n  ROWS = 2\n  OBJECT = COLUMN\n    NAME = "WAVELENGTH"\n    DATA_TYPE = CHARACTER\n'
           '    START_BYTE = 1\n    BYTES = 3\n  END_OBJECT\n  OBJECT = COLUMN\n    NAME = "ORBIT_NUMBER"\n'
           '    START_BYTE = 4\n    BYTES = 5\n  END_OBJECT\nEND_OBJECT\nEND\n')
    t = parse_pds3_tables(lbl)
    assert len(t) == 1 and [c.name for c in t[0].columns] == ["WAVELENGTH", "ORBIT_NUMBER"] and t[0].file == "X.DAT"


def test_records_split_by_stray_newlines_are_rejoined():
    from veda.readers.pds3_reader import _rejoin_broken_records
    rec = "A" * 40
    lines = [rec] * 20 + [rec[:25], rec[25:]] + [rec] * 20 + ["short tail ok"]
    assert _rejoin_broken_records(lines) == [rec] * 41 + ["short tail ok"]
    free_text = ["a", "bb", "ccc", "dddd"]          # not fixed-length: left alone
    assert _rejoin_broken_records(free_text) == free_text


def test_venus_express_vera_time_from_file_name():
    ds = get_dataset("vex-v-vra-1-2-3")
    assert ds.time_from_filename("V32ICL2L1B_AG1_073610303_00.LBL") == "2007-12-27T03:03:00"
    assert ds.classify("DATA/LEVEL02/CLOSED_LOOP/IFMS/DP1/V32ICL2L02_D1X_073610303_00.LBL")[0] == "Level 2 (calibrated) record"


def _ascii_profile(tmp_path, z, t, p):
    rows = "".join(f"{a:8.2f} {b:8.2f} {c:10.4f}\r\n" for a, b, c in zip(z, t, p))
    (tmp_path / "prof.tab").write_text(rows, newline="")
    (tmp_path / "prof.lbl").write_text(f"""PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 30
FILE_RECORDS = {len(z)}
^TABLE = "prof.tab"
OBJECT = TABLE
  INTERCHANGE_FORMAT = ASCII
  ROWS = {len(z)}
  COLUMNS = 3
  ROW_BYTES = 30
  OBJECT = COLUMN
    NAME = ALTITUDE
    DATA_TYPE = ASCII_REAL
    START_BYTE = 1
    BYTES = 8
    UNIT = KILOMETER
  END_OBJECT = COLUMN
  OBJECT = COLUMN
    NAME = TEMPERATURE
    DATA_TYPE = ASCII_REAL
    START_BYTE = 10
    BYTES = 8
    UNIT = KELVIN
  END_OBJECT = COLUMN
  OBJECT = COLUMN
    NAME = PRESSURE
    DATA_TYPE = ASCII_REAL
    START_BYTE = 19
    BYTES = 10
    UNIT = BAR
  END_OBJECT = COLUMN
END_OBJECT = TABLE
END
""")
    return tmp_path / "prof.lbl"


def test_magellan_altitudes_move_onto_the_venus_reference_radius(tmp_path):
    """Magellan RSS altitudes are above 6052 km; VEDA's Venus reference (and the VEX
    radius-derived altitudes) use 6051.8 km, so Magellan profiles move up 0.2 km."""
    import dataclasses
    from veda.archives.profiles import profile_from_label
    from veda.core.registry import get_body
    ds = dataclasses.replace(get_dataset("mgn-v-rss-5-occ-prof-rtpd-v1.0"), split_by=(), column_units={},
                             extra_variables={}, profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE",
                                                                  "pressure": "PRESSURE"})
    lbl = _ascii_profile(tmp_path, [40.0, 50.0, 60.0], [420.0, 350.0, 260.0], [3.5, 1.0, 0.2])
    prod = {"product_id": "x", "start_time": "1991-10-05T00:00:00", "volume": "mg_2401", "url": "", "product_type": "profile"}
    prof = profile_from_label(ds, prod, lbl)
    shift = 6052.0 - get_body("venus").radius_km
    np.testing.assert_allclose(prof.altitude_km, np.array([40.0, 50.0, 60.0]) + shift)
    assert "6052" in prof.raw_attributes["ALTITUDE_REFERENCE"]
    assert prof.to_dict()["altitude_reference"].startswith("a sphere of radius")


def test_kilogram_per_cubic_metre_is_not_grams_per_cubic_centimetre(tmp_path):
    """With the spaces removed, KILOGRAM PER CUBIC METER contains "GRAM" and "CM", so
    densities labelled in kg/m^3 were multiplied by 1000 as if in g/cm^3."""
    import dataclasses
    from veda.archives.profiles import _grams_per_cm3, profile_from_label
    assert _grams_per_cm3("GM/CM**3") and _grams_per_cm3("GRAM PER CUBIC CENTIMETER")
    assert not _grams_per_cm3("KILOGRAM PER CUBIC METER") and not _grams_per_cm3("KG/M**3")
    lbl = _ascii_profile(tmp_path, [40.0, 50.0, 60.0], [420.0, 350.0, 260.0], [3.5, 1.0, 0.2])
    text = lbl.read_text().replace("NAME = PRESSURE", "NAME = DENSITY")
    for unit, factor in (("KILOGRAM PER CUBIC METER", 1.0), ("GM/CM**3", 1000.0)):
        lbl.write_text(text.replace("UNIT = BAR", f'UNIT = "{unit}"'))
        ds = dataclasses.replace(get_dataset("mgn-v-rss-5-occ-prof-rtpd-v1.0"), split_by=(), column_units={},
                                 extra_variables={"density_measured": ("DENSITY", None)},
                                 profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE"})
        prod = {"product_id": "x", "start_time": "1991-10-05T00:00:00", "volume": "mg_2401", "url": "",
                "product_type": "profile"}
        prof = profile_from_label(ds, prod, lbl)
        np.testing.assert_allclose(prof.derived["density_measured"], np.array([3.5, 1.0, 0.2]) * factor)


def test_comparison_warns_when_vertical_references_differ():
    from veda.analysis.atmospheric import _vertical_reference_warning
    sphere = {"mission_id": "vex", "altitude_reference": "a sphere of radius 6051.8 km (from the radius column)"}
    sphere2 = {"mission_id": "magellan", "altitude_reference": "a sphere of radius 6051.8 km (archive ...)"}
    onebar = {"mission_id": "galileo", "altitude_reference": "the 1-bar pressure level"}
    assert _vertical_reference_warning([sphere, sphere2]) == ""
    assert _vertical_reference_warning([sphere, {"mission_id": "upload", "altitude_reference": ""}]) == ""
    assert "1-bar" in _vertical_reference_warning([sphere, onebar])


def test_pds4_header_table_fill_values_and_bracketing_systematic_uncertainty(tmp_path):
    """PVO radio occultation layout: a one-row header table (location), then the profile
    with three retrievals (upper boundary 150/200/250 K); fills stated only in prose."""
    import dataclasses
    from veda.archives.profiles import profile_from_label
    head = f"{-60.07:10.2f}{94.93:10.2f}\r\n"
    rows = [(6146.0, 150.0, 200.0, 250.0, 0.156, 0.208, 0.260), (6110.0, 225.0, 226.0, 227.0, 40.0, 40.0, 40.1),
            (1e9, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)]
    body = "".join("".join(f"{v:12.3f}" if v < 1e8 else f"{v:12.0e}" for v in r) + "\r\n" for r in rows)
    (tmp_path / "p.tab").write_text(head + body, newline="")
    def fields(names, units):
        return "".join(f"<Field_Character><name>{n}</name><field_location unit='byte'>{1 + i * w}</field_location>"
                       f"<data_type>ASCII_Real</data_type><field_length unit='byte'>{w}</field_length><unit>{u}</unit>"
                       f"</Field_Character>" for i, (n, u, w) in enumerate(zip(names, units, [10 if len(names) == 2 else 12] * len(names))))
    xml = f"""<?xml version="1.0"?><Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
<Identification_Area><logical_identifier>urn:nasa:pds:pvoro:data_derived:x</logical_identifier><title>t</title></Identification_Area>
<Observation_Area><Time_Coordinates><start_date_time>1978-12-10T15:09:40Z</start_date_time></Time_Coordinates></Observation_Area>
<File_Area_Observational><File><file_name>p.tab</file_name></File>
<Table_Character><offset unit="byte">0</offset><records>1</records><record_delimiter>Carriage-Return Line-Feed</record_delimiter>
<Record_Character>{fields(["LAT16_SPICE", "LON16_SPICE"], ["degree", "degree"])}</Record_Character></Table_Character>
<Table_Character><offset unit="byte">{len(head)}</offset><records>3</records><record_delimiter>Carriage-Return Line-Feed</record_delimiter>
<Record_Character>{fields(["R20016", "T15016", "T20016", "T25016", "P15016", "P20016", "P25016"],
                          ["kilometer", "kelvin", "kelvin", "kelvin", "millibar", "millibar", "millibar"])}</Record_Character></Table_Character>
</File_Area_Observational></Product_Observational>"""
    (tmp_path / "p.xml").write_text(xml)
    ds = get_dataset("pvoro-nssdc")
    ds = dataclasses.replace(ds, fill_values={**ds.fill_values, "R20016": (1e9,)})
    prof = profile_from_label(ds, {"product_id": "x", "start_time": "1978-12-10T15:09:40", "volume": "pvoro_bundle",
                                   "url": "", "product_type": "profile"}, tmp_path / "p.xml")
    assert prof.latitude == pytest.approx(-60.07) and prof.longitude == pytest.approx(94.93)
    np.testing.assert_allclose(prof.altitude_km[:2], [6146.0 - 6051.8, 6110.0 - 6051.8])
    assert np.isnan(prof.altitude_km[2]) and np.isnan(prof.temperature_k[2])
    np.testing.assert_allclose(prof.temperature_k[:2], [200.0, 226.0])
    # the spread of the three retrievals is a systematic uncertainty, not a random one
    assert "temperature_k" not in prof.uncertainty
    np.testing.assert_allclose(prof.systematic["temperature_k"][:2], [50.0, 1.0])
    np.testing.assert_allclose(prof.systematic["pressure_hpa"][1], 0.05, atol=1e-6)


def test_error_tables_in_supplemental_files_combine_in_quadrature(tmp_path):
    """Cassini Titan profiles: the profile file plus ephemeris (CE) and thermal-noise (WE)
    1-sigma error files with the same rows; number density in cm^-3, density in g/cm^3."""
    from veda.archives.profiles import profile_from_label
    def delimited(fname, names, units, rows, area="File_Area_Observational"):
        (tmp_path / fname).write_text("".join(", ".join(str(v) for v in r) + "\r\n" for r in rows), newline="")
        f = "".join(f"<Field_Delimited><name>{n}</name><field_number>{i + 1}</field_number><data_type>ASCII_Real</data_type>"
                    f"<unit>{u}</unit></Field_Delimited>" for i, (n, u) in enumerate(zip(names, units)))
        return (f"<{area}><File><file_name>{fname}</file_name></File><Table_Delimited><offset unit='byte'>0</offset>"
                f"<records>{len(rows)}</records><record_delimiter>Carriage-Return Line-Feed</record_delimiter>"
                f"<field_delimiter>Comma</field_delimiter><Record_Delimited>{f}</Record_Delimited></Table_Delimited></{area}>")
    main = delimited("P.TAB", ["RADIUS", "TEMPERATURE", "PRESSURE", "NUMBER_DENSITY", "MASS_DENSITY"],
                     ["KM", "KELVIN", "BAR", "1/CM**3", "GM/CM**3"],
                     [(2575.2, 93.0, 1.45, 1.2e20, 5.4e-3), (2620.0, 70.0, 0.10, 1.1e19, 5.0e-4)])
    err = ["TEMPERATURE ERROR BAR", "PRESSURE ERROR BAR", "DENSITY ERROR BAR"]
    ce = delimited("RSS_T1_R1_CE_X_14_E_16K.TAB", err, ["K", "BAR", "GM/CM**3"], [(0.3, 3e-4, 4e-7), (0.6, 3e-4, 1e-7)],
                   "File_Area_Observational_Supplemental")
    we = delimited("RSS_T1_R1_WE_X_14_E_16K.TAB", err, ["K", "BAR", "GM/CM**3"], [(0.4, 4e-4, 3e-7), (0.8, 4e-4, 1e-7)],
                   "File_Area_Observational_Supplemental")
    (tmp_path / "x.xml").write_text(
        '<?xml version="1.0"?><Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1"><Identification_Area>'
        "<logical_identifier>urn:nasa:pds:corsstpp:data:x</logical_identifier><title>t</title></Identification_Area>"
        f"{main}{ce}{we}</Product_Observational>")
    ds = get_dataset("corss-titan-neutral-profiles")
    prof = profile_from_label(ds, {"product_id": "x", "start_time": "2008-11-03T17:43:36", "volume": "v", "url": "",
                                   "product_type": "profile"}, tmp_path / "x.xml")
    np.testing.assert_allclose(prof.uncertainty["temperature_k"], [0.5, 1.0])          # 3-4-5
    np.testing.assert_allclose(prof.uncertainty["pressure_hpa"], [0.5, 0.5])            # bar -> hPa
    np.testing.assert_allclose(prof.uncertainty["density_measured"], [5e-4, np.sqrt(2) * 1e-4])  # g/cm3 -> kg/m3
    np.testing.assert_allclose(prof.derived["number_density_m3"], [1.2e26, 1.1e25])      # cm^-3 -> m^-3
    np.testing.assert_allclose(prof.derived["density_measured"], [5.4, 0.5])
    assert prof.altitude_km[0] == pytest.approx(2575.2 - 2574.7)


def test_saturn_error_bar_width_is_halved_and_zero_means_not_given(tmp_path):
    from veda.archives.profiles import profile_from_label
    rows = [(3000.0, 1.0e3, -8.0, 40.0), (2000.0, 2.0e3, -8.0, 0.0)]
    (tmp_path / "S.TAB").write_text("".join(", ".join(str(v) for v in r) + "\r\n" for r in rows), newline="")
    names = [("Altitude", "km"), ("Electron Density", "1/cm**3"), ("Latitude", "Degree"), ("Electron Density Error Bar", "1/cm**3")]
    f = "".join(f"<Field_Delimited><name>{n}</name><field_number>{i + 1}</field_number><data_type>ASCII_Real</data_type>"
                f"<unit>{u}</unit></Field_Delimited>" for i, (n, u) in enumerate(names))
    (tmp_path / "s.xml").write_text(
        '<?xml version="1.0"?><Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1"><Identification_Area>'
        "<logical_identifier>urn:nasa:pds:x:data:s</logical_identifier><title>t</title></Identification_Area>"
        "<File_Area_Observational><File><file_name>S.TAB</file_name></File><Table_Delimited><offset unit='byte'>0</offset>"
        "<records>2</records><record_delimiter>Carriage-Return Line-Feed</record_delimiter><field_delimiter>Comma</field_delimiter>"
        f"<Record_Delimited>{f}</Record_Delimited></Table_Delimited></File_Area_Observational></Product_Observational>")
    prof = profile_from_label(get_dataset("corss-saturn-ionosphere"),
                              {"product_id": "s", "start_time": "2005-05-03T06:55:20", "volume": "saturn_iono", "url": "",
                               "product_type": "profile"}, tmp_path / "s.xml")
    s = prof.uncertainty["electron_density_cm3"]
    assert s[0] == pytest.approx(20.0) and np.isnan(s[1])
    assert prof.raw_attributes["ALTITUDE_REFERENCE"].startswith("the 1-bar NAIF reference ellipsoid")


def test_every_dataset_mission_is_listed_on_its_bodies():
    """A body's mission list drives discovery and comparison: a data set whose mission is
    missing there can never be compared."""
    from veda.core.registry import BODIES
    for d in DATASETS:
        for b in d.body_ids:
            assert b in BODIES, (d.id, b)
            assert d.mission_id in BODIES[b].supported_missions, (d.id, b, d.mission_id)


@pytest.mark.parametrize("volume,path", [
    ("MEX-M-MRS-5-OCC-V1.0", "DATA/LEVEL04/2004/ITEM.LBL"),
    ("vol", "./a//b/c.lbl"),
    ("", "x/y.xml"),
    ("v", "https://pds.example.org/archive/bundle/data/p.xml"),
    ("v" * 60, "d/" * 40 + "long.lbl"),
])
def test_local_key_matches_local_label_path(volume, path):
    from veda.archives import catalog
    ref = catalog.local_label_path("ds", volume, path).relative_to(catalog.PRODUCT_ROOT / "ds").as_posix()
    assert catalog._local_key(volume, path) == ref


def test_downloaded_only_finds_label_and_repository_products():
    from veda.archives import catalog
    ds_pds = next(d for d in DATASETS if not d.repository and not d.service and not d.portal_only)
    ds_rep = next(d for d in DATASETS if d.repository)
    rows = [
        dict(dataset_id=ds_pds.id, product_id="on_disk", volume="VOL1", path="DATA/ON_DISK.LBL"),
        dict(dataset_id=ds_pds.id, product_id="not_on_disk", volume="VOL1", path="DATA/MISSING.LBL"),
        dict(dataset_id=ds_rep.id, product_id="rep_on_disk", volume="repository", path="rep_on_disk"),
        dict(dataset_id=ds_rep.id, product_id="rep_missing", volume="repository", path="rep_missing"),
    ]
    with catalog._db_lock, catalog._connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
            "'2010-01-01T00:00:00','2010-01-01T00:00:00','VENUS','TEST','profile','{}')", rows)
    label = catalog.local_label_path(ds_pds.id, "VOL1", "DATA/ON_DISK.LBL")
    label.parent.mkdir(parents=True, exist_ok=True)
    label.write_text("PDS_VERSION_ID = PDS3\nEND\n")
    csv = catalog._repository_csv(ds_rep, "rep_on_disk")
    csv.parent.mkdir(parents=True, exist_ok=True)
    csv.write_text("altitude [km]\n1\n")
    try:
        got = {p["product_id"] for p in catalog.downloaded_products([ds_pds.id, ds_rep.id])}
        assert got >= {"on_disk", "rep_on_disk"} and not got & {"not_on_disk", "rep_missing"}
        r = catalog.search(catalog.SearchQuery(dataset_ids=[ds_pds.id, ds_rep.id], downloaded_only=True, limit=50))
        ids = {p["product_id"] for p in r["products"]}
        assert {"on_disk", "rep_on_disk"} <= ids and not ids & {"not_on_disk", "rep_missing"}
        assert all(p["downloaded"] for p in r["products"])
    finally:
        with catalog._db_lock, catalog._connect() as conn:
            conn.executemany("DELETE FROM products WHERE dataset_id=:dataset_id AND product_id=:product_id", rows)
        label.unlink(); csv.unlink()


@pytest.mark.parametrize("name,kind", [
    ("M65RSR0L04_AIO_041391512_05.LBL", "other"),      # occultation geometry text, not a table
    ("M32ICL2L04_IIO_043622341_05.LBL", "other"),
    ("M32ICL2L04_AIX_040931105_60.LBL", "profile"),
    ("M32ICL2L04_IIX_040931105_60.LBL", "profile"),
    ("M32ICL2L04_IID_040931105_60.LBL", "profile"),
])
def test_mex_occultation_geometry_files_are_not_profiles(name, kind):
    assert get_dataset("mex-m-mrs-5-occ").classify(f"DATA/X/{name}")[1] == kind


def test_changed_rules_reclassify_catalogued_rows():
    from veda.archives import catalog
    row = dict(dataset_id="mex-m-mrs-5-occ", product_id="M65RSR0L04_AIO_041391512_05", volume="V",
               path="DATA/X/M65RSR0L04_AIO_041391512_05.LBL")
    with catalog._db_lock, catalog._connect() as conn:
        conn.execute("INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                     "'2004-05-18T15:26:42','','MARS','L4 neutral atmosphere profile','profile','{}')", row)
        conn.execute("DELETE FROM meta WHERE key='rules:mex-m-mrs-5-occ'")      # as indexed by an older VEDA
        catalog._reclassify(conn)
        kind = conn.execute("SELECT kind FROM products WHERE dataset_id=? AND product_id=?",
                            (row["dataset_id"], row["product_id"])).fetchone()[0]
        conn.execute("DELETE FROM products WHERE dataset_id=? AND product_id=?", (row["dataset_id"], row["product_id"]))
    assert kind == "other"


def test_aerobraking_pass_is_two_profiles_with_corrected_density_unit(tmp_path):
    """Mars Odyssey accelerometer files hold a whole pass through periapsis.  Each is listed
    as an inbound and an outbound profile (different places, they would zigzag as one),
    both at the periapsis time, and the densities, labelled kg/m^3, are kg/km^3."""
    import json
    from veda.archives import catalog
    from veda.archives.profiles import profile_from_label
    ds = get_dataset("ody-m-accel-5-derived-v1.0")
    row = {"dataset_id": ds.id, "product_id": "ACCPROFP100", "volume": "odya_1001",
           "path": "DATA/PROF/ACCPROFP100.LBL", "start_time": "2001-12-12T15:11:59.702", "stop_time": "",
           "target": "MARS", "product_type": ds.classify("DATA/PROF/ACCPROFP100.LBL")[0], "kind": "profile",
           "extra": "{}"}
    legs = catalog._pass_legs(ds, row)
    assert [r["product_id"] for r in legs] == ["ACCPROFP100_IN", "ACCPROFP100_OUT"]
    assert [json.loads(r["extra"])["LEG"] for r in legs] == ["inbound", "outbound"]
    assert catalog._pass_legs(ds, {**row, "kind": "other"}) == [{**row, "kind": "other"}]
    # rows as in the archive: time after periapsis, radial distance (km), latitude, density
    t = [-502.0, -100.0, -50.0, 0.0, 50.0, 100.0]
    r = [3800.0, 3510.0, 3490.0, 3480.0, 3492.0, 3515.0]
    lat = [80.0, 78.0, 77.0, 76.0, 74.0, 72.0]
    rho = [0.0, 8.0, 30.0, 60.0, 25.0, 7.0]          # kg/km^3; 0 = null
    names = ["TIME_AFTER_PERI", "RADIAL_DIST", "LATITUDE", "RHO7", "SRHO7"]
    units = ["SECOND", "KILOMETER", "DEGREES NORTH", "KILOGRAM PER CUBIC METER", "KILOGRAM PER CUBIC METER"]
    lines = "".join("".join(f"{v:14.5f}" for v in vals) + "\r\n"
                    for vals in zip(t, r, lat, rho, [1.0] * 6))
    (tmp_path / "ACCPROFP100.TAB").write_text(lines, newline="")
    cols = "".join(f"""  OBJECT = COLUMN
    NAME = {n}
    DATA_TYPE = ASCII_REAL
    START_BYTE = {1 + 14 * i}
    BYTES = 14
    UNIT = "{u}"
  END_OBJECT = COLUMN
""" for i, (n, u) in enumerate(zip(names, units)))
    (tmp_path / "ACCPROFP100.LBL").write_text(f"""PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 72
^TABLE = "ACCPROFP100.TAB"
OBJECT = TABLE
  INTERCHANGE_FORMAT = ASCII
  ROWS = 6
  COLUMNS = 5
  ROW_BYTES = 72
{cols}END_OBJECT = TABLE
END
""")
    profs = {}
    for leg in ("inbound", "outbound"):
        prod = {"product_id": "ACCPROFP100_" + leg, "start_time": row["start_time"], "leg": leg,
                "volume": "odya_1001", "url": "", "product_type": "profile"}
        profs[leg] = profile_from_label(ds, prod, tmp_path / "ACCPROFP100.LBL")
    inb, out = profs["inbound"], profs["outbound"]
    np.testing.assert_allclose(inb.altitude_km, np.array([3800.0, 3510.0, 3490.0]) - 3389.5)
    np.testing.assert_allclose(out.altitude_km, np.array([3480.0, 3492.0, 3515.0]) - 3389.5)
    np.testing.assert_allclose(inb.derived["density_measured"], [np.nan, 8e-9, 3e-8])
    np.testing.assert_allclose(out.derived["density_measured"], [6e-8, 2.5e-8, 7e-9])
    np.testing.assert_allclose(out.uncertainty["density_measured"], [1e-9] * 3)
    assert inb.time_utc == out.time_utc == "2001-12-12T15:20:21.702"     # start + 502 s
    assert inb.latitude == 78.0 and out.latitude == 74.0


def test_spheroid_altitudes_to_sphere():
    """Heights above a spheroid along its normal: a + h at the equator, b + h at the poles,
    and the planetocentric latitude is smaller in size than the geodetic one."""
    from veda.archives.profiles import above_spheroid
    a, f = 3396.19, 5.88600756e-3
    r, lat = above_spheroid([100.0, 100.0, 100.0], [0.0, 90.0, -45.0], a, f)
    np.testing.assert_allclose(r[:2], [a + 100.0, a * (1 - f) + 100.0])
    assert lat[0] == 0.0 and lat[1] == pytest.approx(90.0)
    assert -45.0 < lat[2] < -44.6


def test_mro_accelerometer_pass_attached_label_and_misplaced_columns(tmp_path):
    """MRO accelerometer profiles: the label is at the top of the data file, its columns
    are in LABEL/PROFILE.FMT, whose byte positions start every column after the first
    one byte early; altitudes are above the areodetic spheroid and densities in kg/km^3.
    Rows from the archive's L2P150.TAB."""
    from veda.archives import catalog
    from veda.archives.profiles import profile_from_label
    from veda.readers.pds3_reader import read_pds3_table
    ds = get_dataset("mro-m-accel-5-profile-v1.0")
    names = ["TIME_FROM_PERIAPSIS", "AREODETIC LATITUDE", "LONGITUDE", "LOCAL_SOLAR_TIME", "SOLAR_ZENITH_ANGLE",
             "1_SEC_ALTITUDE", "1_SEC_AVG_DENSITY", "1_SEC_SIGMA", "39_SEC_ALTITUDE", "39_SEC_AVG_DENSITY",
             "39_SEC_SIGMA"]
    starts = [1, 8, 14, 21, 26, 32, 39, 47, 54, 61, 69]          # as in the archive's PROFILE.FMT
    sizes = [7, 5, 6, 4, 5, 6, 7, 6, 6, 7, 6]
    units = ["SECONDS", "DEGREES", "DEGREES", "HOURS", "DEGREES", "KILOMETERS", "KG/KM^3", "KG/KM^3",
             "KILOMETERS", "KG/KM^3", "KG/KM^3"]
    (tmp_path / "LABEL").mkdir()
    (tmp_path / "LABEL" / "PROFILE.FMT").write_text("".join(
        f' OBJECT = COLUMN\n  NAME = "{n}"\n  DATA_TYPE = ASCII_REAL\n  UNIT = "{u}"\n'
        f'  START_BYTE = {s}\n  BYTES = {b}\n END_OBJECT = COLUMN\n\n'
        for n, s, b, u in zip(names, starts, sizes, units)))
    rows = [" -212.7 -73.1  206.7  3.9 122.7 151.16   0.020  0.036 149.91   0.015  0.006",
            "  -18.7 -85.9  164.5  1.1 118.6 100.71  39.863  0.031 100.85  39.928  0.557",
            "  211.3 -75.4   48.1 17.4 111.5   -1        -1     -1  149.19   0.034  0.011",
            "  212.3 -75.3   48.1 17.4 111.4 151.14   0.022  0.027 149.72   0.032  0.010"]
    label = ["PDS_VERSION_ID = PDS3", "RECORD_TYPE = FIXED_LENGTH", "RECORD_BYTES = 80", "^TABLE = 13",
             'PRODUCT_ID = "ORBIT_PROFILE_L2P150"', "OBJECT = TABLE", " ROWS = 4", " INTERCHANGE_FORMAT = ASCII",
             " COLUMNS = 11", ' ^STRUCTURE = "PROFILE.FMT"', "END_OBJECT = TABLE", "END"]
    data_dir = tmp_path / "DATA" / "PROFILE_DATA" / "P100_199"
    data_dir.mkdir(parents=True)
    tab = data_dir / "L2P150.TAB"
    tab.write_text("".join(line.ljust(78) + "\r\n" for line in label + rows), newline="")
    tbl = read_pds3_table(str(tab))
    np.testing.assert_allclose(tbl.columns["AREODETIC LATITUDE"], [-73.1, -85.9, -75.4, -75.3])
    np.testing.assert_allclose(tbl.columns["1_SEC_AVG_DENSITY"], [0.02, 39.863, -1, 0.022])
    # index rows: inbound and outbound legs, and files of one name in many folders kept apart
    idx = [{"dataset_id": ds.id, "product_id": "ACCEL", "path": f"DATA/RAW_DATA/P001_099/P0{n}/ACCEL.TAB",
            "extra": f'{{"PRODUCT_ID": "Y_ACCELEROMETER_DATA_P0{n}"}}'} for n in (16, 17)]
    catalog._unique_product_ids(idx)
    assert [r["product_id"] for r in idx] == ["Y_ACCELEROMETER_DATA_P016", "Y_ACCELEROMETER_DATA_P017"]
    assert ds.classify("DATA/PROFILE_DATA/P100_199/L2P150.TAB")[1] == "profile"
    assert ds.classify("DATA/RAW_DATA/P001_099/P016/ACCEL.TAB")[1] == "timeseries"
    profs = {}
    for leg in ("inbound", "outbound"):
        prod = {"product_id": "L2P150_" + leg, "start_time": "2006-07-12T05:42:59.00", "leg": leg,
                "volume": "MROA_0001", "url": "", "product_type": "profile"}
        profs[leg] = profile_from_label(ds, prod, tab)
    inb, out = profs["inbound"], profs["outbound"]
    assert inb.time_utc == out.time_utc == "2006-07-12T05:46:31.700"        # start + 212.7 s
    np.testing.assert_allclose(inb.derived["density_measured"], [2.0e-11, 3.9863e-8])
    np.testing.assert_allclose(inb.uncertainty["density_measured"], [3.6e-11, 3.1e-11])
    np.testing.assert_allclose(out.derived["density_measured"], [np.nan, 2.2e-11])     # -1: no data
    # 100.71 km above the spheroid at areodetic latitude -85.9 deg is 3477.0 km from the centre
    r = np.hypot((3396.19 / np.sqrt(1 - 0.011737 * np.sin(np.radians(85.9)) ** 2) + 100.71) * np.cos(np.radians(85.9)),
                 (3396.19 / np.sqrt(1 - 0.011737 * np.sin(np.radians(85.9)) ** 2) * (1 - 0.011737) + 100.71)
                 * np.sin(np.radians(85.9)))
    assert inb.altitude_km[1] == pytest.approx(r - 3389.5, abs=0.01)
    assert inb.altitude_km[1] == pytest.approx(87.5, abs=0.2)
    assert -85.9 < inb.track["latitude"][1] < -85.8                     # planetocentric
    assert np.isnan(out.altitude_km[0]) and out.altitude_km[1] > 0
    assert "spheroid" in inb.raw_attributes["ALTITUDE_REFERENCE"]


def test_negative_uncertainties_are_fill(tmp_path):
    """The Phoenix entry profile writes -1 in its SIGMA columns where it has no value: a
    1-sigma uncertainty is never negative, so those are missing, not -1 K."""
    from veda.archives.profiles import profile_from_label
    ds = get_dataset("phx-m-ase-5-edl-rdr-v1.0")
    names = ["RADIAL_DISTANCE", "TEMP", "SIGMA_TEMP", "PRESS", "SIGMA_PRESS", "RHO", "SIGMA_RHO"]
    units = ["KILOMETER", "K", "K", "PASCAL", "PASCAL", "KG/M**3", "KG/M**3"]
    rows = [(3400.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0),
            (3430.0, 150.0, 2.0, 30.0, 0.5, 1.0e-3, 2.0e-5),
            (3440.0, 145.0, 3.0, 15.0, 0.4, 5.0e-4, 1.0e-5)]
    (tmp_path / "PHX.TAB").write_text("".join("".join(f"{v:14.6g}" for v in r) + "\r\n" for r in rows), newline="")
    cols = "".join(f"  OBJECT = COLUMN\n    NAME = {n}\n    DATA_TYPE = ASCII_REAL\n    START_BYTE = {1 + 14 * i}\n"
                   f"    BYTES = 14\n    UNIT = \"{u}\"\n  END_OBJECT = COLUMN\n" for i, (n, u) in enumerate(zip(names, units)))
    (tmp_path / "PHX.LBL").write_text(f"PDS_VERSION_ID = PDS3\nRECORD_TYPE = FIXED_LENGTH\nRECORD_BYTES = 100\n"
                                      f"^TABLE = \"PHX.TAB\"\nOBJECT = TABLE\n  ROWS = 3\n  COLUMNS = 7\n  ROW_BYTES = 100\n"
                                      f"{cols}END_OBJECT = TABLE\nEND\n")
    prod = {"product_id": "PHX", "start_time": "2008-05-25T23:30:00", "volume": "phxase_0002", "url": "",
            "product_type": "profile"}
    p = profile_from_label(ds, prod, tmp_path / "PHX.LBL")
    for key in ("temperature_k", "pressure_hpa", "density_measured"):
        assert np.isnan(p.uncertainty[key][0]), key
    np.testing.assert_allclose(p.uncertainty["temperature_k"][1:], [2.0, 3.0])
    np.testing.assert_allclose(p.uncertainty["density_measured"][1:], [2.0e-5, 1.0e-5])


@pytest.mark.parametrize("unit,factor", [
    ("PASCAL", 0.01), ("PA", 0.01), ("HPA", 1.0), ("MBAR", 1.0), ("MILLIBAR", 1.0), ("BAR", 1000.0),
    ("KPA", 10.0), ("KILOPASCAL", 10.0), ("MICROBAR", 1e-3), ("NBAR", 1e-6), ("DYN/CM**2", 1e-3), ("hPa", 1.0),
])
def test_pressure_units_to_hpa(unit, factor):
    """Pressures in kPa, microbar, nanobar or dyn/cm^2 were all taken for pascals."""
    np.testing.assert_allclose(_to_hpa(np.array([2.0]), unit), [2.0 * factor])


def test_repository_pages_are_linked_without_the_trailing_slash():
    """Zenodo and BIRA-IASB answer 404 for record pages ending in a slash, which the
    product links of the archive browser and the Data & Licenses table used; archive
    folders keep theirs."""
    from veda.archives.catalog import product_dict
    from veda.archives.datasets import get_dataset
    for did, page in (("vex-vera-gramigna2023", "https://zenodo.org/records/20056665"),
                      ("vex-vera-fsi-imamura", "https://zenodo.org/records/4621070"),
                      ("vex-soir-co2-temperature",
                       "https://data.aeronomie.be/dataset/venus-atmospheric-profiles-from-spicav-soir-vexv23")):
        ds = get_dataset(did)
        assert ds.base_url == page + "/" and ds.to_dict()["url"] == page
        row = {"dataset_id": did, "product_id": "x", "volume": "repository", "path": "x.csv", "start_time": "",
               "stop_time": "", "target": "VENUS", "product_type": "Profile", "kind": "profile", "extra": "{}"}
        assert product_dict(row)["url"] == page
    mgs = get_dataset("mgs-m-rss-5-sdp-v1.0")
    assert mgs.to_dict()["url"] == mgs.base_url and mgs.base_url.endswith("/")


def test_pds4_table_whose_label_is_a_byte_and_a_column_off():
    """MAVEN accelerometer profiles (archive files): the label puts the table at byte 1
    where it starts at 0, and gives the spacecraft mass and the bias noise 7 characters
    where they take 8.  That read the first row's -300 s as 300 s, 1055.214 kg as 1055.21
    and the bias noise 0.008 kg/km^3 as 0.00 (the archive's user advisory gives 0.0077611
    for this pass, P03302, and a peak density near 5.07 kg/km^3 in its figure 3)."""
    from pathlib import Path

    from veda.readers.pds4_reader import read_pds4_table
    t = read_pds4_table(str(Path(__file__).parent / "data" / "maven_acc" / "mvn_acc_l3_pro-acc-p03302_20160610_v02_r01.xml"))
    c = t.columns
    assert t.row_count() == 601 and c["Seconds from Periapsis"][0] == -300.0 and c["AREODETIC ALTITUDE"][0] == 184.334
    assert np.all(c["SPACECRAFT MASS"] == 1055.214) and np.all(c["BIAS NOISE 1-SIGMA"] == 0.008)
    assert np.all(np.diff(c["Seconds from Periapsis"]) == 1.0) and np.nanmax(c["1-SEC DENSITY"]) == 5.065
