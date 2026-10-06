"""What changed in the settings between the version that wrote settings.json and this one.

Another version (an update, or an older copy started again) may have options this one
lacks, lack options this one has, or allow other values.  Nothing stored is changed
when that happens: every stored value this version can use is used as it is, and the
others stay in settings.json (``Settings.preserved``).  Once per version and build the
user is shown what changed (with "What's new" after an update) and can accept or change
the values; the schema they saw is then kept in ``settings_seen.json`` beside
settings.json and the next comparison starts from it.

A first start (no settings.json yet) has nothing to compare and shows nothing.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from . import __version__
from . import config
from .config import DATA_ROOT, RENAMED_SETTINGS, SETTING_CHOICES, SETTINGS_PATH, Settings

MARKER_PATH = DATA_ROOT / "settings_seen.json"


def _rule_json(key: str, rule: Any, default: Any) -> Any:
    """A setting's allowed values in JSON: a list of choices, {"min", "max"} for a range,
    "known id" for registry ids."""
    if rule is None:
        return "known id"
    if isinstance(default, bool):
        return [False, True]
    if isinstance(default, int) and isinstance(rule, tuple) and len(rule) == 2:
        return {"min": rule[0], "max": rule[1]}
    return list(rule)


def current_schema() -> Dict[str, Dict[str, Any]]:
    defaults = Settings().to_dict()
    return {k: {"default": defaults.get(k), "rule": _rule_json(k, rule, defaults.get(k))}
            for k, rule in SETTING_CHOICES.items()}


def _valid(key: str, value: Any) -> bool:
    try:
        Settings.validate(key, value)
        return True
    except ValueError:
        return False


def compare(stored: Dict[str, Any], old_schema: Optional[Dict[str, Dict[str, Any]]],
            new_schema: Dict[str, Dict[str, Any]], renamed: Optional[Dict[str, str]] = None) -> Dict[str, List]:
    """The differences that concern the user.

    ``stored``: settings.json as written; ``old_schema``: the schema the user last saw
    (None: unknown, then the stored keys stand for it).  Returns
      new      options this version has and the old one had not: {key, default, rule}
      renamed  {old, key, stored, valid}
      removed  options of the old version this one has not: {key, stored}
      changed  options whose allowed values or default changed:
               {key, rule, old_rule, default, old_default, stored, valid}
      invalid  other stored values this version does not accept: {key, stored, rule, default}
    """
    renamed = renamed or {}
    old_keys = set(old_schema) if old_schema is not None else set(stored)
    out: Dict[str, List] = {"new": [], "renamed": [], "removed": [], "changed": [], "invalid": []}
    renamed_to = {new: old for old, new in renamed.items() if old in old_keys or old in stored}
    for key, spec in new_schema.items():
        if key in renamed_to:
            old = renamed_to[key]
            if old in stored:
                out["renamed"].append({"old": old, "key": key, "stored": stored[old],
                                       "valid": _valid(key, stored[old])})
            continue
        if key not in old_keys:
            out["new"].append({"key": key, "default": spec["default"], "rule": spec["rule"]})
            continue
        has = key in stored
        if old_schema is not None and key in old_schema and (
                old_schema[key].get("rule") != spec["rule"] or old_schema[key].get("default") != spec["default"]):
            out["changed"].append({"key": key, "rule": spec["rule"], "old_rule": old_schema[key].get("rule"),
                                   "default": spec["default"], "old_default": old_schema[key].get("default"),
                                   "stored": stored.get(key), "valid": has and _valid(key, stored[key])})
        elif has and not _valid(key, stored[key]):
            out["invalid"].append({"key": key, "stored": stored[key], "rule": spec["rule"], "default": spec["default"]})
    for key in sorted(old_keys | set(stored)):
        if key not in new_schema and key not in renamed:
            out["removed"].append({"key": key, "stored": stored.get(key)})
    return out


def _read_json(path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_marker() -> None:
    from .updates import BUILD
    tmp = MARKER_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": __version__, "build": BUILD.get("number"), "schema": current_schema()}, fh, indent=2)
    os.replace(tmp, MARKER_PATH)


def pending() -> Dict[str, Any]:
    """What to show the user once at this start: the settings changes since the schema
    they last saw and, after an update, the release notes of the new build.  When there
    is nothing to show, the marker is brought up to date at once."""
    from .updates import BUILD
    from . import autoupdate
    marker = _read_json(MARKER_PATH)
    build = BUILD.get("number")
    if marker is None and config.SETTINGS_CREATED:
        try:
            _write_marker()
        except OSError:
            pass
        return {"show": False}
    stored = _read_json(SETTINGS_PATH) or {}
    changes = compare(stored, (marker or {}).get("schema"), current_schema(), RENAMED_SETTINGS)
    seen_here = marker is not None and marker.get("version") == __version__ and marker.get("build") == build
    notes = None if seen_here else autoupdate.installed_notes(build)
    has_changes = any(changes.values())
    if not has_changes and not notes:
        try:
            _write_marker()
        except OSError:
            pass
        return {"show": False}
    return {"show": True, "version": __version__, "build": build,
            "previous": None if marker is None else {"version": marker.get("version"), "build": marker.get("build")},
            "whats_new": notes, "changes": changes, "settings": config.SETTINGS.to_dict()}


def acknowledge(patch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The user has seen the changes: apply their choices (all validated first), drop the
    stored entries this version cannot use, save, and remember the schema they saw.
    Raises ValueError for an invalid choice (nothing is changed then)."""
    settings = config.SETTINGS
    settings.update(dict(patch or {}))
    settings.preserved().clear()
    settings.save()
    _write_marker()
    return settings.to_dict()
