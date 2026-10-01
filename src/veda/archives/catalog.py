"""Local catalogue of archive products, built from the volumes' index tables.

Indexing a dataset downloads only the small index files.  Searches run against
the local SQLite catalogue, so filtering by instrument, date range, target or
product type is instant and works offline once a dataset has been indexed.
Products themselves are downloaded on request into ``<cache>/archive/``.
"""
from __future__ import annotations

import json
import re

import numpy as np
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Optional

from ..config import CACHE_DIR
from . import net as http
from .datasets import DATASETS, Dataset, get_dataset
from .pds3_index import parse_index

DB_PATH = CACHE_DIR / "archive_catalog.sqlite"
PRODUCT_ROOT = CACHE_DIR / "archive"
INDEX_MAX_AGE_S = 7 * 24 * 3600

_db_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS volumes (
    dataset_id TEXT NOT NULL, volume TEXT NOT NULL,
    indexed_at REAL NOT NULL, n_products INTEGER NOT NULL,
    PRIMARY KEY (dataset_id, volume));
CREATE TABLE IF NOT EXISTS products (
    dataset_id TEXT NOT NULL, product_id TEXT NOT NULL, volume TEXT NOT NULL,
    path TEXT NOT NULL, start_time TEXT, stop_time TEXT, target TEXT,
    product_type TEXT, kind TEXT, extra TEXT,
    PRIMARY KEY (dataset_id, product_id));
CREATE INDEX IF NOT EXISTS idx_products_time ON products(dataset_id, start_time);
"""


# Real archive products shipped with VEDA (sampledata/), registered under their
# true archive location so they behave exactly like downloaded products.
#   (dataset_id, volume, path in volume, sampledata folder, start_time, product_type, kind)
BUNDLED_SAMPLES = [
    ("vco-v-rs-5-occ-v1.0", "vcors_2001", "data/l4/rs_20160303_223100_udsc64_l4_ae_v10.lbl",
     "venus_akatsuki", "2016-03-03T23:17:09.324", "L4 atmosphere profile, egress", "profile", "VENUS"),
    ("mex-m-mrs-5-occ", "MEX-M-MRS-5-OCC-9101-V1.0", "DATA/2004_093_0017/LEVEL04/M32ICL2L04_AIX_040931105_60.LBL",
     "mars_express", "2004-04-02T11:05:00", "L4 neutral atmosphere profile", "profile", "MARS"),
    ("mex-m-mrs-5-occ", "MEX-M-MRS-5-OCC-9101-V1.0", "DATA/2004_093_0017/LEVEL04/M32ICL2L04_IIX_040931105_60.LBL",
     "mars_express", "2004-04-02T11:05:00", "L4 ionosphere electron density profile", "profile", "MARS"),
    ("corss_occul_el_dens", "corss_occul_el_dens", "data/s19tioc2006078_0107_n_sx_14_titan_edp_v01_r00.xml",
     "titan_cassini_rss", "2006-03-19T00:00:13.587", "Ionosphere electron density profile", "profile", "TITAN"),
]
_seeded = False


def _seed(conn: sqlite3.Connection) -> None:
    """Copy the bundled samples into the archive cache and catalogue (once per process)."""
    global _seeded
    if _seeded:
        return
    _seeded = True
    import shutil
    from ..config import sampledata_dir
    for ds_id, vol, path, folder, t0, ptype, kind, target in BUNDLED_SAMPLES:
        src_dir = sampledata_dir() / folder
        stem = PurePosixPath(path).stem
        dest = PRODUCT_ROOT / ds_id / vol / PurePosixPath(path)
        try:
            for f in src_dir.glob(stem + ".*"):
                out = dest.parent / f.name
                if not out.exists():
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, out)
        except OSError:
            continue
        conn.execute("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (ds_id, stem, vol, path, t0, "", target, ptype, kind, '{"BUNDLED": "yes"}'))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _seed(conn)
    return conn


# ------------------------------------------------------------------ indexing

def _pick(row: Dict[str, str], *candidates: str) -> str:
    for c in candidates:
        for k, v in row.items():
            if k == c or (c.endswith("*") and k.startswith(c[:-1])):
                if v:
                    return v
    return ""


def _normalise_time(t: str) -> str:
    """ISO calendar time; PDS day-of-year times (2014-001T00:00:02) are converted."""
    t = t.strip().rstrip("Z")
    if re.match(r"^\d{4}-\d{2}-\d{2}", t):
        return t
    m = re.match(r"^(\d{4})-(\d{3})(T.*)?$", t)
    if m:
        import datetime as _dt
        d = _dt.date(int(m.group(1)), 1, 1) + _dt.timedelta(days=int(m.group(2)) - 1)
        return d.isoformat() + (m.group(3) or "")
    return ""


def find_index(vol_url: str, login_url: Optional[str] = None) -> str:
    """URL of a volume's product index, whatever its case or name.

    PDS3 volumes keep it in index/ or INDEX/ as index.tab, INDEX.TAB or
    volindex.tab; the cumulative CUMINDEX.TAB is only used if nothing else is
    there.
    """
    entries = http.list_directory(vol_url, login_url=login_url)
    idx_dir = next((e for e in entries if e.lower() == "index"), None)
    if idx_dir is None:
        raise http.ArchiveError(f"{vol_url} has no index directory")
    files = http.list_directory(vol_url + idx_dir + "/", login_url=login_url)
    tabs = [f for f in files if f.lower().endswith(".tab")]
    for want in ("index.tab", "volindex.tab"):
        hit = next((f for f in tabs if f.lower() == want), None)
        if hit:
            return f"{vol_url}{idx_dir}/{hit}"
    others = [f for f in tabs if "index" in f.lower() and not f.lower().startswith("cum")] or              [f for f in tabs if "index" in f.lower()]
    if not others:
        raise http.ArchiveError(f"No index table in {vol_url}{idx_dir}/")
    return f"{vol_url}{idx_dir}/{others[0]}"


def _with_structure(label: str, base: str, login_url: Optional[str]) -> str:
    """Append the column definitions a label pulls in with ^STRUCTURE = "X.FMT"."""
    for name in re.findall(r'\^STRUCTURE\s*=\s*"?([^"\s]+)"?', label, flags=re.I):
        for cand in (name, name.upper(), name.lower()):
            try:
                return label + "\n" + http.get_text(base + cand, login_url=login_url)
            except http.LoginRequired:
                raise
            except http.ArchiveError:
                continue
    return label


def _label_start_time(vol_url: str, path: str, login_url: Optional[str]) -> str:
    """START_TIME from a product label (used when the index has no observation time)."""
    for p in dict.fromkeys([path, path.lower(), path.upper()]):
        try:
            text = http.get_text(vol_url + p, login_url=login_url)
        except http.LoginRequired:
            raise
        except http.ArchiveError:
            continue
        m = re.search(r"^\s*START_TIME\s*=\s*\"?([0-9T:.\-]+)", text, re.M)
        return _normalise_time(m.group(1)) if m else ""
    return ""


def _pds4_times(text: str) -> tuple:
    def tag(t):
        m = re.search(rf"<{t}>\s*([^<]+?)\s*</{t}>", text)
        return _normalise_time(m.group(1)) if m else ""
    return tag("start_date_time"), tag("stop_date_time")


def index_pds4(ds: Dataset, volume: str) -> List[Dict[str, Any]]:
    """Products of a PDS4 bundle folder: every product XML label in it."""
    folder = f"{ds.base_url}{volume}/{ds.pds4_product_dir}"
    names = [n for n in http.list_directory(folder, login_url=ds.login_url)
             if n.lower().endswith(".xml") and not n.lower().startswith("collection")]
    out = []
    for n in names:
        path = ds.pds4_product_dir + n
        ptype, kind = ds.classify(path)
        t0 = t1 = ""
        if ds.times_from_labels:
            try:
                t0, t1 = _pds4_times(http.get_text(folder + n, login_url=ds.login_url))
            except http.LoginRequired:
                raise
            except http.ArchiveError:
                pass
        out.append({"dataset_id": ds.id, "product_id": PurePosixPath(n).stem, "volume": volume, "path": path,
                    "start_time": t0, "stop_time": t1,
                    "target": (ds.body_ids[0] if len(ds.body_ids) == 1 else "").upper(),
                    "product_type": ptype, "kind": kind, "extra": "{}"})
    return out


def index_volume(ds: Dataset, volume: str) -> List[Dict[str, Any]]:
    """Fetch and parse one volume's index into catalogue rows."""
    vol_url = f"{ds.base_url}{volume}/"
    tab_url = vol_url + ds.index_path if ds.index_path else find_index(vol_url, ds.login_url)
    label = ""
    stem = tab_url.rsplit(".", 1)[0]
    for lbl_url in (stem + ".lbl", stem + ".LBL"):
        try:
            label = http.get_text(lbl_url, login_url=ds.login_url)
            break
        except http.LoginRequired:
            raise
        except http.ArchiveError:
            continue
    label = _with_structure(label, tab_url.rsplit("/", 1)[0] + "/", ds.login_url)
    table = http.get_text(tab_url, login_url=ds.login_url)
    out = []
    for row in parse_index(label, table):
        path = _pick(row, "FILE_SPECIFICATION_NAME", "PATH_NAME", "FILE_NAME")
        if row.get("PATH_NAME") and row.get("FILE_NAME"):
            path = row["PATH_NAME"].rstrip("/") + "/" + row["FILE_NAME"]
        if not path:
            continue
        path = path.replace("\\", "/").lstrip("/")
        if ds.label_from_data and not path.lower().endswith(".lbl"):
            stem = path.rsplit(".", 1)[0]
            path = stem + (".LBL" if path[-3:].isupper() else ".lbl")
        if ".." in PurePosixPath(path).parts:
            continue  # never let an index entry point outside the volume
        product_id = PurePosixPath(path).stem
        ptype, kind = ds.classify(path)   # full path: some archives encode the type in the folder
        extra = {k: v for k, v in row.items()
                 if k not in ("FILE_SPECIFICATION_NAME", "PATH_NAME", "FILE_NAME") and v}
        out.append({
            "dataset_id": ds.id, "product_id": product_id, "volume": volume, "path": path,
            # Never fall back to PRODUCT_CREATION_TIME: that is when the archive
            # file was made, not when the observation was taken.
            "start_time": _normalise_time(_pick(row, "START_TIME", "OBSERVATION_TIME"))
                          or ds.time_from_filename(PurePosixPath(path).name)
                          or (_label_start_time(vol_url, path, ds.login_url) if ds.times_from_labels else "")
                          or (ds.fixed_time or ""),
            "stop_time": _normalise_time(_pick(row, "STOP_TIME")),
            # Single-body data sets often omit TARGET_NAME from their index.
            "target": (_pick(row, "TARGET_NAME", "TARGET*") or
                       (ds.body_ids[0] if len(ds.body_ids) == 1 else "")).upper(),
            "product_type": ptype, "kind": kind, "extra": json.dumps(extra),
        })
    return out


def index_static(ds: Dataset, volume: str) -> List[Dict[str, Any]]:
    """Products of a volume without an index: the data set's declared labels,
    split into one product per distinct value of ``ds.split_by``."""
    import datetime as _dt
    from ..readers.pds3_reader import read_pds3_table
    out: List[Dict[str, Any]] = []
    for path in ds.static_labels:
        stem = PurePosixPath(path).stem
        ptype, kind = ds.classify(path)
        target = (ds.body_ids[0] if len(ds.body_ids) == 1 else "").upper()
        if not ds.split_by:
            out.append({"dataset_id": ds.id, "product_id": stem, "volume": volume, "path": path,
                        "start_time": ds.fixed_time or "", "stop_time": "", "target": target,
                        "product_type": ptype, "kind": kind, "extra": "{}"})
            continue
        # The table must be read to know its groups: fetch label and data once.
        tmp = {"dataset_id": ds.id, "product_id": stem, "volume": volume, "path": path,
               "start_time": "", "stop_time": "", "target": target, "product_type": ptype,
               "kind": kind, "extra": '{"STATIC": "yes"}'}
        with _db_lock, _connect() as conn:
            conn.execute("INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                         ":start_time,:stop_time,:target,:product_type,:kind,:extra)", tmp)
        label = fetch_product(ds.id, stem)
        with _db_lock, _connect() as conn:
            conn.execute("DELETE FROM products WHERE dataset_id=? AND product_id=?", (ds.id, stem))
        tbl = read_pds3_table(str(label))
        keys = []
        for col in ds.split_by:
            if col in tbl.text_columns:
                keys.append(tbl.text_columns[col])
            else:
                keys.append([("" if not np.isfinite(v) else str(int(v)) if float(v).is_integer() else str(v))
                             for v in tbl.columns[col]])
        groups: Dict[tuple, List[int]] = {}
        for i, k in enumerate(zip(*keys)):
            groups.setdefault(k, []).append(i)
        # Observation time per group
        times: Dict[tuple, str] = {}
        if ds.split_time == "ert_rollover" and "ERT" in tbl.columns and ds.fixed_time:
            day = _dt.datetime.fromisoformat(ds.fixed_time[:10])
            first_ert = {k: float(np.nanmin(tbl.columns["ERT"][idx])) for k, idx in groups.items()}
            prev, offset = None, 0
            for k in sorted(groups, key=lambda g: g[0]):        # in orbit order
                ert = first_ert[k]
                if prev is not None and k[0] != prev[0] and ert < prev[1]:
                    offset += 1                              # ERT wrapped: next UT day
                prev = (k[0], ert)
                times[k] = (day + _dt.timedelta(days=offset, seconds=ert)).isoformat(timespec="seconds")
        for k, idx in groups.items():
            out.append({
                "dataset_id": ds.id, "product_id": f"{stem}_" + "_".join(k), "volume": volume, "path": path,
                "start_time": times.get(k, ds.fixed_time or ""), "stop_time": "", "target": target,
                "product_type": ptype, "kind": kind,
                "extra": json.dumps({"SPLIT": dict(zip(ds.split_by, k)), "ROWS": len(idx),
                                     "ORBIT_NUMBER": k[0] if "ORBIT_NUMBER" in ds.split_by[:1] else None}),
            })
    return out


def refresh_dataset(ds: Dataset, force: bool = False,
                    progress: Optional[Callable[[int, int, str], None]] = None) -> int:
    """(Re)index every volume of ``ds``; returns the number of products."""
    if ds.portal_only:
        raise http.LoginRequired(ds.archive, ds.login_url or ds.base_url)
    volumes = http.list_directory(ds.base_url, ds.volume_pattern, dirs_only=True, login_url=ds.login_url)
    if not volumes:
        raise http.ArchiveError(f"No volumes found at {ds.base_url}")
    with _db_lock, _connect() as conn:
        known = {r["volume"]: r["indexed_at"] for r in
                 conn.execute("SELECT volume, indexed_at FROM volumes WHERE dataset_id=?", (ds.id,))}
    now = time.time()
    for i, vol in enumerate(volumes):
        if progress:
            progress(i, len(volumes), vol)
        if not force and vol in known and now - known[vol] < INDEX_MAX_AGE_S:
            continue
        rows = (index_pds4(ds, vol) if ds.pds4_product_dir else
                index_static(ds, vol) if ds.static_labels else index_volume(ds, vol))
        with _db_lock, _connect() as conn:
            conn.execute("DELETE FROM products WHERE dataset_id=? AND volume=?", (ds.id, vol))
            conn.executemany(
                "INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                ":start_time,:stop_time,:target,:product_type,:kind,:extra)", rows)
            conn.execute("INSERT OR REPLACE INTO volumes VALUES (?,?,?,?)", (ds.id, vol, now, len(rows)))
    if progress:
        progress(len(volumes), len(volumes), "done")
    with _db_lock, _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM products WHERE dataset_id=?", (ds.id,)).fetchone()[0]


def dataset_status(ds: Dataset) -> Dict[str, Any]:
    with _db_lock, _connect() as conn:
        r = conn.execute("SELECT COUNT(*) n, MIN(start_time) t0, MAX(start_time) t1 FROM products "
                         "WHERE dataset_id=?", (ds.id,)).fetchone()
        v = conn.execute("SELECT COUNT(*) n, MAX(indexed_at) at FROM volumes WHERE dataset_id=?",
                         (ds.id,)).fetchone()
    return {"indexed_products": r["n"], "first_time": r["t0"], "last_time": r["t1"],
            "indexed_volumes": v["n"], "indexed_at": v["at"]}


# ------------------------------------------------------------------ search

@dataclass
class SearchQuery:
    mission_id: Optional[str] = None
    dataset_ids: Optional[List[str]] = None
    target: Optional[str] = None
    start: Optional[str] = None       # ISO date/time, inclusive
    end: Optional[str] = None         # ISO date/time, inclusive (date = whole day)
    kind: Optional[str] = None        # profile | timeseries | other
    product_type: Optional[str] = None
    text: Optional[str] = None
    limit: int = 200
    offset: int = 0
    newest_first: bool = False
    downloaded_only: bool = False


def search(q: SearchQuery) -> Dict[str, Any]:
    ds_ids = [d.lower() for d in q.dataset_ids] if q.dataset_ids else \
        [d.id for d in DATASETS if not q.mission_id or d.mission_id == q.mission_id.lower()]
    if not ds_ids:
        return {"total": 0, "products": []}
    where = [f"dataset_id IN ({','.join('?' * len(ds_ids))})"]
    args: List[Any] = list(ds_ids)
    if q.target:
        where.append("target = ?"); args.append(q.target.upper())
    if q.start:
        where.append("start_time >= ?"); args.append(q.start)
    if q.end:
        end = q.end + ("T23:59:59.999" if len(q.end) == 10 else "")
        where.append("start_time <= ?"); args.append(end)
    if q.kind:
        where.append("kind = ?"); args.append(q.kind)
    if q.product_type:
        where.append("product_type = ?"); args.append(q.product_type)
    if q.text:
        where.append("(product_id LIKE ? OR path LIKE ? OR extra LIKE ?)")
        args += [f"%{q.text}%"] * 3
    sql_where = " AND ".join(where)
    order = "DESC" if q.newest_first else "ASC"
    with _db_lock, _connect() as conn:
        if q.downloaded_only:
            # Download state lives on disk, so filter in Python, then page.
            every = conn.execute(f"SELECT * FROM products WHERE {sql_where} ORDER BY start_time {order}",
                                 args).fetchall()
            local = [r for r in every if local_label_path(r["dataset_id"], r["volume"], r["path"]).is_file()]
            total, rows = len(local), local[q.offset:q.offset + q.limit]
        else:
            total = conn.execute(f"SELECT COUNT(*) FROM products WHERE {sql_where}", args).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM products WHERE {sql_where} ORDER BY start_time {order} "
                                "LIMIT ? OFFSET ?", args + [q.limit, q.offset]).fetchall()
        types = conn.execute(f"SELECT product_type, COUNT(*) n FROM products WHERE "
                             f"dataset_id IN ({','.join('?' * len(ds_ids))}) GROUP BY product_type",
                             ds_ids).fetchall()
    return {"total": total, "products": [product_dict(r) for r in rows],
            "product_types": {t["product_type"]: t["n"] for t in types}}


def product_dict(r: sqlite3.Row) -> Dict[str, Any]:
    ds = get_dataset(r["dataset_id"])
    local = local_label_path(r["dataset_id"], r["volume"], r["path"])
    extra = json.loads(r["extra"] or "{}")
    return {
        "dataset_id": r["dataset_id"], "product_id": r["product_id"], "volume": r["volume"],
        "mission_id": ds.mission_id if ds else None, "instrument": ds.instrument if ds else None,
        "level": ds.level if ds else None,
        "path": r["path"], "start_time": r["start_time"], "stop_time": r["stop_time"],
        "target": r["target"], "product_type": r["product_type"], "kind": r["kind"],
        "url": f"{ds.base_url}{r['volume']}/{r['path']}" if ds else None,
        "downloaded": local.is_file(),
        "orbit": extra.get("ORBIT_NUMBER") or extra.get("REVOLUTION_NUMBER"),
        "split": extra.get("SPLIT"),
    }


def get_product(dataset_id: str, product_id: str) -> Optional[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        r = conn.execute("SELECT * FROM products WHERE dataset_id=? AND product_id=?",
                         (dataset_id.lower(), product_id)).fetchone()
    return product_dict(r) if r else None


# ------------------------------------------------------------------ download

def local_label_path(dataset_id: str, volume: str, path: str) -> Path:
    return PRODUCT_ROOT / dataset_id / volume / PurePosixPath(path)


_POINTER = re.compile(r'^\s*\^(\w+)\s*=\s*\(?\s*"?([^",)\s]+\.\w+)"?', re.M)


def label_pointers(label_text: str) -> List[tuple]:
    """(pointer, file) pairs a label refers to: PDS3 ^TABLE = "x.tab", ^SERIES = ("x.dat", 1)
    ..., or the <file_name> entries of a PDS4 XML label."""
    if label_text.lstrip().startswith("<?xml") or "<Product_" in label_text[:3000]:
        names = re.findall(r"<file_name>\s*([^<\s]+)\s*</file_name>", label_text)
        own = re.search(r"<File_Area_Observational>", label_text)
        return [("FILE", n) for n in dict.fromkeys(names) if own and not n.lower().endswith(".xml")]
    out = []
    for m in _POINTER.finditer(label_text):
        pair = (m.group(1).upper(), m.group(2))
        if pair not in out:
            out.append(pair)
    return out


def _case_variants(name: str) -> List[str]:
    return list(dict.fromkeys([name, name.upper(), name.lower()]))


def _fetch_first(urls: List[str], dest: Path, login_url: Optional[str], progress=None) -> bool:
    for u in urls:
        try:
            http.download(u, dest, login_url=login_url, progress=progress)
            return True
        except http.LoginRequired:
            raise
        except http.ArchiveError:
            continue
    return False


def fetch_product(dataset_id: str, product_id: str,
                  progress: Optional[Callable[[int, int], None]] = None) -> Path:
    """Download a product's label and the files it points to; returns the label path.

    Pointer files are looked up the way PDS3 resolves them: next to the label
    first, then in the volume's LABEL/ (format files) or DOCUMENT/ (descriptions)
    folder.  Data objects (^TABLE, ^SERIES, ...) are required; format files are
    fetched because the table cannot be read without them; description texts
    are optional.
    """
    ds = get_dataset(dataset_id)
    prod = get_product(dataset_id, product_id)
    if not ds or not prod:
        raise http.ArchiveError(f"Unknown product {dataset_id}/{product_id}; refresh the dataset index.")
    label_path = local_label_path(ds.id, prod["volume"], prod["path"])
    volume_url = f"{ds.base_url}{prod['volume']}/"
    # Indexes often list upper-case paths for volumes served in lower case
    # (MGS mors_1xxx) or the reverse, so try the path as listed, then both cases.
    candidates = [volume_url + p for p in dict.fromkeys([prod["path"], prod["path"].lower(), prod["path"].upper()])]
    product_dirs = list(dict.fromkeys(u.rsplit("/", 1)[0] + "/" for u in candidates))
    if not label_path.is_file():
        for url in candidates:
            try:
                http.download(url, label_path, login_url=ds.login_url)
                # the spelling that worked goes first for the pointer files
                product_dirs.insert(0, product_dirs.pop(product_dirs.index(url.rsplit("/", 1)[0] + "/")))
                break
            except http.LoginRequired:
                raise
            except http.ArchiveError:
                continue
        else:
            raise http.ArchiveError(f"{prod['path']} is not on the archive server ({volume_url})")
    if label_path.suffix.lower() not in (".lbl", ".xml"):
        return label_path

    pending = label_pointers(label_path.read_text(encoding="latin-1", errors="replace"))
    seen = set()
    while pending:
        pointer, name = pending.pop(0)
        if PurePosixPath(name.replace("\\", "/")).name != name:
            continue  # pointers name files, not paths; ignore anything else
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        dest = label_path.parent / name
        if dest.is_file():
            continue
        is_format = name.lower().endswith(".fmt") or pointer == "STRUCTURE"
        is_doc = "DESCRIPTION" in pointer or name.lower().endswith((".txt", ".asc", ".cat"))
        folders = list(product_dirs)
        if is_format:
            folders += [volume_url + d for d in ("LABEL/", "label/")]
        if is_doc:
            folders += [volume_url + d for d in ("DOCUMENT/", "document/")]
        folders.append(volume_url)
        urls = [f + n for f in folders for n in _case_variants(name)]
        ok = _fetch_first(urls, dest, ds.login_url, progress=progress if not (is_format or is_doc) else None)
        if not ok and not is_doc:
            raise http.ArchiveError(f"{name} (referenced by {label_path.name}) is missing from the archive.")
        if ok and is_format:
            # Format files can include further format files.
            pending += label_pointers(dest.read_text(encoding="latin-1", errors="replace"))
    return label_path


def downloaded_products(dataset_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    # None means every data set; an empty list (a mission with no data sets yet) means none.
    ids = [d.lower() for d in dataset_ids] if dataset_ids is not None else [d.id for d in DATASETS]
    if not ids:
        return []
    out = []
    with _db_lock, _connect() as conn:
        rows = conn.execute(f"SELECT * FROM products WHERE dataset_id IN ({','.join('?' * len(ids))}) "
                            "ORDER BY start_time", ids).fetchall()
    for r in rows:
        if local_label_path(r["dataset_id"], r["volume"], r["path"]).is_file():
            out.append(product_dict(r))
    return out
