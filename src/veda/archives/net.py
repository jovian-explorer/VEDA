"""HTTP access to planetary archives.

One shared ``requests`` session so connections are reused and, for portals
that need an account, the user's login cookies are sent with every request.
All network use goes through here so the Settings > Network switch and timeout
apply everywhere.
"""
from __future__ import annotations

import ftplib
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

# Archives that also serve the same tree by anonymous FTP (checked 2026-10): used
# when HTTPS fails for any reason other than a missing file.  The PDS Rings, PPI and
# NAIF nodes, ESA PSA and JAXA DARTS have no public FTP; they are HTTPS only.
FTP_MIRRORS = {"pds-atmospheres.nmsu.edu", "pds-geosciences.wustl.edu", "spiftp.esac.esa.int"}

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


class TooLarge(ArchiveError):
    """A file is larger than the caller allowed; nothing was downloaded."""

    def __init__(self, name: str, size_bytes: int):
        super().__init__(f"{name} is {size_bytes / 1e6:,.0f} MB")
        self.name = name
        self.size_bytes = size_bytes


class _SharedTLSAdapter(requests.adapters.HTTPAdapter):
    """One TLS context for every connection: loading the CA bundle took about 1.4 s
    for each new HTTPS connection, which made the first requests to an archive slow."""

    _ctx = None

    def init_poolmanager(self, *args, **kwargs):
        if _SharedTLSAdapter._ctx is None:
            import ssl
            import certifi
            _SharedTLSAdapter._ctx = ssl.create_default_context(cafile=certifi.where())
        kwargs["ssl_context"] = _SharedTLSAdapter._ctx
        return super().init_poolmanager(*args, **kwargs)


def session() -> requests.Session:
    global _session
    with _lock:
        if _session is None:
            s = requests.Session()
            s.headers["User-Agent"] = USER_AGENT
            # (16 connections per host: indexing lists archive folders 8 at a time)
            s.mount("https://", _SharedTLSAdapter(pool_connections=16, pool_maxsize=16))
            s.mount("http://", requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16))
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


def get(url: str, *, login_url: Optional[str] = None, stream: bool = False,
        params: Optional[dict] = None, timeout: Optional[float] = None) -> requests.Response:
    """GET with retries: archives drop connections when many index files are read."""
    _check_network()
    for attempt in range(RETRIES + 1):
        try:
            r = session().get(url, timeout=timeout or SETTINGS.network_timeout_s, stream=stream,
                              allow_redirects=True, params=params)
            if r.status_code in (401, 403) and login_url:
                raise LoginRequired(urlparse(url).netloc, login_url)
            # (a 403 from a public archive is usually a busy server shedding load,
            # e.g. the PDS Rings Node after many requests: wait and try again)
            if r.status_code in (403, 429, 502, 503, 504) and attempt < RETRIES:
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


def _ftp_url(url: str) -> Optional[str]:
    u = urlparse(url)
    return f"ftp://{u.netloc}{u.path}" if u.scheme == "https" and u.netloc in FTP_MIRRORS else None


def _ftp_download(url: str, dest: Path, progress=None, max_bytes: Optional[int] = None) -> Path:
    u = urlparse(url)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with ftplib.FTP(u.netloc, timeout=SETTINGS.network_timeout_s) as ftp:
            ftp.login()
            ftp.voidcmd("TYPE I")
            try:
                total = ftp.size(u.path) or 0
            except ftplib.error_perm:
                total = 0
            if max_bytes is not None and total > max_bytes:
                raise TooLarge(dest.name, total)
            done = 0
            with open(tmp, "wb") as fh:
                def write(chunk: bytes) -> None:
                    nonlocal done
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
                ftp.retrbinary(f"RETR {u.path}", write, blocksize=256 * 1024)
        tmp.replace(dest)
        return dest
    except ftplib.error_perm as exc:
        tmp.unlink(missing_ok=True)
        raise ArchiveError(f"{u.netloc} does not have {u.path} (FTP {str(exc)[:3]}).") from exc
    except (ftplib.Error, OSError, EOFError) as exc:
        tmp.unlink(missing_ok=True)
        raise ArchiveError(f"FTP from {u.netloc} failed: {exc}") from exc


def download(url: str, dest: Path, progress: Optional[Callable[[int, int], None]] = None,
             max_bytes: Optional[int] = None, **kw) -> Path:
    """Stream ``url`` to ``dest`` atomically; returns ``dest``.

    With ``max_bytes``, a file the server reports as larger raises TooLarge before
    anything is written.  For archives in FTP_MIRRORS, a failed HTTPS transfer
    (server busy or down, not a missing file) is retried over FTP.
    """
    try:
        return _https_download(url, dest, progress, max_bytes, **kw)
    except (LoginRequired, TooLarge):
        raise
    except ArchiveError as exc:
        ftp = _ftp_url(url)
        if ftp is None or "HTTP 404" in str(exc) or not SETTINGS.network_enabled:
            raise
        try:
            return _ftp_download(ftp, dest, progress, max_bytes)
        except TooLarge:
            raise
        except ArchiveError:
            raise exc from None          # report the HTTPS failure, the primary route


def _https_download(url: str, dest: Path, progress=None, max_bytes: Optional[int] = None, **kw) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    r = get(url, stream=True, **kw)
    total = int(r.headers.get("Content-Length") or 0)
    if max_bytes is not None and total > max_bytes:
        r.close()
        raise TooLarge(dest.name, total)
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


def _ftp_list(url: str, dirs_only: bool) -> List[str]:
    u = urlparse(url)
    try:
        with ftplib.FTP(u.netloc, timeout=SETTINGS.network_timeout_s) as ftp:
            ftp.login()
            try:
                return [n for n, facts in ftp.mlsd(u.path) if n not in (".", "..")
                        and (not dirs_only or facts.get("type") == "dir")]
            except ftplib.error_perm:          # server without MLSD
                names = [n.rsplit("/", 1)[-1] for n in ftp.nlst(u.path)]
                return [n for n in names if not dirs_only or "." not in n]
    except (ftplib.Error, OSError, EOFError) as exc:
        raise ArchiveError(f"FTP listing of {url} failed: {exc}") from exc


def list_directory(url: str, pattern: Optional[str] = None, dirs_only: bool = False,
                   login_url: Optional[str] = None) -> List[str]:
    """Names in an Apache/nginx/FTP-style HTML index, optionally filtered by regex."""
    if not url.endswith("/"):
        url += "/"
    try:
        html = get_text(url, login_url=login_url)
    except LoginRequired:
        raise
    except ArchiveError as exc:
        ftp = _ftp_url(url)
        if ftp is None or "HTTP 404" in str(exc):
            raise
        try:
            names = _ftp_list(ftp, dirs_only)
        except ArchiveError:
            raise exc from None
        rx = re.compile(pattern, re.I) if pattern else None
        return [n for n in names if not rx or rx.search(n)]
    p = _Links()
    p.feed(html)
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
