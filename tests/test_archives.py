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


def test_comparison_warns_when_vertical_references_differ():
    from veda.analysis.atmospheric import _vertical_reference_warning
    sphere = {"mission_id": "vex", "altitude_reference": "a sphere of radius 6051.8 km (from the radius column)"}
    sphere2 = {"mission_id": "magellan", "altitude_reference": "a sphere of radius 6051.8 km (archive ...)"}
    onebar = {"mission_id": "galileo", "altitude_reference": "the 1-bar pressure level"}
    assert _vertical_reference_warning([sphere, sphere2]) == ""
    assert _vertical_reference_warning([sphere, {"mission_id": "upload", "altitude_reference": ""}]) == ""
    assert "1-bar" in _vertical_reference_warning([sphere, onebar])


def test_pds4_header_table_fill_values_and_bracketing_uncertainty(tmp_path):
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
    np.testing.assert_allclose(prof.uncertainty["temperature_k"][:2], [50.0, 1.0])
    np.testing.assert_allclose(prof.uncertainty["pressure_hpa"][1], 0.05, atol=1e-6)


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
