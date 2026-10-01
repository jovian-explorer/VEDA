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


def test_netcdf_map_and_profile_table(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    f = tmp_path / "sample.nc"
    with netCDF4.Dataset(f, "w") as ds:
        ds.createDimension("time", 1); ds.createDimension("lat", 4); ds.createDimension("lon", 8)
        ds.createDimension("alt", 5)
        t = ds.createVariable("time", "f8", ("time",)); t.units = "hours since 2000-01-01 00:00:00"; t[:] = [24.0]
        la = ds.createVariable("lat", "f4", ("lat",)); la[:] = [-67.5, -22.5, 22.5, 67.5]
        lo = ds.createVariable("lon", "f4", ("lon",)); lo[:] = np.arange(8) * 45 + 22.5
        rad = ds.createVariable("radiance", "f4", ("time", "lat", "lon"), fill_value=-1.0); rad.units = "W/m2/sr/m"
        data = np.arange(32, dtype="f4").reshape(1, 4, 8); data[0, 0, 0] = -1.0; rad[:] = data
        z = ds.createVariable("alt", "f4", ("alt",)); z[:] = [10, 20, 30, 40, 50]
        tk = ds.createVariable("temperature", "f4", ("alt",)); tk.units = "K"; tk[:] = [220, 210, 200, 190, 185]
    p = open_product(str(f))
    img = next(o for o in p.objects if o.kind == "image")
    assert img.name == "radiance" and img.extent["x"][2] == "lon" and img.extent["y"][0] == -67.5
    a = img.read_array()
    assert a.shape == (1, 4, 8) and np.isnan(a[0, 0, 0]) and a[0, 3, 7] == 31
    tab = next(o for o in p.objects if o.kind == "table")
    d = tab.read_table()
    assert list(d["alt"]) == [10, 20, 30, 40, 50] and d["temperature"][2] == 200


_PDS4_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Identification_Area><logical_identifier>urn:nasa:pds:test:data:x</logical_identifier><title>t</title></Identification_Area>
  <File_Area_Observational>
    <File><file_name>{name}</file_name></File>
"""


def test_floats_in_the_opposite_byte_order_to_the_label_are_repaired(tmp_path):
    """Juno JIRAM RDR spectra are labelled MSB but written LSB."""
    rng = np.random.default_rng(1)
    spec = (rng.random((64, 32)) * 0.5 + 1e-3).astype("<f4")      # radiances, W/(m2 sr um)
    (tmp_path / "s.dat").write_bytes(spec.tobytes())
    (tmp_path / "s.xml").write_text(_PDS4_HEAD.format(name="s.dat") + """
    <Table_Binary><offset unit="byte">0</offset><records>64</records>
      <Record_Binary><fields>0</fields><groups>1</groups><record_length unit="byte">128</record_length>
        <Group_Field_Binary><repetitions>32</repetitions><fields>1</fields><groups>0</groups>
          <group_location unit="byte">1</group_location><group_length unit="byte">128</group_length>
          <Field_Binary><name>BAND</name><field_location unit="byte">1</field_location>
            <data_type>IEEE754MSBSingle</data_type><field_length unit="byte">4</field_length></Field_Binary>
        </Group_Field_Binary></Record_Binary></Table_Binary>
  </File_Area_Observational></Product_Observational>""")
    v = open_product(str(tmp_path / "s.xml")).objects[0].read_table()["BAND"]
    np.testing.assert_allclose(v, spec, rtol=1e-6)


def test_correct_byte_order_is_left_alone(tmp_path):
    wide = np.geomspace(1e-6, 1e6, 1000).astype(">f4")             # 12 decades of real dynamic range
    from veda.readers.product import _fix_byte_order
    assert _fix_byte_order(wide).dtype == wide.dtype


def test_text_stream_product_opens_as_text(tmp_path):
    log = "".join(f"2016-01-01T00:{i:02d}:00 FSW event {i}\r\n" for i in range(50))
    (tmp_path / "log.txt").write_bytes(log.encode())
    (tmp_path / "log.xml").write_text(_PDS4_HEAD.format(name="log.txt") + """
    <Stream_Text><name>Operations Log</name><offset unit="byte">0</offset>
      <parsing_standard_id>ASCII_String</parsing_standard_id>
      <record_delimiter>carriage-return line-feed</record_delimiter></Stream_Text>
  </File_Area_Observational></Product_Observational>""")
    o = open_product(str(tmp_path / "log.xml")).objects[0]
    assert o.kind == "text" and o.shape == (50,)
    text, truncated = o.read_text()
    assert text.startswith("2016-01-01T00:00:00 FSW event 0\n") and not truncated
    assert o.read_text(1000)[1] is True
    with pytest.raises(ProductError):
        o.read_array()


def test_pds3_text_object_when_nothing_else_is_readable(tmp_path):
    label = """PDS_VERSION_ID = PDS3
^TEXT = "notes.txt"
OBJECT = TEXT
  PUBLICATION_DATE = 2020-01-01
  NOTE = "Instrument notes"
END_OBJECT = TEXT
END
"""
    lbl = _write(tmp_path, "notes.txt", label, b"Line one\r\nLine two\r\n")
    o = open_product(str(lbl)).objects[0]
    assert o.kind == "text" and o.read_text()[0] == "Line one\nLine two\n"
