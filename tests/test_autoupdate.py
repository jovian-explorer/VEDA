"""Weekly automatic update (autoupdate.py) and the settings comparison shown after an
update (settings_migration.py)."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veda import autoupdate, config, settings_migration as sm
from veda.api.app import create_app
from veda.config import SETTINGS, Settings


# ---------------------------------------------------------------- settings comparison

def _schema(**over):
    s = sm.current_schema()
    s.update(over)
    return s


def test_compare_lists_new_removed_changed_invalid_and_renamed():
    new = sm.current_schema()
    old = {k: dict(v) for k, v in new.items() if k != "auto_update"}       # an older version
    old["gone_option"] = {"default": 1, "rule": {"min": 0, "max": 5}}
    old["plot_dpi"] = {"default": 300, "rule": {"min": 72, "max": 2400}}   # range narrowed since
    old["old_name"] = {"default": "K", "rule": ["K", "C"]}
    stored = {"ui_theme": "light", "plot_dpi": 2000, "gone_option": 3, "units_pressure": "mmHg",
              "old_name": "C", "cpu_workers": 2}
    out = sm.compare(stored, old, new, renamed={"old_name": "units_temperature"})
    assert [n["key"] for n in out["new"]] == ["auto_update"] and out["new"][0]["default"] is True
    assert out["removed"] == [{"key": "gone_option", "stored": 3}]
    ch = {c["key"]: c for c in out["changed"]}
    assert ch["plot_dpi"]["stored"] == 2000 and ch["plot_dpi"]["valid"] is False
    assert ch["plot_dpi"]["old_rule"] == {"min": 72, "max": 2400} and ch["plot_dpi"]["rule"] == {"min": 72, "max": 1200}
    assert [i["key"] for i in out["invalid"]] == ["units_pressure"]
    assert out["renamed"] == [{"old": "old_name", "key": "units_temperature", "stored": "C", "valid": True}]
    # unchanged options with valid values are not listed
    listed = {x.get("key") for v in out.values() for x in v}
    assert "ui_theme" not in listed and "cpu_workers" not in listed


def test_compare_without_a_marker_uses_the_stored_keys():
    stored = Settings().to_dict()
    stored.pop("auto_update")
    stored["obsolete"] = True
    out = sm.compare(stored, None, sm.current_schema())
    assert [n["key"] for n in out["new"]] == ["auto_update"]
    assert out["removed"] == [{"key": "obsolete", "stored": True}] and not out["changed"]


def _write_settings(data):
    config.SETTINGS_PATH.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def fresh_settings(monkeypatch):
    """A settings.json written by another version, loaded as at start-up."""
    saved = SETTINGS.to_dict(), dict(SETTINGS.preserved())
    created = config.SETTINGS_CREATED
    sm.MARKER_PATH.unlink(missing_ok=True)

    def load(data):
        _write_settings(data)
        s = Settings.load()
        for k, v in s.to_dict().items():
            setattr(SETTINGS, k, v)
        SETTINGS.preserved().clear()
        SETTINGS.preserved().update(s.preserved())
        config.SETTINGS_CREATED = False
        return SETTINGS
    yield load
    for k, v in saved[0].items():
        setattr(SETTINGS, k, v)
    SETTINGS.preserved().clear()
    SETTINGS.preserved().update(saved[1])
    config.SETTINGS_CREATED = created
    sm.MARKER_PATH.unlink(missing_ok=True)
    SETTINGS.save()


def test_stored_values_are_kept_even_when_this_version_cannot_use_them(fresh_settings):
    s = fresh_settings({"ui_theme": "light", "plot_dpi": 5000, "retired_option": "x", "cpu_workers": 3})
    assert s.ui_theme == "light" and s.cpu_workers == 3
    assert s.plot_dpi == Settings().plot_dpi                        # out of range: default in use
    s.save()
    on_disk = json.loads(config.SETTINGS_PATH.read_text(encoding="utf-8"))
    assert on_disk["plot_dpi"] == 5000 and on_disk["retired_option"] == "x" and on_disk["ui_theme"] == "light"
    s.update({"plot_dpi": 600})                                     # chosen by the user: written
    s.save()
    on_disk = json.loads(config.SETTINGS_PATH.read_text(encoding="utf-8"))
    assert on_disk["plot_dpi"] == 600 and on_disk["retired_option"] == "x"


def test_changes_shown_once_then_marker(fresh_settings):
    old = Settings().to_dict()
    old.pop("auto_update")
    old.update({"ui_theme": "light", "plot_dpi": 5000, "retired_option": 7})
    fresh_settings(old)
    client = TestClient(create_app())
    r = client.get("/api/settings/changes").json()
    assert r["show"] is True and r["whats_new"] is None
    assert [n["key"] for n in r["changes"]["new"]] == ["auto_update"]
    assert [i["key"] for i in r["changes"]["invalid"]] == ["plot_dpi"]
    assert r["changes"]["removed"] == [{"key": "retired_option", "stored": 7}]
    bad = client.post("/api/settings/changes/ack", json={"settings": {"plot_dpi": 99999}})
    assert bad.status_code == 422 and not sm.MARKER_PATH.exists()
    ok = client.post("/api/settings/changes/ack", json={"settings": {"plot_dpi": 600, "auto_update": False}}).json()
    assert ok["plot_dpi"] == 600 and ok["auto_update"] is False and ok["ui_theme"] == "light"
    on_disk = json.loads(config.SETTINGS_PATH.read_text(encoding="utf-8"))
    assert "retired_option" not in on_disk and on_disk["ui_theme"] == "light"
    marker = json.loads(sm.MARKER_PATH.read_text(encoding="utf-8"))
    assert marker["schema"] == sm.current_schema()
    assert client.get("/api/settings/changes").json() == {"show": False}


def test_first_start_shows_nothing(fresh_settings):
    fresh_settings(Settings().to_dict())
    config.SETTINGS_CREATED = True
    assert sm.pending() == {"show": False} and sm.MARKER_PATH.exists()


def test_whats_new_after_an_update(fresh_settings, monkeypatch):
    fresh_settings(Settings().to_dict())
    sm.MARKER_PATH.write_text(json.dumps({"version": "0.2.0", "build": 41, "schema": sm.current_schema()}))
    monkeypatch.setitem(autoupdate.BUILD, "number", 42)
    autoupdate.save_state({"installed": {"tag": "v0.2.0-build.42", "name": "VEDA 0.2.0 build 42", "build": 42,
                                         "notes": "### Changes\n- one", "url": "https://example.org"}})
    try:
        r = sm.pending()
        assert r["show"] and r["whats_new"]["notes"].endswith("- one") and r["previous"]["build"] == 41
        assert not any(r["changes"].values())
        sm.acknowledge({})
        assert sm.pending() == {"show": False}
    finally:
        autoupdate.STATE_PATH.unlink(missing_ok=True)


# ---------------------------------------------------------------- download, check, stage

def _release_zip(top="VEDA-0.2.0-test", launcher=None, extra=None) -> bytes:
    launcher = launcher or ("VEDA.app/Contents/Info.plist" if sys.platform == "darwin"
                            else "VEDA.exe" if sys.platform == "win32" else "VEDA")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo(f"{top}/{launcher}")
        info.external_attr = 0o755 << 16
        zf.writestr(info, b"new build")
        zf.writestr(f"{top}/_internal/lib.txt", b"x")
        zf.writestr(f"{top}/README.md", b"readme")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_verify_checks_size_digest_and_zip(tmp_path):
    data = _release_zip()
    p = tmp_path / "r.zip"
    p.write_bytes(data)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    autoupdate.verify(p, len(data), digest)
    with pytest.raises(ValueError, match="bytes"):
        autoupdate.verify(p, len(data) + 1, digest)
    with pytest.raises(ValueError, match="SHA-256"):
        autoupdate.verify(p, len(data), "sha256:" + "0" * 64)
    p.write_bytes(data[:-10])
    with pytest.raises(Exception):
        autoupdate.verify(p, None, None)


def test_extract_refuses_paths_outside_the_folder(tmp_path):
    if sys.platform == "darwin":
        pytest.skip("ditto unpacks on macOS")
    p = tmp_path / "evil.zip"
    p.write_bytes(_release_zip(extra={"../outside.txt": b"no"}))
    with pytest.raises(ValueError, match="outside"):
        autoupdate.extract(p, tmp_path / "x")
    assert not (tmp_path / "outside.txt").exists()


def test_pick_asset_for_this_platform():
    rel = {"assets": [{"name": "VEDA-0.2.0-linux-x86_64.zip"}, {"name": "VEDA-0.2.0-macos-arm64.zip"},
                      {"name": "VEDA-0.2.0-windows-x86_64.zip"}]}
    assert autoupdate.pick_asset(rel, "windows-x86_64")["name"] == "VEDA-0.2.0-windows-x86_64.zip"
    assert autoupdate.pick_asset(rel, "macos-arm64")["name"].endswith("macos-arm64.zip")
    assert autoupdate.pick_asset(rel, "linux-arm64") is None


def test_from_source_never_updates():
    assert autoupdate.BUILD.get("number") is None
    assert "source" in autoupdate.install_problem()
    assert autoupdate.due() is False
    assert autoupdate.check_and_stage(force=True)["result"] == "disabled"
    client = TestClient(create_app())
    assert client.post("/api/update/download").status_code == 409
    assert client.get("/api/update/status").json()["problem"]


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """A published build unpacked in tmp_path/VEDA-0.2.0-test (data folder elsewhere)."""
    root = tmp_path / "VEDA-0.2.0-test"
    if sys.platform == "darwin":
        (root / "VEDA.app" / "Contents").mkdir(parents=True)
    else:
        root.mkdir()
        (root / ("VEDA.exe" if sys.platform == "win32" else "VEDA")).write_bytes(b"old build")
    monkeypatch.setitem(autoupdate.BUILD, "number", 41)
    monkeypatch.setattr(autoupdate, "install_root", lambda: root)
    saved = SETTINGS.network_enabled, SETTINGS.auto_update
    SETTINGS.network_enabled, SETTINGS.auto_update = True, True
    yield root
    SETTINGS.network_enabled, SETTINGS.auto_update = saved
    autoupdate.STATE_PATH.unlink(missing_ok=True)


class _Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        for i in range(0, len(self.data), n):
            yield self.data[i:i + n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _release(data, tag="v0.2.0-build.42", digest=True):
    name = f"VEDA-0.2.0-{autoupdate.platform_tag()}.zip"
    return {"tag_name": tag, "name": "VEDA 0.2.0 build 42", "body": "### Changes\n- faster", "html_url": "https://x/r",
            "assets": [{"name": name, "size": len(data), "browser_download_url": "https://x/" + name,
                        **({"digest": "sha256:" + hashlib.sha256(data).hexdigest()} if digest else {})}]}


def test_weekly_check_downloads_verifies_and_stages(installed, monkeypatch):
    data = _release_zip()
    from veda.archives import net

    class Sess:
        def get(self, url, **k):
            return _Resp(data)
    monkeypatch.setattr(net, "session", lambda: Sess())
    assert autoupdate.due()                                          # never checked
    res = autoupdate.check_and_stage(release=_release(data))
    assert res["result"] == "staged"
    staged = installed.parent / f"{installed.name}.update"
    assert (staged / "README.md").read_bytes() == b"readme" and (staged / "_internal" / "lib.txt").exists()
    st = autoupdate.load_state()
    assert st["staged"]["build"] == 42 and st["staged"]["notes"].endswith("- faster")
    assert not autoupdate.due() and abs(st["last_check"] - time.time()) < 60
    assert list(autoupdate.UPDATES_DIR.glob("*.part")) == []
    # a week later it is due again; the same build is not downloaded twice
    st["last_check"] -= autoupdate.CHECK_EVERY_S + 1
    autoupdate.save_state(st)
    assert autoupdate.due()
    assert autoupdate.check_and_stage(release=_release(data))["result"] == "already staged"
    # nothing newer: nothing downloaded
    assert autoupdate.check_and_stage(force=True, release=_release(data, tag="v0.2.0-build.41"))["result"] == "latest"
    # a release whose files are not all uploaded yet: tried again at the next hourly look
    st = autoupdate.load_state()
    st["last_check"] -= autoupdate.CHECK_EVERY_S + 1
    autoupdate.save_state(st)
    partial = _release(data, tag="v0.2.0-build.43")
    partial["assets"] = []
    assert autoupdate.check_and_stage(release=partial)["result"] == "error" and autoupdate.due()
    # off: no check
    SETTINGS.auto_update = False
    assert not autoupdate.due()


def test_a_bad_download_is_not_staged(installed, monkeypatch):
    data = _release_zip()
    from veda.archives import net

    class Sess:
        def get(self, url, **k):
            return _Resp(data[:-100] + b"x" * 100)                      # damaged on the way
    monkeypatch.setattr(net, "session", lambda: Sess())
    with pytest.raises(ValueError, match="SHA-256"):
        autoupdate.check_and_stage(force=True, release=_release(data))
    assert "staged" not in autoupdate.load_state()
    assert not (installed.parent / f"{installed.name}.update").exists()
    assert list(autoupdate.UPDATES_DIR.glob("*.part")) == []


def test_data_folder_inside_the_installation_is_never_updated(installed, monkeypatch):
    monkeypatch.setattr(autoupdate, "DATA_ROOT", installed / "data")
    assert "data folder" in autoupdate.install_problem()


def test_install_on_start_hands_over_to_the_swap_script(installed, monkeypatch):
    staged = installed.parent / f"{installed.name}.update"
    staged.mkdir()
    if sys.platform == "darwin":
        (staged / "VEDA.app").mkdir()
    else:
        (staged / ("VEDA.exe" if sys.platform == "win32" else "VEDA")).write_bytes(b"new")
    autoupdate.save_state({"staged": {"tag": "v0.2.0-build.42", "build": 42, "path": str(staged), "notes": "n"}})
    started = []
    monkeypatch.setattr(autoupdate.subprocess, "Popen", lambda cmd, **kw: started.append((cmd, kw)))
    assert autoupdate.install_staged_on_start(["--no-window", "--port", "8899"]) is True
    cmd, kw = started[0]
    script = Path(cmd[-1]).read_text(encoding="utf-8-sig")
    assert str(os.getpid()) in script and str(installed) in script and str(staged) in script
    assert "--no-window" in script and "8899" in script
    # an older or equal build staged: nothing happens
    autoupdate.save_state({"staged": {"tag": "v0.2.0-build.41", "build": 41, "path": str(staged)}})
    assert autoupdate.install_staged_on_start([]) is False
    # the new build, started: it was installed; the previous one is removed
    autoupdate.save_state({"staged": {"tag": "v0.2.0-build.42", "build": 42, "path": str(staged), "notes": "n",
                                      "name": "VEDA 0.2.0 build 42"}})
    previous = installed.parent / f"{installed.name}.previous"
    previous.mkdir()
    monkeypatch.setitem(autoupdate.BUILD, "number", 42)
    autoupdate.finish_install()
    st = autoupdate.load_state()
    assert "staged" not in st and st["installed"]["build"] == 42 and not previous.exists()
    assert autoupdate.installed_notes(42)["notes"] == "n"


class _GitHub:
    """GitHub as the updater sees it after months offline: only the latest two releases
    (150 and 151) are listed, older ones are deleted (their tags may stay)."""

    def __init__(self, data, tags=("v0.2.0-build.151", "v0.2.0-build.150", "v0.2.0-build.144")):
        self.data, self.tags, self.urls = data, list(tags), []

    def get(self, url, **k):
        self.urls.append(url)
        if url.endswith("/releases/latest"):
            return _Json(_release(self.data, tag="v0.2.0-build.151"))
        if "/releases/download/" in url or url.startswith("https://x/"):
            return _Resp(self.data)
        if "/tags" in url:
            return _Json([{"name": t} for t in self.tags])
        return _Json({"message": "Not Found"}, status=404)


class _Json:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_copy_that_missed_releases_goes_straight_to_the_latest(installed, monkeypatch):
    """Installed build 144 (its release deleted from GitHub); GitHub lists only 150 and 151:
    151 is staged, from /releases/latest, without asking for anything about 144 or 150."""
    from veda.archives import net
    monkeypatch.setitem(autoupdate.BUILD, "number", 144)
    gh = _GitHub(_release_zip())
    monkeypatch.setattr(net, "session", lambda: gh)
    res = autoupdate.check_and_stage(force=True)
    assert res == {"result": "staged", "tag": "v0.2.0-build.151"}
    assert autoupdate.load_state()["staged"]["build"] == 151
    assert gh.urls[0].endswith("/releases/latest")
    assert not any("build.144" in u or "build.150" in u for u in gh.urls)


def test_the_installed_release_missing_from_github_breaks_nothing(installed, monkeypatch, fresh_settings):
    """Build 144's release is gone from GitHub: the update notice, the weekly check and the
    settings panel still work."""
    from veda import updates
    from veda.archives import net
    monkeypatch.setitem(autoupdate.BUILD, "number", 144)
    monkeypatch.setitem(updates.BUILD, "number", 144)
    gh = _GitHub(_release_zip(), tags=("v0.2.0-build.151", "v0.2.0-build.150"))   # tag 144 gone too
    monkeypatch.setattr(net, "session", lambda: gh)
    updates._cache.clear()
    try:
        r = updates.check(force=True)
        assert r["checked"] and r["newer"] and r["latest"]["tag"] == "v0.2.0-build.151"
    finally:
        updates._cache.clear()
    assert autoupdate.check_and_stage(force=True)["result"] == "staged"
    fresh_settings(config.Settings().to_dict())
    assert sm.pending() == {"show": False}


def test_how_many_releases_a_copy_skipped(monkeypatch):
    """The new release's notes list only the changes since the release before it: a copy
    that skipped releases is told how many and gets the comparison from its own tag
    (when that tag still exists) and the CHANGELOG."""
    monkeypatch.setitem(autoupdate.BUILD, "number", 144)
    tags = ["v0.2.0-build.151", "v0.2.0-build.150", "v0.2.0-build.147", "v0.2.0-build.144", "v0.2.0-build.143",
            "v0.1.0", "v0.0.1"]
    b = autoupdate.releases_behind("v0.2.0-build.151", tags)
    assert b["releases"] == 3 and b["from_build"] == 144 and b["to_build"] == 151
    assert b["compare_url"] == "https://github.com/jovian-explorer/VEDA/compare/v0.2.0-build.144...v0.2.0-build.151"
    assert b["changelog_url"].endswith("/blob/main/CHANGELOG.md")
    # directly after the release installed: one release, no extra line needed
    assert autoupdate.releases_behind("v0.2.0-build.147", tags)["releases"] == 1
    monkeypatch.setitem(autoupdate.BUILD, "number", 150)
    assert autoupdate.releases_behind("v0.2.0-build.151", tags)["releases"] == 1
    # a build whose tag was deleted by the old workflow (137 and older): no comparison link
    monkeypatch.setitem(autoupdate.BUILD, "number", 129)
    b = autoupdate.releases_behind("v0.2.0-build.151", tags)
    assert b["releases"] == 5 and b["compare_url"] is None and b["changelog_url"]
    # the tags cannot be read: unknown count, the CHANGELOG link only
    from veda.archives import net

    class Down:
        def get(self, *a, **k):
            raise OSError("offline")
    monkeypatch.setattr(net, "session", lambda: Down())
    b = autoupdate.releases_behind("v0.2.0-build.151")
    assert b["releases"] is None and b["compare_url"] is None and b["changelog_url"]
    monkeypatch.setitem(autoupdate.BUILD, "number", None)
    assert autoupdate.releases_behind("v0.2.0-build.151", tags) is None


def test_whats_new_tells_a_copy_that_skipped_releases(installed, monkeypatch, fresh_settings):
    """Build 144 updated to 151 (150 in between): the staged notes carry how far behind it
    was; after the swap the settings panel's What's new has it."""
    from veda.archives import net
    monkeypatch.setitem(autoupdate.BUILD, "number", 144)
    gh = _GitHub(_release_zip())
    monkeypatch.setattr(net, "session", lambda: gh)
    assert autoupdate.check_and_stage(force=True)["result"] == "staged"
    behind = autoupdate.load_state()["staged"]["behind"]
    assert behind["releases"] == 2 and "compare/v0.2.0-build.144...v0.2.0-build.151" in behind["compare_url"]
    fresh_settings(config.Settings().to_dict())
    sm.MARKER_PATH.write_text(json.dumps({"version": "0.2.0", "build": 144, "schema": sm.current_schema()}))
    monkeypatch.setitem(autoupdate.BUILD, "number", 151)              # the new build has started
    autoupdate.finish_install()
    r = sm.pending()
    assert r["show"] and r["whats_new"]["behind"]["releases"] == 2 and r["previous"]["build"] == 144
