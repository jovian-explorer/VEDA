"""Archive engine: index parsing, pointers, times and units (offline, no network)."""
from __future__ import annotations

import numpy as np

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
