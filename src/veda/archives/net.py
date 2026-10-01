"""HTTP access to planetary archives.

One shared ``requests`` session so connections are reused and, for portals
that need an account, the user's login cookies are sent with every request.
All network use goes through here so the Settings > Network switch and timeout
apply everywhere.
"""
from __future__ import annotations

import re
import threading
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from .. import __version__
from ..config import SETTINGS

USER_AGENT = f"VEDA/{__version__} (+https://github.com/jovian-explorer/VEDA)"

_session: Optional[requests.Session] = None
_lock = threading.Lock()


class ArchiveError(RuntimeError):
    """A readable reason an archive request failed."""


class LoginRequired(ArchiveError):
    """The portal answered with a login page or 401/403."""

    def __init__(self, host: str, login_url: str):
        super().__init__(f"{host} needs you to sign in. Open {login_url}, log in, then try again.")
        self.host = host
        self.login_url = login_url


def session() -> requests.Session:
    global _session
    with _lock:
        if _session is None:
            s = requests.Session()
            s.headers["User-Agent"] = USER_AGENT
            _session = s
        return _session


def set_cookies(domain: str, cookies: Dict[str, str]) -> None:
    """Attach login cookies (copied from the user's browser) for one portal."""
    s = session()
    for name, value in cookies.items():
        s.cookies.set(name, value, domain=domain)


def _check_network() -> None:
    if not SETTINGS.network_enabled:
        raise ArchiveError("Online archive access is turned off (Settings > Network).")


def _describe(exc: Exception, url: str) -> ArchiveError:
    host = urlparse(url).netloc or url
    if isinstance(exc, requests.Timeout):
        return ArchiveError(f"No response from {host} within {SETTINGS.network_timeout_s} s. "
                            "The archive may be slow or offline; try again or raise the timeout in Settings.")
    if isinstance(exc, requests.ConnectionError):
        return ArchiveError(f"Could not connect to {host}. Check your internet connection.")
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 404:
            return ArchiveError(f"{host} does not have {urlparse(url).path} (HTTP 404).")
        return ArchiveError(f"{host} refused the request (HTTP {code}).")
    return ArchiveError(f"Request to {host} failed: {exc}")


RETRIES = 3


def get(url: str, *, login_url: Optional[str] = None, stream: bool = False) -> requests.Response:
    """GET with retries: archives drop connections when many index files are read."""
    _check_network()
    for attempt in range(RETRIES + 1):
        try:
            r = session().get(url, timeout=SETTINGS.network_timeout_s, stream=stream, allow_redirects=True)
            if r.status_code in (401, 403) and login_url:
                raise LoginRequired(urlparse(url).netloc, login_url)
            if r.status_code in (429, 502, 503, 504) and attempt < RETRIES:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r
        except LoginRequired:
            raise
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt < RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise _describe(exc, url) from exc
        except requests.RequestException as exc:
            raise _describe(exc, url) from exc
    raise ArchiveError(f"{urlparse(url).netloc} kept failing; try again later.")


def get_text(url: str, **kw) -> str:
    r = get(url, **kw)
    if not r.encoding:
        r.encoding = "latin-1"
    return r.text


def download(url: str, dest: Path, progress: Optional[Callable[[int, int], None]] = None, **kw) -> Path:
    """Stream ``url`` to ``dest`` atomically; returns ``dest``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    r = get(url, stream=True, **kw)
    total = int(r.headers.get("Content-Length") or 0)
    done = 0
    try:
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        tmp.replace(dest)
    except requests.RequestException as exc:
        tmp.unlink(missing_ok=True)
        raise _describe(exc, url) from exc
    finally:
        r.close()
    return dest


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def list_directory(url: str, pattern: Optional[str] = None, dirs_only: bool = False,
                   login_url: Optional[str] = None) -> List[str]:
    """Names in an Apache/nginx/FTP-style HTML index, optionally filtered by regex."""
    if not url.endswith("/"):
        url += "/"
    p = _Links()
    p.feed(get_text(url, login_url=login_url))
    base = urlparse(url)
    rx = re.compile(pattern, re.I) if pattern else None
    names: List[str] = []
    for href in p.hrefs:
        full = urlparse(urljoin(url, href))
        if full.netloc != base.netloc or not full.path.startswith(base.path) or full.path == base.path:
            continue
        name = full.path[len(base.path):]
        if "/" in name.rstrip("/") or name.startswith("?"):
            continue
        is_dir = name.endswith("/")
        name = name.rstrip("/")
        if dirs_only and not is_dir:
            continue
        if rx and not rx.search(name):
            continue
        if name not in names:
            names.append(name)
    return names
