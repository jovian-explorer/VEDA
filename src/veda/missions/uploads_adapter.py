"""Files the user loaded into VEDA (Load File / drag and drop).

Uploads are kept under ``<cache>/uploads`` so an ingested profile or image
can be re-opened, exported and rendered like any mission observation, and so
the UI can offer them as recent files.  Each upload gets its own folder
``<cache>/uploads/<filename>/`` holding the file, its companions (e.g. the
.tab of a PDS3 label) and ``meta.json`` recording the target body.  Separate
folders mean one upload can never pick up, overwrite or delete another
upload's companion files.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import CACHE_DIR
from ..core.base_adapter import BaseMissionAdapter
from ..core.models import ObservationImage, ObservationProfile, ProvenanceRecord
from ..core.registry import get_body

MISSION_ID = "user_imported"
UPLOAD_DIR = CACHE_DIR / "uploads"
MAX_RECENT = 25
_META = "meta.json"


def _entry_dirs() -> List[Path]:
    if not UPLOAD_DIR.is_dir():
        return []
    return [d for d in UPLOAD_DIR.iterdir() if d.is_dir() and not d.name.startswith(".staging-")
            and (d / _META).is_file()]


def stage_upload(name: str, payload: bytes, companions: Dict[str, bytes]) -> Path:
    """Write an upload (and its companion files) to a staging folder of its own and
    return the primary path, to be read before it replaces anything (commit_upload)
    or thrown away (discard_upload).  The primary file is written last, so a
    companion of the same name cannot replace it."""
    import uuid
    entry = UPLOAD_DIR / f".staging-{uuid.uuid4().hex}"
    entry.mkdir(parents=True, exist_ok=True)
    for cname, data in companions.items():
        if cname != name:
            (entry / cname).write_bytes(data)
    primary = entry / name
    primary.write_bytes(payload)
    return primary


def discard_upload(staged: Path) -> None:
    shutil.rmtree(staged.parent, ignore_errors=True)


def commit_upload(staged: Path, body_id: str, info: Optional[Dict[str, Any]] = None) -> Path:
    """Make a staged upload the upload of its file name and return the primary path.

    Re-uploading a file of the same name replaces the earlier upload entirely,
    so companions left over from it are not reused.
    """
    name = staged.name
    companions = sorted(p.name for p in staged.parent.iterdir() if p.name != name)
    # info: what the user said the file is (source mission and instrument, time,
    # column roles and units), so the profile is rebuilt the same way later
    meta = {"filename": name, "body_id": body_id, "companions": companions,
            "uploaded_at": time.time(), **(info or {})}
    (staged.parent / _META).write_text(json.dumps(meta), encoding="utf-8")
    entry = UPLOAD_DIR / name
    if entry.exists():
        shutil.rmtree(entry, ignore_errors=True)
    staged.parent.rename(entry)
    _prune()
    return entry / name


def save_upload(name: str, payload: bytes, companions: Dict[str, bytes], body_id: str,
                info: Optional[Dict[str, Any]] = None) -> Path:
    """Store an upload (and its companion files) and return the primary path."""
    return commit_upload(stage_upload(name, payload, companions), body_id, info)


def _read_meta(entry: Path) -> Optional[Dict[str, Any]]:
    try:
        meta = json.loads((entry / _META).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or not (entry / meta.get("filename", "")).is_file():
        return None
    return meta


def list_uploads() -> List[Dict[str, Any]]:
    """Recent uploads, newest first."""
    from ..pipeline.ingest import IMAGE_SUFFIXES
    items = []
    for entry in _entry_dirs():
        meta = _read_meta(entry)
        if not meta:
            continue
        p = entry / meta["filename"]
        items.append({
            "observation_id": p.stem,
            "filename": p.name,
            "mission_id": MISSION_ID,
            "source_mission": meta.get("source_mission") or "",
            "instrument": meta.get("instrument") or "",
            "time_utc": meta.get("time_utc") or "",
            "roles": meta.get("roles"),
            "body_id": meta.get("body_id", "venus"),
            "data_type": "image" if p.suffix.lower() in IMAGE_SUFFIXES else "profile",
            "size_bytes": p.stat().st_size,
            "uploaded_at": meta.get("uploaded_at", p.stat().st_mtime),
        })
    items.sort(key=lambda d: d["uploaded_at"], reverse=True)
    return items


def delete_upload(observation_id: str) -> bool:
    for entry in _entry_dirs():
        meta = _read_meta(entry)
        if meta and Path(meta["filename"]).stem == observation_id:
            shutil.rmtree(entry, ignore_errors=True)
            return True
    return False


def _prune() -> None:
    items = list_uploads()
    for old in items[MAX_RECENT:]:
        # by file name: another upload may share the id (obs.csv and obs.tab are both "obs")
        shutil.rmtree(UPLOAD_DIR / old["filename"], ignore_errors=True)


def find_upload(observation_id: str) -> Optional[tuple]:
    for item in list_uploads():
        if item["observation_id"] == observation_id:
            return UPLOAD_DIR / item["filename"] / item["filename"], item
    return None


def describe(item: Dict[str, Any]) -> str:
    """'MEX MaRS (your file)' from what the user said the file is."""
    from ..core.registry import get_mission
    mid = item.get("source_mission") or ""
    m = get_mission(mid) if mid else None
    who = (m.id.upper() if m else mid) if mid else ""
    inst = item.get("instrument") or ""
    text = " ".join(x for x in (who, inst) if x).strip()
    return f"{text} (your file)" if text else "Your file"


class UploadsAdapter(BaseMissionAdapter):
    """Serves user uploads through the regular profile/image/export endpoints."""

    def __init__(self):
        super().__init__(MISSION_ID)

    def list_supported_bodies(self) -> List[str]:
        return []

    def list_supported_instruments(self) -> List[str]:
        return []

    def discover_observations(self, body_id=None, instrument_id=None, start_time=None,
                              end_time=None, limit: int = 100) -> List[Dict[str, Any]]:
        items = [i for i in list_uploads() if not body_id or i["body_id"] == body_id]
        return items[:limit]

    def load_profile(self, observation_id: str) -> Optional[ObservationProfile]:
        from ..pipeline.ingest import IMAGE_SUFFIXES, build_profile
        hit = find_upload(observation_id)
        if not hit or hit[0].suffix.lower() in IMAGE_SUFFIXES:
            return None
        path, item = hit
        body = get_body(item["body_id"]) or get_body("venus")
        try:
            prof, _ = build_profile(path, body, mission_id=MISSION_ID, instrument=describe(item),
                                    roles=item.get("roles"), time_utc=item.get("time_utc") or None)
        except Exception:  # noqa: BLE001
            return None
        prof.raw_attributes["SOURCE_MISSION"] = item.get("source_mission") or ""
        return prof

    def load_image(self, observation_id: str) -> Optional[ObservationImage]:
        from ..pipeline.ingest import IMAGE_SUFFIXES
        from ..readers.fits_reader import load_fits_image
        hit = find_upload(observation_id)
        if not hit or hit[0].suffix.lower() not in IMAGE_SUFFIXES:
            return None
        path, item = hit
        try:
            hdr = load_fits_image(str(path)).header
        except Exception:  # noqa: BLE001
            return None

        def _num(key):
            try:
                return float(hdr.get(key)) if hdr.get(key) is not None else None
            except (TypeError, ValueError):
                return None

        return ObservationImage(
            observation_id=observation_id,
            mission_id=MISSION_ID,
            body_id=item["body_id"],
            instrument=str(hdr.get("INSTRUME") or "Camera"),
            # the time typed when loading, else DATE-OBS (FITS DATE is when the file was written)
            time_utc=item.get("time_utc") or str(hdr.get("DATE-OBS") or ""),
            target_name=str(hdr.get("OBJECT") or item["body_id"]).upper(),
            filter_name=str(hdr.get("FILTER") or ""),
            exposure_seconds=_num("EXPTIME") if _num("EXPTIME") is not None else _num("EXPOSURE"),
            target_distance_km=_num("DISTANCE"),
            solar_phase_angle_deg=_num("PHASE"),
            local_path=str(path),
            provenance=ProvenanceRecord(
                mission_id=MISSION_ID, instrument=str(hdr.get("INSTRUME") or "Camera"),
                product_level="User supplied", original_file=path.name,
                archive_source="Local file", archive_url="",
                doi_or_citation="", retrieval_method="Loaded from disk"),
            metadata=hdr,
        )
