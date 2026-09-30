"""Universal file ingestion: FITS/camera images and tabular soundings (PDS3, CSV, ASCII)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..analysis.atmospheric import compute_atmospheric_diagnostics
from ..core.models import ObservationProfile, ProvenanceRecord
from ..core.registry import get_body
from ..readers.fits_reader import load_fits_image
from ..readers.pds3_reader import Pds3Table, read_any_table


IMAGE_SUFFIXES = (".fit", ".fits", ".fts", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


def ingest_planetary_file(
    file_path: Path,
    body_id: str = "venus",
    mission_id: Optional[str] = None,
    instrument: Optional[str] = None,
    decimate_max: int = 0,
) -> Dict[str, Any]:
    """Ingest and parse any planetary science file (FITS image, PDS3, CSV, or ASCII table)."""
    b = get_body(body_id) or get_body("venus")
    suffix = file_path.suffix.lower()

    # 1. Astronomical Camera Image or FITS File
    if suffix in IMAGE_SUFFIXES:
        fits_data = load_fits_image(str(file_path))
        return {
            "type": "image",
            "filename": file_path.name,
            "observation_id": file_path.stem,
            "body_id": b.id,
            "mission_id": mission_id or "user_imported",
            "instrument": instrument or (str(fits_data.header.get("INSTRUME", "Camera")) if suffix in (".fit", ".fits", ".fts") else "Camera"),
            "time_utc": str(fits_data.header.get("DATE-OBS") or fits_data.header.get("DATE") or "2026-01-01T00:00:00Z"),
            "shape": [fits_data.stats.get("shape_y", 0), fits_data.stats.get("shape_x", 0)],
            "stats": fits_data.stats,
            "header": fits_data.header,
            "local_path": str(file_path),
        }

    prof, tbl = build_profile(file_path, b, mission_id=mission_id, instrument=instrument)
    return {
        "type": "profile",
        "filename": file_path.name,
        "observation_id": file_path.stem,
        "body_id": b.id,
        "mission_id": mission_id or "user_imported",
        "instrument": prof.instrument,
        "columns_detected": list(tbl.columns.keys()),
        "data": prof.to_dict(decimate_max=decimate_max),
    }


def build_profile(file_path: Path, b, mission_id: Optional[str] = None,
                  instrument: Optional[str] = None) -> Tuple[ObservationProfile, Pds3Table]:
    """Parse a tabular sounding into an ObservationProfile with derived diagnostics."""
    tbl = read_any_table(str(file_path))
    if not tbl.columns:
        raise ValueError(f"No numeric columns could be extracted from {file_path.name}")

    cols_upper = {k.upper(): k for k in tbl.columns.keys()}

    def find_col(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in cols_upper:
                return cols_upper[c]
            for k in cols_upper:
                if c in k:
                    return cols_upper[k]
        return None

    alt_col = find_col(["ALTITUDE", "ALT", "HEIGHT", "GEOPOTENTIAL_HEIGHT", "Z", "RADIUS", "RAD"])
    temp_col = find_col(["TEMPERATURE", "TEMP", "T_K", "TK", "TC", "T"])
    pres_col = find_col(["PRESSURE", "PRESS", "P_HPA", "P_PA", "P_BAR", "P"])
    edens_col = find_col(["ELECTRON_DENSITY", "NE", "EDENS", "ELECTRON_NUMBER_DENSITY"])
    ref_col = find_col(["REFRACTIVITY", "REF", "N_UNITS"])

    # Altitude mapping.  A vertical profile needs a real altitude axis, so a
    # table without one is rejected rather than plotted against row numbers.
    z_arr = tbl.series(alt_col) if alt_col else None
    if z_arr is None or z_arr.size == 0 or not np.isfinite(z_arr).any():
        found = ", ".join(tbl.columns.keys()) or "none"
        hint = (" If this is a PDS3 .tab file, select it together with its .lbl label."
                if all(k.startswith("COL_") for k in tbl.columns) else "")
        raise ValueError(
            "No altitude column found (looked for ALTITUDE, ALT, HEIGHT, Z or RADIUS; "
            f"columns in the file: {found}).{hint}")
    if ("RADIUS" in alt_col.upper() or "RAD" in alt_col.upper()) and np.nanmean(z_arr) > 400.0:
        z_arr = z_arr - b.radius_km

    # Temperature mapping
    t_k = None
    t_c = None
    if temp_col:
        t_raw = tbl.series(temp_col)
        if t_raw is not None and t_raw.size > 0:
            unit = tbl.units.get(temp_col, "").upper()
            if unit == "C" or (np.nanmedian(t_raw) < 120.0 and b.id in ("venus", "earth", "jupiter")):
                t_k = t_raw + 273.15
                t_c = t_raw
            else:
                t_k = t_raw
                t_c = t_raw - 273.15

    # Pressure mapping
    p_hpa = None
    if pres_col:
        p_raw = tbl.series(pres_col)
        if p_raw is not None and p_raw.size > 0:
            unit = tbl.units.get(pres_col, "").upper()
            if "PA" in unit or np.nanmean(p_raw) > 20000.0:
                p_hpa = p_raw / 100.0
            elif "BAR" in unit and "HPA" not in unit:
                p_hpa = p_raw * 1000.0
            else:
                p_hpa = p_raw

    ne_cm3 = tbl.series(edens_col) if edens_col else None
    ref_arr = tbl.series(ref_col) if ref_col else None

    prof = ObservationProfile(
        observation_id=file_path.stem,
        mission_id=mission_id or "user_imported",
        body_id=b.id,
        instrument=instrument or "User Ingested Sounder",
        time_utc="2026-01-01T12:00:00Z",
        altitude_km=z_arr,
        pressure_hpa=p_hpa,
        temperature_k=t_k,
        temperature_c=t_c,
        refractivity=ref_arr,
        electron_density_cm3=ne_cm3,
        provenance=ProvenanceRecord(
            mission_id=mission_id or "user_imported",
            instrument=instrument or "User Ingested Sounder",
            product_level="User Processed",
            original_file=file_path.name,
            archive_source="Local File System",
            archive_url="",
            doi_or_citation="User Ingested Observation Granule",
            retrieval_method="Automated Ingestion Pipeline",
        ),
        raw_attributes=tbl.metadata,
    )

    prof.derived = compute_atmospheric_diagnostics(prof, b)
    return prof, tbl
