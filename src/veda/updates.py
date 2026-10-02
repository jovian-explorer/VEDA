"""Which build this is, and whether a newer one has been published.

Every push to VEDA's main branch that passes the tests is built and published as
the latest GitHub release, tagged ``v<version>-build.<n>`` (named versions are
tagged ``v<version>``).  Release builds carry their number in ``veda/_build.py``,
written by the release workflow; a copy run from source has no build number.

The check makes one request to the GitHub API per session, and none when
downloads are turned off (Settings > Network) or update checks are.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, Optional, Tuple

from . import __version__

REPO = "jovian-explorer/VEDA"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
_API = f"https://api.github.com/repos/{REPO}/releases/latest"

try:
    from ._build import BUILD  # type: ignore[import-not-found]
except ImportError:            # running from source
    BUILD = {}

_cache: Dict[str, Any] = {}
_lock = threading.Lock()
_TTL_S = 6 * 3600


def build_info() -> Dict[str, Any]:
    return {"version": __version__, "build": BUILD.get("number"), "commit": BUILD.get("commit"),
            "date": BUILD.get("date")}


def _version_tuple(v: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def parse_tag(tag: str) -> Tuple[Tuple[int, ...], int]:
    """("v0.2.0-build.42") -> ((0, 2, 0), 42); a plain version tag has build 0."""
    m = re.match(r"v?(\d+(?:\.\d+)*)(?:-build\.(\d+))?$", (tag or "").strip())
    if not m:
        return (), 0
    return _version_tuple(m.group(1)), int(m.group(2) or 0)


def is_newer(tag: str, version: str = __version__, build: Optional[int] = None) -> bool:
    """Whether the release ``tag`` is newer than this copy.  Builds of the same version
    are ordered by number; from source (no build number) only a higher version counts,
    since the source may already be ahead of the last build."""
    rv, rb = parse_tag(tag)
    if not rv:
        return False
    here = _version_tuple(version)
    if rv != here:
        return rv > here
    return build is not None and rb > build


def check(force: bool = False) -> Dict[str, Any]:
    """The latest published release and whether it is newer than this copy."""
    from .config import SETTINGS
    info = build_info()
    out: Dict[str, Any] = {**info, "url": RELEASES_URL, "latest": None, "newer": False, "checked": False}
    if not SETTINGS.network_enabled or not getattr(SETTINGS, "check_updates", True):
        return out
    with _lock:
        hit = _cache.get("latest")
        if force or not hit or time.time() - hit[0] > _TTL_S:
            try:
                from .archives import net
                r = net.session().get(_API, timeout=8, headers={"Accept": "application/vnd.github+json"})
                r.raise_for_status()
                rel = r.json()
                hit = (time.time(), {"tag": rel.get("tag_name", ""), "name": rel.get("name", ""),
                                     "published": rel.get("published_at", ""), "url": rel.get("html_url") or RELEASES_URL})
            except Exception as exc:  # noqa: BLE001 - offline or rate limited: no notice
                return {**out, "error": str(exc)[:200]}
            _cache["latest"] = hit
    latest = hit[1]
    return {**out, "checked": True, "latest": latest, "url": latest["url"],
            "newer": is_newer(latest["tag"], info["version"], info["build"])}
