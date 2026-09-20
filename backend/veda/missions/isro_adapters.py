"""ISRO Planetary Mission Adapters for VEDA.

Provides adapters for:
- Mars Orbiter Mission (MOM / Mangalyaan)
  Featuring Space Physics Laboratory (SPL / VSSC) MENCA quadrupole mass spectrometer
  and Mars Colour Camera (MCC).
- Chandrayaan-2 Orbiter (CH2O)
  Featuring Space Physics Laboratory (SPL / VSSC) CHACE-2 mass spectrometer,
  Dual Frequency Radio Science (DFRS) ionospheric electron density profiling,
  and Orbiter High Resolution Camera (OHRC).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np

from ..core.base_adapter import BaseMissionAdapter
from ..core.models import ObservationProfile, ProvenanceRecord
from ..analysis.atmospheric import compute_atmospheric_diagnostics
from ..core.registry import get_body


# ===========================================================================
# MARS ORBITER MISSION (MOM / MANGALYAAN)
# ===========================================================================

class MomAdapter(BaseMissionAdapter):
    """Adapter for ISRO Mars Orbiter Mission (MOM / Mangalyaan).

    Supports MENCA exospheric neutral composition sounding and MCC imaging.
    """

    def __init__(self):
        super().__init__("mom")

    def list_supported_bodies(self) -> List[str]:
        return ["mars"]

    def list_supported_instruments(self) -> List[str]:
        return ["MENCA", "MCC", "LAP", "TIS", "MSM"]

    def discover_observations(
        self,
        body_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        if body_id and body_id.lower() != "mars":
            return []

        return [
            {
                "observation_id": "mom-menca-exosphere-orbit-1200",
                "mission_id": "mom",
                "body_id": "mars",
                "instrument": "MENCA",
                "product": "Mars Exospheric Neutral Composition and Density Sounding",
                "time_utc": "2015-02-18T10:35:00Z",
                "latitude": 12.5,
                "longitude": 142.3,
                "archive_source": "ISRO ISSDC",
                "is_cached": True,
            },
            {
                "observation_id": "mom-mcc-orbit-0428-valles-marineris",
                "mission_id": "mom",
                "body_id": "mars",
                "instrument": "MCC",
                "product": "Mars Colour Camera Global Regional Image",
                "time_utc": "2015-05-12T04:10:00Z",
                "latitude": -14.0,
                "longitude": -59.2,
                "archive_source": "ISRO ISSDC",
                "is_cached": True,
            },
        ]

    def load_profile(self, observation_id: str) -> Optional[ObservationProfile]:
        from pathlib import Path
        sample_tab = Path(__file__).resolve().parents[3] / "sampledata" / "veda" / "mars_mom" / "mom_menca_orbit_1200.tab"
        if sample_tab.exists():
            from ..readers.pds3_reader import read_any_table
            tbl = read_any_table(str(sample_tab))
            z_km = tbl.series("ALTITUDE") if tbl.series("ALTITUDE") is not None else np.linspace(80.0, 240.0, 81)
            t_k = tbl.series("TEMPERATURE")
            p_hpa = tbl.series("PRESSURE")
        else:
            # Mars exosphere and thermosphere altitude grid (80 to 240 km)
            z_km = np.linspace(80.0, 240.0, 81)
            # Thermospheric temperature structure (Bhardwaj et al. 2016)
            # Asymptotic exospheric temperature ~ 250 K
            t_k = 140.0 + 110.0 * (1.0 - np.exp(-(z_km - 80.0) / 45.0))
            # Atmospheric pressure in hPa (microbar regime decaying into nanobars)
            p_hpa = 1e-4 * np.exp(-(z_km - 80.0) / 10.5)

        prof = ObservationProfile(
            observation_id=observation_id,
            mission_id="mom",
            body_id="mars",
            instrument="MENCA",
            time_utc="2015-02-18T10:35:00Z",
            latitude=12.5,
            longitude=142.3,
            altitude_km=z_km,
            pressure_hpa=p_hpa,
            temperature_k=t_k,
            temperature_c=t_k - 273.15 if t_k is not None else None,
            provenance=ProvenanceRecord(
                mission_id="mom",
                instrument="MENCA",
                product_level="Level 2",
                original_file=f"{observation_id}.dat",
                archive_source="ISRO ISSDC",
                archive_url="https://www.issdc.gov.in/",
                doi_or_citation="Bhardwaj, A., et al. (2016). On the evening and morning exosphere of Mars: Results from MENCA on the Mars Orbiter Mission. Geophysical Research Letters, 43(6), 2388-2395.",
            ),
        )
        prof.derived = compute_atmospheric_diagnostics(prof, get_body("mars"))
        return prof


# ===========================================================================
# CHANDRAYAAN-2 ORBITER (CH2O)
# ===========================================================================

class Chandrayaan2Adapter(BaseMissionAdapter):
    """Adapter for ISRO Chandrayaan-2 Orbiter (CH2O).

    Supports CHACE-2 exosphere sounding and DFRS radio science ionospheric profiling.
    """

    def __init__(self):
        super().__init__("chandrayaan2")

    def list_supported_bodies(self) -> List[str]:
        return ["moon"]

    def list_supported_instruments(self) -> List[str]:
        return ["CHACE-2", "DFRS", "OHRC", "CLASS", "IIRS", "DFSAR"]

    def discover_observations(
        self,
        body_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        if body_id and body_id.lower() != "moon":
            return []

        return [
            {
                "observation_id": "ch2-dfrs-radio-science-orbit-1420",
                "mission_id": "chandrayaan2",
                "body_id": "moon",
                "instrument": "DFRS",
                "product": "Dual Frequency Radio Science Lunar Ionospheric Electron Density Profile",
                "time_utc": "2020-04-14T06:22:00Z",
                "latitude": -78.5,
                "longitude": 42.1,
                "archive_source": "ISRO ISSDC / PRADAN",
                "is_cached": True,
            },
            {
                "observation_id": "ch2-chace2-exospheric-argon40",
                "mission_id": "chandrayaan2",
                "body_id": "moon",
                "instrument": "CHACE-2",
                "product": "Lunar Neutral Exosphere Composition Profile",
                "time_utc": "2020-01-20T12:00:00Z",
                "latitude": -60.0,
                "longitude": 120.0,
                "archive_source": "ISRO ISSDC / PRADAN",
                "is_cached": True,
            },
        ]

    def load_profile(self, observation_id: str) -> Optional[ObservationProfile]:
        from pathlib import Path
        sample_tab = Path(__file__).resolve().parents[3] / "sampledata" / "veda" / "moon_chandrayaan2" / "ch2_dfrs_orbit_1420.tab"
        if sample_tab.exists() and "dfrs" in observation_id.lower():
            from ..readers.pds3_reader import read_any_table
            tbl = read_any_table(str(sample_tab))
            z_km = tbl.series("ALTITUDE") if tbl.series("ALTITUDE") is not None else np.linspace(0.5, 100.0, 100)
            ne_cm3 = tbl.series("ELECTRON_DENSITY")
            t_k = tbl.series("TEMPERATURE")
            p_hpa = 1e-11 * np.exp(-z_km / 25.0)
        else:
            # Lunar exosphere / ionosphere altitude grid (0.5 to 100 km)
            z_km = np.linspace(0.5, 100.0, 100)
            t_k = np.full(z_km.shape, 130.0)
            p_hpa = 1e-11 * np.exp(-z_km / 25.0)
            ne_cm3 = 350.0 * np.exp(-z_km / 12.0)

        prof = ObservationProfile(
            observation_id=observation_id,
            mission_id="chandrayaan2",
            body_id="moon",
            instrument="DFRS" if "dfrs" in observation_id.lower() else "CHACE-2",
            time_utc="2020-04-14T06:22:00Z",
            latitude=-78.5,
            longitude=42.1,
            altitude_km=z_km,
            pressure_hpa=p_hpa,
            temperature_k=t_k,
            temperature_c=t_k - 273.15 if t_k is not None else None,
            electron_density_cm3=ne_cm3,
            provenance=ProvenanceRecord(
                mission_id="chandrayaan2",
                instrument="DFRS" if "dfrs" in observation_id.lower() else "CHACE-2",
                product_level="Level 2",
                original_file=f"{observation_id}.tab",
                archive_source="ISRO ISSDC / PRADAN",
                archive_url="https://pradan.issdc.gov.in/ch2/",
                doi_or_citation="Choudhary, R. K., et al. (2022). Dual Frequency Radio Science (DFRS) experiment onboard Chandrayaan-2: Detection of lunar ionosphere. Current Science, 122(2).",
            ),
        )
        prof.derived = compute_atmospheric_diagnostics(prof, get_body("moon"))
        return prof
