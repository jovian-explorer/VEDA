"""The generic product reader (veda.readers.product): every payload's data as tables, images or cubes."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from veda.readers.product import ProductError, iso_time, open_product

SAMPLES = Path(__file__).resolve().parents[1] / "src" / "veda" / "sampledata"


def test_ascii_profile_table_with_times():
    p = open_product(str(SAMPLES / "mars_express" / "M32ICL2L04_AIX_040931105_60.LBL"))
    t = p.objects[0]
    assert t.kind == "table" and t.shape[0] == 354
    assert any(f.name == "UTC TIME" and f.kind == "time" for f in t.fields)
    d = t.read_table(["UTC TIME", "RADIUS"])
    assert d["UTC TIME"][0].startswith("2004-04-02T11:44")
    assert 3300 < np.nanmean(d["RADIUS"]) < 3500


def test_pds4_delimited_table():
    p = open_product(str(SAMPLES / "titan_cassini_rss" / "s19tioc2006078_0107_n_sx_14_titan_edp_v01_r00.xml"))
    assert p.format == "PDS4"
    d = p.objects[0].read_table(limit=5)
    assert len(d["ELECDEN"]) == 5


def test_pds3_label_for_fits_backplanes_and_lazy_reads():
    p = open_product(str(SAMPLES / "venus_akatsuki" / "uvi_20181105_080112_283_geo_v10.lbl"))
    names = [o.name for o in p.objects]
    assert "LATITUDE_IMAGE" in names and all(o.kind == "image" for o in p.objects)
    lat = p.get("LATITUDE_IMAGE")
    small = lat.read_array(step=4)
    assert small.shape == (1, 256, 256) and small.dtype == np.float32
    assert -90 <= np.nanmin(small) and np.nanmax(small) <= 90


def test_iso_time_formats():
    assert iso_time("2004-160T15:43:00.5") == "2004-06-08T15:43:00.5"
    assert iso_time("2006 MAR 19 00:00:13.5") == "2006-03-19T00:00:13.5"
    assert iso_time("2010-01-02 03:04:05Z") == "2010-01-02T03:04:05"


def _write(tmp: Path, name: str, label: str, data: bytes) -> Path:
    (tmp / name).write_bytes(data)
    lbl = tmp / (Path(name).stem + ".lbl")
    lbl.write_text(label)
    return lbl


def test_binary_table_with_vector_and_container(tmp_path):
    rows = 5
    rec = np.zeros(rows, dtype=[("t", ">f8"), ("spec", ">i2", (4,)), ("c", [("a", "<f4"), ("b", "<u2")], (2,))])
    rec["t"] = np.arange(rows) * 10.0
    rec["spec"] = np.arange(rows * 4).reshape(rows, 4)
    rec["c"]["a"] = [[1.5, 2.5]] * rows
    rec["c"]["b"] = [[7, 65535]] * rows          # 65535 is the declared missing value
    row_bytes = rec.dtype.itemsize
    label = f"""PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = {row_bytes}
^TABLE = "data.dat"
OBJECT = TABLE
  INTERCHANGE_FORMAT = BINARY
  ROWS = {rows}
  ROW_BYTES = {row_bytes}
  COLUMNS = 3
  OBJECT = COLUMN
    NAME = ET
    DATA_TYPE = IEEE_REAL
    START_BYTE = 1
    BYTES = 8
  END_OBJECT = COLUMN
  OBJECT = COLUMN
    NAME = COUNTS
    DATA_TYPE = MSB_INTEGER
    START_BYTE = 9
    BYTES = 8
    ITEMS = 4
    ITEM_BYTES = 2
  END_OBJECT = COLUMN
  OBJECT = CONTAINER
    NAME = PAIR
    START_BYTE = 17
    BYTES = 6
    REPETITIONS = 2
    OBJECT = COLUMN
      NAME = A
      DATA_TYPE = PC_REAL
      START_BYTE = 1
      BYTES = 4
    END_OBJECT = COLUMN
    OBJECT = COLUMN
      NAME = B
      DATA_TYPE = LSB_UNSIGNED_INTEGER
      START_BYTE = 5
      BYTES = 2
      MISSING_CONSTANT = 65535
    END_OBJECT = COLUMN
  END_OBJECT = CONTAINER
END_OBJECT = TABLE
END
"""
    lbl = _write(tmp_path, "data.dat", label, rec.tobytes())
    t = open_product(str(lbl)).objects[0]
    d = t.read_table()
    assert np.allclose(d["ET"], rec["t"])
    assert d["COUNTS"].shape == (rows, 4) and d["COUNTS"][2, 3] == 11
    assert np.allclose(d["PAIR.A"][:, 0], 1.5) and np.allclose(d["PAIR.A"][:, 1], 2.5)
    assert d["PAIR.B"][0, 0] == 7 and np.isnan(d["PAIR.B"][0, 1])


def test_image_with_prefix_and_scaling(tmp_path):
    lines, samples, prefix = 6, 8, 4
    img = (np.arange(lines * samples, dtype=">u2").reshape(lines, samples))
    raw = b"".join(b"\0" * prefix + row.tobytes() for row in img)
    label = f"""PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = {prefix + samples * 2}
^IMAGE = "img.img"
OBJECT = IMAGE
  LINES = {lines}
  LINE_SAMPLES = {samples}
  SAMPLE_TYPE = MSB_UNSIGNED_INTEGER
  SAMPLE_BITS = 16
  LINE_PREFIX_BYTES = {prefix}
  SCALING_FACTOR = 0.5
  OFFSET = 1.0
END_OBJECT = IMAGE
END
"""
    lbl = _write(tmp_path, "img.img", label, raw)
    o = open_product(str(lbl)).objects[0]
    a = o.read_array()
    assert a.shape == (1, lines, samples)
    assert a[0, 2, 3] == pytest.approx(img[2, 3] * 0.5 + 1.0)
    assert o.read_array(lines=slice(1, 3), samples=slice(2, 4)).shape == (1, 2, 2)


def test_qube_band_line_sample_order(tmp_path):
    bands, samples, lines = 3, 4, 2
    cube = np.arange(bands * samples * lines, dtype="<f4").reshape(lines, samples, bands)   # BIP
    label = f"""PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 512
^QUBE = "c.qub"
OBJECT = QUBE
  AXES = 3
  AXIS_NAME = (BAND, SAMPLE, LINE)
  CORE_ITEMS = ({bands}, {samples}, {lines})
  CORE_ITEM_BYTES = 4
  CORE_ITEM_TYPE = PC_REAL
  SUFFIX_ITEMS = (0, 0, 0)
END_OBJECT = QUBE
END
"""
    lbl = _write(tmp_path, "c.qub", label, cube.tobytes())
    o = open_product(str(lbl)).objects[0]
    assert o.kind == "cube" and o.shape == (bands, lines, samples)
    a = o.read_array()
    assert a[2, 1, 3] == cube[1, 3, 2]


def test_raw_file_without_layout_gives_a_clear_message(tmp_path):
    label = """PDS_VERSION_ID = PDS3
^FILE = "raw.dat"
OBJECT = FILE
  RECORD_TYPE = UNDEFINED
END_OBJECT = FILE
END
"""
    lbl = _write(tmp_path, "raw.dat", label, b"\1\2\3")
    with pytest.raises(ProductError, match="raw bytes"):
        open_product(str(lbl))


def test_netcdf_profile_table():
    nc = sorted((SAMPLES / "earth_cosmic2").glob("atmPrf_*"))
    if not nc:
        pytest.skip("no COSMIC-2 sample")
    p = open_product(str(nc[0]))
    t = next(o for o in p.objects if o.kind == "table")
    d = t.read_table(limit=10)
    assert "MSL_alt" in d and len(d["MSL_alt"]) == 10
