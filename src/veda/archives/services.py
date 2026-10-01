"""Live archive search services: every payload, queried by date.

Some archives are too large to copy as index tables but can be searched by
instrument and time on the server:

* ESA PSA EPN-TAP      (Mars Express, Venus Express, Rosetta, BepiColombo, Huygens, ...)
* NASA PDS Registry     (PDS4 products at every NASA node: MAVEN, Juno, New Horizons,
                         MESSENGER, LRO, Galileo, Magellan, MGS, MRO, PVO, Dawn, ...)
* PDS Rings node OPUS   (Cassini ISS/VIMS/UVIS/CIRS, Galileo SSI, New Horizons LORRI/MVIC)

A query for a date window is sent once; the products found go into the local
catalogue together with the window, so the same search later is instant and
works offline.  Each product is stored with the full URL of its label, and is
downloaded and read like any indexed product.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import net

PSA_TAP = "https://psa.esa.int/psa-tap/tap/sync"
PDS_API = "https://pds.nasa.gov/api/search/1/products"
OPUS_API = "https://opus.pds-rings.seti.org/api/"
WINDOW_MAX_AGE_S = 7 * 24 * 3600
MAX_PER_QUERY = 5000           # products listed per data set and window
MAX_WINDOW_DAYS = 3660         # a single query never spans more than ~10 years

_lock = threading.Lock()


class ServiceError(net.ArchiveError):
    pass


# ------------------------------------------------------------------ time helpers

def _parse(t: str, end: bool = False) -> dt.datetime:
    t = t.strip().rstrip("Z")
    if len(t) == 10:
        d = dt.datetime.fromisoformat(t)
        return d + dt.timedelta(days=1) if end else d
    return dt.datetime.fromisoformat(t[:26])


def _jd(d: dt.datetime) -> float:
    return (d - dt.datetime(1970, 1, 1)).total_seconds() / 86400.0 + 2440587.5


def _from_jd(jd: float) -> str:
    try:
        d = dt.datetime(1970, 1, 1) + dt.timedelta(days=float(jd) - 2440587.5)
        return d.isoformat(timespec="milliseconds")
    except (ValueError, OverflowError):
        return ""


def _iso(v: Any) -> str:
    s = (v[0] if isinstance(v, list) and v else v) or ""
    s = str(s).strip().rstrip("Z")
    if not s or s.startswith(("1965-01-01", "0001")):   # registry placeholders, not real times
        return ""
    return s


# ------------------------------------------------------------------ queries

def _get_json(url: str, params: Dict[str, Any], tries: int = 3) -> Any:
    last: Optional[Exception] = None
    for i in range(tries):
        try:
            r = net.get(url, params=params, timeout=max(60, net.SETTINGS.network_timeout_s))
            return r.json()
        except (ValueError, net.ArchiveError) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise ServiceError(f"The archive search service did not answer ({last})")


def _tap(query: str) -> List[Dict[str, str]]:
    """Rows of an ADQL query against the PSA (CSV output, retried: the service drops connections)."""
    import csv
    import io
    last: Optional[Exception] = None
    for i in range(4):
        try:
            r = net.get(PSA_TAP, params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query},
                        timeout=max(90, net.SETTINGS.network_timeout_s))
            text = r.text
            if text.lstrip().startswith("<"):
                m = re.search(r'QUERY_STATUS" value="ERROR">\s*(.*?)\s*</INFO>', text, re.S)
                raise ServiceError(f"PSA search failed: {m.group(1)[:200] if m else 'unexpected answer'}")
            return list(csv.DictReader(io.StringIO(text)))
        except net.ArchiveError as exc:
            last = exc
            time.sleep(2.0 * (i + 1))
    raise ServiceError(f"The ESA PSA search service did not answer ({last})")


def _quote(s: str) -> str:
    return s.replace("'", "''")


def query_psa(q: Dict[str, Any], t0: dt.datetime, t1: dt.datetime, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    where = (f"instrument_host_name='{_quote(q['host'])}' AND instrument_name='{_quote(q['instrument'])}' "
             f"AND label_url IS NOT NULL AND time_min >= {_jd(t0):.6f} AND time_min < {_jd(t1):.6f}")
    if q.get("gid_like"):
        where += f" AND granule_gid LIKE '{_quote(q['gid_like'])}'"
    if q.get("gid_not_like"):
        where += f" AND granule_gid NOT LIKE '{_quote(q['gid_not_like'])}'"
    total = int((_tap(f"SELECT COUNT(*) AS n FROM epn_core WHERE {where}") or [{"n": 0}])[0].get("n") or 0)
    rows = _tap(f"SELECT TOP {limit} granule_uid, granule_gid, label_url, time_min, time_max, processing_level, "
                f"target_name FROM epn_core WHERE {where} ORDER BY time_min") if total else []
    out = []
    for r in rows:
        gid = (r.get("granule_gid") or "").split(":")[0]
        uid = r.get("granule_uid") or ""
        pid = uid.split("::")[0].rsplit(":", 1)[-1] or uid
        lvl = r.get("processing_level") or ""
        out.append({
            "product_id": pid, "volume": gid, "path": r["label_url"],
            "start_time": _from_jd(r["time_min"]) if r.get("time_min") else "",
            "stop_time": _from_jd(r["time_max"]) if r.get("time_max") else "",
            "target": (r.get("target_name") or "").upper(),
            "product_type": _psa_type(gid, lvl),
            "extra": {"DATA_SET_ID": gid, "PROCESSING_LEVEL": lvl},
        })
    return out, total


def _psa_type(gid: str, level: str) -> str:
    """'MEX-M-ASPERA3-2-EDR-ELS-EXT1-V1.0' -> 'ASPERA3 EDR ELS (level 2)'."""
    parts = re.sub(r"-V\d+\.\d+$", "", gid).split("-")
    parts = [p for p in parts[2:] if not re.fullmatch(r"EXT\d*|\d{4}|PRL|MTP\d+", p)] or parts
    lvl = next((p for p in parts if re.fullmatch(r"\d(/\d)*", p)), level)
    words = [p for p in parts if not re.fullmatch(r"\d(/\d)*", p)]
    return f"{' '.join(words)}" + (f" (level {lvl})" if lvl else "")


def query_pds(q: Dict[str, Any], t0: dt.datetime, t1: dt.datetime, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    insts = q["instruments"]
    inst = " or ".join(f'ref_lid_instrument eq "{i}"' for i in insts)
    query = (f"(({inst}) and product_class eq \"Product_Observational\" and "
             f"pds:Time_Coordinates.pds:start_date_time ge \"{t0.isoformat()}Z\" and "
             f"pds:Time_Coordinates.pds:start_date_time lt \"{t1.isoformat()}Z\")")
    fields = ("lid,title,pds:Time_Coordinates.pds:start_date_time,pds:Time_Coordinates.pds:stop_date_time,"
              "ops:Label_File_Info.ops:file_ref,pds:Primary_Result_Summary.pds:processing_level,ref_lid_target")
    out: List[Dict[str, Any]] = []
    total = 0
    after: Optional[str] = None
    while len(out) < limit:
        params = {"q": query, "limit": min(500, limit - len(out)), "fields": fields,
                  "sort": "pds:Time_Coordinates.pds:start_date_time"}
        if after:
            params["search-after"] = after
        d = _get_json(PDS_API, params)
        total = int(d.get("summary", {}).get("hits") or 0)
        page = d.get("data") or []
        for p in page:
            pr = p.get("properties") or {}
            label = _iso(pr.get("ops:Label_File_Info.ops:file_ref"))
            if not label.startswith("http"):
                continue
            lid = (pr.get("lid") or [p.get("id", "")])[0]
            bits = lid.split(":")
            bundle, coll = (bits[3] if len(bits) > 3 else ""), (bits[4] if len(bits) > 4 else "")
            tgt = _iso(pr.get("ref_lid_target")).rsplit(".", 1)[-1].replace("_", " ").upper()
            out.append({
                "product_id": bits[-1] if bits else lid, "volume": f"{bundle}:{coll}", "path": label,
                "start_time": _iso(pr.get("pds:Time_Coordinates.pds:start_date_time")),
                "stop_time": _iso(pr.get("pds:Time_Coordinates.pds:stop_date_time")),
                "target": tgt,
                "product_type": f"{coll.replace('_', ' ').replace('-', ' ')} ({_iso(pr.get('pds:Primary_Result_Summary.pds:processing_level')) or 'level n/a'})".strip(),
                "extra": {"LID": lid, "TITLE": _iso(pr.get("title"))[:200]},
            })
        if len(page) < params["limit"] or not page:
            break
        last = (page[-1].get("properties") or {}).get("pds:Time_Coordinates.pds:start_date_time")
        nxt = _iso(last)
        if not nxt or nxt == after:
            break
        after = nxt + "Z"
    return out, total


def query_opus(q: Dict[str, Any], t0: dt.datetime, t1: dt.datetime, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    # OPUS accepts dates without hours most reliably; extend to whole days.
    # time2 is exclusive and dates without hours work most reliably: whole days.
    d0 = t0.date().isoformat()
    d1 = (t1.date() + dt.timedelta(days=1 if t1.time() != dt.time(0) else 0)).isoformat()
    params = {"instrument": q["instrument"], "time1": d0, "time2": d1, "limit": min(limit, MAX_PER_QUERY),
              "cols": "opusid,time1,time2,target,primaryfilespec,volumeid"}
    d = _get_json(OPUS_API + "data.json", params)
    total = int(d.get("available") or 0)
    out = []
    for opusid, t_a, t_b, target, spec, vol in d.get("page") or []:
        if not spec or not vol:
            continue
        group = re.sub(r"\d{3}$", "xxx", vol)
        label = spec if spec.upper().endswith(".LBL") else re.sub(r"\.[^./]+$", ".LBL", spec)
        out.append({
            "product_id": opusid, "volume": vol,
            "path": f"https://opus.pds-rings.seti.org/holdings/volumes/{group}/{label}",
            "start_time": (t_a or "").rstrip("Z"), "stop_time": (t_b or "").rstrip("Z"),
            "target": (target or "").upper(), "product_type": f"{q['instrument']} raw ({vol})",
            "extra": {"OPUS_ID": opusid, "PRIMARY_FILE": spec},
        })
    return out, total


QUERIES = {"psa_tap": query_psa, "pds_api": query_pds, "opus": query_opus}


# ------------------------------------------------------------------ windows in the catalogue

def _windows_schema(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS service_windows (dataset_id TEXT NOT NULL, start TEXT NOT NULL, "
                 "end TEXT NOT NULL, queried_at REAL NOT NULL, listed INTEGER, available INTEGER)")


def covered(conn, ds_id: str, start: str, end: str) -> Optional[Tuple[int, int]]:
    """(listed, available) of a fresh earlier query covering [start, end), else None."""
    _windows_schema(conn)
    r = conn.execute("SELECT listed, available FROM service_windows WHERE dataset_id=? AND start<=? AND end>=? "
                     "AND queried_at>? ORDER BY queried_at DESC LIMIT 1",
                     (ds_id, start, end, time.time() - WINDOW_MAX_AGE_S)).fetchone()
    return (r[0], r[1]) if r else None


def search_window(ds, start: str, end: str, connect: Callable, lock, force: bool = False) -> Dict[str, Any]:
    """Make sure the catalogue holds ``ds``'s products for [start, end]; returns what was found."""
    if ds.service not in QUERIES:
        raise ServiceError(f"{ds.id} is not a live-search data set")
    t0, t1 = _parse(start), _parse(end, end=True)
    if t1 <= t0:
        raise ServiceError("The end date is before the start date")
    if (t1 - t0).days > MAX_WINDOW_DAYS:
        raise ServiceError("Choose a date range of at most ten years for live archive searches")
    s, e = t0.isoformat(), t1.isoformat()
    with lock, connect() as conn:
        hit = None if force else covered(conn, ds.id, s, e)
    if hit:
        return {"dataset_id": ds.id, "listed": hit[0], "available": hit[1], "cached": True}
    rows, available = QUERIES[ds.service](ds.service_query, t0, t1, MAX_PER_QUERY)
    recs = []
    for r in rows:
        ptype, kind = r["product_type"], str(ds.service_query.get("kind") or "other")
        for rx, label, k in ds.rules:            # data set rules may name profiles etc.
            if re.search(rx, (r["path"] + " " + r["product_type"]).lower()):
                ptype, kind = label, k
                break
        recs.append({"dataset_id": ds.id, "product_id": r["product_id"], "volume": r["volume"], "path": r["path"],
                     "start_time": r["start_time"], "stop_time": r["stop_time"],
                     "target": r["target"] or (ds.body_ids[0].upper() if len(ds.body_ids) == 1 else ""),
                     "product_type": ptype, "kind": kind, "extra": json.dumps(r["extra"])})
    with lock, connect() as conn:
        _windows_schema(conn)
        conn.executemany("INSERT OR REPLACE INTO products VALUES (:dataset_id,:product_id,:volume,:path,"
                         ":start_time,:stop_time,:target,:product_type,:kind,:extra)", recs)
        conn.execute("INSERT INTO service_windows VALUES (?,?,?,?,?,?)",
                     (ds.id, s, e, time.time(), len(recs), available))
    return {"dataset_id": ds.id, "listed": len(recs), "available": available, "cached": False}
