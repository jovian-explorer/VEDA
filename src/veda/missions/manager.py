"""Central Mission & Body Manager for VEDA.

Coordinates discovery, profile retrieval, imaging extraction, and cross-mission
comparative analysis across all supported planetary spacecraft.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from ..core.base_adapter import BaseMissionAdapter
from ..core.models import ObservationImage, ObservationProfile, ProvenanceRecord
from ..core.registry import BODIES, MISSIONS, get_body, get_mission
from ..analysis.atmospheric import compare_profiles_on_body

from .akatsuki_adapter import AkatsukiAdapter
from .archive_adapter import ArchiveMissionAdapter
from .uploads_adapter import MISSION_ID as UPLOADS_MISSION_ID, UploadsAdapter


class MissionManager:
    """Singleton manager aggregating all mission adapters."""

    def __init__(self):
        self._adapters: Dict[str, BaseMissionAdapter] = {}
        self._uploads = UploadsAdapter()
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        # Every mission is served from the real archive catalogue; Akatsuki also
        # has a bundled UVI image, read by its original image loader.
        for mid in MISSIONS:
            images = AkatsukiAdapter() if mid == "akatsuki" else None
            self.register_adapter(ArchiveMissionAdapter(mid, image_provider=images))

    def register_adapter(self, adapter: BaseMissionAdapter) -> None:
        self._adapters[adapter.mission_id.lower()] = adapter

    def get_adapter(self, mission_id: str) -> Optional[BaseMissionAdapter]:
        # User uploads are served like a mission but are not listed as one.
        if mission_id.lower() == UPLOADS_MISSION_ID:
            return self._uploads
        return self._adapters.get(mission_id.lower())

    def list_missions(self) -> List[str]:
        return list(self._adapters.keys())

    def discover_by_mission(
        self,
        mission_id: str,
        body_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search observations available for a specific spacecraft mission."""
        adapter = self.get_adapter(mission_id)
        if not adapter:
            return []
        return adapter.discover_observations(body_id=body_id, instrument_id=instrument_id, limit=limit)

    def discover_by_body(
        self,
        body_id: str,
        mission_ids: Optional[List[str]] = None,
        limit_per_mission: int = 25,
    ) -> Dict[str, Any]:
        """Search observations across all missions for a specific target body."""
        body = get_body(body_id)
        if not body:
            return {"body_id": body_id, "observations": [], "missions": []}

        target_missions = mission_ids or body.supported_missions
        all_obs: List[Dict[str, Any]] = []
        missions_found: List[str] = []

        for mid in target_missions:
            adapter = self.get_adapter(mid)
            if adapter and (not body_id or body_id.lower() in [b.lower() for b in adapter.list_supported_bodies()]):
                obs = adapter.discover_observations(body_id=body_id, limit=limit_per_mission)
                if obs:
                    all_obs.extend(obs)
                    missions_found.append(mid)

        return {
            "body_id": body.id,
            "body_name": body.name,
            "category": body.category,
            "radius_km": body.radius_km,
            "surface_gravity": body.surface_gravity,
            "gas_constant_r": body.gas_constant_r,
            "reference_pressure_hpa": body.reference_pressure_hpa,
            "missions_queried": target_missions,
            "missions_with_data": list(set(missions_found)),
            "observations_count": len(all_obs),
            "observations": all_obs,
        }

    def load_profile(self, mission_id: str, observation_id: str) -> Optional[ObservationProfile]:
        adapter = self.get_adapter(mission_id)
        if not adapter:
            return None
        return adapter.load_profile(observation_id)

    def load_image(self, mission_id: str, observation_id: str) -> Optional[ObservationImage]:
        adapter = self.get_adapter(mission_id)
        if not adapter:
            return None
        return adapter.load_image(observation_id)

    def profiles_for_comparison(
        self,
        body_id: str,
        selected_observations: Optional[List[Dict[str, str]]] = None,
        mission_ids: Optional[List[str]] = None,
        variable_name: str = "temperature_k",
        selection: Optional["ProfileFilter"] = None,
    ) -> Tuple[List[ObservationProfile], Optional[Dict[str, Any]]]:
        """The profiles a comparison uses, and the selection report (None when hand-picked)."""
        from .selection import ProfileFilter, select_profiles
        body = get_body(body_id)
        if selected_observations:
            return self._load_hand_picked(selected_observations), None
        sel = selection or ProfileFilter(per_mission=3, download=False)
        return select_profiles(self, body_id, list(mission_ids or body.supported_missions), variable_name, sel)

    def _load_hand_picked(self, items: List[Dict[str, str]]) -> List[ObservationProfile]:
        """Hand-picked observations in their order.  Archive products are read together in
        the worker processes (Settings > Performance), like filtered comparisons; loaded
        files one by one.  A product that cannot be read is left out instead of failing
        the whole comparison."""
        from ..archives.profiles import load_profiles
        slots: List[Any] = [None] * len(items)
        archive: List[Tuple[int, Tuple[str, str]]] = []
        for i, item in enumerate(items):
            m_id, o_id = item.get("mission_id"), item.get("observation_id")
            if not (m_id and o_id):
                continue
            adapter = self.get_adapter(m_id)
            if isinstance(adapter, ArchiveMissionAdapter):
                key = adapter.profile_key(o_id)
                if key:
                    archive.append((i, key))
                continue
            try:
                slots[i] = self.load_profile(m_id, o_id)
            except Exception:  # noqa: BLE001 - one unreadable file must not stop the comparison
                slots[i] = None
        for (i, _), res in zip(archive, load_profiles([pair for _, pair in archive])):
            slots[i] = res if isinstance(res, ObservationProfile) else None
        return [p for p in slots if p is not None]

    def compare_on_body(
        self,
        body_id: str,
        selected_observations: Optional[List[Dict[str, str]]] = None,
        mission_ids: Optional[List[str]] = None,
        variable_name: str = "temperature_k",
        selection: Optional["ProfileFilter"] = None,
        group_by: str = "",
        group_width: float = 0.0,
    ) -> Dict[str, Any]:
        """Load multiple profiles across missions and compute cross-mission comparison.

        Hand-picked observations are used as given.  Otherwise, with ``selection``,
        profiles are chosen from the archive catalogue by date and geometry (see
        missions/selection.py); without it, from the profiles already downloaded.
        """
        body = get_body(body_id)
        if not body:
            return {"error": f"Unknown planetary body: {body_id}"}
        loaded_profiles, report = self.profiles_for_comparison(body_id, selected_observations, mission_ids,
                                                               variable_name, selection)

        # Compute multi-mission composite
        out = compare_profiles_on_body(
            profiles=loaded_profiles,
            body=body,
            altitude_step_km=0.5 if body_id in ("mars", "pluto", "venus") else 2.0,
            variable_name=variable_name,
            group_by=group_by,
            group_width=group_width,
        )
        if report is not None and isinstance(out, dict):
            out["selection"] = report
        return out


# Global singleton instance
_GLOBAL_MANAGER: Optional[MissionManager] = None

def get_mission_manager() -> MissionManager:
    global _GLOBAL_MANAGER
    if _GLOBAL_MANAGER is None:
        _GLOBAL_MANAGER = MissionManager()
    return _GLOBAL_MANAGER
