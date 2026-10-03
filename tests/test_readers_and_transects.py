"""Verification tests for VEDA PDS3 and FITS scientific readers and 1D image transects.

Validates:
- All contrast stretch methods: zscale, percentile, linear, log, sqrt, asinh, histeq
- Robustness against edge cases (uniform arrays, negative pixel values, extreme outliers)
- 1D photometric line transects (horizontal, vertical, diagonal, boundary clipping)
- 60-bin image histogram and monotonic cumulative distribution functions (CDF)
- PDS3 fixed-width and comma-delimited table reading with sentinel value handling
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pytest


from veda.readers.fits_reader import (
    apply_contrast_stretch,
    compute_image_histogram,
    extract_photometric_transect,
    render_to_png,
)
from veda.readers.pds3_reader import read_pds3_table, Pds3Table


# ===========================================================================
# 1. FITS CONTRAST STRETCH & RASTER PIPELINE TESTS
# ===========================================================================

def test_contrast_stretch_all_algorithms():
    """Verify each contrast stretch algorithm normalizes pixel values into [0.0, 1.0]."""
    np.random.seed(101)
    data = np.random.exponential(scale=50.0, size=(100, 100)).astype(np.float32)
    data[20:30, 20:30] += 500.0  # high-intensity feature

    algorithms = ["zscale", "percentile", "linear", "log", "sqrt", "asinh", "histeq"]
    for alg in algorithms:
        stretched = apply_contrast_stretch(data, stretch_method=alg)
        assert stretched.shape == data.shape
        assert np.isfinite(stretched).all(), f"Non-finite values produced by {alg}"
        assert stretched.min() >= -1e-6, f"Values below 0 in {alg}: {stretched.min()}"
        assert stretched.max() <= 1.0 + 1e-6, f"Values above 1 in {alg}: {stretched.max()}"


def test_contrast_stretch_flat_uniform_image():
    """Verify contrast stretch does not divide by zero on flat constant images."""
    flat = np.full((64, 64), 42.0, dtype=np.float32)
    for alg in ["zscale", "percentile", "linear", "log", "sqrt", "asinh"]:
        stretched = apply_contrast_stretch(flat, stretch_method=alg)
        assert np.isfinite(stretched).all()
        assert (stretched >= 0.0).all() and (stretched <= 1.0).all()


def test_contrast_stretch_negative_and_zero_values():
    """Verify log and sqrt stretches handle zero and negative background noise safely."""
    noisy = np.random.normal(loc=0.0, scale=10.0, size=(64, 64)).astype(np.float32)
    # Ensure some values are strictly negative
    assert (noisy < 0).any()

    for alg in ["log", "sqrt", "asinh"]:
        stretched = apply_contrast_stretch(noisy, stretch_method=alg)
        assert np.isfinite(stretched).all()
        assert stretched.min() >= 0.0
        assert stretched.max() <= 1.0


def test_render_to_png_multiple_colormaps():
    """Verify rendering PNG image streams across scientific colormaps."""
    data = np.linspace(0, 100, 64 * 64, dtype=np.float32).reshape((64, 64))
    colormaps = ["inferno", "viridis", "plasma", "magma", "gray"]
    for cm in colormaps:
        png_bytes = render_to_png(data, stretch_method="zscale", colormap=cm)
        assert isinstance(png_bytes, bytes)
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(png_bytes) > 200


# ===========================================================================
# 2. 1D PHOTOMETRIC TRANSECT TESTS
# ===========================================================================

def test_transect_orientations():
    """Verify horizontal, vertical, and diagonal transect extraction."""
    # Synthetic image with a known linear gradient: I(x, y) = x + 2*y
    y, x = np.mgrid[0:100, 0:100]
    img = (x + 2.0 * y).astype(np.float32)

    # Horizontal slice at y = 50 from x = 10 to x = 90
    h_slice = extract_photometric_transect(img, x0=10, y0=50, x1=90, y1=50, num_samples=81)
    assert len(h_slice["intensities"]) == 81
    # Intensities should be monotonically increasing
    assert np.all(np.diff(h_slice["intensities"]) > 0)
    assert abs(h_slice["intensities"][0] - (10 + 100)) < 1.0
    assert abs(h_slice["intensities"][-1] - (90 + 100)) < 1.0

    # Vertical slice at x = 40 from y = 10 to y = 80
    v_slice = extract_photometric_transect(img, x0=40, y0=10, x1=40, y1=80, num_samples=71)
    assert len(v_slice["intensities"]) == 71
    assert np.all(np.diff(v_slice["intensities"]) > 0)

    # Diagonal slice
    d_slice = extract_photometric_transect(img, x0=0, y0=0, x1=99, y1=99, num_samples=100)
    assert len(d_slice["intensities"]) == 100
    assert np.all(np.diff(d_slice["intensities"]) > 0)


def test_transect_out_of_bounds_clipping():
    """Verify transects requested outside image dimensions are safely clipped."""
    img = np.ones((50, 50), dtype=np.float32) * 25.0
    # Request start and end outside image coordinates
    clipped = extract_photometric_transect(img, x0=-20, y0=25, x1=70, y1=25, num_samples=40)
    assert len(clipped["intensities"]) == 40
    assert np.isfinite(clipped["intensities"]).all()


# ===========================================================================
# 3. IMAGE HISTOGRAM & CDF TESTS
# ===========================================================================

def test_image_histogram_properties():
    """Verify histogram binning and monotonic cumulative distribution."""
    data = np.random.normal(loc=128.0, scale=20.0, size=(100, 100)).astype(np.float32)
    hist = compute_image_histogram(data, num_bins=60)
    assert len(hist["counts"]) == 60
    assert len(hist["bins"]) == 60
    assert len(hist["cdf"]) == 60
    # Total sum of counts reflects percentile-clipped image pixels
    assert sum(hist["counts"]) >= 9900
    # CDF should be monotonically non-decreasing and end at 1.0
    assert np.all(np.diff(hist["cdf"]) >= 0.0)
    assert abs(hist["cdf"][-1] - 1.0) < 1e-5


# ===========================================================================
# 4. PDS3 TABLE READER TESTS
# ===========================================================================

def test_pds3_table_class_behavior():
    """Verify Pds3Table data access methods and column indexing."""
    cols = {
        "ALTITUDE": np.array([10.0, 20.0, 30.0], dtype=np.float64),
        "TEMPERATURE": np.array([250.0, 240.0, -999.0], dtype=np.float64),
    }

    tbl = Pds3Table(
        label_path="sample.lbl",
        table_path="sample.tab",
        metadata={"TARGET_NAME": "VENUS"},
        columns=cols,
        units={"ALTITUDE": "km", "TEMPERATURE": "K"},
    )
    assert tbl.series("ALTITUDE") is not None
    assert tbl.series("TEMPERATURE") is not None
    assert tbl.series("NOT_EXIST") is None
    assert tbl.metadata.get("TARGET_NAME") == "VENUS"

    alt = tbl.series("ALTITUDE")
    assert len(alt) == 3
    assert alt[0] == 10.0


def test_transect_single_pixel_image():
    """Verify transect extraction safely handles 1x1 single pixel images without errors."""
    tiny_img = np.array([[42.0]], dtype=np.float32)
    res = extract_photometric_transect(tiny_img, x0=0, y0=0, x1=0, y1=0, num_samples=10)
    assert len(res["intensities"]) == 10
    assert res["intensities"][0] == 42.0
    assert res["min_intensity"] == 42.0
    assert res["max_intensity"] == 42.0


def test_pds3_table_pointer_fallback(tmp_path):
    """Verify PDS3 reader resolves table filename from ^TABLE pointer when base name differs."""
    from veda.readers.pds3_reader import read_pds3_table
    lbl_content = """PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 20
FILE_RECORDS = 2
^TABLE = "custom_telemetry.tab"
OBJECT = COLUMN
  NAME = ALTITUDE
  COLUMN_NUMBER = 1
  START_BYTE = 1
  BYTES = 10
  DATA_TYPE = ASCII_REAL
END_OBJECT = COLUMN
OBJECT = COLUMN
  NAME = TEMPERATURE
  COLUMN_NUMBER = 2
  START_BYTE = 11
  BYTES = 10
  DATA_TYPE = ASCII_REAL
END_OBJECT = COLUMN
END
"""
    tab_content = "      10.5     245.2\n      11.0     244.8\n"

    lbl_file = tmp_path / "metadata.lbl"
    tab_file = tmp_path / "custom_telemetry.tab"
    lbl_file.write_text(lbl_content, encoding="utf-8")
    tab_file.write_text(tab_content, encoding="utf-8")

    parsed = read_pds3_table(str(lbl_file))
    assert parsed.series("ALTITUDE") is not None
    assert len(parsed.series("ALTITUDE")) == 2
    assert abs(parsed.series("ALTITUDE")[0] - 10.5) < 1e-3
    assert abs(parsed.series("TEMPERATURE")[0] - 245.2) < 1e-3



def test_label_statements_with_comments_and_quotes():
    """The label tokeniser (regular expressions since it was made faster) keeps comment
    marks inside quotes, ignores quotes inside comments and joins wrapped values."""
    from veda.readers.pds3_reader import _label_lines
    text = ('A = 1 /* a "quoted" comment */\r\n'
            'B = "x /* not a comment */\r\n  y"\n'
            '/* multi\nline */ C =\n  2\n'
            'D = "left open')
    assert _label_lines(text) == ['A = 1', 'B = "x /* not a comment */ y"', 'C = 2', 'D = "left open"']
