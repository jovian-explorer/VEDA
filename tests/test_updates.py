"""Build identification and the "newer VEDA available" check."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from veda import __version__, updates
from veda.api.app import create_app
from veda.config import SETTINGS


@pytest.mark.parametrize("tag,expected", [
    ("v0.2.0-build.42", ((0, 2, 0), 42)),
    ("v1.0.0", ((1, 0, 0), 0)),
    ("0.3.1", ((0, 3, 1), 0)),
    ("nightly", ((), 0)),
])
def test_parse_tag(tag, expected):
    assert updates.parse_tag(tag) == expected


@pytest.mark.parametrize("tag,version,build,newer", [
    ("v0.2.0-build.43", "0.2.0", 42, True),
    ("v0.2.0-build.42", "0.2.0", 42, False),
    ("v0.2.0-build.41", "0.2.0", 42, False),
    ("v0.3.0", "0.2.0", 42, True),
    ("v0.1.0-build.99", "0.2.0", 1, False),
    ("v0.2.0-build.50", "0.2.0", None, False),   # from source: only a higher version counts
    ("v0.10.0", "0.9.0", None, True),            # numeric, not text, comparison
    ("garbage", "0.2.0", 1, False),
])
def test_is_newer(tag, version, build, newer):
    assert updates.is_newer(tag, version, build) is newer


def test_no_request_when_downloads_or_checks_are_off(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not contact GitHub")
    from veda.archives import net
    monkeypatch.setattr(net, "session", boom)
    saved = SETTINGS.network_enabled, SETTINGS.check_updates
    try:
        SETTINGS.network_enabled, SETTINGS.check_updates = False, True
        assert updates.check(force=True)["checked"] is False
        SETTINGS.network_enabled, SETTINGS.check_updates = True, False
        assert updates.check(force=True)["checked"] is False
    finally:
        SETTINGS.network_enabled, SETTINGS.check_updates = saved


def test_update_endpoint_reports_newer_release(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"tag_name": "v99.0.0", "name": "VEDA 99.0.0", "html_url": "https://example.org/r"}

    class Sess:
        def get(self, *a, **k):
            return Resp()
    from veda.archives import net
    monkeypatch.setattr(net, "session", lambda: Sess())
    saved = SETTINGS.network_enabled, SETTINGS.check_updates
    SETTINGS.network_enabled, SETTINGS.check_updates = True, True
    try:
        client = TestClient(create_app())
        r = client.get("/api/update?force=true").json()
        assert r["checked"] and r["newer"] and r["latest"]["tag"] == "v99.0.0" and r["url"] == "https://example.org/r"
        assert client.get("/api/meta").json()["build"]["version"] == __version__
    finally:
        SETTINGS.network_enabled, SETTINGS.check_updates = saved
        updates._cache.clear()
