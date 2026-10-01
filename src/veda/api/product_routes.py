"""Any archive product as plottable data: /api/veda/product/{dataset_id}/{product_id}/...

Works for every payload VEDA can download: tables (time series, spectra per
row, housekeeping), images, spectral cubes and maps, whatever the format
(PDS3, PDS4, FITS, netCDF).  Large products are memory-mapped and decimated
before they are sent, so the browser never receives more than a few thousand
points or a screen-sized image.
"""
from __future__ import annotations

import math
import re
import warnings
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ..archives import catalog, net
from ..readers.product import DataObject, Product, ProductError, open_product

router = APIRouter(prefix="/api/veda/product", tags=["product"])


def _product(dataset_id: str, product_id: str, confirm_large: bool = True) -> Product:
    if not catalog.get_product(dataset_id, product_id):
        raise HTTPException(404, f"Unknown product {dataset_id}/{product_id}")
    from ..config import SETTINGS
    try:
        label = catalog.fetch_product(dataset_id, product_id, max_bytes=None if confirm_large
                                      else SETTINGS.product_confirm_mb * 1_000_000)
        return open_product(str(label))
    except net.TooLarge as exc:
        # 413 with the size, so the viewer can ask before a very long download
        raise HTTPException(413, {"message": f"{exc.name} is {exc.size_bytes / 1e6:,.0f} MB. Download it?",
                                  "file": exc.name, "size_bytes": exc.size_bytes})
    except net.LoginRequired as exc:
        raise HTTPException(401, str(exc))
    except net.ArchiveError as exc:
        raise HTTPException(502, str(exc))
    except ProductError as exc:
        raise HTTPException(422, str(exc))
    except (OSError, ValueError) as exc:
        raise HTTPException(422, f"Could not read this product: {exc}")


def _object(prod: Product, name: Optional[str], kinds=None) -> DataObject:
    try:
        obj = prod.get(name)
    except ProductError as exc:
        raise HTTPException(404, str(exc))
    if kinds and obj.kind not in kinds:
        raise HTTPException(400, f"{obj.name} is a {obj.kind}, not a {' or '.join(kinds)}")
    return obj


def _finite_list(a: np.ndarray, digits: int = 6) -> List[Optional[float]]:
    out = []
    for v in np.asarray(a, dtype=float).ravel().tolist():
        out.append(None if not math.isfinite(v) else float(f"{v:.{digits}g}"))
    return out


def minmax_indices(y: np.ndarray, max_points: int) -> np.ndarray:
    """Row indices keeping the min and max of each bucket, so peaks survive decimation."""
    n = y.shape[0]
    if n <= max_points:
        return np.arange(n)
    buckets = max(max_points // 2, 1)
    edges = np.linspace(0, n, buckets + 1).astype(int)
    keep = [0, n - 1]
    yy = np.where(np.isfinite(y), y, np.nan)
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        seg = yy[a:b]
        if np.all(np.isnan(seg)):
            keep.append(a)
            continue
        keep.append(a + int(np.nanargmin(seg)))
        keep.append(a + int(np.nanargmax(seg)))
    return np.unique(np.array(keep))


_NOT_A_MEASUREMENT = re.compile(
    r"(^|[ _.])(SAMPLE|RECORD|ROW|INDEX|PACKET|SEQUENCE|FRAME|COUNTER)([ _]?(NUMBER|NO|ID|COUNT))?$|"
    r"EPHEMERIS|SCLK|SPACECRAFT[ _]CLOCK|(^|[ _])(ET|TIME|UTC|JD|MJD|DOY|YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)"
    r"([ _]|$)|^(ET|UTC|SCET|ERT|OBT|SCLK)([A-Z]{0,4}|[ _].*)$|(^|[ _])(ID|TYPE|VERSION|COUNTER)$|QUALITY|FLAG|MODE|STATUS|CHECKSUM|SPARE", re.I)


def default_y(obj: DataObject, x: Optional[str]) -> Optional[str]:
    """The first field that looks like a measurement (not a counter, clock or flag)."""
    nums = [f for f in obj.fields if f.kind == "number" and f.name != x]
    for f in nums:
        if f.items == 1 and not _NOT_A_MEASUREMENT.search(f.name):
            return f.name
    vec = next((f for f in nums if f.items > 1 and not _NOT_A_MEASUREMENT.search(f.name)), None)
    if vec:
        return vec.name
    return nums[0].name if nums else None


@router.get("/{dataset_id}/{product_id}/structure")
def structure(dataset_id: str, product_id: str, confirm_large: bool = False) -> Dict[str, Any]:
    """The data objects of a product (tables with their fields, images, cubes).

    The first request for a product downloads it; a file larger than the
    product_confirm_mb setting answers 413 until ``confirm_large`` is set.
    """
    prod = _product(dataset_id, product_id, confirm_large)
    d = prod.to_dict()
    d["product"] = catalog.get_product(dataset_id, product_id)
    return d


@router.get("/{dataset_id}/{product_id}/table")
def table(dataset_id: str, product_id: str, object: Optional[str] = None,
          x: Optional[str] = None, y: Optional[List[str]] = Query(None),
          max_points: int = Query(4000, ge=100, le=50000),
          max_channels: int = Query(256, ge=8, le=2048)) -> Dict[str, Any]:
    """Columns of a table for plotting: x, one or more y series, vector columns as 2-D (rows x items)."""
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("table",))
    fields = {f.name: f for f in obj.fields}
    if x and x not in fields:
        raise HTTPException(400, f"{obj.name} has no field {x!r}")
    for name in y or []:
        if name not in fields:
            raise HTTPException(400, f"{obj.name} has no field {name!r}")
    if not x:   # default: the first time field, else the row number
        x = next((f.name for f in obj.fields if f.kind == "time"), None)
    if not y:
        y = [default_y(obj, x)]
        y = [v for v in y if v]
    try:
        data = obj.read_table([n for n in [x, *(y or [])] if n])
    except ProductError as exc:
        raise HTTPException(422, str(exc))
    except (OSError, ValueError, IndexError) as exc:
        raise HTTPException(422, f"Could not read {obj.name}: {exc}")
    n = len(next(iter(data.values()))) if data else 0
    # choose rows with the first scalar series (peaks kept), then apply to everything
    first = next((np.asarray(data[v]) for v in y or [] if isinstance(data.get(v), np.ndarray) and np.ndim(data[v]) == 1),
                 None)
    idx = minmax_indices(first, max_points) if first is not None else np.linspace(0, max(n - 1, 0),
                                                                                 min(n, max_points)).astype(int)
    out: Dict[str, Any] = {"object": obj.name, "rows": n, "shown": int(idx.size), "series": [], "vectors": []}
    if x:
        xv = data[x]
        out["x"] = {"name": x, "unit": fields[x].unit, "kind": fields[x].kind,
                    "values": [xv[i] for i in idx] if isinstance(xv, list) else _finite_list(np.asarray(xv)[idx], 12)}
    else:
        out["x"] = {"name": "Row", "unit": "", "kind": "number", "values": [int(i) + 1 for i in idx]}
    for name in y or []:
        v = data[name]
        f = fields[name]
        if isinstance(v, list):
            out["series"].append({"name": name, "unit": f.unit, "kind": f.kind, "text": [v[i] for i in idx]})
            continue
        v = np.asarray(v)
        if v.ndim == 1:
            out["series"].append({"name": name, "unit": f.unit, "kind": "number", "description": f.description,
                                  "values": _finite_list(v[idx])})
        else:
            # vector column: rows x channels, averaged down to a heat-map sized grid
            rows = v[np.linspace(0, v.shape[0] - 1, min(v.shape[0], 800)).astype(int)] if v.shape[0] > 800 else v
            ch_step = max(1, math.ceil(rows.shape[1] / max_channels))
            if ch_step > 1:
                cut = rows.shape[1] // ch_step * ch_step
                with np.errstate(invalid="ignore"), warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)       # all-NaN channel groups stay NaN
                    rows = np.nanmean(rows[:, :cut].reshape(rows.shape[0], -1, ch_step), axis=2)
            row_idx = np.linspace(0, v.shape[0] - 1, rows.shape[0]).astype(int)
            xs = data[x] if x else None
            out["vectors"].append({
                "name": name, "unit": f.unit, "description": f.description, "channels": int(v.shape[1]),
                "channel_step": ch_step, "z": [_finite_list(r, 5) for r in rows],
                "x": ([xs[i] for i in row_idx] if isinstance(xs, list) else _finite_list(np.asarray(xs)[row_idx], 12))
                if xs is not None else [int(i) + 1 for i in row_idx],
                "mean": _finite_list(np.nanmean(v, axis=0) if np.isfinite(v).any() else np.full(v.shape[1], np.nan)),
            })
    return out


def _band_array(obj: DataObject, band: int, max_dim: int) -> tuple:
    bands, lines, samples = obj.shape if len(obj.shape) == 3 else (1, *obj.shape[-2:])
    if not 0 <= band < bands:
        raise HTTPException(400, f"band must be between 0 and {bands - 1}")
    step = max(1, math.ceil(max(lines, samples) / max_dim))
    try:
        a = obj.read_array(step=step, bands=slice(band, band + 1))[0]
    except ProductError as exc:
        raise HTTPException(422, str(exc))
    except (OSError, ValueError, MemoryError) as exc:
        raise HTTPException(422, f"Could not read {obj.name}: {exc}")
    return a, step


@router.get("/{dataset_id}/{product_id}/text")
def text(dataset_id: str, product_id: str, object: Optional[str] = None,
         max_bytes: int = Query(400_000, ge=1000, le=4_000_000)) -> Dict[str, Any]:
    """A text object (operations log, document) for reading in the viewer."""
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("text",))
    try:
        body, truncated = obj.read_text(max_bytes)
    except (OSError, ProductError) as exc:
        raise HTTPException(422, f"Could not read {obj.name}: {exc}")
    return {"object": obj.name, "lines": obj.shape[0], "truncated": truncated, "text": body}


@router.get("/{dataset_id}/{product_id}/image.png")
def image_png(dataset_id: str, product_id: str, object: Optional[str] = None, band: int = 0,
              stretch: str = Query("percentile", pattern="^(zscale|percentile|linear|log|sqrt|asinh|histeq)$"),
              cmap: str = Query("gray", max_length=30), max_dim: int = Query(1400, ge=128, le=4096),
              vmin: Optional[float] = None, vmax: Optional[float] = None, flip: bool = False):
    from ..readers.fits_reader import render_to_png
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("image", "cube", "array"))
    a, _ = _band_array(obj, band, max_dim)
    if flip:
        a = a[::-1]
    png = render_to_png(np.asarray(a, dtype=np.float64), stretch, cmap, vmin, vmax, max_dimension=0)
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.get("/{dataset_id}/{product_id}/image/stats")
def image_stats(dataset_id: str, product_id: str, object: Optional[str] = None, band: int = 0) -> Dict[str, Any]:
    from ..readers.fits_reader import compute_image_histogram
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("image", "cube", "array"))
    a, step = _band_array(obj, band, 1024)
    fin = a[np.isfinite(a)]
    return {"object": obj.name, "kind": obj.kind, "shape": list(obj.shape), "unit": obj.unit, "extent": obj.extent,
            "axes": list(obj.axes), "band": band, "step": step,
            "min": float(fin.min()) if fin.size else None, "max": float(fin.max()) if fin.size else None,
            "mean": float(fin.mean()) if fin.size else None, "valid_fraction": float(fin.size / max(a.size, 1)),
            "histogram": compute_image_histogram(a, 80)}


@router.get("/{dataset_id}/{product_id}/image/transect")
def image_transect(dataset_id: str, product_id: str, x0: float, y0: float, x1: float, y1: float,
                   object: Optional[str] = None, band: int = 0) -> Dict[str, Any]:
    """Values along a line, in full-resolution pixel coordinates."""
    from ..readers.fits_reader import extract_photometric_transect
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("image", "cube", "array"))
    _, lines, samples = obj.shape if len(obj.shape) == 3 else (1, *obj.shape[-2:])
    lo_l, hi_l = int(max(0, min(y0, y1))), int(min(lines, max(y0, y1) + 2))
    lo_s, hi_s = int(max(0, min(x0, x1))), int(min(samples, max(x0, x1) + 2))
    if hi_l - lo_l < 2 or hi_s - lo_s < 2:      # nearly horizontal/vertical: widen the window
        lo_l, hi_l = max(0, lo_l - 1), min(lines, hi_l + 1)
        lo_s, hi_s = max(0, lo_s - 1), min(samples, hi_s + 1)
    a = obj.read_array(bands=slice(band, band + 1), lines=slice(lo_l, hi_l), samples=slice(lo_s, hi_s))[0]
    res = extract_photometric_transect(np.asarray(a, dtype=np.float64), x0 - lo_s, y0 - lo_l, x1 - lo_s, y1 - lo_l,
                                       num_samples=300)
    res.update({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "unit": obj.unit})
    return res


@router.get("/{dataset_id}/{product_id}/cube/spectrum")
def cube_spectrum(dataset_id: str, product_id: str, line: int, sample: int,
                  object: Optional[str] = None, box: int = Query(0, ge=0, le=10)) -> Dict[str, Any]:
    """All bands at one pixel (averaged over a (2*box+1)^2 box)."""
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("cube", "image", "array"))
    bands, lines, samples = obj.shape if len(obj.shape) == 3 else (1, *obj.shape[-2:])
    if not (0 <= line < lines and 0 <= sample < samples):
        raise HTTPException(400, "pixel outside the cube")
    a = obj.read_array(lines=slice(max(0, line - box), line + box + 1),
                       samples=slice(max(0, sample - box), sample + box + 1))
    with np.errstate(invalid="ignore"):
        spec = np.nanmean(a.reshape(a.shape[0], -1), axis=1)
    return {"object": obj.name, "line": line, "sample": sample, "box": box, "unit": obj.unit,
            "band": list(range(bands)), "values": _finite_list(spec)}


@router.get("/{dataset_id}/{product_id}/rows")
def table_rows(dataset_id: str, product_id: str, fields: List[str] = Query(...), rows: List[int] = Query(...),
               object: Optional[str] = None, label: Optional[str] = None) -> Dict[str, Any]:
    """Vector fields of selected rows at full resolution (e.g. MCS DDR: one profile per row)."""
    prod = _product(dataset_id, product_id)
    obj = _object(prod, object, ("table",))
    names = {f.name: f for f in obj.fields}
    for f in fields:
        if f not in names:
            raise HTTPException(400, f"{obj.name} has no field {f!r}")
    if len(rows) > 50:
        raise HTTPException(400, "At most 50 rows at a time")
    want = list(dict.fromkeys(fields + ([label] if label and label in names else [])))
    try:
        data = obj.read_table(want)
    except (ProductError, OSError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    n = len(next(iter(data.values()))) if data else 0
    out = []
    for r in rows:
        if not 0 <= r < n:
            continue
        item = {"row": r, "label": (data[label][r] if label and isinstance(data.get(label), list)
                                    else (_finite_list(np.asarray([data[label][r]]))[0] if label and label in data else None))}
        for f in fields:
            v = data[f]
            if isinstance(v, list):
                item[f] = v[r]
            else:
                a = np.asarray(v)
                item[f] = _finite_list(a[r] if a.ndim > 1 else a[r:r + 1])
        out.append(item)
    return {"object": obj.name, "rows_total": n, "rows": out,
            "units": {f: names[f].unit for f in fields}}
