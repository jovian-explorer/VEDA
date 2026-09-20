"""Akatsuki (Venus Climate Orbiter) Mission Adapter for VEDA."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from ..core.base_adapter import BaseMissionAdapter
from ..core.models import ObservationImage, ObservationProfile, ProvenanceRecord
from ..readers.pds3_reader import read_pds3_table
from ..analysis.atmospheric import compute_atmospheric_diagnostics
from ..core.registry import get_body


class AkatsukiAdapter(BaseMissionAdapter):
    """Adapter for JAXA Akatsuki (VCO) Venus Radio Science and Imaging data."""

    def __init__(self, data_dir: Optional[str] = None):
        super().__init__("akatsuki")
        self.data_dir = data_dir or str(
            Path(__file__).resolve().parents[3] / "sampledata" / "veda" / "venus_akatsuki"
        )

    def list_supported_bodies(self) -> List[str]:
        return ["venus"]

    def list_supported_instruments(self) -> List[str]:
        return ["RS", "UVI", "LIR", "IR1", "IR2"]

    def discover_observations(
        self,
        body_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if body_id and body_id.lower() != "venus":
            return []

        results = []
        d = Path(self.data_dir)
        if d.is_dir():
            for f in sorted(d.glob("*.lbl")):
                name = f.stem
                is_rs = "rs_" in name.lower()
                is_img = "uvi_" in name.lower() or "lir_" in name.lower()
                results.append({
                    "observation_id": name,
                    "mission_id": "akatsuki",
                    "body_id": "venus",
                    "instrument": "RS" if is_rs else ("UVI" if "uvi_" in name.lower() else "LIR"),
                    "product": "Level 4 Atmospheric Profile" if "_l4_" in name else ("Calibrated FITS Image" if is_img else "Radio Occultation"),
                    "time_utc": "2016-03-03T23:20:05.791Z" if is_rs else "2018-11-05T08:01:12.000Z",
                    "latitude": 4.22 if is_rs else 0.0,
                    "longitude": 9.27 if is_rs else 0.0,
                    "archive_source": "JAXA DARTS / ISAS",
                    "is_cached": True,
                    "file_path": str(f),
                })
                if len(results) >= limit:
                    break
        return results

    def load_profile(self, observation_id: str) -> Optional[ObservationProfile]:
        if "uvi" in observation_id.lower() or "lir" in observation_id.lower():
            return None

        d = Path(self.data_dir)
        lbl_file = d / f"{observation_id}.lbl"
        if not lbl_file.exists():
            for f in d.glob(f"*{observation_id}*.lbl"):
                lbl_file = f
                break

        if not lbl_file.exists():
            return None

        try:
            tbl = read_pds3_table(str(lbl_file))
            meta = tbl.metadata

            # Extract Radius and convert to altitude: z = Radius - R_Venus (6051.8 km)
            radius_arr = tbl.series("RADIUS")
            if radius_arr is None or radius_arr.size == 0:
                radius_arr = tbl.series("GEOPOTENTIAL_HEIGHT")
                z_km = radius_arr if radius_arr is not None else np.array([])
            else:
                z_km = radius_arr - 6051.8

            # Extract Temperature
            t_k = tbl.series("TEMPERATURE")
            t_c = t_k - 273.15 if t_k is not None else None

            # Extract Pressure (PASCAL -> hPa)
            p_pa = tbl.series("PRESSURE")
            p_hpa = p_pa / 100.0 if p_pa is not None else None

            # Extract Refractivity
            ref = tbl.series("REFRACTIVITY")

            # Extract Latitude / Longitude
            lat_arr = tbl.series("LATITUDE")
            lon_arr = tbl.series("LONGITUDE")
            lat_val = float(np.nanmean(lat_arr)) if lat_arr is not None and np.isfinite(lat_arr).any() else None
            lon_val = float(np.nanmean(lon_arr)) if lon_arr is not None and np.isfinite(lon_arr).any() else None

            prof = ObservationProfile(
                observation_id=observation_id,
                mission_id="akatsuki",
                body_id="venus",
                instrument="RS",
                time_utc=meta.get("OBSERVATION_TIME") or meta.get("START_TIME") or "2016-03-03T23:20:05Z",
                latitude=lat_val,
                longitude=lon_val,
                altitude_km=z_km,
                pressure_hpa=p_hpa,
                temperature_k=t_k,
                temperature_c=t_c,
                refractivity=ref,
                provenance=ProvenanceRecord(
                    mission_id="akatsuki",
                    instrument="RS",
                    product_level="Level 4",
                    original_file=lbl_file.name,
                    archive_source="JAXA DARTS / NASA PDS",
                    archive_url="https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-rs-5-occ-v1.0/",
                    doi_or_citation="Imamura, T., et al. (2017). Initial performance of Akatsuki radio occultation. EPS, 69:137.",
                    retrieval_method="Abel Inversion + Hydrostatic Integration",
                ),
                raw_attributes=meta,
            )

            # Compute Venus-specific thermodynamic diagnostics
            venus_body = get_body("venus")
            prof.derived = compute_atmospheric_diagnostics(prof, venus_body)
            return prof

        except Exception as e:
            return None

    def load_image(self, observation_id: str) -> Optional[ObservationImage]:
        """Load JAXA Akatsuki camera observation (UVI, LIR, IR1, IR2)."""
        d = Path(self.data_dir)
        fits_file = d / f"{observation_id}.fit"
        if not fits_file.exists():
            fits_file = d / f"{observation_id}.fits"
        if not fits_file.exists():
            for f in d.glob(f"*{observation_id}*.fit*"):
                fits_file = f
                break

        if not fits_file.exists():
            return None

        from ..readers.fits_reader import load_fits_image
        try:
            f_data = load_fits_image(str(fits_file))
            hdr = f_data.header
            return ObservationImage(
                observation_id=observation_id,
                mission_id="akatsuki",
                body_id="venus",
                instrument="UVI" if "uvi" in observation_id.lower() else "LIR",
                time_utc=str(hdr.get("DATE-OBS") or hdr.get("DATE") or "2018-11-05T08:01:12Z"),
                target_name="VENUS",
                filter_name=str(hdr.get("FILTER") or "283 nm SO2 Absorption Band"),
                exposure_seconds=float(hdr.get("EXPTIME") or 0.05),
                target_distance_km=float(hdr.get("DISTANCE") or 350000.0),
                solar_phase_angle_deg=float(hdr.get("PHASE") or 45.0),
                browse_url="",
                fits_url=f"https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-uvi-3-sedr-v1.0/geometry/{fits_file.name}",
                local_path=str(fits_file),
                provenance=ProvenanceRecord(
                    mission_id="akatsuki",
                    instrument="UVI",
                    product_level="Level 3 Geometry Calibrated",
                    original_file=fits_file.name,
                    archive_source="JAXA DARTS / ISAS",
                    archive_url="https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-uvi-3-sedr-v1.0/",
                    doi_or_citation="Yamazaki, A., et al. (2018). Ultraviolet Imager on Akatsuki. Earth, Planets and Space, 70:23.",
                    retrieval_method="Radiance Calibration and Geometric Back-Projection",
                ),
                metadata=hdr,
            )
        except Exception:
            return None

    def get_provenance(self, observation_id: str) -> Optional[ProvenanceRecord]:
        return ProvenanceRecord(
            mission_id="akatsuki",
            instrument="RS",
            product_level="Level 4",
            original_file=observation_id,
            archive_source="JAXA DARTS",
            archive_url="https://data.darts.isas.jaxa.jp/pub/pds3/",
            doi_or_citation="JAXA Akatsuki Radio Science Team, VCO-V-RS-5-OCC-V1.0",
        )
