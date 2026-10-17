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
  optional ``meta_xlsx``: a spreadsheet listing per-file date, latitude, local time;
  ``mask_constant`` and ``max_lapse`` mask padding and failed levels at the bottom,
  ``revision`` is raised when that changes so that cached CSVs are rewritten);
* ``zenodo_zip``: profiles are the members of a zip or .tar.xz file in a Zenodo record
  (``record``, ``zip``, ``members`` regex, ``columns``, ``delimiter``, None for any
  whitespace); the time is a column (``time_column``) or the name's ``date`` and
  ``time`` groups; ``header_ranges`` names the header lines whose midpoints place the
  profile (NOMAD), ``header_values`` the "# Label: value" lines that do, ``min_kernel`` (column, threshold) masks levels whose averaging
  kernel is below the threshold; a ``catalog`` table in the archive can place the
  profiles instead (``_catalog``), ``product_id`` is formatted from the name's groups and
  ``columns`` may be given per ``kind`` group; with ``url`` (Mendeley, BIRA-IASB) ``zip``
  names the cached file;
* in both, ``points`` gives each profile's time, latitude and longitude from a table keyed
  by the name's ``pj`` and ``dir`` groups (``directions`` maps the letters), for files
  without them (Juno); ``delimiter`` in ``zenodo_files`` reads delimited text with time
  columns ("UTC") instead of plain numbers;
* ``votable_files``: one VOTable per profile in a zip (``url``, ``members`` regex with
  the groups ``product_id`` is formatted from), time and place from its PARAMs (``time``,
  ``geometry``: key -> PARAM names averaged), columns ``keep``;
* ``csv_split``: one delimited text table at ``url`` holding every profile (``columns``:
  [(name, unit), ...] in file order, ``header``: whether the first line names them),
  split into products by ``split`` columns.  ``mars_year``/``ls`` name the columns
  that date a profile when the table has no time, ``west_longitude`` a longitude
  given positive west, ``fill`` the value meaning missing;
* ``text_blocks``: one text file at ``url`` holding every profile as a block (NOMAD UVIS,
  Flimon et al.): a line starting with ``block``, the line of its values (the product id,
  then the columns ``meta`` names), a line naming the ``columns``, then the levels; the
  time is the product id's ``date`` and ``time`` groups (``members``).
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
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
    """``progress`` is the indexing progress (done, total, what); the download's is (bytes,
    total): passed on as it was, the CRISM tables' indexing stopped with a TypeError."""
    if not dest.is_file():
        http.download(url, dest, progress=(lambda done, total: progress(done, total, f"downloading {dest.name}"))
                      if progress else None)
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
    which turns their temperature there into nonsense; SOIR profiles hold the
    temperature of the retrieval's upper boundary over their top 10 km): set them to NaN."""
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


def _mask_unstable_bottom(cols: Dict[str, np.ndarray], temperature: str, altitude: str, max_lapse: float,
                          also: List[str], window: float = 1.0, ahead: float = 1.0) -> None:
    """Mask the levels at the bottom of a profile where the temperature falls faster
    with height than ``max_lapse`` (K/km, over ``window`` km), up to the first level
    above which it does not for ``ahead`` km.  A lapse rate well beyond the dry
    adiabatic one cannot last in an atmosphere (convection removes it); in FSI
    profiles it marks the levels just above the constant-density padding where the
    retrieved density flattens as the signal fades, so the temperature computed
    from it rises to 400-580 K at 45-55 km (Venus: about 10 K/km adiabatic)."""
    t, z = cols.get(temperature), cols.get(altitude)
    if t is None or z is None:
        return
    ok = np.where(np.isfinite(t) & np.isfinite(z))[0]
    if ok.size < 3:
        return
    ok = ok[np.argsort(z[ok])]
    zi, ti = z[ok], t[ok]
    lapse = (ti - np.interp(zi + window, zi, ti, right=np.nan)) / window
    bad = lapse > max_lapse
    k = 0
    while k < zi.size:
        if not bad[k]:
            later = np.where(bad & (zi >= zi[k]) & (zi <= zi[k] + ahead))[0]
            if later.size == 0:
                break
            k = later[-1]
        k += 1
    if k:
        for c in [temperature, *also]:
            if c in cols:
                cols[c][ok[:k]] = np.nan


def _stale(ds: Dataset, csv_path: Path) -> bool:
    """A cached normalised CSV written before the data set's current ``revision``."""
    rev = ds.repository.get("revision")
    if not rev:
        return False
    with open(csv_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            if line.strip() == f"# REVISION={rev}":
                return False
    return True


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


def _point(r: Dict[str, Any], m: Optional[re.Match]) -> Dict[str, Any]:
    """Time, latitude and longitude from the data set's ``points`` table, keyed by the file
    name's perijove and direction (Juno: no time or place in the files themselves)."""
    if not r.get("points") or not m:
        return {}
    key = f"{int(m.group('pj'))}{r.get('directions', {}).get(m.group('dir'), m.group('dir'))}"
    hit = r["points"].get(key)
    return {"START_TIME": hit[0], "LATITUDE": hit[1], "LONGITUDE": hit[2]} if hit else {}


def _row(ds: Dataset, pid: str, path: str, t0: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
    ptype, kind = ds.classify(pid)
    return {"dataset_id": ds.id, "product_id": pid, "volume": "repository", "path": path,
            "start_time": t0, "stop_time": "", "target": ds.body_ids[0].upper(),
            "product_type": ptype, "kind": kind, "extra": json.dumps(extra or {})}


# ------------------------------------------------------------------ indexing and fetching

def index_repository(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    kind = ds.repository["kind"]
    return {"zenodo_files": _index_zenodo_files, "zenodo_zip": _index_zenodo_zip,
            "votable_files": _index_votable_files,
            "csv_split": _index_csv_split, "text_blocks": _index_text_blocks}[kind](ds, progress)


def fetch_repository_product(ds: Dataset, prod: Dict[str, Any]) -> Path:
    """The product's normalised CSV, made from the repository file when needed."""
    out = _cache_dir(ds) / f"{prod['product_id']}.csv"
    kind = ds.repository["kind"]
    if out.is_file() and not _stale(ds, out):
        return out
    if kind == "zenodo_files":
        return _fetch_zenodo_file(ds, prod, out)
    if kind == "zenodo_zip":
        return _fetch_zip_member(ds, prod, out)
    if kind in ("csv_split", "text_blocks"):
        index_repository(ds, None)            # writes every product of the table
    else:
        _index_votable_files(ds, None)
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
        pt = _point(r, m)
        if pt:
            t0 = pt.pop("START_TIME")
            extra.update(pt)
        rows.append(_row(ds, pid, f["url"], t0, extra))
    return rows


def _fetch_zenodo_file(ds: Dataset, prod: Dict[str, Any], out: Path) -> Path:
    r = ds.repository
    raw = _download(prod["path"], _cache_dir(ds) / (prod["product_id"] + ".src"))
    names = r["columns"]
    if "delimiter" in r:                             # delimited text (Juno, Coffin et al.: CSV with times)
        rows = _parse_rows(raw.read_text(encoding="utf-8", errors="replace"), names, r["delimiter"])
        names = [(n, "h" if u == "hh:mm:ss" else u) for n, u in names]
        cols = {n: np.array([row[i] for row in rows], dtype=object if u == "UTC" else float)
                for i, (n, u) in enumerate(names)}
    else:
        data = np.loadtxt(raw, ndmin=2)
        cols = {n: data[:, i].astype(float) for i, (n, _) in enumerate(names) if i < data.shape[1]}
    if r.get("mask_constant"):
        key, also = r["mask_constant"]
        _mask_constant_runs(cols, key, list(also))
    if r.get("max_lapse"):
        temperature, altitude, lapse, also = r["max_lapse"]
        _mask_unstable_bottom(cols, temperature, altitude, lapse, list(also))
    extra = prod.get("extra") or {}
    extra = json.loads(extra) if isinstance(extra, str) else extra
    meta = {"START_TIME": prod["start_time"], "LATITUDE": extra.get("LATITUDE"), "LONGITUDE": extra.get("LONGITUDE"),
            "LST": extra.get("LST"),
            "DIRECTION": extra.get("DIRECTION"), "SOURCE": prod["path"], "REVISION": r.get("revision")}
    n = len(next(iter(cols.values())))
    return write_normalised(out, meta, list(names), (tuple(cols[c][i] for c, _ in names) for i in range(n)))


def _members(zf: Path):
    """(name, text) of each file in a zip or tar (.tar, .tar.xz, .tar.gz) archive."""
    if not zipfile.is_zipfile(zf):
        import tarfile
        with tarfile.open(zf) as t:
            for m in t.getmembers():
                if m.isfile():
                    yield m.name, t.extractfile(m).read().decode("utf-8", "replace")
    else:
        with zipfile.ZipFile(zf) as z:
            for name in z.namelist():
                yield name, z.read(name).decode("utf-8", "replace")


def _member_text(ds: Dataset, name: str) -> str:
    """One file of the data set's archive: read from a zip directly; a tar is unpacked into
    the cache the first time (reading one member of a .tar.gz otherwise decompresses the
    archive up to it, and a data set's thousands of profiles took minutes each)."""
    zf = _zip_path(ds)
    if zipfile.is_zipfile(zf):
        with zipfile.ZipFile(zf) as z:
            return z.read(name).decode("utf-8", "replace")
    import tarfile
    root = _cache_dir(ds) / "members"
    done = root / ".unpacked"
    stamp = f"{zf.name} {zf.stat().st_size}"           # (a new version of the archive is unpacked again)
    if not done.is_file() or done.read_text() != stamp:
        # member by member: extractall(filter="data") fails on Windows paths (WinError 4390)
        with tarfile.open(zf) as t:
            for m in t:
                parts = PurePosixPath(m.name).parts
                if not m.isfile() or m.name.startswith("/") or ".." in parts:
                    continue
                dest = root.joinpath(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(t.extractfile(m).read())
        done.write_text(stamp)
    return (root / name).read_text(encoding="utf-8", errors="replace")


def _header_ranges(text: str, keys: Dict[str, str]) -> Dict[str, float]:
    """Midpoints of header lines "<min> <max> <name> (...)" (NOMAD: lats, longit, lct, L_s)."""
    out = {}
    for line in text.splitlines()[:30]:
        p = line.split()
        for key, name in keys.items():
            if len(p) >= 3 and p[2] == name:
                try:
                    a, b = float(p[0]), float(p[1])
                except ValueError:
                    continue
                period = {"LONGITUDE": 360.0, "LST": 24.0}.get(key)
                if period and abs(a - b) > period / 2:       # across 180 E / midnight
                    b += period if b < a else -period
                out[key] = 0.5 * (a + b) % period if period else 0.5 * (a + b)
    return out


def _group_key(v: str):
    """A catalogue key from a file name's group or a table cell: numbers as integers,
    words by their first letter (NORTHERN -> N)."""
    try:
        return int(float(v))
    except ValueError:
        return v[:1].upper()


def _catalog(text: str, spec: Dict[str, Any]) -> Dict[tuple, Dict[str, Any]]:
    """Time and place of each profile from a table in the archive (TGO ACS): ``key`` the
    (column, how) pairs a row is found by ("sign": N or S from a latitude), ``meta`` the
    columns of the values, the date from ``date`` (year, month name, day columns) or from
    ``ls`` with the Mars year counted from ``first_mars_year`` (rows in time order)."""
    from ..analysis.solar_geometry import mars_time_from_ls
    out: Dict[tuple, Dict[str, Any]] = {}
    my, prev = spec.get("first_mars_year"), None
    for line in text.splitlines():
        p = line.split()
        try:
            meta = {k: float(p[i]) for k, i in spec["meta"].items()}
            key = tuple(("N" if float(p[i]) >= 0 else "S") if how == "sign" else _group_key(p[i])
                        for i, how in spec["key"])
        except (ValueError, IndexError):
            continue                                   # header lines
        if "LONGITUDE" in meta:
            meta["LONGITUDE"] %= 360.0
        if spec.get("date"):
            y, mon, d = (p[i] for i in spec["date"])
            meta["START_TIME"] = datetime.strptime(f"{y} {mon} {d}", "%Y %b %d").date().isoformat()
        elif my:
            if prev is not None and meta["LS"] < prev - 180:
                my += 1                                # a new Mars year
            prev = meta["LS"]
            # the date only: the table gives the season, not the time of day
            meta["START_TIME"], meta["MARS_YEAR"] = (mars_time_from_ls(my, meta["LS"]) or "")[:10], my
        # a key found twice (two Belyaev et al. occultations of one orbit in one hemisphere)
        # cannot be told apart: neither is placed
        out[key] = None if key in out else meta
    return out


def _index_zenodo_zip(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    r = ds.repository
    zf = _zip_path(ds, progress)
    rx = re.compile(r["members"])
    cat = None
    if r.get("catalog"):
        spec = r["catalog"]
        text = next((t for n, t in _members(zf) if n.rsplit("/", 1)[-1] == spec["member"]), None)
        if text is None:
            raise http.ArchiveError(f"{spec['member']} is not in {zf.name}")
        cat = _catalog(text, spec)
    rows = []
    for name, text in _members(zf):
        base = name.rsplit("/", 1)[-1]
        m = rx.fullmatch(base) or rx.fullmatch(name)
        if not m:
            continue
        pid = r["product_id"].format(**m.groupdict()) if r.get("product_id") else base.split(".")[0]
        if not any(ln.strip() and not ln.lstrip().startswith("#") for ln in text.splitlines()):
            continue                                   # a header without data (one Brines et al. scan)
        if cat is not None:
            meta = cat.get(tuple(_group_key(m.group(g)) for g in r["catalog"]["groups"]))
            if meta is None:
                continue                               # not in the team's list
            meta = dict(meta, KIND=m.groupdict().get("kind"))
            rows.append(_row(ds, pid, name, meta.pop("START_TIME"), meta))
            continue
        pt = _point(r, m)
        if pt:
            rows.append(_row(ds, pid, name, pt.pop("START_TIME"), pt))
            continue
        extra = _header_ranges(text, r["header_ranges"]) if r.get("header_ranges") else {}
        if r.get("header_values"):                     # "# Latitude: 78.94" lines (NOMAD, Brines et al.)
            for key, label in r["header_values"].items():
                hit = re.search(rf"^#\s*{re.escape(label)}\s*:\s*([-+0-9.eE]+)", text, re.M)
                if hit:
                    extra[key] = float(hit.group(1)) % 360.0 if key == "LONGITUDE" else float(hit.group(1))
        if "date" in m.groupdict():                    # the time in the file name
            d, t = m.group("date"), m.group("time")
            rows.append(_row(ds, pid, name, f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}", extra))
            continue
        t0 = ""
        for line in text.splitlines()[:20]:            # the first line with a readable time
            cells = line.split(r.get("delimiter", "\t"))
            if len(cells) > r["time_column"]:
                t0 = _parse_time(cells[r["time_column"]].strip())
            if t0:
                break
        rows.append(_row(ds, pid, name, t0, extra))
    return rows


def _zip_path(ds: Dataset, progress=None) -> Path:
    r = ds.repository
    if r.get("url"):
        url, key = r["url"], r.get("zip") or r["url"].rsplit("/", 1)[-1]
        if (_cache_dir(ds) / key).is_file():
            return _cache_dir(ds) / key
    elif (_cache_dir(ds) / r["zip"]).is_file():
        # downloaded already: without this every profile read asked Zenodo for the file list,
        # and reading a few hundred (NOMAD: 324) ran into its rate limit (HTTP 429)
        return _cache_dir(ds) / r["zip"]
    else:
        f = next((f for f in _zenodo_files(r["record"]) if f["key"] == r["zip"]), None)
        if f is None:
            raise http.ArchiveError(f"{r['zip']} is no longer in Zenodo record {r['record']}")
        url, key = f["url"], f["key"]
    return _download(url, _cache_dir(ds) / key, progress=progress)


def _parse_time(s: str) -> str:
    """'17-Feb-2014 03:47:57.625000 (UTC)', ISO strings, or Julian dates -> ISO UTC."""
    s = s.replace("(UTC)", "").strip()
    if s[:2] in ("b'", 'b"'):
        s = s[2:-1].strip()                          # a Python bytes repr (Juno, Coffin et al.)
    for fmt in ("%d-%b-%Y %H:%M:%S.%f", "%d-%b-%Y %H:%M:%S", "%Y %b %d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
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
    text = _member_text(ds, prod["path"])
    extra = prod.get("extra") or {}
    extra = json.loads(extra) if isinstance(extra, str) else extra
    # one column layout, or one per kind of file (TGO ACS NIR: water, temperature, aerosol)
    names = r["columns"] if isinstance(r["columns"], list) else r["columns"][extra["KIND"]]
    rows = _parse_rows(text, names, r.get("delimiter", "\t"))
    if r.get("min_kernel"):
        # levels where the averaging kernel's diagonal is below the threshold hold the first
        # guess (the measurement contributes under that fraction): masked, kernel kept
        col, threshold = r["min_kernel"]
        k = [n for n, _ in names].index(col)
        keep = {i for i, (n, _) in enumerate(names) if i == 0 or n == col}
        for row in rows:
            if not row[k] >= threshold:
                for i in range(len(row)):
                    if i not in keep:
                        row[i] = np.nan
    out_names = [(n, "h" if u == "hh:mm:ss" else u) for n, u in names]
    meta = {"START_TIME": prod["start_time"], "SOURCE": f"{r.get('record', '')} {prod['path']}",
            **{k: v for k, v in extra.items() if k.isupper()}}
    return write_normalised(out, meta, out_names, rows)


def _parse_rows(text: str, names: List[Tuple[str, str]], delim: Optional[str]) -> List[List[Any]]:
    """Rows of a delimited text (None: any whitespace); "UTC" columns as ISO times and
    "hh:mm:ss" ones as hours; header lines are skipped."""
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
                    break
        else:
            rows.append(row)
    return rows


def _cell(c: str) -> float:
    """A VOTable cell; "(76+0j)" (a complex number written by the SOIR w24 software, in
    one file) is its real part."""
    if not c:
        return np.nan
    try:
        return float(c)
    except ValueError:
        try:
            v = complex(c.strip("()").replace(" ", ""))
        except ValueError:
            return np.nan
        return v.real if v.imag == 0 else np.nan


def _write_votable_profile(ds: Dataset, pid: str, meta: Dict[str, Any], fields: List[Tuple[str, str]],
                           cells: List[List[str]], keep: List[int]) -> None:
    r = ds.repository
    out_names = [fields[i] for i in keep]
    cols = {fields[i][0]: np.array([_cell(c[i]) for c in cells]) for i in keep}
    if r.get("mask_constant"):
        mkey, also = r["mask_constant"]
        _mask_constant_runs(cols, mkey, list(also))
    if r.get("mask_zero_sigma"):
        skey, masked = r["mask_zero_sigma"]
        with np.errstate(invalid="ignore"):
            zero = cols[skey] < 1e-6
        for c in masked:
            cols[c][zero] = np.nan
    write_normalised(_cache_dir(ds) / f"{pid}.csv", meta, out_names,
                     ([cols[n][j] for n, _ in out_names] for j in range(len(cells))))


def _index_votable_files(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    """One VOTable per profile in a zip (SOIR w24: CO2_0/Orbit0021.1_CO2_0_w24.01.xml), its
    time and place in PARAMs; every product's CSV is written, the rows returned."""
    import xml.etree.ElementTree as ET
    r = ds.repository
    rx = re.compile(r["members"])
    rows = []
    for name, text in _members(_zip_path(ds, progress)):
        m = rx.fullmatch(name)
        if not m:
            continue
        pid = r["product_id"].format(**{k: int(v) for k, v in m.groupdict().items()})
        root = ET.fromstring(text)
        params, fields, cells = {}, [], []
        for el in root.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "PARAM":
                params[el.get("name")] = el.get("value")
            elif tag == "FIELD":
                fields.append((el.get("name"), el.get("unit") or ""))
            elif tag == "TR":
                cells.append([(td.text or "").strip() for td in el])
        t0 = _parse_time(params.get(r["time"], ""))
        meta = {"START_TIME": t0}
        for key, names in r["geometry"].items():
            vals = [_cell(params.get(n, "")) for n in names]
            meta[key] = round(float(np.mean(vals)), 4)
        if r.get("revision"):
            meta["REVISION"] = r["revision"]
        keep = [i for i, (n, _) in enumerate(fields) if n in r["keep"]]
        _write_votable_profile(ds, pid, meta, fields, cells, keep)
        rows.append(_row(ds, pid, name, t0, {k: v for k, v in meta.items() if k not in ("START_TIME", "REVISION")}))
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
    src = _download(r["url"], _cache_dir(ds) / r["url"].rsplit("/", 1)[-1], progress=progress)
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
                             {k: v for k, v in meta.items() if k not in ("START_TIME", "REVISION")}))
    return out_rows


def _index_text_blocks(ds: Dataset, progress=None) -> List[Dict[str, Any]]:
    """Read the whole file once, write every block's CSV, return the rows."""
    r = ds.repository
    name = r["url"].rsplit("/", 1)[-1]
    lines = _download(r["url"], _cache_dir(ds) / name, progress=progress).read_text(
        encoding="utf-8-sig", errors="replace").splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(r["block"])] + [len(lines)]
    rx = re.compile(r["members"])
    keys = [k.strip() for k in lines[starts[0]].split(",")] if starts[:-1] else []
    out_rows = []
    for a, b in zip(starts, starts[1:]):
        vals = [v.strip() for v in lines[a + 1].split(",")]
        m = rx.fullmatch(vals[0])
        if not m:
            continue
        d, t = m.group("date"), m.group("time")
        t0 = f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}"
        meta = {key: float(vals[keys.index(col)]) for key, col in r["meta"].items()}
        if "LONGITUDE" in meta:
            meta["LONGITUDE"] %= 360.0
        rows = _parse_rows("\n".join(lines[a + 3:b]), r["columns"], ",")
        write_normalised(_cache_dir(ds) / f"{vals[0]}.csv", {"START_TIME": t0, **meta}, r["columns"], rows)
        out_rows.append(_row(ds, vals[0], f"{name}#{vals[0]}", t0, meta))
    return out_rows
