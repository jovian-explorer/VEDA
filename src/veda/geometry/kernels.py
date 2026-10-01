"""SPICE kernels: which ones an observation needs, and downloading them.

Only the kernels covering the observation are fetched: the generic set (leap
seconds, planetary constants, DE440s), a satellite kernel when the planet's
centre is not in DE440s (Mars), and the one spacecraft SPK whose file name
covers the observation date. Files are cached under <cache>/spice and reused.
"""
from __future__ import annotations

import datetime as dt
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..archives import net
from ..config import CACHE_DIR

KERNEL_DIR = CACHE_DIR / "spice"
NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"

GENERIC = [
    NAIF + "lsk/naif0012.tls",
    NAIF + "pck/pck00011.tpc",
    NAIF + "spk/planets/de440s.bsp",
]

# DE440s has the Mars system barycentre but not Mars itself (499); spacecraft
# SPKs centred on 499 need the satellite kernel to connect to the barycentre.
BODY_KERNELS: Dict[str, List[str]] = {
    "mars": [NAIF + "spk/satellites/mar099s.bsp"],
}


def _date(s: str) -> dt.date:
    s = s.strip()
    if len(s) == 6:   # yymmdd
        return dt.date(2000 + int(s[:2]) if int(s[:2]) < 70 else 1900 + int(s[:2]), int(s[2:4]), int(s[4:6]))
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


@dataclass(frozen=True)
class MissionSpice:
    naif_id: int
    spk_dir: str
    # (regex, kind): kind "year" -> group 1 is the year; "range" -> groups 1, 2 are
    # start/end dates (yymmdd or yyyymmdd). Earlier rules are preferred.
    spk_rules: Tuple[Tuple[str, str], ...]
    source: str


MISSION_SPICE: Dict[str, MissionSpice] = {
    "akatsuki": MissionSpice(
        naif_id=-5,
        spk_dir="https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-spice-6-v1.0/vcosp_1000/data/spk/",
        spk_rules=((r"^vco_(\d{4})_v\d+\.bsp$", "year"),),
        source="JAXA DARTS (vco-v-spice-6-v1.0)",
    ),
    "mex": MissionSpice(
        naif_id=-41,
        spk_dir="https://spiftp.esac.esa.int/data/SPICE/MARS-EXPRESS/kernels/spk/",
        # Names as listed by the ESA SPICE service (checked): yearly reconstructed
        # orbits to 2013, then monthly ORMM files, plus ORMF ranges.
        spk_rules=(
            (r"^MEX_ROB_(\d{6})_(\d{6})_\d+\.BSP$", "range"),
            (r"^ORMM__(\d{6})\d{6}_\d+\.BSP$", "month"),
            (r"^ORMM_T19_(\d{6})\d{6}_\d+\.BSP$", "month"),
            (r"^ORMF_(\d{6})_(\d{6})_\d+\.BSP$", "range"),
        ),
        source="ESA SPICE service (MARS-EXPRESS)",
    ),
}

_listing_cache: Dict[str, Tuple[float, List[str]]] = {}
_lock = threading.Lock()


def _listing(url: str) -> List[str]:
    import time
    with _lock:
        hit = _listing_cache.get(url)
        if hit and time.time() - hit[0] < 24 * 3600:
            return hit[1]
    names = net.list_directory(url)
    with _lock:
        _listing_cache[url] = (time.time(), names)
    return names


def mission_spk_for(mission_id: str, when: dt.date) -> Optional[str]:
    """URL of the spacecraft SPK whose file name covers ``when``."""
    ms = MISSION_SPICE.get(mission_id)
    if not ms:
        return None
    names = _listing(ms.spk_dir)
    for rx, kind in ms.spk_rules:
        best = None
        for n in names:
            m = re.match(rx, n, re.I)
            if not m:
                continue
            if kind == "year" and int(m.group(1)) == when.year:
                best = n
            elif kind == "range" and _date(m.group(1)) <= when <= _date(m.group(2)):
                best = n
            elif kind == "month":
                d = _date(m.group(1))
                if (d.year, d.month) == (when.year, when.month):
                    best = n
            # later listings (higher versions) overwrite earlier ones
        if best:
            return ms.spk_dir + best
    return None


@dataclass
class KernelPlan:
    urls: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def local(self, url: str) -> Path:
        return KERNEL_DIR / url.rsplit("/", 1)[1]


def plan(mission_id: str, body_id: str, when: dt.date) -> KernelPlan:
    p = KernelPlan()
    p.urls = list(GENERIC) + BODY_KERNELS.get(body_id, [])
    spk = mission_spk_for(mission_id, when)
    if spk is None:
        raise LookupError(f"No {mission_id} spacecraft ephemeris (SPK) covers {when.isoformat()}")
    p.urls.append(spk)
    p.missing = [u for u in p.urls if not p.local(u).is_file()]
    return p


def remote_size(url: str) -> int:
    try:
        r = net.session().head(url, timeout=20, allow_redirects=True)
        return int(r.headers.get("Content-Length") or 0)
    except Exception:  # noqa: BLE001 - size is only informative
        return 0


def download(p: KernelPlan, progress: Optional[Callable[[int, int, str], None]] = None) -> None:
    KERNEL_DIR.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(p.missing):
        name = url.rsplit("/", 1)[1]
        net.download(url, p.local(url),
                     progress=(lambda d, t, i=i, name=name: progress(i, len(p.missing), f"{name}: {d // 1048576} of {t // 1048576 or '?'} MB")) if progress else None)
    p.missing = []
