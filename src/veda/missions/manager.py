"""Central Mission & Body Manager for VEDA.

Coordinates discovery, profile retrieval, imaging extraction, and cross-mission
comparative analysis across all supported planetary spacecraft.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
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

    def compare_on_body(
        self,
        body_id: str,
        selected_observations: Optional[List[Dict[str, str]]] = None,
        mission_ids: Optional[List[str]] = None,
        variable_name: str = "temperature_k",
        selection: Optional["ProfileFilter"] = None,
    ) -> Dict[str, Any]:
        """Load multiple profiles across missions and compute cross-mission comparison.

        Hand-picked observations are used as given.  Otherwise, with ``selection``,
        profiles are chosen from the archive catalogue by date and geometry (see
        missions/selection.py); without it, from the profiles already downloaded.
        """
        from .selection import ProfileFilter, select_profiles
        body = get_body(body_id)
        if not body:
            return {"error": f"Unknown planetary body: {body_id}"}

        loaded_profiles: List[ObservationProfile] = []
        report: Optional[Dict[str, Any]] = None
        if not (selected_observations and len(selected_observations) > 0):
            sel = selection or ProfileFilter(per_mission=3, download=False)
            loaded_profiles, report = select_profiles(self, body_id, list(mission_ids or body.supported_missions),
                                                      variable_name, sel)
        if selected_observations and len(selected_observations) > 0:
            for item in selected_observations:
                m_id = item.get("mission_id")
                o_id = item.get("observation_id")
                if m_id and o_id:
                    prof = self.load_profile(m_id, o_id)
                    if prof:
                        loaded_profiles.append(prof)

        # Compute multi-mission composite
        out = compare_profiles_on_body(
            profiles=loaded_profiles,
            body=body,
            altitude_step_km=0.5 if body_id in ("mars", "pluto", "venus") else 2.0,
            variable_name=variable_name,
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
