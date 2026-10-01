"""SPICE kernels: which ones an observation needs, and downloading them.

For every mission VEDA knows where the reconstructed spacecraft ephemeris
lives and how to tell which file covers a date (checked against the NAIF,
ESA and JAXA servers on 2026-10-01):

* file names that encode their coverage (MAVEN, Juno, Cassini, LRO, Dawn, ...);
* the PDS3 SPICE archive's ``dsindex.tab`` coverage table (MGS, MRO, MESSENGER,
  New Horizons), which lists START_TIME / STOP_TIME for every kernel;
* small fixed tables from the archive read-me files (Magellan, Galileo, Rosetta).

Only the kernels covering the observation are fetched: the generic set (leap
seconds, planetary constants, DE440s), body kernels when the target is not in
DE440s (Mars, Pluto, Ceres, Vesta, 67P), and the spacecraft SPK.  Files are
cached under <cache>/spice and reused by every later observation.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..archives import net
from ..config import CACHE_DIR

KERNEL_DIR = CACHE_DIR / "spice"
NAIF = "https://naif.jpl.nasa.gov/pub/naif/"
GEN = NAIF + "generic_kernels/"
ESA = "https://spiftp.esac.esa.int/data/SPICE/"

GENERIC = [
    GEN + "lsk/naif0012.tls",
    GEN + "pck/pck00011.tpc",
    GEN + "spk/planets/de440s.bsp",
]

# Targets whose centre is not in DE440s (it has planet barycentres, Mercury, Venus,
# Earth and the Moon).  Juno, Galileo and Cassini SPKs already include their moons.
BODY_KERNELS: Dict[str, List[str]] = {
    "mars": [GEN + "spk/satellites/mar099s.bsp"],
    "pluto": [NAIF + "pds/data/nh-j_p_ss-spice-6-v1.0/nhsp_1000/data/spk/nh_plu047_od122.bsp"],
    "ceres": [NAIF + "pds/data/dawn-m_a-spice-6-v1.0/dawnsp_1000/data/spk/sb_ceres_140724.bsp"],
    "vesta": [NAIF + "pds/data/dawn-m_a-spice-6-v1.0/dawnsp_1000/data/spk/sb_vesta_ssd_120716.bsp"],
    "comet_67p": [ESA + "ROSETTA/kernels/spk/CORB_DV_257_03___T19_00345.BSP",
                  ESA + "ROSETTA/kernels/fk/ROS_V38.TF",
                  ESA + "ROSETTA/kernels/pck/ROS_CGS_RSOC_V03.TPC"],
}


@dataclass(frozen=True)
class Source:
    """One place spacecraft SPKs are found and how a file's coverage is known.

    mode:
      "range"   named groups ``start`` and ``end`` hold dates (yymmdd, yyyymmdd, yyDOY, yyyyDOY);
      "year"    group ``year``: the file covers that calendar year;
      "month"   group ``start``: covers that calendar month;
      "next"    group ``start`` (yymmddhhmmss or a date): covers until the next file's start;
      "fixed"   ``table`` of (start, end, file name);
      "dsindex" ``dir`` is a PDS3 SPICE data set; its dsindex.tab gives each kernel's coverage.
    Among several files covering the date the last in name order wins (newer releases sort
    later), except for "dsindex" and ``prefer_shortest`` where the shortest coverage wins
    (usually the smallest file).
    """
    dir: str
    mode: str
    regex: str = ""
    table: Tuple[Tuple[str, str, str], ...] = ()
    prefer_shortest: bool = False


@dataclass(frozen=True)
class MissionSpice:
    naif_id: int
    sources: Tuple[Source, ...]
    source: str                              # shown to the user
    extra: Tuple[str, ...] = ()              # frame kernels etc. always loaded


MISSION_SPICE: Dict[str, MissionSpice] = {
    "akatsuki": MissionSpice(-5, (
        Source(NAIF + "pds/pds4/vco/vco_spice/spice_kernels/spk/", "year", r"^vco_(?P<year>\d{4})_v\d+\.bsp$"),
        Source("https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-spice-6-v1.0/vcosp_1000/data/spk/", "year",
               r"^vco_(?P<year>\d{4})_v\d+\.bsp$"),
    ), "NAIF PDS4 Akatsuki SPICE archive (JAXA DARTS copy as fallback)"),
    "mex": MissionSpice(-41, (
        Source(ESA + "MARS-EXPRESS/kernels/spk/", "range", r"^MEX_ROB_(?P<start>\d{6})_(?P<end>\d{6})_\d+\.BSP$"),
        Source(ESA + "MARS-EXPRESS/kernels/spk/", "month", r"^ORMM_T19_(?P<start>\d{6})\d{6}_\d+\.BSP$"),
        Source(ESA + "MARS-EXPRESS/kernels/spk/", "month", r"^ORMM__(?P<start>\d{6})\d{6}_\d+\.BSP$"),
        Source(ESA + "MARS-EXPRESS/kernels/spk/", "range", r"^ORMF_(?P<start>\d{6})_(?P<end>\d{6})_\d+\.BSP$"),
    ), "ESA SPICE service (MARS-EXPRESS)"),
    "vex": MissionSpice(-248, (
        Source(NAIF + "VEX/kernels/spk/", "next", r"^ORVV_T19_(?P<start>\d{12})_\d{5}\.BSP$"),
        Source(NAIF + "VEX/kernels/spk/", "fixed", table=(("2005-11-09", "2006-04-10", "ORHV_T19___________00030.BSP"),)),
    ), "NAIF Venus Express archive (ESA kernels)"),
    "magellan": MissionSpice(-18, (
        Source(NAIF + "MGN/kernels/spk/nav/", "fixed", table=(
            ("1990-08-16", "1990-08-17", "PRECYCL1.BSP"), ("1990-09-15", "1991-05-16", "CYCLE1.BSP"),
            ("1991-05-15", "1992-01-16", "CYCLE2.BSP"), ("1992-01-25", "1992-09-15", "CYCLE3.BSP"),
            ("1992-09-13", "1993-05-26", "CYCLE4.BSP"), ("1993-05-25", "1993-08-16", "AEROBRAK.BSP"),
            ("1993-08-15", "1994-04-16", "CYCLE5.BSP"), ("1994-04-15", "1994-10-14", "CYCLE6.BSP"))),
    ), "NAIF Magellan navigation kernels"),
    "pvo": MissionSpice(-12, (
        Source(NAIF + "PIONEER12/kernels/spk/", "range", r"^pvo_(?P<start>\d{6})_(?P<end>\d{6})_ssd1999\.bsp$"),
    ), "NAIF Pioneer Venus kernels", extra=(NAIF + "PIONEER12/kernels/fk/pvo.tf",)),
    "mgs": MissionSpice(-94, (
        Source(NAIF + "pds/data/mgs-m-spice-6-v1.0/", "dsindex"),
    ), "NAIF PDS3 MGS SPICE archive"),
    "mro": MissionSpice(-74, (
        Source(NAIF + "MRO/kernels/spk/", "fixed", table=(("2005-08-12", "2006-03-10", "mro_cruise.bsp"),
                                                         ("2006-03-10", "2006-09-12", "mro_ab.bsp"))),
        Source(NAIF + "pds/data/mro-m-spice-6-v1.0/", "dsindex"),
    ), "NAIF MRO kernels and PDS3 SPICE archive"),
    "maven": MissionSpice(-202, (
        Source(NAIF + "MAVEN/kernels/spk/", "range", r"^maven_orb_rec_(?P<start>\d{6})_(?P<end>\d{6})_v\d+\.bsp$"),
        Source(NAIF + "MAVEN/kernels/spk/", "range", r"^trj_c_(?P<start>\d{6})-(?P<end>\d{6})_rec_v\d+\.bsp$"),
    ), "NAIF MAVEN kernels"),
    "juno": MissionSpice(-61, (
        Source(NAIF + "JUNO/kernels/spk/", "range", r"^spk_rec_(?P<start>\d{6})_(?P<end>\d{6})_\d{6}\.bsp$",
               prefer_shortest=True),
    ), "NAIF Juno kernels"),
    "galileo": MissionSpice(-77, (
        Source(NAIF + "GLL/kernels/spk/", "fixed", table=(
            ("1989-10-19", "1995-07-02", "s970311a.bsp"), ("1995-06-30", "1998-01-01", "s980326a.bsp"),
            ("1997-12-01", "2000-02-01", "s000131a.bsp"), ("2000-01-31", "2003-09-30", "s030916a.bsp"))),
    ), "NAIF Galileo navigation kernels"),
    "cassini": MissionSpice(-82, (
        Source(NAIF + "CASSINI/kernels/spk/", "range", r"^200128RU_SCPSE_(?P<start>\d{5})_(?P<end>\d{5})\.bsp$"),
        Source(NAIF + "pds/data/co-s_j_e_v-spice-6-v1.0/", "dsindex"),
    ), "NAIF Cassini final reconstruction (2020)"),
    "new_horizons": MissionSpice(-98, (
        Source(NAIF + "pds/data/nh-j_p_ss-spice-6-v1.0/", "dsindex"),
    ), "NAIF PDS3 New Horizons SPICE archive"),
    "messenger": MissionSpice(-236, (
        Source(NAIF + "pds/data/mess-e_v_h-spice-6-v1.0/", "dsindex"),
    ), "NAIF PDS3 MESSENGER SPICE archive"),
    "lro": MissionSpice(-85, (
        Source(NAIF + "pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/spk/", "range",
               r"^lrorg_(?P<start>\d{7})_(?P<end>\d{7})_v\d{2}\.bsp$"),
    ), "NAIF PDS3 LRO SPICE archive"),
    "dawn": MissionSpice(-203, (
        Source(NAIF + "pds/data/dawn-m_a-spice-6-v1.0/dawnsp_1000/data/spk/", "range",
               r"^dawn_rec_(?P<start>\d{6})_(?P<end>\d{6})_\d{6}_v\d\.bsp$", prefer_shortest=True),
    ), "NAIF PDS3 Dawn SPICE archive"),
    "rosetta": MissionSpice(-226, (
        Source(ESA + "ROSETTA/kernels/spk/", "fixed", table=(
            ("2014-01-01", "2016-10-05", "RORB_DV_257_03___T19_00345.BSP"),
            ("2004-03-02", "2014-08-04", "ORHR___________T19_00122.BSP"))),
    ), "ESA SPICE service (ROSETTA)", extra=(ESA + "ROSETTA/kernels/fk/ROS_V38.TF",)),
    "bepicolombo": MissionSpice(-121, (
        Source(ESA + "BEPICOLOMBO/kernels/spk/", "range",
               r"^bc_mpo_fcp_\d{5}_(?P<start>\d{8})_(?P<end>\d{8})_v\d{2}\.bsp$"),
    ), "ESA SPICE service (BEPICOLOMBO)"),
}
# No public SPICE kernels: Mars Orbiter Mission, Chandrayaan-2 (PRADAN, account needed).


def _date(s: str) -> dt.date:
    """yymmdd, yyyymmdd, yyDOY, yyyyDOY, yymmddhhmmss or yyyy-mm-dd."""
    s = s.strip()
    if "-" in s:
        return dt.date.fromisoformat(s[:10])
    if len(s) == 12:
        s = s[:6]
    if len(s) == 5:                                   # yyDOY
        y = int(s[:2]); y += 2000 if y < 70 else 1900
        return dt.date(y, 1, 1) + dt.timedelta(days=int(s[2:]) - 1)
    if len(s) == 7:                                   # yyyyDOY
        return dt.date(int(s[:4]), 1, 1) + dt.timedelta(days=int(s[4:]) - 1)
    if len(s) == 6:                                   # yymmdd
        y = int(s[:2]); y += 2000 if y < 70 else 1900
        return dt.date(y, int(s[2:4]), int(s[4:6]))
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


_listing_cache: Dict[str, Tuple[float, List[str]]] = {}
_dsindex_cache: Dict[str, Tuple[float, List[Tuple[dt.date, dt.date, str]]]] = {}
_lock = threading.Lock()


def _listing(url: str) -> List[str]:
    with _lock:
        hit = _listing_cache.get(url)
        if hit and time.time() - hit[0] < 24 * 3600:
            return hit[1]
    names = net.list_directory(url)
    with _lock:
        _listing_cache[url] = (time.time(), names)
    return names


def _dsindex(dataset_url: str) -> List[Tuple[dt.date, dt.date, str]]:
    """(start, stop, kernel URL) of every SPK in a PDS3 SPICE archive."""
    with _lock:
        hit = _dsindex_cache.get(dataset_url)
        if hit and time.time() - hit[0] < 7 * 24 * 3600:
            return hit[1]
    text = net.get_text(dataset_url + "dsindex.tab")
    out = []
    for row in csv.reader(io.StringIO(text), skipinitialspace=True):
        if len(row) < 10:
            continue
        start, stop, spec, kind, pid, vol = row[0], row[1], row[2], row[7], row[8], row[9]
        if kind.strip().upper() != "SPK" or any(x in pid.lower() for x in ("_gsfc_", "_ipng_", "pred", "_plan")):
            continue
        try:
            t0, t1 = dt.date.fromisoformat(start.strip()[:10]), dt.date.fromisoformat(stop.strip()[:10])
        except ValueError:
            continue
        folder = spec.strip().replace("\\", "/").rsplit("/", 1)[0]
        out.append((t0, t1, f"{dataset_url}{vol.strip().lower()}/{folder}/{pid.strip()}"))
    with _lock:
        _dsindex_cache[dataset_url] = (time.time(), out)
    return out


def _from_source(src: Source, when: dt.date) -> List[str]:
    """Kernel URLs covering ``when``.  Files whose range starts or ends on that day are all
    returned (an observation in the early hours may lie in the previous file)."""
    if src.mode == "range":
        names = sorted(_listing(src.dir))
        rx = re.compile(src.regex, re.I)
        by_range: Dict[Tuple[dt.date, dt.date], str] = {}
        for n in names:
            m = rx.match(n)
            if not m:
                continue
            try:
                a, b = _date(m.group("start")), _date(m.group("end"))
            except (ValueError, KeyError):
                continue
            if a <= when <= b:
                by_range[(a, b)] = n           # later names (newer releases) replace earlier ones
        if not by_range:
            return []
        ranges = sorted(by_range, key=lambda r: (r[1] - r[0]).days)
        pick = [r for r in ranges if r[0] == when or r[1] == when]
        best = ranges[0] if src.prefer_shortest else max(by_range, key=lambda r: by_range[r])
        return [src.dir + by_range[r] for r in dict.fromkeys([best, *pick])]
    one = _single_from_source(src, when)
    return [one] if one else []


def _single_from_source(src: Source, when: dt.date) -> Optional[str]:
    if src.mode == "fixed":
        for a, b, name in src.table:
            if dt.date.fromisoformat(a) <= when <= dt.date.fromisoformat(b):
                return src.dir + name
        return None
    if src.mode == "dsindex":
        cands = [(t1 - t0, u) for t0, t1, u in _dsindex(src.dir) if t0 <= when <= t1]
        return min(cands)[1] if cands else None
    names = sorted(_listing(src.dir))
    rx = re.compile(src.regex, re.I)
    best: Optional[Tuple[object, str]] = None
    starts: List[Tuple[dt.date, str]] = []
    for n in names:
        m = rx.match(n)
        if not m:
            continue
        g = m.groupdict()
        try:
            if src.mode == "year":
                ok, span = int(g["year"]) == when.year, 365
            elif src.mode == "month":
                d = _date(g["start"])
                ok, span = (d.year, d.month) == (when.year, when.month), 31
            elif src.mode == "next":
                starts.append((_date(g["start"]), n))
                continue
            else:
                a, b = _date(g["start"]), _date(g["end"])
                ok, span = a <= when <= b, (b - a).days
        except (ValueError, KeyError):
            continue
        if ok:
            key = span if src.prefer_shortest else 0
            if best is None or (src.prefer_shortest and key <= best[0]) or not src.prefer_shortest:
                best = (key, n)
    if src.mode == "next" and starts:
        starts.sort()
        prior = [s for s in starts if s[0] <= when]
        if prior and (when - prior[-1][0]).days <= 62:
            same = [s for s in starts if s[0] == prior[-1][0]]     # highest version of that start
            return src.dir + same[-1][1]
        return None
    return src.dir + best[1] if best else None


def mission_spks_for(mission_id: str, when: dt.date) -> List[str]:
    """URLs of the spacecraft SPKs covering ``when`` (empty when no file covers it)."""
    ms = MISSION_SPICE.get(mission_id)
    if not ms:
        return []
    last_error: Optional[Exception] = None
    for src in ms.sources:
        try:
            urls = _from_source(src, when)
        except net.ArchiveError as exc:        # one mirror down: try the next source
            last_error = exc
            continue
        if urls:
            return urls
    if last_error:
        raise last_error
    return []


def mission_spk_for(mission_id: str, when: dt.date) -> Optional[str]:
    """The main spacecraft SPK covering ``when``."""
    urls = mission_spks_for(mission_id, when)
    return urls[0] if urls else None


@dataclass
class KernelPlan:
    urls: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def local(self, url: str) -> Path:
        return KERNEL_DIR / url.rsplit("/", 1)[1]


def plan(mission_id: str, body_id: str, when: dt.date) -> KernelPlan:
    p = KernelPlan()
    ms = MISSION_SPICE.get(mission_id)
    if ms is None:
        raise LookupError(f"No public SPICE kernels are known for {mission_id}")
    p.urls = list(GENERIC) + BODY_KERNELS.get(body_id, []) + list(ms.extra)
    spks = mission_spks_for(mission_id, when)
    if not spks:
        raise LookupError(f"No {mission_id} spacecraft ephemeris (SPK) covers {when.isoformat()}")
    p.urls.extend(spks)
    p.urls = list(dict.fromkeys(p.urls))
    p.missing = [u for u in p.urls if not p.local(u).is_file()]
    return p


def base_plan(body_id: str) -> KernelPlan:
    """Generic and body kernels only (prefetched when a mission is opened)."""
    p = KernelPlan(urls=list(dict.fromkeys(GENERIC + BODY_KERNELS.get(body_id, []))))
    p.missing = [u for u in p.urls if not p.local(u).is_file()]
    return p


_size_cache: Dict[str, int] = {}


def remote_size(url: str) -> int:
    if url in _size_cache:
        return _size_cache[url]
    try:
        r = net.session().head(url, timeout=20, allow_redirects=True)
        n = int(r.headers.get("Content-Length") or 0)
    except Exception:  # noqa: BLE001 - size is only informative
        n = 0
    _size_cache[url] = n
    return n


_download_lock = threading.Lock()


def download(p: KernelPlan, progress: Optional[Callable[[int, int, str], None]] = None) -> None:
    """Download the plan's missing kernels (one download at a time across the app)."""
    KERNEL_DIR.mkdir(parents=True, exist_ok=True)
    with _download_lock:
        for i, url in enumerate(p.missing):
            if p.local(url).is_file():          # fetched meanwhile by another job
                continue
            name = url.rsplit("/", 1)[1]
            net.download(url, p.local(url),
                         progress=(lambda d, t, i=i, name=name: progress(i, len(p.missing), f"{name}: {d // 1048576} of {t // 1048576 or '?'} MB")) if progress else None)
        p.missing = []
