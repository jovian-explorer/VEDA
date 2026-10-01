"""Mission adapter backed by the real archive catalogue.

Observations are archive products: the bundled samples plus anything the user
has downloaded. Times, targets and product types come from the archive's own
index; positions and profiles come from the product files. Nothing here is
generated.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..archives import catalog
from ..archives.datasets import datasets_for
from ..core.base_adapter import BaseMissionAdapter
from ..core.models import ObservationImage, ObservationProfile, ProvenanceRecord
from ..core.registry import get_mission


class ArchiveMissionAdapter(BaseMissionAdapter):
    def __init__(self, mission_id: str, image_provider: Optional[BaseMissionAdapter] = None):
        super().__init__(mission_id)
        self._images = image_provider

    # -- registry information ------------------------------------------------
    def list_supported_bodies(self) -> List[str]:
        m = get_mission(self.mission_id)
        return list(m.primary_targets) if m else []

    def list_supported_instruments(self) -> List[str]:
        return sorted({d.instrument for d in datasets_for(self.mission_id)})

    # -- observations ----------------------------------------------------------
    def discover_observations(self, body_id=None, instrument_id=None, start_time=None,
                              end_time=None, limit: int = 100) -> List[Dict[str, Any]]:
        if body_id and body_id.lower() not in self.list_supported_bodies():
            return []
        ds_ids = [d.id for d in datasets_for(self.mission_id)
                  if not instrument_id or d.instrument.lower().startswith(instrument_id.lower())]
        out: List[Dict[str, Any]] = []
        for p in catalog.downloaded_products(ds_ids):
            if p["kind"] != "profile":
                continue
            if start_time and p["start_time"] and p["start_time"] < start_time:
                continue
            if end_time and p["start_time"] and p["start_time"] > end_time:
                continue
            out.append({
                "observation_id": p["product_id"],
                "dataset_id": p["dataset_id"],
                "mission_id": self.mission_id,
                "body_id": (p["target"] or "").lower() or (self.list_supported_bodies() or [""])[0],
                "instrument": p["instrument"],
                "product": p["product_type"],
                "data_type": "profile",
                "time_utc": p["start_time"],
                "orbit": p["orbit"],
                "archive_source": p["url"],
                "is_cached": True,
            })
        if self._images is not None:
            for img in self._images.discover_observations(body_id=body_id):
                if img.get("data_type") == "image" or "uvi" in img.get("observation_id", "").lower():
                    out.append(self._image_entry(img))
        out.sort(key=lambda o: o.get("time_utc") or "", reverse=True)
        return out[:limit]

    def _image_entry(self, img: Dict[str, Any]) -> Dict[str, Any]:
        # Image time from the file name (uvi_YYYYMMDD_HHMMSS_...); no invented position.
        oid = img["observation_id"]
        m = re.search(r"_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", oid)
        t = f"{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}" if m else ""
        return {"observation_id": oid, "mission_id": self.mission_id, "body_id": img.get("body_id"),
                "instrument": img.get("instrument"), "product": img.get("product"), "data_type": "image",
                "time_utc": t, "archive_source": img.get("archive_source"), "is_cached": True}

    def _find(self, observation_id: str) -> Optional[Dict[str, Any]]:
        for ds in datasets_for(self.mission_id):
            p = catalog.get_product(ds.id, observation_id)
            if p:
                return p
        return None

    def load_profile(self, observation_id: str) -> Optional[ObservationProfile]:
        from ..archives.profiles import load_profile
        p = self._find(observation_id)
        if not p or p["kind"] != "profile":
            return None
        return load_profile(p["dataset_id"], p["product_id"])

    def load_image(self, observation_id: str) -> Optional[ObservationImage]:
        return self._images.load_image(observation_id) if self._images else None

    def get_provenance(self, observation_id: str) -> Optional[ProvenanceRecord]:
        prof = self.load_profile(observation_id)
        return prof.provenance if prof else None
