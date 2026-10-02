"""Read any archive product into plottable objects.

One entry point, :func:`open_product`, for PDS3 labels (attached or
detached), PDS4 XML labels, FITS files and plain text tables.  A product is a
list of :class:`DataObject` s:

* ``table``  rows of named fields; a field may be a vector (``items`` > 1,
  e.g. a spectrum or energy channels per row) or text / time;
* ``image``  a 2-D array (or a few bands);
* ``cube``   a spectral cube, read as (band, line, sample);
* ``array``  any other N-D array.

Supported: PDS3 TABLE / SERIES / TIME_SERIES / SPREADSHEET (ASCII and
binary, ITEMS, CONTAINER repetitions, ROW_PREFIX/SUFFIX_BYTES, scaling and
missing constants), IMAGE (band sequential / line / sample interleaved,
line prefix and suffix bytes), QUBE and SPECTRAL_QUBE (with suffix planes),
ARRAY; PDS4 Table_Character / Table_Binary / Table_Delimited (with
Group_Field repetitions), Array_1D/2D/3D[_Image/_Spectrum/_Map]; FITS image
and table HDUs.  Binary data are memory-mapped, so very large files are only
read where needed.
"""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .pds3_reader import _label_lines, _rejoin_broken_records, _strip_comments  # noqa: F401


class ProductError(ValueError):
    """The product cannot be read; the message says why, in plain words."""


@dataclass
class Field:
    name: str
    unit: str = ""
    description: str = ""
    items: int = 1                 # values per row (>1: a vector such as a spectrum)
    kind: str = "number"           # "number" | "time" | "text"

    def __post_init__(self) -> None:
        self.unit = _unit(self.unit)


_NO_UNIT = {"N/A", "NA", "NONE", "UNK", "UNKNOWN", "NULL", "-", "DIMENSIONLESS", "NO UNIT"}


def _unit(u: str) -> str:
    u = (u or "").strip().strip('"').strip()
    return "" if u.upper() in _NO_UNIT else u


@dataclass
class DataObject:
    name: str
    kind: str                      # "table" | "image" | "cube" | "array" | "text"
    shape: Tuple[int, ...]
    fields: List[Field] = field(default_factory=list)
    description: str = ""
    axes: Tuple[str, ...] = ()     # for arrays: axis names, slowest first
    unit: str = ""                 # for arrays
    # for arrays on a regular grid: {"x": (first, last, name, unit), "y": (...)}, e.g. lon/lat maps
    extent: Dict[str, Any] = field(default_factory=dict)
    _reader: Optional[Callable[..., Any]] = field(default=None, repr=False)

    def read_table(self, names: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Selected fields (all when None), first ``limit`` rows (all when None).

        Numeric fields -> float64 array (rows,) or (rows, items); text/time -> list[str].
        """
        if self.kind != "table":
            raise ProductError(f"{self.name} is not a table")
        return self._reader(names, limit)

    def read_array(self, step: int = 1, bands: Optional[slice] = None,
                   lines: Optional[slice] = None, samples: Optional[slice] = None) -> np.ndarray:
        """Array values as float32 (NaN where missing); images and cubes as (band, line, sample).

        ``step`` keeps every n-th line and sample, and ``bands`` / ``lines`` / ``samples``
        select a part, so a quick look at a very large image never loads all of it:
        the file is memory-mapped and only the selected bytes are converted.
        """
        if self.kind not in ("image", "cube", "array"):
            raise ProductError(f"{self.name} is a {self.kind}")
        view, clean = self._reader()
        if view.ndim == 3:
            view = view[bands or slice(None), lines or slice(None, None, step), samples or slice(None, None, step)]
        elif view.ndim >= 2 and step > 1:
            view = view[..., ::step, ::step]
        return clean(np.asarray(view)).astype(np.float32, copy=False)

    def read_text(self, max_bytes: int = 400_000) -> Tuple[str, bool]:
        """A text object (log, document, label-described ASCII stream): (text, truncated)."""
        if self.kind != "text":
            raise ProductError(f"{self.name} is not a text object")
        return self._reader(max_bytes)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "shape": list(self.shape),
                "description": self.description, "axes": list(self.axes), "unit": self.unit,
                "extent": self.extent, "fields": [f.__dict__ for f in self.fields]}


@dataclass
class Product:
    path: str
    format: str                    # "PDS3" | "PDS4" | "FITS" | "TEXT"
    metadata: Dict[str, Any]
    objects: List[DataObject]

    def get(self, name: Optional[str] = None) -> DataObject:
        if not self.objects:
            raise ProductError("This product contains no data object VEDA can read")
        if name is None:
            return self.objects[0]
        for o in self.objects:
            if o.name == name:
                return o
        raise ProductError(f"No data object named {name!r}")

    def to_dict(self) -> Dict[str, Any]:
        keep = ("START_TIME", "STOP_TIME", "TARGET_NAME", "INSTRUMENT_NAME", "INSTRUMENT_ID",
                "SPACECRAFT_NAME", "INSTRUMENT_HOST_NAME", "PRODUCT_ID", "DATA_SET_ID", "TITLE",
                "PRODUCT_TYPE", "PROCESSING_LEVEL_ID", "LOGICAL_IDENTIFIER", "DESCRIPTION")
        meta = {k: v for k, v in self.metadata.items() if k in keep and isinstance(v, (str, int, float))}
        return {"path": Path(self.path).name, "format": self.format, "metadata": meta,
                "objects": [o.to_dict() for o in self.objects]}


# ====================================================================== helpers

_TIME_RX = re.compile(r"^\s*(\d{4}-(\d{2}-\d{2}|\d{3})[T ]|\d{4} [A-Za-z]{3} \d{1,2} )\d{2}:\d{2}(:\d{2}(\.\d*)?)?Z?\s*$")
_MONTHS = {m: i + 1 for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"))}


def _looks_like_time(values: List[str]) -> bool:
    sample = [v for v in values[:50] if v]
    return bool(sample) and all(_TIME_RX.match(v) for v in sample)


def iso_time(v: str) -> str:
    """'2004-160T15:43:00.5' or '2004-06-08 15:43' -> '2004-06-08T15:43:00.500' (Plotly-friendly)."""
    import datetime as _dt
    s = v.strip().rstrip("Z")
    m = re.match(r"^(\d{4}) ([A-Za-z]{3}) (\d{1,2}) (.*)$", s)
    if m and m.group(2).upper() in _MONTHS:
        return f"{m.group(1)}-{_MONTHS[m.group(2).upper()]:02d}-{int(m.group(3)):02d}T{m.group(4)}"
    s = s.replace(" ", "T")
    m = re.match(r"^(\d{4})-(\d{3})T(.*)$", s)
    if m:
        d = _dt.date(int(m.group(1)), 1, 1) + _dt.timedelta(days=int(m.group(2)) - 1)
        s = f"{d.isoformat()}T{m.group(3)}"
    return s


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None:
        return default
    s = str(v).strip().strip('"')
    s = re.sub(r"<[^>]*>", "", s).strip()
    m = re.match(r"^([+-]?\d+)#([0-9A-Fa-f]+)#$", s)        # 16#FF7FFFFB#
    if m:
        return float(int(m.group(2), int(m.group(1))))
    try:
        return float(s)
    except ValueError:
        return default


def _int(v: Any, default: int = 0) -> int:
    x = _num(v)
    return int(x) if x is not None else default


def _seq(v: Any) -> List[str]:
    s = str(v or "").strip()
    if s.startswith(("(", "{")):
        s = s[1:-1]
    return [x.strip().strip('"') for x in s.split(",") if x.strip()]


def _find(folder: Path, name: str) -> Optional[Path]:
    """A file next to the label (any case), or in a sibling LABEL/ or DATA/ folder."""
    name = name.strip().strip('"')
    for base in (folder, folder.parent / "LABEL", folder.parent / "label", folder.parent.parent / "LABEL",
                 folder.parent.parent / "label"):
        for cand in (name, name.lower(), name.upper()):
            p = base / cand
            if p.exists():
                return p
    return None


# PDS3 binary types -> numpy
def _pds3_dtype(data_type: str, nbytes: int) -> Tuple[Optional[np.dtype], str]:
    dt = (data_type or "").upper().replace(" ", "_")
    if "VAX" in dt and "REAL" in dt:
        return None, "vax"
    little = any(x in dt for x in ("LSB", "PC_", "VAX"))
    order = "<" if little else ">"
    if any(x in dt for x in ("CHARACTER", "ASCII", "TIME", "DATE", "UTF8")):
        return np.dtype(f"S{nbytes}"), "text"
    if "COMPLEX" in dt:
        return np.dtype(f"{order}c{nbytes}"), "complex"
    if "UNSIGNED" in dt or "BIT_STRING" in dt or "BOOLEAN" in dt or dt == "N/A":
        if nbytes in (1, 2, 4, 8):
            return np.dtype(f"{order}u{nbytes}"), "number"
        return np.dtype(f"S{nbytes}"), "text"
    if "INTEGER" in dt:
        if nbytes in (1, 2, 4, 8):
            return np.dtype(f"{order}i{nbytes}"), "number"
        return np.dtype(f"S{nbytes}"), "text"
    if "REAL" in dt or "FLOAT" in dt or "IEEE" in dt:
        if nbytes in (4, 8):
            return np.dtype(f"{order}f{nbytes}"), "number"
    if nbytes in (1, 2, 4, 8):
        return np.dtype(f"{order}i{nbytes}"), "number"
    return np.dtype(f"S{nbytes}"), "text"


def _vax_to_float(raw: np.ndarray, nbytes: int) -> np.ndarray:
    """VAX F (4 byte) / D (8 byte, read as G-like approximation) floats to IEEE."""
    if nbytes == 4:
        a = raw.view("<u2").reshape(-1, 2)
        swapped = (a[:, 0].astype(np.uint32) << 16) | a[:, 1].astype(np.uint32)
        f = swapped.view(np.float32) / 4.0
        return f.astype(np.float64)
    a = raw.view("<u2").reshape(-1, 4)
    words = (a[:, 0].astype(np.uint64) << 48) | (a[:, 1].astype(np.uint64) << 32) | \
            (a[:, 2].astype(np.uint64) << 16) | a[:, 3].astype(np.uint64)
    sign = (words >> 63) & 1
    exp = (words >> 55) & 0xFF
    mant = words & ((1 << 55) - 1)
    val = (1.0 + mant.astype(np.float64) / float(1 << 55)) * np.power(2.0, exp.astype(np.float64) - 129.0)
    val[exp == 0] = 0.0
    return np.where(sign == 1, -val, val)


def _decades(sample: np.ndarray) -> float:
    """How many orders of magnitude the bulk (5-95 %) of the non-zero values spans; values
    read in the wrong byte order span ~70, measurements a few.  NaN/Inf count as extreme."""
    with np.errstate(invalid="ignore", over="ignore", divide="ignore"):
        s = sample.astype(np.float64)
        nz = s[s != 0]
        if nz.size < 20:
            return 0.0
        lg = np.log10(np.abs(nz))
    lg = np.where(np.isfinite(lg), lg, 400.0)
    lo, hi = np.percentile(lg, [5, 95])
    return float(hi - lo)


def _fix_byte_order(raw: np.ndarray) -> np.ndarray:
    """Floats written in the opposite byte order to the label read back as values spread
    over ~70 decades (and NaNs); when the swapped bytes look like measurements, use them."""
    if raw.dtype.kind != "f" or raw.size == 0 or raw.dtype.itemsize < 4:
        return raw
    flat = raw.reshape(-1)
    sample = flat[:: max(1, flat.size // 5000)][:5000]
    if _decades(sample) > 30 and _decades(sample.view(sample.dtype.newbyteorder())) < 15:
        return raw.view(raw.dtype.newbyteorder())
    return raw


def _fix_mislabelled_float(raw: np.ndarray) -> np.ndarray:
    """Repair two label errors seen in the archives, judged from the values themselves:

    * floats in the opposite byte order to the label (Juno JIRAM RDR spectra are labelled
      MSB but written LSB): read as labelled they are denormals, ~1e38 and NaNs, while the
      swapped bytes are ordinary numbers;
    * a float column whose non-zero values are all denormal (|x| < 1e-30) is integer data
      labelled as REAL (VEX SPICAV IR): reinterpret the same bytes as integers.
    """
    if raw.dtype.kind != "f" or raw.size == 0 or raw.dtype.itemsize < 4:
        return raw
    raw = _fix_byte_order(raw)
    flat = raw.reshape(-1)
    sample = flat[:: max(1, flat.size // 5000)][:5000]
    with np.errstate(invalid="ignore"):
        nz = sample[(sample != 0) & np.isfinite(sample)]
    if nz.size and np.all(np.abs(nz) < 1e-30):
        return raw.view(raw.dtype.str.replace("f", "i"))
    return raw


def _mmap(path: Path) -> np.memmap:
    if path.stat().st_size == 0:
        raise ProductError(f"{path.name} is empty")
    return np.memmap(path, dtype=np.uint8, mode="r")


def _strided(buf: np.ndarray, dtype: np.dtype, offset: int, shape: Tuple[int, ...],
             strides: Tuple[int, ...]) -> np.ndarray:
    """A strided view into a byte buffer, checked against its length."""
    need = offset + sum((n - 1) * s for n, s in zip(shape, strides) if n > 0) + dtype.itemsize
    if any(n == 0 for n in shape):
        return np.zeros(shape, dtype)
    if offset < 0 or need > buf.size:
        raise ProductError(f"The data file is shorter than its label says ({buf.size} bytes, needs {need}); "
                           "it may be truncated or the label may describe another file")
    return np.ndarray(shape, dtype=dtype, buffer=buf, offset=offset, strides=strides)


def _clean(values: np.ndarray, missing: List[float], scale: float = 1.0, offset: float = 0.0,
           valid_range: Optional[Tuple[float, float]] = None) -> np.ndarray:
    with np.errstate(invalid="ignore"):          # signalling NaNs in the file
        out = values.astype(np.float64)
    bad = ~np.isfinite(out)
    for m in missing:
        bad |= np.isclose(out, m, rtol=0, atol=max(abs(m) * 1e-7, 1e-9))
    if valid_range:
        lo, hi = valid_range
        bad |= (out < lo) | (out > hi)
    if scale != 1.0 or offset != 0.0:
        out = out * scale + offset
    out[bad] = np.nan
    return out


# ====================================================================== PDS3 label tree

@dataclass
class _Node:
    kind: str                      # "OBJECT" | "GROUP" | "ROOT"
    name: str
    attrs: Dict[str, str] = field(default_factory=dict)
    children: List["_Node"] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key, default)


def _parse_pds3_tree(text: str, folder: Optional[Path]) -> _Node:
    root = _Node("ROOT", "ROOT")
    stack = [root]
    seen_fmt: set = set()

    def feed(lines: List[str], depth: int = 0) -> None:
        for line in lines:
            key, sep, val = line.partition("=")
            key = key.strip().upper()
            val = val.strip()
            if key == "END" and len(stack) == 1 and depth == 0:
                return
            clean = val[1:-1] if len(val) >= 2 and val[0] == val[-1] == '"' else val
            if key in ("OBJECT", "GROUP") and sep:
                node = _Node(key, clean.strip().upper())
                stack[-1].children.append(node)
                stack.append(node)
            elif key in ("END_OBJECT", "END_GROUP"):
                if len(stack) > 1:
                    stack.pop()
            elif key == "^STRUCTURE" and folder is not None and depth < 4:
                fmt = _find(folder, clean)
                if fmt and fmt not in seen_fmt:
                    seen_fmt.add(fmt)
                    feed(_label_lines(fmt.read_text(encoding="latin-1", errors="replace")), depth + 1)
            elif sep:
                stack[-1].attrs[key] = clean
    feed(_label_lines(text))
    return root


def _label_text(path: Path) -> str:
    """The label part of an attached or detached PDS3 label."""
    with path.open("rb") as fh:
        head = fh.read(2_000_000)
    txt = head.decode("latin-1", errors="replace")
    m = re.search(r"(?m)^\s*END\s*$", txt)
    return txt[:m.end()] if m else txt


def _pds3_offset(pointer: str, record_bytes: int, label_path: Path) -> Tuple[Path, int]:
    """^X value -> (data file, byte offset)."""
    v = pointer.strip()
    m = re.match(r'^\(?\s*"?([^",)\s]+)"?\s*(?:,\s*(\d+)\s*(<BYTES>)?)?\s*\)?$', v)
    if not m:
        raise ProductError(f"Cannot read the data pointer {pointer!r}")
    first, num, unit_bytes = m.group(1), m.group(2), m.group(3)
    if first.isdigit() and num is None:                     # attached: record (or <BYTES>) in this file
        n = int(first)
        if "<BYTES>" in v.upper():
            return label_path, n - 1
        return label_path, (n - 1) * record_bytes if record_bytes > 1 else _line_offset(label_path, n)
    data = _find(label_path.parent, first)
    if data is None:
        raise ProductError(f"The data file {first} named in {label_path.name} is not here; download the product again")
    if num is None:
        return data, 0
    n = int(num)
    if unit_bytes:
        return data, n - 1
    return data, (n - 1) * record_bytes if record_bytes > 1 else _line_offset(data, n)


def _line_offset(path: Path, record: int) -> int:
    """Byte offset of line ``record`` (1-based) in a STREAM file without RECORD_BYTES."""
    if record <= 1:
        return 0
    pos = 0
    with path.open("rb") as fh:
        for _ in range(record - 1):
            line = fh.readline()
            if not line:
                break
            pos += len(line)
    return pos


def _pds3_fields(node: _Node, base: int = 0) -> List[Tuple[Field, Dict[str, Any]]]:
    """COLUMN / FIELD objects of a table, CONTAINERs flattened (repetitions -> items)."""
    out: List[Tuple[Field, Dict[str, Any]]] = []
    for ch in node.children:
        if ch.kind != "OBJECT":
            continue
        if ch.name in ("COLUMN", "FIELD"):
            items = max(_int(ch.get("ITEMS"), 1), 1)
            nbytes = _int(ch.get("BYTES"), 0)
            ib = _int(ch.get("ITEM_BYTES"), nbytes // items if items else nbytes)
            spec = {
                "start": base + _int(ch.get("START_BYTE"), 1) - 1, "bytes": nbytes, "items": items,
                "item_bytes": ib or nbytes, "item_offset": _int(ch.get("ITEM_OFFSET"), ib or nbytes),
                "type": ch.get("DATA_TYPE", "ASCII_REAL"), "field_number": _int(ch.get("FIELD_NUMBER"), 0),
                "scale": _num(ch.get("SCALING_FACTOR"), 1.0), "offset": _num(ch.get("OFFSET"), 0.0),
                "missing": [x for x in (_num(ch.get(k)) for k in (
                    "MISSING_CONSTANT", "INVALID_CONSTANT", "NULL_CONSTANT", "MISSING", "INVALID")) if x is not None],
                "reps": [],
            }
            f = Field(name=ch.get("NAME", f"COL_{len(out) + 1}"), unit=ch.get("UNIT", "").strip('"'),
                      description=" ".join(ch.get("DESCRIPTION", "").split())[:300], items=items)
            out.append((f, spec))
        elif ch.name == "CONTAINER":
            start = base + _int(ch.get("START_BYTE"), 1) - 1
            reps = max(_int(ch.get("REPETITIONS"), 1), 1)
            size = _int(ch.get("BYTES"), 0)
            prefix = ch.get("NAME", "CONTAINER")
            for f, spec in _pds3_fields(ch, start):
                f.name = f"{prefix}.{f.name}" if not f.name.startswith(prefix) else f.name
                if reps > 1:
                    spec["reps"] = [(reps, size)] + spec["reps"]
                    f.items *= reps
                out.append((f, spec))
    return out


def _binary_table_reader(buf_path: Path, offset: int, rows: int, row_stride: int, prefix: int,
                         specs: List[Tuple[Field, Dict[str, Any]]]):
    def read(names: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        buf = _mmap(buf_path)
        n = rows
        if n <= 0:
            n = max((buf.size - offset) // row_stride, 0)
        stride = row_stride
        tail = buf.size - offset
        if rows > 1 and tail != rows * row_stride and tail % rows == 0 and 0 < abs(tail // rows - row_stride) <= 64:
            # The data end exactly at another record length (labels sometimes omit a
            # few pad or checksum bytes per record, e.g. SPICAV IR): trust the file.
            stride = tail // rows
        # Files shorter than their label (seen in PSA PFS): read the complete rows there are.
        if stride and n * stride > tail:
            n = max(tail // stride, 0)
        if limit is not None:
            n = min(n, limit)
        out: Dict[str, Any] = {}
        for f, s in specs:
            if names is not None and f.name not in names:
                continue
            dt, kind = _pds3_dtype(s["type"], s["item_bytes"])
            shape: List[int] = [n]
            strides: List[int] = [stride]
            for reps, size in s["reps"]:
                shape.append(reps)
                strides.append(size)
            shape.append(s["items"])
            strides.append(s["item_offset"])
            base = offset + prefix + s["start"]
            if kind == "vax":
                raw = _strided(buf, np.dtype(f"V{s['item_bytes']}"), base, tuple(shape), tuple(strides))
                vals = _vax_to_float(np.ascontiguousarray(raw).view(np.uint8), s["item_bytes"]).reshape(shape)
                arr = _clean(vals, s["missing"], s["scale"], s["offset"])
            else:
                raw = _strided(buf, dt, base, tuple(shape), tuple(strides))
                if kind == "text":
                    flat = np.ascontiguousarray(raw).reshape(n, -1)[:, 0]
                    texts = [b.decode("latin-1", errors="replace").strip().strip('"') for b in flat]
                    out[f.name] = [iso_time(t) for t in texts] if f.kind == "time" else texts
                    continue
                if kind == "complex":
                    raw = np.abs(raw)
                raw = _fix_mislabelled_float(np.asarray(raw))
                arr = _clean(raw, s["missing"], s["scale"], s["offset"])
            arr = arr.reshape(n, -1)
            out[f.name] = arr[:, 0] if arr.shape[1] == 1 else arr
        return out
    return read


def _ascii_table_reader(data_path: Path, offset: int, rows: int, row_bytes: int,
                        specs: List[Tuple[Field, Dict[str, Any]]], delimited: bool):
    def read(names: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        raw = data_path.read_bytes()[offset:]
        if rows and row_bytes and not delimited:
            raw = raw[:rows * row_bytes + 4]
        text = raw.decode("latin-1", errors="replace")
        lines = [ln for ln in text.splitlines()]
        multiline = False
        if rows and row_bytes and not delimited and lines and \
                sorted(len(x) for x in lines[:200])[min(len(lines), 200) // 2] < 0.8 * row_bytes:
            # Records spanning several lines (MRO MCS DDR: 106 lines per profile): START_BYTE
            # counts across the line breaks, so cut the stream into ROW_BYTES records.
            lines = [text[i * row_bytes:(i + 1) * row_bytes] for i in range(min(rows, len(text) // row_bytes))]
            multiline = True
        else:
            lines = _rejoin_broken_records(lines)
        lines = [ln for ln in lines if ln.strip()]
        if rows:
            lines = lines[:rows]
        if limit is not None:
            lines = lines[:limit]
        cells_by_row = None
        if delimited or (not multiline and lines and "," in lines[0] and len(next(csv.reader([lines[0]]))) >= len(specs) > 1
                         and all(s["items"] == 1 for _, s in specs)):
            cells_by_row = list(csv.reader(lines))
        out: Dict[str, Any] = {}
        for idx, (f, s) in enumerate(specs):
            if names is not None and f.name not in names:
                continue
            per_row: List[List[str]] = []
            starts = [s["start"]]
            for reps_n, size in s["reps"]:
                starts = [a + k * size for a in starts for k in range(reps_n)]
            for r, ln in enumerate(lines):
                if cells_by_row is not None:
                    row = cells_by_row[r]
                    k = (s["field_number"] or idx + 1) - 1
                    per_row.append([row[k] if k < len(row) else ""])
                else:
                    vals = []
                    for b0 in starts:
                        for i in range(s["items"]):
                            a = b0 + i * s["item_offset"]
                            vals.append(ln[a:a + s["item_bytes"]])
                    per_row.append(vals)
            if f.kind in ("text", "time"):
                texts = [v[0].strip().strip('"').strip() for v in per_row]
                out[f.name] = [iso_time(t) if f.kind == "time" and t else t for t in texts]
                continue
            arr = np.full((len(per_row), max(len(per_row[0]) if per_row else 1, 1)), np.nan)
            for r, vals in enumerate(per_row):
                for i, v in enumerate(vals):
                    v = v.strip().strip(",").strip('"')
                    if v:
                        try:
                            arr[r, i] = float(v.replace("D", "E").replace("d", "e"))
                        except ValueError:
                            pass
            missing = list(s["missing"])
            if not missing:
                missing = [-999.0, -9999.0, -99999.0, -1e32]       # common undeclared fill values
            arr = _clean(arr, missing, s["scale"], s["offset"])
            out[f.name] = arr[:, 0] if arr.shape[1] == 1 else arr
        return out
    return read


_DATE_PARTS = ("YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND")


def _date_text_iso(d: str) -> Optional[str]:
    """'01-Jan-2016', '2016-01-01', '2016/01/01' or '2016-001' -> '2016-01-01'."""
    import datetime as _dt
    d = d.strip().strip('"')
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%j"):
        try:
            return _dt.datetime.strptime(d, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _add_date_plus_time(obj: DataObject) -> bool:
    """A text DATE column and a time-of-day column (MRO MCS: "01-Jan-2016", "00:00:29.499") -> UTC."""
    names = {f.name.upper(): f for f in obj.fields}
    date_f = names.get("DATE") or names.get("OBS_DATE") or names.get("UTC_DATE")
    time_f = next((names[k] for k in ("UTC", "TIME", "UTC_TIME", "TIME_UTC", "OBS_TIME") if k in names), None)
    if not date_f or not time_f or date_f.kind == "number" or "UTC (assembled)" in names:
        return False
    inner = obj._reader
    try:
        sample = inner([date_f.name, time_f.name], 3)
    except Exception:          # noqa: BLE001
        return False
    d0, t0 = (sample.get(date_f.name) or [""])[0], (sample.get(time_f.name) or [""])[0]
    if not isinstance(d0, str) or not _date_text_iso(d0) or not re.match(r"^\s*\d{1,2}:\d{2}", str(t0)):
        return False

    def read(sel=None, limit=None):
        want = None if sel is None else [s for s in sel if s != "UTC (assembled)"]
        out = inner(want, limit) if want is None or want else {}
        if sel is None or "UTC (assembled)" in sel:
            src = inner([date_f.name, time_f.name], limit)
            out["UTC (assembled)"] = [f"{_date_text_iso(d) or ''}T{str(t).strip()}" if _date_text_iso(d) else ""
                                      for d, t in zip(src[date_f.name], src[time_f.name])]
        return out
    obj._reader = read
    obj.fields.insert(0, Field("UTC (assembled)", description=f"{date_f.name} + {time_f.name}", kind="time"))
    return True


def _add_assembled_time(obj: DataObject) -> None:
    """Tables storing the date as YEAR, MONTH, DAY, HOUR, MINUTE, SECOND numbers get a UTC column."""
    if _add_date_plus_time(obj):
        return
    names = {f.name.upper(): f.name for f in obj.fields}
    have = [p for p in _DATE_PARTS if p in names]
    doy = names.get("DAY_OF_YEAR") or names.get("DOY")
    if "YEAR" not in names or not (("MONTH" in names and "DAY" in names) or doy) or "UTC (assembled)" in names:
        return
    inner = obj._reader
    parts = [names[p] for p in have] + ([doy] if doy else [])
    frac = names.get("CENTISECOND") or names.get("MILLISECOND")

    def read(sel=None, limit=None):
        want = None if sel is None else [s for s in sel if s != "UTC (assembled)"]
        out = inner(want, limit) if want is None or want else {}
        if sel is None or "UTC (assembled)" in sel:
            import datetime as _dt
            src = inner(parts + ([frac] if frac else []), limit)
            n = len(src[names["YEAR"]])
            times = []
            for i in range(n):
                try:
                    g = {p: src[names[p]][i] for p in have}
                    if doy and "MONTH" not in g:
                        d = _dt.date(int(g["YEAR"]), 1, 1) + _dt.timedelta(days=int(src[doy][i]) - 1)
                    else:
                        d = _dt.date(int(g["YEAR"]), int(g["MONTH"]), int(g["DAY"]))
                    sec = float(g.get("SECOND", 0) or 0)
                    if frac:
                        sec += float(src[frac][i]) / (100.0 if "CENTI" in frac.upper() else 1000.0)
                    t = _dt.datetime(d.year, d.month, d.day, int(g.get("HOUR", 0) or 0), int(g.get("MINUTE", 0) or 0)) \
                        + _dt.timedelta(seconds=sec)
                    times.append(t.isoformat(timespec="milliseconds"))
                except (ValueError, KeyError, OverflowError):
                    times.append("")
            out["UTC (assembled)"] = times
        return out
    obj._reader = read
    obj.fields.insert(0, Field("UTC (assembled)", description="Built from the date and time fields", kind="time"))


def _classify_text_fields(obj: DataObject) -> None:
    """Mark text fields holding UTC times as 'time' (reads a few rows)."""
    _add_assembled_time(obj)
    texts = [f for f in obj.fields if f.kind == "text"]
    if not texts:
        return
    try:
        sample = obj._reader([f.name for f in texts], 50)
    except Exception:          # noqa: BLE001 - classification only
        return
    for f in texts:
        vals = sample.get(f.name) or []
        if isinstance(vals, list) and _looks_like_time(vals):
            f.kind = "time"


def _pds3_table(node: _Node, ptr: str, record_bytes: int, label: Path) -> DataObject:
    data, off = _pds3_offset(ptr, record_bytes, label)
    specs = _pds3_fields(node)
    if not specs:
        raise ProductError(f"{node.name} has no columns")
    fmt = (node.get("INTERCHANGE_FORMAT") or "").upper()
    binary = "BINARY" in fmt or node.name.endswith("BINARY_TABLE") or (
        not fmt and any(not s["type"].upper().startswith(("ASCII", "CHARACTER", "DATE", "TIME")) for _, s in specs))
    rows = _int(node.get("ROWS"), 0)
    row_bytes = _int(node.get("ROW_BYTES"), 0)
    for f, s in specs:
        t = s["type"].upper()
        if any(x in t for x in ("CHARACTER", "TIME", "DATE")) or (binary and "ASCII" in t):
            f.kind = "text"
    if binary:
        if not row_bytes:
            raise ProductError(f"{node.name}: binary table without ROW_BYTES")
        prefix = _int(node.get("ROW_PREFIX_BYTES"), 0)
        stride = row_bytes + prefix + _int(node.get("ROW_SUFFIX_BYTES"), 0)
        reader = _binary_table_reader(data, off, rows, stride, prefix, specs)
    else:
        reader = _ascii_table_reader(data, off, rows, row_bytes, specs, node.name.endswith("SPREADSHEET")
                                     or (node.get("FIELD_DELIMITER") is not None))
    obj = DataObject(name=node.name, kind="table", shape=(rows, len(specs)), fields=[f for f, _ in specs],
                     description=" ".join(node.get("DESCRIPTION", "").split())[:400], _reader=reader)
    _classify_text_fields(obj)
    return obj


def _sample_dtype(sample_type: str, bits: int) -> Tuple[Optional[np.dtype], str]:
    t = (sample_type or "").upper()
    if not t:
        t = "UNSIGNED_INTEGER" if bits <= 16 else "MSB_INTEGER"
    if bits == 8 and "REAL" not in t:
        signed = "INTEGER" in t and "UNSIGNED" not in t
        return np.dtype("i1" if signed else "u1"), "number"
    return _pds3_dtype(t, bits // 8)


def _pds3_image(node: _Node, ptr: str, record_bytes: int, label: Path) -> DataObject:
    data, off = _pds3_offset(ptr, record_bytes, label)
    if node.get("ENCODING_TYPE") and node.get("ENCODING_TYPE").upper() not in ("N/A", "NONE"):
        raise ProductError(f"{node.name} is compressed ({node.get('ENCODING_TYPE')}); VEDA reads uncompressed images only")
    lines, samples = _int(node.get("LINES")), _int(node.get("LINE_SAMPLES"))
    bands = max(_int(node.get("BANDS"), 1), 1)
    bits = _int(node.get("SAMPLE_BITS"), 8)
    dt, kind = _sample_dtype(node.get("SAMPLE_TYPE", ""), bits)
    if kind not in ("number", "vax") or dt is None:
        raise ProductError(f"{node.name}: unsupported SAMPLE_TYPE {node.get('SAMPLE_TYPE')}")
    pre, suf = _int(node.get("LINE_PREFIX_BYTES")), _int(node.get("LINE_SUFFIX_BYTES"))
    storage = (node.get("BAND_STORAGE_TYPE") or "BAND_SEQUENTIAL").upper()
    missing = [x for x in (_num(node.get(k)) for k in ("MISSING_CONSTANT", "INVALID_CONSTANT", "NULL", "CORE_NULL",
                                                         "MISSING", "INVALID")) if x is not None]
    vrange = None
    vmin, vmax = _num(node.get("VALID_MINIMUM")), _num(node.get("VALID_MAXIMUM"))
    if vmin is not None and vmax is not None and vmax > vmin:
        vrange = (vmin, vmax)
    scale, offs = _num(node.get("SCALING_FACTOR"), 1.0), _num(node.get("OFFSET"), 0.0)
    b = dt.itemsize

    def read():
        buf = _mmap(data)
        if storage.startswith("SAMPLE_INTERLEAVED"):
            line_len = pre + samples * bands * b + suf
            v = _strided(buf, dt, off + pre, (bands, lines, samples), (b, line_len, bands * b))
        elif storage.startswith("LINE_INTERLEAVED"):
            line_len = pre + samples * b + suf
            v = _strided(buf, dt, off + pre, (bands, lines, samples), (line_len, line_len * bands, b))
        else:
            line_len = pre + samples * b + suf
            v = _strided(buf, dt, off + pre, (bands, lines, samples), (line_len * lines, line_len, b))
        return v, lambda a: _clean(a, missing, scale, offs, vrange)

    return DataObject(name=node.name, kind="image", shape=(bands, lines, samples), unit=node.get("UNIT", ""),
                      axes=("BAND", "LINE", "SAMPLE"),
                      description=" ".join(node.get("DESCRIPTION", "").split())[:400], _reader=read)


def _pds3_qube(node: _Node, ptr: str, record_bytes: int, label: Path) -> DataObject:
    data, off = _pds3_offset(ptr, record_bytes, label)
    names = [n.upper() for n in _seq(node.get("AXIS_NAME"))]
    core = [int(float(x)) for x in _seq(node.get("CORE_ITEMS"))]
    if len(names) != 3 or len(core) != 3:
        raise ProductError(f"{node.name}: only 3-axis cubes are supported")
    cb = _int(node.get("CORE_ITEM_BYTES"), 2)
    dt, kind = _pds3_dtype(node.get("CORE_ITEM_TYPE", "MSB_INTEGER"), cb)
    if dt is None or kind not in ("number",):
        raise ProductError(f"{node.name}: unsupported CORE_ITEM_TYPE {node.get('CORE_ITEM_TYPE')}")
    suffix = [int(float(x)) for x in _seq(node.get("SUFFIX_ITEMS"))] or [0, 0, 0]
    sb = _int(node.get("SUFFIX_BYTES"), 4)
    a, bb, c = core                                  # first axis fastest
    sa, sbb, _sc = suffix + [0] * (3 - len(suffix))
    row_core = a * cb + sa * sb                      # one fastest-axis run plus its side items
    row_suffix = (a + sa) * sb
    plane = bb * row_core + sbb * row_suffix
    base_v, mult = _num(node.get("CORE_BASE"), 0.0), _num(node.get("CORE_MULTIPLIER"), 1.0)
    missing = [x for x in (_num(node.get(k)) for k in ("CORE_NULL", "CORE_VALID_MINIMUM_NULL", "MISSING_CONSTANT"))
               if x is not None]
    vmin = _num(node.get("CORE_VALID_MINIMUM"))
    if dt.kind == "i" and dt.itemsize == 2 and not missing:
        missing = [-32768.0]

    def read():
        buf = _mmap(data)
        v = _strided(buf, dt, off, (c, bb, a), (plane, row_core, cb))
        # numpy axes are (slowest, middle, fastest) = names reversed
        order = [names[2], names[1], names[0]]
        want = ["BAND", "LINE", "SAMPLE"]
        if set(order) == set(want):
            v = np.transpose(v, [order.index(w) for w in want])

        def clean(raw):
            raw = _fix_byte_order(raw)
            arr = _clean(raw, missing, mult, base_v)
            if vmin is not None and dt.kind in "iu":
                arr[raw < vmin] = np.nan
            return arr
        return v, clean

    order = [names[2], names[1], names[0]]
    shape = (c, bb, a)
    if set(order) == {"BAND", "LINE", "SAMPLE"}:
        shape = tuple(shape[order.index(w)] for w in ("BAND", "LINE", "SAMPLE"))
    return DataObject(name=node.name, kind="cube", shape=shape, axes=("BAND", "LINE", "SAMPLE"),
                      description=" ".join(node.get("DESCRIPTION", "").split())[:400], _reader=read)


def _collection_specs(coll: _Node, base: int = 0) -> List[Tuple[Field, Dict[str, Any]]]:
    """ELEMENTs and nested ARRAYs of a COLLECTION as binary-table fields."""
    out: List[Tuple[Field, Dict[str, Any]]] = []
    for ch in coll.children:
        if ch.kind != "OBJECT":
            continue
        start = base + _int(ch.get("START_BYTE"), 1) - 1
        if ch.name == "ELEMENT":
            nb = _int(ch.get("BYTES"), 4)
            spec = {"start": start, "bytes": nb, "items": 1, "item_bytes": nb, "item_offset": nb,
                    "type": ch.get("DATA_TYPE", "MSB_INTEGER"), "scale": _num(ch.get("SCALING_FACTOR"), 1.0),
                    "offset": _num(ch.get("OFFSET"), 0.0), "field_number": 0, "reps": [],
                    "missing": [x for x in (_num(ch.get(k)) for k in ("MISSING_CONSTANT", "INVALID_CONSTANT")) if x is not None]}
            f = Field(ch.get("NAME", f"ELEMENT_{len(out) + 1}"), ch.get("UNIT", ""),
                      " ".join(ch.get("DESCRIPTION", "").split())[:300])
            if any(x in spec["type"].upper() for x in ("CHARACTER", "TIME", "DATE", "ASCII")):
                f.kind = "text"
            out.append((f, spec))
        elif ch.name == "ARRAY":
            el = next((c for c in ch.children if c.name == "ELEMENT"), None)
            if el is None:
                continue
            n = int(np.prod([int(float(x)) for x in _seq(ch.get("AXIS_ITEMS"))] or [1]))
            nb = _int(el.get("BYTES"), 4)
            spec = {"start": start, "bytes": n * nb, "items": n, "item_bytes": nb, "item_offset": nb,
                    "type": el.get("DATA_TYPE", "MSB_INTEGER"), "scale": _num(el.get("SCALING_FACTOR"), 1.0),
                    "offset": _num(el.get("OFFSET"), 0.0), "field_number": 0, "reps": [],
                    "missing": [x for x in (_num(el.get(k)) for k in ("MISSING_CONSTANT", "INVALID_CONSTANT")) if x is not None]}
            out.append((Field(ch.get("NAME", "ARRAY"), el.get("UNIT", ""),
                              " ".join(ch.get("DESCRIPTION", "").split())[:300], items=n), spec))
        elif ch.name == "COLLECTION":
            out.extend(_collection_specs(ch, start))
    return out


def _pds3_array(node: _Node, ptr: str, record_bytes: int, label: Path) -> DataObject:
    data, off = _pds3_offset(ptr, record_bytes, label)
    items = [int(float(x)) for x in _seq(node.get("AXIS_ITEMS"))]
    coll = next((c for c in node.children if c.name == "COLLECTION"), None)
    if coll is not None and len(items) == 1:
        # An array of records (e.g. SPICAV): really a binary table, one row per record.
        specs = _collection_specs(coll)
        stride = _int(coll.get("BYTES"), 0)
        if not specs or not stride:
            raise ProductError(f"{node.name}: record array without element layout")
        obj = DataObject(name=node.name, kind="table", shape=(items[0], len(specs)), fields=[f for f, _ in specs],
                         description=" ".join(node.get("DESCRIPTION", "").split())[:400],
                         _reader=_binary_table_reader(data, off, items[0], stride, 0, specs))
        _classify_text_fields(obj)
        return obj
    elem = next((c for c in node.children if c.name in ("ELEMENT", "COLLECTION")), None)
    if not items or elem is None:
        raise ProductError(f"{node.name}: array without AXIS_ITEMS / ELEMENT")
    nb = _int(elem.get("BYTES"), 4)
    dt, kind = _pds3_dtype(elem.get("DATA_TYPE", "MSB_INTEGER"), nb)
    if dt is None or kind != "number":
        raise ProductError(f"{node.name}: unsupported element type {elem.get('DATA_TYPE')}")
    missing = [x for x in (_num(elem.get(k)) for k in ("MISSING_CONSTANT", "INVALID_CONSTANT")) if x is not None]
    scale, offs = _num(elem.get("SCALING_FACTOR"), 1.0), _num(elem.get("OFFSET"), 0.0)

    kind_out = "image" if len(items) == 2 else "array"

    def read():
        buf = _mmap(data)
        strides, acc = [], nb
        for n in reversed(items):
            strides.insert(0, acc)
            acc *= n
        v = _strided(buf, dt, off, tuple(items), tuple(strides))
        return (v[None, ...] if kind_out == "image" else v), lambda a: _clean(a, missing, scale, offs)

    return DataObject(name=node.name, kind=kind_out, shape=tuple(items) if kind_out != "image" else (1, *items),
                      axes=tuple(_seq(node.get("AXIS_NAME"))), unit=elem.get("UNIT", ""), _reader=read)


_TABLE_NAMES = ("TABLE", "SERIES", "SPREADSHEET", "SPECTRUM", "HISTOGRAM", "PALETTE")


def _open_pds3(label: Path) -> Product:
    text = _label_text(label)
    tree = _parse_pds3_tree(text, label.parent)
    meta = {k: v for k, v in tree.attrs.items() if not k.startswith("^")}
    pointers = {k[1:]: v for k, v in tree.attrs.items() if k.startswith("^") and k != "^STRUCTURE"}
    record_bytes = _int(tree.get("RECORD_BYTES"), 0) or 1
    objects: List[DataObject] = []
    texts: List[DataObject] = []
    errors: List[str] = []
    for node in tree.children:
        if node.kind != "OBJECT":
            continue
        ptr = pointers.get(node.name)
        if ptr is None:
            # the pointer may name a FILE object's members, or use a prefix (^IMAGE for OBJECT = IMAGE)
            ptr = next((v for k, v in pointers.items() if k.endswith(node.name) or node.name.endswith(k)), None)
        if node.name == "FILE":
            sub = _parse_file_object(node, label)
            objects.extend(sub)
            if not sub:
                errors.append("the label describes the file only as raw bytes (no table, image or array "
                              "layout), so it can be downloaded but not plotted")
            continue
        if ptr is None:
            continue
        try:
            if node.name.endswith("QUBE"):
                objects.append(_pds3_qube(node, ptr, record_bytes, label))
            elif node.name.endswith("IMAGE") and not node.name.endswith("HEADER"):
                objects.append(_pds3_image(node, ptr, record_bytes, label))
            elif node.name.endswith("ARRAY"):
                objects.append(_pds3_array(node, ptr, record_bytes, label))
            elif any(node.name.endswith(t) for t in _TABLE_NAMES) or node.name.endswith("TABLE_OBJECT"):
                objects.append(_pds3_table(node, ptr, record_bytes, label))
            elif node.name.endswith(("TEXT", "DOCUMENT")) and not node.name.endswith("HEADER"):
                texts.append(_text_object(node.name, label, ptr, record_bytes, str(node.get("DESCRIPTION") or "").strip('"')))
        except ProductError as exc:
            errors.append(f"{node.name}: {exc}")
        except (OSError, ValueError) as exc:
            errors.append(f"{node.name}: {exc}")
    if not objects:
        # FITS data with a PDS3 label (e.g. Akatsuki): read the FITS file itself
        fits_name = next((str(v).strip('"') for k, v in pointers.items()
                          if str(v).strip('"').lower().endswith((".fit", ".fits", ".fts"))), None)
        fits_name = fits_name or next((v for k, v in meta.items() if k == "FILE_NAME" and
                                       str(v).lower().endswith((".fit", ".fits"))), None)
        nc_name = next((str(v).strip('"') for v in pointers.values()
                        if str(v).strip('"').lower().endswith((".nc", ".nc4"))), None)
        if nc_name and _find(label.parent, nc_name):
            prod = _open_netcdf(_find(label.parent, nc_name))
            prod.metadata = {**meta, **prod.metadata}
            prod.path = str(label)
            return prod
        fp = _find(label.parent, fits_name) if fits_name else None
        if fp:
            prod = _open_fits(fp)
            prod.metadata = {**meta, **prod.metadata}
            prod.path = str(label)
            return prod
        if texts:
            return Product(path=str(label), format="PDS3", metadata=meta, objects=texts)
        raise ProductError("; ".join(errors) if errors else
                           f"{label.name} describes no table, image or cube VEDA can read")
    return Product(path=str(label), format="PDS3", metadata=meta, objects=objects)


def _parse_file_object(node: _Node, label: Path) -> List[DataObject]:
    """OBJECT = FILE groups (several data files described in one label)."""
    out: List[DataObject] = []
    ptrs = {k[1:]: v for k, v in node.attrs.items() if k.startswith("^")}
    rb = _int(node.get("RECORD_BYTES"), 1) or 1
    for ch in node.children:
        ptr = ptrs.get(ch.name)
        if ch.kind != "OBJECT" or ptr is None:
            continue
        try:
            if ch.name.endswith("IMAGE"):
                out.append(_pds3_image(ch, ptr, rb, label))
            elif any(ch.name.endswith(t) for t in _TABLE_NAMES):
                out.append(_pds3_table(ch, ptr, rb, label))
        except (ProductError, OSError, ValueError):
            continue
    return out


# ====================================================================== PDS4

_PDS4_TYPES = {
    "IEEE754MSBSingle": ">f4", "IEEE754MSBDouble": ">f8", "IEEE754LSBSingle": "<f4", "IEEE754LSBDouble": "<f8",
    "SignedMSB2": ">i2", "SignedMSB4": ">i4", "SignedMSB8": ">i8", "SignedLSB2": "<i2", "SignedLSB4": "<i4",
    "SignedLSB8": "<i8", "UnsignedMSB2": ">u2", "UnsignedMSB4": ">u4", "UnsignedMSB8": ">u8",
    "UnsignedLSB2": "<u2", "UnsignedLSB4": "<u4", "UnsignedLSB8": "<u8", "SignedByte": "i1",
    "UnsignedByte": "u1", "ComplexMSB8": ">c8", "ComplexMSB16": ">c16", "ComplexLSB8": "<c8",
    "ComplexLSB16": "<c16",
}


def _strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _t(el: Optional[ET.Element], path: str, default: str = "") -> str:
    if el is None:
        return default
    f = el.find(path)
    return (f.text or "").strip() if f is not None and f.text else default


def _special(el: ET.Element) -> List[float]:
    out = []
    for sc in el.findall("Special_Constants/*"):
        if sc.tag.startswith(("valid_", "high_", "low_")) and sc.tag not in ("high_instrument_saturation",
                                                                          "low_instrument_saturation",
                                                                          "high_representation_saturation",
                                                                          "low_representation_saturation"):
            continue
        v = _num(sc.text)
        if v is not None:
            out.append(v)
    return out


def _pds4_fields(rec: ET.Element, base: int, binary: bool) -> List[Tuple[Field, Dict[str, Any]]]:
    out: List[Tuple[Field, Dict[str, Any]]] = []
    ftag, gtag = ("Field_Binary", "Group_Field_Binary") if binary else ("Field_Character", "Group_Field_Character")
    for ch in list(rec):
        if ch.tag == ftag:
            dtype = _t(ch, "data_type")
            n = _int(_t(ch, "field_length"), 0)
            spec = {"start": base + _int(_t(ch, "field_location"), 1) - 1, "bytes": n, "items": 1,
                    "item_bytes": n, "item_offset": n, "type": dtype,
                    "scale": _num(_t(ch, "scaling_factor"), 1.0), "offset": _num(_t(ch, "value_offset"), 0.0),
                    "missing": _special(ch), "reps": [], "field_number": 0}
            kind = "time" if "Date_Time" in dtype or dtype.startswith("ASCII_Date") else \
                "text" if (dtype.startswith(("ASCII_String", "UTF8", "ASCII_AnyURI", "ASCII_File", "ASCII_Directory",
                                             "ASCII_LID", "ASCII_VID", "ASCII_MD5")) or
                           (binary and dtype not in _PDS4_TYPES and not dtype.startswith("ASCII_"))) else "number"
            if binary and dtype.startswith("ASCII_") and kind == "number":
                kind = "text"
                spec["ascii_number"] = True
            f = Field(name=_t(ch, "name") or f"FIELD_{len(out) + 1}", unit=_t(ch, "unit"),
                      description=" ".join(_t(ch, "description").split())[:300], kind=kind)
            out.append((f, spec))
        elif ch.tag == gtag:
            reps = max(_int(_t(ch, "repetitions"), 1), 1)
            start = base + _int(_t(ch, "group_location"), 1) - 1
            glen = _int(_t(ch, "group_length"), 0)
            size = glen // reps if reps else glen
            gname = _t(ch, "name")
            for f, spec in _pds4_fields(ch, start, binary):
                if gname:
                    f.name = f"{gname}.{f.name}"
                if reps > 1:
                    spec["reps"] = [(reps, size)] + spec["reps"]
                    f.items *= reps
                out.append((f, spec))
    return out


def _pds4_binary_reader(path: Path, offset: int, rows: int, rec_len: int,
                        specs: List[Tuple[Field, Dict[str, Any]]]):
    def read(names: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        buf = _mmap(path)
        out: Dict[str, Any] = {}
        n = rows if limit is None else min(rows, limit)
        if rec_len and n * rec_len > buf.size - offset:
            n = max((buf.size - offset) // rec_len, 0)
        for f, s in specs:
            if names is not None and f.name not in names:
                continue
            reps = s["reps"]
            shape = [n] + [r for r, _ in reps]
            strides = [rec_len] + [sz for _, sz in reps]
            base = offset + s["start"]
            if f.kind in ("text", "time") or s["type"] not in _PDS4_TYPES:
                raw = _strided(buf, np.dtype(f"S{s['bytes']}"), base, tuple(shape), tuple(strides))
                flat = np.ascontiguousarray(raw).reshape(n, -1)[:, 0]
                texts = [b.decode("utf-8", errors="replace").strip() for b in flat]
                if s.get("ascii_number"):
                    out[f.name] = np.array([_num(t, np.nan) for t in texts], dtype=float)
                else:
                    out[f.name] = [iso_time(t) for t in texts] if f.kind == "time" else texts
                continue
            dt = np.dtype(_PDS4_TYPES[s["type"]])
            raw = np.asarray(_strided(buf, dt, base, tuple(shape), tuple(strides)))
            if dt.kind == "c":
                raw = np.abs(raw)
            raw = _fix_mislabelled_float(raw)
            arr = _clean(raw, s["missing"], s["scale"], s["offset"]).reshape(n, -1)
            out[f.name] = arr[:, 0] if arr.shape[1] == 1 else arr
        return out
    return read


def _pds4_char_reader(path: Path, offset: int, rows: int, rec_len: int,
                      specs: List[Tuple[Field, Dict[str, Any]]]):
    def read(names: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        n = rows if limit is None else min(rows or limit, limit)
        raw = path.read_bytes()[offset:offset + n * rec_len if n and rec_len else None]
        lines = raw.decode("utf-8", errors="replace").splitlines() if not rec_len else \
            [raw[i * rec_len:(i + 1) * rec_len].decode("utf-8", errors="replace") for i in range(len(raw) // rec_len)]
        out: Dict[str, Any] = {}
        for f, s in specs:
            if names is not None and f.name not in names:
                continue
            reps = s["reps"]
            starts = [s["start"]]
            for r, sz in reps:
                starts = [a + k * sz for a in starts for k in range(r)]
            cells = [[ln[a:a + s["bytes"]].strip() for a in starts] for ln in lines]
            if f.kind in ("text", "time"):
                out[f.name] = [iso_time(c[0]) if f.kind == "time" and c[0] else c[0] for c in cells]
                continue
            arr = np.array([[_num(v, np.nan) for v in c] for c in cells], dtype=float).reshape(len(cells), -1)
            arr = _clean(arr, s["missing"], s["scale"], s["offset"])
            out[f.name] = arr[:, 0] if arr.shape[1] == 1 else arr
        return out
    return read


def _pds4_delim_reader(path: Path, offset: int, rows: int, delim: str, fields: List[ET.Element],
                       flist: List[Field], skip_header: bool):
    def read(names: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        text = path.read_bytes()[offset:].decode("utf-8", errors="replace")
        recs = list(csv.reader(io.StringIO(text), delimiter=delim))
        recs = [r for r in recs if any(c.strip() for c in r)]
        hdr = [c.strip() for c in recs[0]] if recs else []
        if recs and hdr[:len(flist)] == [f.name for f in flist]:
            recs = recs[1:]
        if rows:
            recs = recs[:rows]
        if limit is not None:
            recs = recs[:limit]
        out: Dict[str, Any] = {}
        for i, (f, el) in enumerate(zip(flist, fields)):
            if names is not None and f.name not in names:
                continue
            k = _int(_t(el, "field_number"), i + 1) - 1
            cells = [r[k].strip() if k < len(r) else "" for r in recs]
            if f.kind in ("text", "time"):
                out[f.name] = [iso_time(c) if f.kind == "time" and c else c for c in cells]
            else:
                arr = np.array([_num(c, np.nan) for c in cells], dtype=float)
                out[f.name] = _clean(arr, _special(el), _num(_t(el, "scaling_factor"), 1.0),
                                     _num(_t(el, "value_offset"), 0.0))
        return out
    return read


def _open_pds4(label: Path) -> Product:
    root = _strip_ns(ET.parse(label).getroot())
    meta: Dict[str, Any] = {
        "LOGICAL_IDENTIFIER": _t(root, "Identification_Area/logical_identifier"),
        "TITLE": _t(root, "Identification_Area/title"),
    }
    obs = root.find("Observation_Area")
    if obs is not None:
        meta["START_TIME"] = _t(obs, "Time_Coordinates/start_date_time")
        meta["STOP_TIME"] = _t(obs, "Time_Coordinates/stop_date_time")
        meta["TARGET_NAME"] = _t(obs, "Target_Identification/name")
        meta["INSTRUMENT_NAME"] = _t(obs, "Observing_System/Observing_System_Component[type='Instrument']/name")
        meta["INSTRUMENT_HOST_NAME"] = _t(obs, "Observing_System/Observing_System_Component[type='Host']/name") or \
            _t(obs, "Observing_System/Observing_System_Component[type='Spacecraft']/name")
        meta["PROCESSING_LEVEL_ID"] = _t(obs, "Primary_Result_Summary/processing_level")
    objects: List[DataObject] = []
    texts: List[DataObject] = []
    errors: List[str] = []
    for fao in root.findall("File_Area_Observational"):
        fname = _t(fao, "File/file_name")
        data = _find(label.parent, fname) if fname else None
        for el in list(fao):
            tag = el.tag
            if tag in ("File", "Header", "Encoded_Header", "Encoded_Image", "Encoded_Binary"):
                continue
            if tag == "Stream_Text":
                if data is None:
                    errors.append(f"{fname} (named in {label.name}) is not here; download the product again")
                else:
                    texts.append(_text_file_object(_t(el, "name") or fname, data, _int(_t(el, "offset"), 0),
                                                   _int(_t(el, "object_length"), 0), _t(el, "description")))
                continue
            if data is None:
                errors.append(f"{fname} (named in {label.name}) is not here; download the product again")
                break
            name = _t(el, "name") or _t(el, "local_identifier") or tag
            off = _int(_t(el, "offset"), 0)
            try:
                if tag == "Table_Binary":
                    rec = el.find("Record_Binary")
                    specs = _pds4_fields(rec, 0, True)
                    rows, rlen = _int(_t(el, "records")), _int(_t(rec, "record_length"))
                    obj = DataObject(name, "table", (rows, len(specs)), [f for f, _ in specs],
                                     _t(el, "description"), _reader=_pds4_binary_reader(data, off, rows, rlen, specs))
                elif tag == "Table_Character":
                    rec = el.find("Record_Character")
                    specs = _pds4_fields(rec, 0, False)
                    rows, rlen = _int(_t(el, "records")), _int(_t(rec, "record_length"))
                    obj = DataObject(name, "table", (rows, len(specs)), [f for f, _ in specs],
                                     _t(el, "description"), _reader=_pds4_char_reader(data, off, rows, rlen, specs))
                elif tag == "Table_Delimited":
                    rec = el.find("Record_Delimited")
                    fields = rec.findall("Field_Delimited") if rec is not None else []
                    flist = []
                    for i, f in enumerate(fields):
                        dt_ = _t(f, "data_type")
                        flist.append(Field(name=_t(f, "name") or f"FIELD_{i + 1}", unit=_t(f, "unit"),
                                           description=" ".join(_t(f, "description").split())[:300],
                                           kind="time" if "Date_Time" in dt_ else
                                           "text" if dt_.startswith(("ASCII_String", "UTF8", "ASCII_LID", "ASCII_AnyURI"))
                                           else "number"))
                    delim = {"Comma": ",", "Horizontal Tab": "\t", "Semicolon": ";", "Vertical Bar": "|"}.get(
                        _t(el, "field_delimiter", "Comma"), ",")
                    rows = _int(_t(el, "records"))
                    obj = DataObject(name, "table", (rows, len(flist)), flist, _t(el, "description"),
                                     _reader=_pds4_delim_reader(data, off, rows, delim, fields, flist, True))
                elif tag.startswith("Array"):
                    obj = _pds4_array(el, name, data, off)
                else:
                    continue
                if obj.kind == "table":
                    _classify_text_fields(obj)
                objects.append(obj)
            except (ProductError, OSError, ValueError, AttributeError) as exc:
                errors.append(f"{name}: {exc}")
    objects = _gridded_maps(objects, meta) + objects
    if not objects and texts:
        return Product(path=str(label), format="PDS4", metadata=meta, objects=texts)
    if not objects:
        raise ProductError("; ".join(errors) if errors else f"{label.name} describes no table or array VEDA can read")
    return Product(path=str(label), format="PDS4", metadata=meta, objects=objects)


def _gridded_maps(objects: List[DataObject], meta: Dict[str, Any]) -> List[DataObject]:
    """Maps rebuilt from tables of grid cells: rows of (Longitude, Latitude, values...) on
    a regular grid with empty cells left out (Akatsuki LIR L3d: 0.25 deg, 1440 x 720).
    One map per value column, gridded when first read."""
    maps: List[DataObject] = []
    for obj in objects:
        if obj.kind != "table" or obj.shape[0] < 100:
            continue
        names = {f.name.lower(): f.name for f in obj.fields}
        lon_f, lat_f = names.get("longitude"), names.get("latitude")
        if not lon_f or not lat_f:
            continue
        try:
            d = obj.read_table([lon_f, lat_f])
            lon, lat = np.asarray(d[lon_f], float), np.asarray(d[lat_f], float)
        except (ProductError, OSError, ValueError, KeyError):
            continue
        ok = np.isfinite(lon) & np.isfinite(lat)
        if ok.sum() < 100:
            continue
        ulon, ulat = np.unique(lon[ok]), np.unique(lat[ok])
        if ulon.size < 2 or ulat.size < 2:
            continue
        dlon, dlat = float(np.min(np.diff(ulon))), float(np.min(np.diff(ulat)))
        ix = np.rint((lon - ulon[0]) / dlon)
        iy = np.rint((lat - ulat[0]) / dlat)
        # regular grid only: every cell centre within 1 % of a grid node
        if np.nanmax(np.abs(ix - (lon - ulon[0]) / dlon)) > 0.01 or np.nanmax(np.abs(iy - (lat - ulat[0]) / dlat)) > 0.01:
            continue
        nx, ny = int(np.nanmax(ix[ok])) + 1, int(np.nanmax(iy[ok])) + 1
        if nx * ny > 20_000_000:
            continue
        ext = {"x": [float(ulon[0]), float(ulon[0] + (nx - 1) * dlon), "Longitude", "deg"],
               "y": [float(ulat[0]), float(ulat[0] + (ny - 1) * dlat), "Latitude", "deg"]}
        title = str(meta.get("TITLE", ""))
        for f in obj.fields:
            if f.name in (lon_f, lat_f) or f.kind != "number" or f.items != 1:
                continue
            unit, note = f.unit, ""
            if "Longwave Infrared Camera" in title and f.name.lower() == "radiance" and unit.startswith("W/"):
                # The LIR L3d label calls the mapped value a radiance in W/(m**2*sr*m), but
                # the values (about 170-260) are brightness temperatures in kelvin.
                unit, note = "K", " Brightness temperature: the label gives W/(m**2*sr*m), which does not match the values."

            def reader(obj=obj, col=f.name, ix=ix, iy=iy, ok=ok, nx=nx, ny=ny, cache={}):
                if "grid" not in cache:
                    v = np.asarray(obj.read_table([col])[col], float)
                    grid = np.full((1, ny, nx), np.nan, np.float32)
                    sel = ok & np.isfinite(v)
                    grid[0, iy[sel].astype(int), ix[sel].astype(int)] = v[sel]
                    cache["grid"] = grid
                return cache["grid"], (lambda a: a)
            maps.append(DataObject(f"{f.name} map", "image", (1, ny, nx), [], (f.description or "") + note +
                                   f" Gridded from {obj.name} ({dlon:g} x {dlat:g} deg).",
                                   ("BAND", "LATITUDE", "LONGITUDE"), unit, ext, _reader=reader))
    return maps


def _text_file_object(name: str, data: Path, offset: int = 0, length: int = 0, description: str = "") -> DataObject:
    """An ASCII stream (operations log, document) shown as text."""
    size = data.stat().st_size
    length = length if 0 < length <= size - offset else size - offset

    def read(max_bytes: int):
        with data.open("rb") as fh:
            fh.seek(offset)
            raw = fh.read(min(length, max_bytes))
        return raw.decode("utf-8", errors="replace").replace("\r\n", "\n"), length > max_bytes

    with data.open("rb") as fh:
        fh.seek(offset)
        lines = fh.read(min(length, 4_000_000)).count(b"\n")
    return DataObject(name, "text", (lines,), [], description or "", _reader=read)


def _text_object(name: str, label: Path, ptr: Any, record_bytes: int, description: str = "") -> DataObject:
    """A PDS3 TEXT or DOCUMENT object: a separate file, or text attached after the label."""
    data, off = _pds3_offset(ptr, record_bytes, label)
    return _text_file_object(name, data, off, 0, description)


def _pds4_array(el: ET.Element, name: str, data: Path, off: int) -> DataObject:
    axes = sorted(el.findall("Axis_Array"), key=lambda a: _int(_t(a, "sequence_number"), 0))
    dims = [_int(_t(a, "elements")) for a in axes]
    anames = [_t(a, "axis_name") for a in axes]
    elem = el.find("Element_Array")
    dtype = _t(elem, "data_type")
    if dtype not in _PDS4_TYPES:
        raise ProductError(f"unsupported array data type {dtype}")
    dt = np.dtype(_PDS4_TYPES[dtype])
    scale, offs = _num(_t(elem, "scaling_factor"), 1.0), _num(_t(elem, "value_offset"), 0.0)
    missing = _special(el)
    last_fastest = _t(el, "axis_index_order", "Last Index Fastest").startswith("Last")

    def clean(raw):
        if raw.dtype.kind == "c":
            raw = np.abs(raw)
        return _clean(_fix_byte_order(raw), missing, scale, offs)

    def view():
        buf = _mmap(data)
        acc = dt.itemsize
        order = list(range(len(dims)))
        seq = reversed(order) if last_fastest else order
        st = [0] * len(dims)
        for i in seq:
            st[i] = acc
            acc *= dims[i]
        return _strided(buf, dt, off, tuple(dims), tuple(st))

    def read():
        return view(), clean

    tag = el.tag
    lower = [a.lower() for a in anames]
    if len(dims) == 2:
        return DataObject(name, "image", (1, *dims), axes=("BAND", *anames), unit=_t(elem, "unit"),
                          description=_t(el, "description"), _reader=lambda: (view()[None, ...], clean))
    if len(dims) == 3:
        band_i = next((i for i, a in enumerate(lower) if "band" in a or "wave" in a or "spectral" in a or "channel" in a),
                      0 if "Spectrum" in tag else None)

        def read_cube():
            v = view()
            if band_i is not None and band_i != 0:
                v = np.moveaxis(v, band_i, 0)
            return v, clean
        shape = tuple(dims) if band_i in (None, 0) else (dims[band_i], *[d for i, d in enumerate(dims) if i != band_i])
        return DataObject(name, "cube", shape, axes=("BAND", "LINE", "SAMPLE"), unit=_t(elem, "unit"),
                          description=_t(el, "description"), _reader=read_cube)
    return DataObject(name, "array", tuple(dims), axes=tuple(anames), unit=_t(elem, "unit"),
                      description=_t(el, "description"), _reader=read)


# ====================================================================== FITS and text

def _open_fits(path: Path) -> Product:
    from astropy.io import fits
    objects: List[DataObject] = []
    meta: Dict[str, Any] = {}
    with fits.open(path, memmap=True, lazy_load_hdus=True) as hdul:
        hdr0 = hdul[0].header
        for k in ("DATE-OBS", "OBJECT", "TELESCOP", "INSTRUME", "DATE_OBS", "TARGET"):
            if k in hdr0:
                meta[k.replace("-", "_")] = str(hdr0[k])
        if "DATE_OBS" in meta:
            meta["START_TIME"] = meta["DATE_OBS"]
        for i, h in enumerate(hdul):
            name = h.name or f"HDU{i}"
            if h.is_image and h.header.get("NAXIS", 0) >= 2:
                shape = tuple(int(h.header[f"NAXIS{j}"]) for j in range(h.header["NAXIS"], 0, -1))
                unit = str(h.header.get("BUNIT", ""))

                def read_img(idx=i):
                    hl = fits.open(path, memmap=True)        # closed when the data are released
                    a = hl[idx].data
                    if a.ndim == 2:
                        a = a[None, ...]
                    elif a.ndim > 3:
                        a = a.reshape(-1, *a.shape[-2:])
                    return a, lambda raw: np.where(np.isfinite(raw), raw, np.nan).astype(np.float64)
                kind = "cube" if len(shape) >= 3 and shape[0] > 3 else "image"
                objects.append(DataObject(name, kind, shape if len(shape) == 3 else (1, *shape[-2:]),
                                          axes=("BAND", "LINE", "SAMPLE"), unit=unit, _reader=read_img))
            elif isinstance(h, (fits.BinTableHDU, fits.TableHDU)):
                cols = h.columns
                flist = []
                for c in cols:
                    fmt = str(c.format)
                    is_text = "A" in fmt
                    rep = 1
                    m = re.match(r"^(\d+)", fmt)
                    if m and not is_text:
                        rep = int(m.group(1))
                    flist.append(Field(name=c.name, unit=str(c.unit or ""), items=rep,
                                       kind="text" if is_text else "number"))

                def read_tab(names=None, limit=None, idx=i, flist=flist) -> Dict[str, Any]:
                    out: Dict[str, Any] = {}
                    with fits.open(path, memmap=True) as hl:
                        d = hl[idx].data if limit is None else hl[idx].data[:limit]
                        for f in flist:
                            if names is not None and f.name not in names:
                                continue
                            v = d[f.name]
                            if f.kind != "number":
                                out[f.name] = [str(x).strip() for x in v]
                            else:
                                arr = np.asarray(v, dtype=np.float64)
                                out[f.name] = arr.reshape(arr.shape[0], -1) if arr.ndim > 1 else arr
                    return out
                obj = DataObject(name, "table", (int(h.header.get("NAXIS2", 0)), len(flist)), flist, _reader=read_tab)
                _classify_text_fields(obj)
                objects.append(obj)
    if not objects:
        raise ProductError(f"{path.name} contains no image or table")
    return Product(path=str(path), format="FITS", metadata=meta, objects=objects)


class _NcView:
    """A netCDF variable seen as (band, line, sample): leading dimensions are folded into bands."""

    def __init__(self, var):
        self.var = var
        shp = var.shape
        self.lead = shp[:-2]
        self.shape = (int(np.prod(self.lead)) if self.lead else 1, shp[-2], shp[-1])
        self.ndim = 3

    def __getitem__(self, key):
        b, l, s = key
        idx = range(self.shape[0])[b]
        planes = []
        for i in idx:
            lead = np.unravel_index(i, self.lead) if self.lead else ()
            planes.append(np.ma.filled(np.ma.asarray(self.var[(*lead, l, s)]).astype(np.float64), np.nan))
        return np.stack(planes) if planes else np.zeros((0, 0, 0))


def _nc_times(var) -> Optional[List[str]]:
    units = getattr(var, "units", "")
    if " since " not in str(units):
        return None
    try:
        import netCDF4
        dates = netCDF4.num2date(var[:], units, getattr(var, "calendar", "standard"),
                                 only_use_cftime_datetimes=False, only_use_python_datetimes=True)
        return [d.isoformat() if d is not None else "" for d in np.ravel(dates)]
    except Exception:          # noqa: BLE001 - leave the values numeric
        return None


def _open_netcdf(path: Path) -> Product:
    try:
        import netCDF4
    except ImportError as exc:
        raise ProductError("Reading netCDF files needs the netCDF4 package (pip install netCDF4)") from exc
    ds = netCDF4.Dataset(str(path))           # kept open while the views are in use
    ds.set_auto_maskandscale(True)
    meta: Dict[str, Any] = {k.upper(): str(getattr(ds, k))[:500] for k in ds.ncattrs()}
    objects: List[DataObject] = []
    vars_ = ds.variables
    # one-value text variables (FITS-like keywords, e.g. Akatsuki L3) -> metadata
    for name, v in vars_.items():
        if v.dtype.kind == "S" and v.ndim == 1:
            try:
                meta[name.upper()] = b"".join(v[:].compressed() if hasattr(v[:], "compressed") else v[:]).decode(
                    "latin-1", "replace").strip()
            except Exception:  # noqa: BLE001
                pass
    if "DATE_OBS" in meta and "START_TIME" not in meta:
        meta["START_TIME"] = meta["DATE_OBS"]
    coords = {n: vars_[n] for n in ds.dimensions if n in vars_ and vars_[n].ndim == 1}
    by_dim: Dict[str, List[str]] = {}
    for name, v in vars_.items():
        if v.dtype.kind in "SU" or v.dtype == str:
            continue
        dims = v.dimensions
        sizes = [len(ds.dimensions[d]) for d in dims]
        if v.ndim >= 2 and sizes[-1] > 1 and sizes[-2] > 1:
            ext: Dict[str, Any] = {}
            for axis, d in (("x", dims[-1]), ("y", dims[-2])):
                c = coords.get(d)
                if c is not None and c.size > 1:
                    vals = np.ma.filled(np.ma.asarray(c[:]).astype(float), np.nan)
                    ext[axis] = [float(vals[0]), float(vals[-1]), d, str(getattr(c, "units", ""))]
            view = _NcView(v)
            if view.shape[0] > 64 and v.ndim > 3:
                continue          # per-pixel index tables etc.
            objects.append(DataObject(
                name=name, kind="cube" if view.shape[0] > 3 else "image", shape=view.shape,
                axes=("BAND", dims[-2].upper(), dims[-1].upper()), unit=str(getattr(v, "units", "")),
                description=str(getattr(v, "long_name", "") or getattr(v, "description", ""))[:300], extent=ext,
                _reader=(lambda view=view: (view, lambda a: a))))
        elif v.ndim == 1 and sizes[0] > 1:
            by_dim.setdefault(dims[0], []).append(name)
    for dim, names in by_dim.items():
        if dim in names:
            names.remove(dim)
            names.insert(0, dim)
        if len(names) < 1 or (len(names) == 1 and names[0] == dim):
            continue
        flist = []
        for n in names:
            v = vars_[n]
            is_time = " since " in str(getattr(v, "units", ""))
            flist.append(Field(n, "" if is_time else str(getattr(v, "units", "")),
                               str(getattr(v, "long_name", ""))[:300], kind="time" if is_time else "number"))

        def read(sel=None, limit=None, names=names):
            out: Dict[str, Any] = {}
            for n in names:
                if sel is not None and n not in sel:
                    continue
                v = vars_[n]
                t = _nc_times(v)
                if t is not None:
                    out[n] = t[:limit] if limit else t
                else:
                    a = np.ma.filled(np.ma.asarray(v[:limit] if limit else v[:]).astype(np.float64), np.nan)
                    out[n] = a
            return out
        objects.append(DataObject(name=f"{dim} table", kind="table", shape=(len(ds.dimensions[dim]), len(flist)),
                                  fields=flist, _reader=read))
    if not objects:
        raise ProductError(f"{path.name} contains no variable VEDA can plot")
    # the most useful object first: the largest image, else the longest table
    objects.sort(key=lambda o: (o.kind == "table", -int(np.prod(o.shape))))
    return Product(path=str(path), format="NETCDF", metadata=meta, objects=objects)


def _open_text(path: Path) -> Product:
    from .pds3_reader import read_any_table
    tbl = read_any_table(str(path))
    flist = [Field(name=k, unit=tbl.units.get(k, "")) for k in tbl.columns] + \
            [Field(name=k, kind="text") for k in tbl.text_columns]
    data = {**tbl.columns, **tbl.text_columns}

    def read(names=None, limit=None):
        return {k: (v[:limit] if limit is not None else v) for k, v in data.items() if names is None or k in names}
    obj = DataObject("TABLE", "table", (tbl.row_count(), len(flist)), flist, _reader=read)
    _classify_text_fields(obj)
    return Product(path=str(path), format="TEXT", metadata=dict(tbl.metadata), objects=[obj])


# ====================================================================== entry point

_CACHE: Dict[Tuple[str, float], Product] = {}


def open_product(path: str) -> Product:
    """Open a label (PDS3 .lbl, attached-label .dat/.img/.tab, PDS4 .xml), FITS or text table."""
    p = Path(path)
    if not p.exists():
        raise ProductError(f"{p.name} was not found")
    key = (str(p.resolve()), p.stat().st_mtime)
    if key in _CACHE:
        return _CACHE[key]
    suf = p.suffix.lower()
    if suf in (".xml", ".lblx"):
        prod = _open_pds4(p)
    elif suf in (".fit", ".fits", ".fts"):
        prod = _open_fits(p)
    elif suf in (".nc", ".nc4", ".cdf", ".h5", ".hdf5") or p.name.endswith("_nc"):
        prod = _open_netcdf(p)
    elif suf in (".csv", ".txt", ".asc") and not _has_pds3_label(p):
        prod = _open_text(p)
    else:
        lbl = p
        if suf not in (".lbl",) and not _has_pds3_label(p):
            cand = next((c for c in (p.with_suffix(".lbl"), p.with_suffix(".LBL")) if c.exists()), None)
            if cand is None:
                prod = _open_text(p)
                _CACHE[key] = prod
                return prod
            lbl = cand
        prod = _open_pds3(lbl)
    # Images and cubes first: a product holding an image and a small telemetry
    # table (Cassini ISS, Rosetta OSIRIS) should open on the image.
    has_array = any(x.kind in ("image", "cube", "array") for x in prod.objects)   # (computed before sorting: the list is empty during sort)
    prod.objects.sort(key=lambda o: o.kind == "table" and has_array)
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[key] = prod
    return prod


def _has_pds3_label(p: Path) -> bool:
    with p.open("rb") as fh:
        head = fh.read(400).decode("latin-1", errors="replace").upper()
    return "PDS_VERSION_ID" in head or "ODL_VERSION_ID" in head
