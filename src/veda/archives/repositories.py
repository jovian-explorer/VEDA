"""Profiles published in research data repositories (Zenodo, institutional archives).

Not every mission's derived profiles are in PDS or PSA: Venus Express radio
occultation temperature profiles, for example, are published by the teams on
Zenodo, and SPICAV-SOIR profiles in the BIRA-IASB data repository.  These files
carry no PDS labels, so each data set describes its layout (``Dataset.repository``)
and VEDA rewrites every profile as a small normalised CSV:

    # KEY=value                 metadata lines (START_TIME, LATITUDE, ...)
    name [unit],name [unit],...  one header line
    values...

which both the product viewer and the profile loader read like any other table.

``repository`` kinds:

* ``zenodo_files``: one file per profile in a Zenodo record (``record``,
  ``files`` regex, ``columns``: [(name, unit), ...] for whitespace-separated text,
  optional ``meta_xlsx``: a spreadsheet listing per-file date, latitude, local time);
* ``zenodo_zip``: profiles are the members of a zip file in a Zenodo record
  (``record``, ``zip``, ``members`` regex, ``columns``, ``delimiter``);
* ``votable_split``: one VOTable (inside a zip at ``url``, member ``member``) holding
  every profile, split into products by ``split`` columns;
* ``csv_split``: one delimited text table at ``url`` holding every profile (``columns``:
  [(name, unit), ...] in file order, ``header``: whether the first line names them),
  split into products by ``split`` columns.  ``mars_year``/``ls`` name the columns
  that date a profile when the table has no time, ``west_longitude`` a longitude
  given positive west, ``fill`` the value meaning missing.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from . import net as http
from .datasets import Dataset

ZENODO_API = "https://zenodo.org/api/records/"


# ------------------------------------------------------------------ helpers

def _cache_dir(ds: Dataset) -> Path:
    from ..config import CACHE_DIR
    d = CACHE_DIR / "archive" / ds.id / "repository"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _zenodo_files(record: str) -> List[Dict[str, Any]]:
    data = json.loads(http.get_text(ZENODO_API + record))
    return [{"key": f["key"], "size": f.get("size", 0), "url": f["links"]["self"]} for f in data.get("files", [])]


def _download(url: str, dest: Path, progress=None) -> Path:
    if not dest.is_file():
        http.download(url, dest, progress=progress)
    return dest


def write_normalised(path: Path, meta: Dict[str, Any], names: List[Tuple[str, str]], rows: Iterable[Iterable[Any]]) -> Path:
    """The normalised CSV (see module docstring)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    for k, v in meta.items():
        if v is not None and v != "":
            buf.write(f"# {k}={v}\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([f"{n} [{u}]" if u else n for n, u in names])
    for r in rows:
        w.writerow(["" if v is None or (isinstance(v, float) and not np.isfinite(v)) else
                    (f"{v:.8g}" if isinstance(v, float) else v) for v in r])
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def read_normalised(path: Path):
    """A Pds3Table from a normalised CSV: numeric columns, units from the header,
    metadata from the # lines (numbers converted)."""
    from ..readers.pds3_reader import Pds3Table
    meta: Dict[str, Any] = {}
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        k, _, v = lines[i][1:].strip().partition("=")
        try:
            meta[k.strip()] = float(v) if re.fullmatch(r"[-+0-9.eE]+", v.strip()) else v.strip()
        except ValueError:
            meta[k.strip()] = v.strip()
        i += 1
    reader = csv.reader(lines[i:])
    header = next(reader)
    names, units = [], {}
    for h in header:
        m = re.fullmatch(r"(.*?) \[(.*)\]", h)
        n, u = (m.group(1), m.group(2)) if m else (h, "")
        names.append(n)
        units[n] = u
    rows = list(reader)
    cols: Dict[str, np.ndarray] = {}
    text: Dict[str, List[str]] = {}
    for j, n in enumerate(names):
        vals = [r[j] if j < len(r) else "" for r in rows]
        try:
            cols[n] = np.array([float(v) if v != "" else np.nan for v in vals])
        except ValueError:
            text[n] = vals
    t = Pds3Table(label_path=str(path), table_path=str(path), metadata=meta, columns=cols, units=units)
    t.text_columns = text
    return t


def _mask_constant_runs(cols: Dict[str, np.ndarray], key: str, also: List[str], min_run: int = 5) -> None:
    """Rows at either end where ``key`` repeats one value are padding, not data
    (FSI profiles hold the number density constant below the lowest valid level,
    which turns their temperature there into nonsense): set them to NaN."""
    a = cols.get(key)
    if a is None or a.size < min_run:
        return
    for ends in (range(a.size), range(a.size - 1, -1, -1)):
        idx = list(ends)
        first = a[idx[0]]
        run = 0
        for k in idx:
            if a[k] == first:
                run += 1
            else:
                break
        if run >= min_run:
            sel = idx[:run]
            for c in [key, *also]:
                if c in cols:
                    cols[c][sel] = np.nan


def _xlsx_rows(path: Path) -> List[List[Any]]:
    """Cell values of the first sheet of an .xlsx file (numbers as floats, text as str);
    enough for the small file lists some data sets ship (no openpyxl needed)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    out = []
    for row in sheet.iter("{%s}row" % ns["m"]):
        vals: Dict[int, Any] = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r", "")
            col = 0
            for ch in re.match(r"[A-Z]+", ref).group(0):
                col = col * 26 + ord(ch) - 64
            v = c.find("m:v", ns)
            if v is None:
                continue
            if c.get("t") == "s":
                vals[col - 1] = shared[int(v.text)]
            else:
                try:
                    vals[col - 1] = float(v.text)
                except (TypeError, ValueError):
                    vals[col - 1] = v.text
        if vals:
            out.append([vals.get(k) for k in range(max(vals) + 1)])
    return out


def _hours(v: Any) -> Optional[float]:
    """Local time from a spreadsheet cell (fraction of a day, hours, or 'hh:mm[:ss]')."""
    if v is None or v == "":
        return None
    if isinstance(v, float):
        return v * 24.0 if v < 1.0 else v
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d*)?))?\s*", str(v))
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3) or 0) / 3600
    try:
        return float(v)
    except ValueError:
        return None


_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"], 1)}


def _row(ds: Dataset, pid: str, path: str, t0: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
    ptype, kind = ds.classify(pid)
    return {"dataset_id": ds.id, "product_id": pid, "volume": "repository", "path": path,
            "start_time": t0, "stop_time": "", "target": ds.body_ids[0].upper(),
            "product_type": ptype, "kind": kind, "extra": json.dumps(extra or {})}


# ------------------------------------------------------------------ indexing and fetching

def index_repository(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    kind = ds.repository["kind"]
    return {"zenodo_files": _index_zenodo_files, "zenodo_zip": _index_zenodo_zip,
            "votable_split": _index_votable_split, "csv_split": _index_csv_split}[kind](ds, progress)


def fetch_repository_product(ds: Dataset, prod: Dict[str, Any]) -> Path:
    """The product's normalised CSV, made from the repository file when needed."""
    out = _cache_dir(ds) / f"{prod['product_id']}.csv"
    if out.is_file():
        return out
    kind = ds.repository["kind"]
    if kind == "zenodo_files":
        return _fetch_zenodo_file(ds, prod, out)
    if kind == "zenodo_zip":
        return _fetch_zip_member(ds, prod, out)
    if kind == "csv_split":
        _index_csv_split(ds, None)            # writes every product of the table
    else:
        _index_votable_split(ds, None)
    if not out.is_file():
        raise http.ArchiveError(f"{prod['product_id']} is no longer in "
                                f"{ds.repository.get('member') or ds.repository['url'].rsplit('/', 1)[-1]}")
    return out


def _index_zenodo_files(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    r = ds.repository
    files = _zenodo_files(r["record"])
    meta_by_file: Dict[str, Dict[str, Any]] = {}
    if r.get("meta_xlsx"):
        x = next((f for f in files if f["key"] == r["meta_xlsx"]), None)
        if x:
            p = _download(x["url"], _cache_dir(ds) / x["key"])
            for row in _xlsx_rows(p)[1:]:
                if not row or not row[0]:
                    continue
                vals = dict(zip(r["meta_columns"], row))
                meta_by_file[str(row[0])] = vals
    rows = []
    rx = re.compile(r["files"])
    for f in files:
        m = rx.fullmatch(f["key"])
        if not m:
            continue
        pid = Path(f["key"]).stem
        meta = meta_by_file.get(f["key"], {})
        t0 = ""
        if all(k in meta for k in ("year", "month", "day")):
            month = meta["month"] if isinstance(meta["month"], float) else _MONTHS.get(str(meta["month"]).lower(), 0)
            if month:
                t0 = f"{int(meta['year']):04d}-{int(month):02d}-{int(meta['day']):02d}"
        if not t0 and m.groupdict().get("date"):
            d = m.group("date")
            t0 = (f"20{d[:2]}-{d[2:4]}-{d[4:6]}" if len(d) == 6 else f"{d[:4]}-{d[4:6]}-{d[6:8]}")
        extra = {"url": f["url"], "LATITUDE": meta.get("latitude"), "LST": _hours(meta.get("local_time")),
                 "DIRECTION": meta.get("direction")}
        rows.append(_row(ds, pid, f["url"], t0, extra))
    return rows


def _fetch_zenodo_file(ds: Dataset, prod: Dict[str, Any], out: Path) -> Path:
    r = ds.repository
    raw = _download(prod["path"], _cache_dir(ds) / (prod["product_id"] + ".src"))
    data = np.loadtxt(raw, ndmin=2)
    names = r["columns"]
    cols = {n: data[:, i].astype(float) for i, (n, _) in enumerate(names) if i < data.shape[1]}
    if r.get("mask_constant"):
        key, also = r["mask_constant"]
        _mask_constant_runs(cols, key, list(also))
    extra = prod.get("extra") or {}
    extra = json.loads(extra) if isinstance(extra, str) else extra
    meta = {"START_TIME": prod["start_time"], "LATITUDE": extra.get("LATITUDE"), "LST": extra.get("LST"),
            "DIRECTION": extra.get("DIRECTION"), "SOURCE": prod["path"]}
    n = len(next(iter(cols.values())))
    return write_normalised(out, meta, list(names), (tuple(cols[c][i] for c, _ in names) for i in range(n)))


def _index_zenodo_zip(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    r = ds.repository
    zf = _zip_path(ds, progress)
    rx = re.compile(r["members"])
    rows = []
    with zipfile.ZipFile(zf) as z:
        for name in z.namelist():
            base = name.rsplit("/", 1)[-1]
            if not rx.fullmatch(base):
                continue
            pid = base.split(".")[0]
            t0 = ""
            with z.open(name) as fh:
                for _ in range(20):                    # the first line with a readable time
                    line = fh.readline().decode("utf-8", "replace")
                    if not line:
                        break
                    cells = line.rstrip("\r\n").split(r.get("delimiter", "\t"))
                    if len(cells) > r["time_column"]:
                        t0 = _parse_time(cells[r["time_column"]].strip())
                    if t0:
                        break
            rows.append(_row(ds, pid, name, t0))
    return rows


def _zip_path(ds: Dataset, progress=None) -> Path:
    r = ds.repository
    if r.get("url"):
        url, key = r["url"], r["url"].rsplit("/", 1)[-1]
    else:
        f = next((f for f in _zenodo_files(r["record"]) if f["key"] == r["zip"]), None)
        if f is None:
            raise http.ArchiveError(f"{r['zip']} is no longer in Zenodo record {r['record']}")
        url, key = f["url"], f["key"]
    return _download(url, _cache_dir(ds) / key, progress=None)


def _parse_time(s: str) -> str:
    """'17-Feb-2014 03:47:57.625000 (UTC)', ISO strings, or Julian dates -> ISO UTC."""
    s = s.replace("(UTC)", "").strip()
    for fmt in ("%d-%b-%Y %H:%M:%S.%f", "%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
        except ValueError:
            continue
    try:
        jd = float(s)
        if jd > 2_000_000:
            return (datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
    except ValueError:
        pass
    return ""


def _fetch_zip_member(ds: Dataset, prod: Dict[str, Any], out: Path) -> Path:
    r = ds.repository
    zf = _zip_path(ds)
    with zipfile.ZipFile(zf) as z:
        text = z.read(prod["path"]).decode("utf-8", "replace")
    names = r["columns"]
    delim = r.get("delimiter", "\t")
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split(delim)]
        if len(cells) < len(names) or not re.fullmatch(r"[-+0-9.eE]+", cells[0]):
            continue                                   # header line (some files have one)
        row = []
        for (n, u), c in zip(names, cells):
            if u == "UTC":
                row.append(_parse_time(c))
            elif u == "hh:mm:ss":
                row.append(_hours(c))
            else:
                try:
                    row.append(float(c))
                except ValueError:
                    row.append(np.nan)
        rows.append(row)
    out_names = [(n, "h" if u == "hh:mm:ss" else u) for n, u in names]
    return write_normalised(out, {"START_TIME": prod["start_time"], "SOURCE": f"{r.get('record', '')} {prod['path']}"},
                            out_names, rows)


def _index_votable_split(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    """Read the whole VOTable once, write every product's CSV, return the rows."""
    import xml.etree.ElementTree as ET
    r = ds.repository
    zf = _zip_path(ds, progress)
    with zipfile.ZipFile(zf) as z:
        member = next((n for n in z.namelist() if n.rsplit("/", 1)[-1] == r["member"]), None)
        if member is None:
            raise http.ArchiveError(f"{r['member']} is not in {zf.name}")
        fields: List[Tuple[str, str]] = []
        groups: Dict[Tuple, List[List[str]]] = {}
        with z.open(member) as fh:
            for _ev, el in ET.iterparse(fh, events=("end",)):
                tag = el.tag.rsplit("}", 1)[-1]
                if tag == "FIELD":
                    fields.append((el.get("name"), el.get("unit") or ""))
                elif tag == "TR":
                    cells = [(td.text or "").strip() for td in el]
                    key = tuple(cells[fields_index(fields, c)] for c in r["split"])
                    groups.setdefault(key, []).append(cells)
                    el.clear()
    keep = [i for i, (n, _) in enumerate(fields) if n in r["keep"]]
    out_names = [fields[i] for i in keep]
    rows = []
    for key, cells in groups.items():
        pid = r["product_id"].format(*[float(k) for k in key])
        first = cells[0]
        get = lambda n: float(first[fields_index(fields, n)]) if first[fields_index(fields, n)] else np.nan  # noqa: E731
        t0 = _parse_time(first[fields_index(fields, r["time"])])
        meta = {"START_TIME": t0}
        for name, (lo, hi) in r["geometry"].items():
            meta[name] = round((get(lo) + get(hi)) / 2.0, 4)
        write_normalised(_cache_dir(ds) / f"{pid}.csv", meta, out_names,
                         ([float(c[i]) if c[i] else np.nan for i in keep] for c in cells))
        rows.append(_row(ds, pid, f"{r['member']}#{pid}", t0, {k: v for k, v in meta.items() if k != "START_TIME"}))
    return rows


def fields_index(fields: List[Tuple[str, str]], name: str) -> int:
    for i, (n, _) in enumerate(fields):
        if n == name:
            return i
    raise KeyError(name)


def _index_csv_split(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    """Read the whole table once, write every product's CSV, return the rows."""
    from ..analysis.solar_geometry import mars_time_from_ls
    r = ds.repository
    src = _download(r["url"], _cache_dir(ds) / r["url"].rsplit("/", 1)[-1], progress=None)
    names = [n for n, _ in r["columns"]]
    lines = src.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    rows = list(csv.reader(lines[1:] if r.get("header") else lines))
    groups: Dict[Tuple, List[List[str]]] = {}
    for cells in rows:
        cells = [c.strip() for c in cells]
        if len(cells) < len(names):
            continue
        key = tuple(cells[names.index(c)] for c in r["split"])
        groups.setdefault(key, []).append(cells)
    fill = r.get("fill")
    numeric = [i for i, (n, u) in enumerate(r["columns"]) if u != "text"]

    def value(c: str) -> float:
        try:
            v = float(c)
        except ValueError:
            return np.nan
        return np.nan if (fill is not None and v == fill) or not np.isfinite(v) else v

    out_rows = []
    for key, cells in groups.items():
        first = cells[0]
        get = lambda n: first[names.index(n)]  # noqa: E731
        meta: Dict[str, Any] = {}
        t0 = ""
        if r.get("mars_year") and r.get("ls"):
            ls = float(get(r["ls"]))
            t = mars_time_from_ls(int(float(get(r["mars_year"]))), ls)
            # the date only: the table gives the season, not the time of day, and a made-up
            # clock time would give a made-up local time
            t0 = t[:10] if t else ""
            meta.update({"START_TIME": t0, "MARS_YEAR": int(float(get(r["mars_year"]))), "LS": ls})
        for col, name in (("latitude", "LATITUDE"), ("longitude", "LONGITUDE")):
            if r.get(col):
                v = value(get(r[col]))
                if col == "longitude" and r.get("west_longitude"):
                    v = (360.0 - v) % 360.0           # positive west -> positive east
                meta[name] = round(v, 4)
        for n in r.get("text_meta", ()):
            meta[n] = get(n)
        pid = r["product_id"].format(**{k: v for k, v in meta.items()},
                                     key="_".join(k.replace(".", "p").replace("-", "m") for k in key))
        keep = [i for i in numeric if names[i] in r["keep"]]
        write_normalised(_cache_dir(ds) / f"{pid}.csv", meta, [r["columns"][i] for i in keep],
                         ([value(c[i]) for i in keep] for c in cells))
        out_rows.append(_row(ds, pid, f"{r['url'].rsplit('/', 1)[-1]}#{pid}", t0,
                             {k: v for k, v in meta.items() if k != "START_TIME"}))
    return out_rows
