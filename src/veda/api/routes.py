"""FastAPI route definitions for VEDA multi-mission scientific platform."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..core.registry import (
    BODIES, MISSIONS, FIELD_REGISTRY, DATA_PORTALS, DATA_LICENSES, LEAD_RESEARCHER,
    DATA_AVAILABILITY_STATEMENT, get_body, get_mission, list_bodies, list_missions,
    get_missions_for_body, list_variables, get_variable_info, list_data_portals,
)
from ..core.models import ObservationProfile, ProvenanceRecord
from ..missions.manager import get_mission_manager
from ..analysis.atmospheric import (
    compute_atmospheric_diagnostics,
    export_profile_to_csv,
    export_comparison_to_csv,
)
from ..readers.fits_reader import (
    compute_image_histogram,
    extract_photometric_transect,
    load_fits_image,
    render_to_png,
)
from ..readers.pds3_reader import read_any_table, read_pds3_table

router = APIRouter(prefix="/api/veda", tags=["VEDA Multi-Mission"])


# ---------------------------------------------------------------------------
# Platform & Metadata Endpoints
# ---------------------------------------------------------------------------

@router.get("/info")
def platform_info() -> dict:
    """Platform overview, version, and supported assets."""
    mgr = get_mission_manager()
    return {
        "title": "VEDA: Visualization, Exploration, and Data Analysis",
        "version": "2.0.0",
        "description": "Multi-Mission Planetary Science Visualization & Comparative Analysis Platform",
        "lead_researcher": LEAD_RESEARCHER,
        "data_availability": DATA_AVAILABILITY_STATEMENT,
        "agencies_supported": ["NASA", "ESA", "JAXA", "ISRO", "NOAA"],
        "missions_count": len(mgr.list_missions()),
        "bodies_count": len(BODIES),
        "missions": mgr.list_missions(),
        "bodies": list(BODIES.keys()),
        "variables": list_variables(),
        "data_portals": list_data_portals(),
        "licenses": DATA_LICENSES,
    }


@router.get("/variables")
def get_variables_catalog() -> List[dict]:
    """List all registered planetary variables with formulas, DOIs, and citations."""
    return list_variables()


@router.get("/variables/{var_id}")
def get_variable(var_id: str) -> dict:
    """Get metadata for a specific scientific variable."""
    v = get_variable_info(var_id)
    if not v:
        raise HTTPException(status_code=404, detail=f"Variable '{var_id}' not found")
    return v


@router.get("/data-availability")
def get_data_availability() -> dict:
    """Planetary data availability statement and archive endpoints."""
    return {
        "lead_researcher": LEAD_RESEARCHER,
        "statement": DATA_AVAILABILITY_STATEMENT,
        "portals": list_data_portals(),
        "licenses": DATA_LICENSES,
    }


@router.get("/licenses")
def get_licenses() -> dict:
    """Open source and data license declarations."""
    return {
        "lead_researcher": LEAD_RESEARCHER,
        "licenses": DATA_LICENSES,
    }


@router.get("/portals")
def get_portals() -> List[dict]:
    """List authoritative planetary science data portals."""
    return list_data_portals()


@router.get("/missions")
def get_missions() -> List[dict]:
    """List all supported spacecraft missions."""
    return list_missions()


@router.get("/missions/{mission_id}")
def get_mission_details(mission_id: str) -> dict:
    """Get metadata and instrument payloads for a specific mission."""
    m = get_mission(mission_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
    return {
        "id": m.id,
        "name": m.name,
        "agency": m.agency,
        "launch_date": m.launch_date,
        "mission_status": m.mission_status,
        "primary_targets": m.primary_targets,
        "authoritative_archive": m.authoritative_archive,
        "archive_url": m.archive_url,
        "mission_page_url": m.mission_page_url or m.archive_url,
        "data_page_url": m.data_page_url or m.archive_url,
        "citation": m.citation,
        "description": m.description,
        "instruments": [
            {
                "id": i.id,
                "name": i.name,
                "type": i.instrument_type,
                "targets": i.measurement_targets,
                "description": i.description,
            }
            for i in m.instruments
        ],
    }


@router.get("/bodies")
def get_planetary_bodies() -> List[dict]:
    """List all supported target bodies with physical constants."""
    return list_bodies()


@router.get("/bodies/{body_id}")
def get_body_details(body_id: str) -> dict:
    """Get detailed planetary constants and missions that observed this body."""
    b = get_body(body_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Body '{body_id}' not found")
    missions = get_missions_for_body(body_id)
    return {
        "id": b.id,
        "name": b.name,
        "category": b.category,
        "radius_km": b.radius_km,
        "surface_gravity": b.surface_gravity,
        "mean_molecular_weight": b.mean_molecular_weight,
        "gas_constant_r": b.gas_constant_r,
        "reference_pressure_hpa": b.reference_pressure_hpa,
        "atmospheric_composition": b.atmospheric_composition,
        "description": b.description,
        "supported_missions": b.supported_missions,
        "mission_page_url": b.mission_page_url,
        "data_page_url": b.data_page_url,
        "missions": missions,
    }


# ---------------------------------------------------------------------------
# MODE 1: BY MISSION
# ---------------------------------------------------------------------------

@router.get("/explore/mission/{mission_id}")
def explore_by_mission(
    mission_id: str,
    body_id: Optional[str] = None,
    instrument_id: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Retrieve observations available for a selected spacecraft mission."""
    mgr = get_mission_manager()
    m = get_mission(mission_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")

    obs = mgr.discover_by_mission(mission_id, body_id=body_id, instrument_id=instrument_id, limit=limit)
    return {
        "mission_id": m.id,
        "mission_name": m.name,
        "agency": m.agency,
        "archive": m.authoritative_archive,
        "archive_url": m.archive_url,
        "total_found": len(obs),
        "observations": obs,
    }


# ---------------------------------------------------------------------------
# MODE 2: BY PLANET / TARGET BODY
# ---------------------------------------------------------------------------

@router.get("/explore/body/{body_id}")
def explore_by_body(
    body_id: str,
    missions: Optional[str] = None,  # comma-separated mission IDs e.g. "akatsuki,vex"
    limit_per_mission: int = 25,
) -> dict:
    """Retrieve multi-mission observations for a selected target body."""
    mgr = get_mission_manager()
    b = get_body(body_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Body '{body_id}' not found")

    mission_list = [m.strip() for m in missions.split(",")] if missions else None
    return mgr.discover_by_body(body_id, mission_ids=mission_list, limit_per_mission=limit_per_mission)


class CrossCompareRequest(BaseModel):
    observations: Optional[List[Dict[str, str]]] = None  # list of {"mission_id": ..., "observation_id": ...}
    missions: Optional[List[str]] = None  # e.g. ["akatsuki", "vex"]
    variable: str = "temperature_k"  # "temperature_k", "temperature_c", "pressure_hpa", "lapse_rate", "buoyancy_freq_sq"


@router.post("/compare/body/{body_id}")
def compare_missions_on_body(
    body_id: str,
    req: CrossCompareRequest,
) -> dict:
    """Multi-mission comparative vertical profile overlay and composite calculation."""
    mgr = get_mission_manager()
    return mgr.compare_on_body(body_id, req.observations, mission_ids=req.missions, variable_name=req.variable)


# ---------------------------------------------------------------------------
# Observation Data Retrieval (Profiles & Images)
# ---------------------------------------------------------------------------

@router.get("/profile/{mission_id}/{observation_id:path}")
def get_observation_profile(
    mission_id: str,
    observation_id: str,
    decimate_max: int = 600,
) -> dict:
    """Load normalized 1D profile with body-specific derived thermodynamics."""
    mgr = get_mission_manager()
    prof = mgr.load_profile(mission_id, observation_id)
    if not prof:
        raise HTTPException(status_code=404, detail=f"Profile '{observation_id}' for mission '{mission_id}' not found")
    return prof.to_dict(decimate_max=decimate_max)


@router.get("/image/{mission_id}/{observation_id:path}")
def get_image_metadata(
    mission_id: str,
    observation_id: str,
) -> dict:
    """Get metadata for an astronomical camera observation."""
    mgr = get_mission_manager()
    img = mgr.load_image(mission_id, observation_id)
    if not img:
        raise HTTPException(status_code=404, detail=f"Image observation '{observation_id}' not found")
    return img.to_dict()


@router.get("/image/{mission_id}/{observation_id:path}/render")
def render_image(
    mission_id: str,
    observation_id: str,
    stretch: str = "zscale",  # "zscale", "percentile", "linear", "log", "sqrt", "asinh", "histeq"
    colormap: str = "inferno",  # "gray", "inferno", "viridis", "plasma", "magma", "cividis", "twilight"
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    max_dim: int = 1024,
) -> Response:
    """Render astronomical science image array to stretched PNG."""
    mgr = get_mission_manager()
    img = mgr.load_image(mission_id, observation_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image observation not found")

    # If local FITS file exists, render with requested astronomical stretch
    if img.local_path and (img.local_path.endswith(".fit") or img.local_path.endswith(".fits")):
        try:
            fits_data = load_fits_image(img.local_path)
            png_bytes = render_to_png(fits_data.primary_data, stretch_method=stretch,
                                      colormap=colormap, vmin=vmin, vmax=vmax, max_dimension=max_dim)
            return Response(content=png_bytes, media_type="image/png")
        except Exception as e:
            pass

    # If browse image is available locally, serve it
    if img.local_path and (img.local_path.endswith(".jpg") or img.local_path.endswith(".png")):
        with open(img.local_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg" if img.local_path.endswith(".jpg") else "image/png")

    raise HTTPException(status_code=404, detail="Image data unavailable")


class TransectRequest(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    num_samples: int = 200


@router.post("/image/{mission_id}/{observation_id:path}/transect")
def get_image_transect(
    mission_id: str,
    observation_id: str,
    req: TransectRequest,
) -> dict:
    """Compute 1D photometric line slice along (x0, y0) -> (x1, y1)."""
    mgr = get_mission_manager()
    img = mgr.load_image(mission_id, observation_id)
    if not img or not img.local_path:
        raise HTTPException(status_code=404, detail="Image not found for transect")

    try:
        fits_data = load_fits_image(img.local_path)
        return extract_photometric_transect(fits_data.primary_data, req.x0, req.y0, req.x1, req.y1, req.num_samples)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transect computation failed: {e}")


@router.get("/image/{mission_id}/{observation_id:path}/histogram")
def get_image_histogram_endpoint(
    mission_id: str,
    observation_id: str,
    bins: int = 100,
) -> dict:
    """Compute pixel intensity histogram and CDF."""
    mgr = get_mission_manager()
    img = mgr.load_image(mission_id, observation_id)
    if not img or not img.local_path:
        raise HTTPException(status_code=404, detail="Image not found for histogram")

    try:
        fits_data = load_fits_image(img.local_path)
        return compute_image_histogram(fits_data.primary_data, num_bins=bins)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Histogram computation failed: {e}")


# ---------------------------------------------------------------------------
# Data Export Endpoints
# ---------------------------------------------------------------------------

@router.get("/export/profile/{mission_id}/{observation_id:path}/csv")
def export_profile_csv(mission_id: str, observation_id: str):
    """Download vertical profile observation as RFC 4180 CSV with metadata header."""
    mgr = get_mission_manager()
    prof = mgr.load_profile(mission_id, observation_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    csv_text = export_profile_to_csv(prof)
    filename = f"{mission_id}_{observation_id.replace('/', '_')}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/export/profile/{mission_id}/{observation_id:path}/json")
def export_profile_json(mission_id: str, observation_id: str):
    """Download vertical profile observation as structured JSON with full provenance."""
    import json
    mgr = get_mission_manager()
    prof = mgr.load_profile(mission_id, observation_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    filename = f"{mission_id}_{observation_id.replace('/', '_')}.json"
    return Response(
        content=json.dumps(prof.to_dict(decimate_max=0), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/export/compare/{body_id}/csv")
def export_compare_csv(body_id: str, req: CrossCompareRequest):
    """Download cross-mission comparative analysis data as CSV."""
    mgr = get_mission_manager()
    comp = mgr.compare_on_body(body_id, req.observations, mission_ids=req.missions, variable_name=req.variable)
    csv_text = export_comparison_to_csv(comp)
    filename = f"veda_comparison_{body_id}_{req.variable}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ---------------------------------------------------------------------------
# Live Archive Discovery & Pipeline Endpoints
# ---------------------------------------------------------------------------

@router.get("/archive/discover")
def discover_remote_products(
    mission_id: str,
    body_id: Optional[str] = None,
    instrument_id: Optional[str] = None,
) -> dict:
    """Discover authentic remote archive products (NASA PDS, ESA PSA, JAXA DARTS)."""
    from ..pipeline.archive_downloader import get_archive_pipeline
    pipe = get_archive_pipeline()
    products = pipe.query_remote_archive(mission_id, body_id=body_id, instrument_id=instrument_id)
    return {
        "mission_id": mission_id,
        "body_id": body_id,
        "total_available": len(products),
        "products": products,
    }


class DownloadProductRequest(BaseModel):
    task_id: str
    mission_id: str
    body_id: str
    instrument: str
    remote_url: str
    filename: str


@router.post("/archive/download")
def start_archive_download(req: DownloadProductRequest) -> dict:
    """Trigger background or direct download of remote mission observation."""
    import threading
    from ..pipeline.archive_downloader import get_archive_pipeline
    pipe = get_archive_pipeline()

    # Run download
    task = pipe.download_product(
        task_id=req.task_id,
        remote_url=req.remote_url,
        mission_id=req.mission_id,
        body_id=req.body_id,
        instrument=req.instrument,
        filename=req.filename,
    )
    return {
        "task_id": task.task_id,
        "status": task.status,
        "downloaded_bytes": task.downloaded_bytes,
        "total_bytes": task.total_bytes,
        "progress_pct": task.progress_pct,
        "local_path": task.local_path,
        "error": task.error_message,
    }


@router.get("/archive/tasks/{task_id}")
def get_download_task_status(task_id: str) -> dict:
    """Poll progress of a specific archive download task."""
    from ..pipeline.archive_downloader import get_archive_pipeline
    pipe = get_archive_pipeline()
    task = pipe.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Download task not found")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "downloaded_bytes": task.downloaded_bytes,
        "total_bytes": task.total_bytes,
        "progress_pct": task.progress_pct,
        "local_path": task.local_path,
        "error": task.error_message,
    }


@router.get("/archive/local")
def list_local_cached_products(
    mission_id: Optional[str] = None,
    body_id: Optional[str] = None,
) -> List[dict]:
    """List all indexed local granules in the VEDA archive repository."""
    from ..pipeline.archive_downloader import get_archive_pipeline
    pipe = get_archive_pipeline()
    return pipe.list_downloaded(mission_id=mission_id, body_id=body_id)


# ---------------------------------------------------------------------------
# Publication-Quality Figure Generator (Journal-Ready Vector / High-DPI)
# ---------------------------------------------------------------------------

@router.get("/figure/publication")
def generate_publication_figure(
    body_id: str,
    variable: str = "temperature_k",
    missions: Optional[str] = None,
    dpi: int = 300,
    fmt: str = "png",
) -> Response:
    """Generate high-resolution publication-quality figure with journal typography."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mgr = get_mission_manager()
    b = get_body(body_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Unknown body: {body_id}")

    mission_list = [m.strip() for m in missions.split(",")] if missions else None
    comp = mgr.compare_on_body(body_id, None, mission_ids=mission_list, variable_name=variable)

    grid = comp.get("grid_km", [])
    if not grid:
        raise HTTPException(status_code=400, detail="No profile data available for this figure")

    fig, ax = plt.subplots(figsize=(6.5, 7.5), dpi=dpi)

    var_labels = {
        "temperature_k": "Temperature $T$ (K)",
        "temperature_c": r"Temperature $T$ ($^\circ\mathrm{C}$)",
        "pressure_hpa": "Pressure $P$ (hPa)",
        "lapse_rate": r"Lapse Rate $-\partial T/\partial z$ (K/km)",
        "potential_temperature": r"Potential Temperature $\theta$ (K)",
        "buoyancy_freq_sq": r"Buoyancy Frequency $N^2$ ($\mathrm{s^{-2}}$)",
        "density": r"Density $\rho$ ($\mathrm{kg/m^3}$)",
    }
    xlabel = var_labels.get(variable, variable)

    # 1. Shaded +/- 1 sigma band
    plus_sigma = comp.get("composite_plus_1sigma", [])
    minus_sigma = comp.get("composite_minus_1sigma", [])
    if plus_sigma and minus_sigma:
        p_sig = [np.nan if x is None else x for x in plus_sigma]
        m_sig = [np.nan if x is None else x for x in minus_sigma]
        ax.fill_betweenx(grid, m_sig, p_sig, color="#38bdf8", alpha=0.22, label=r"$\pm 1\sigma$ Multi-Mission Spread")

    # 2. Individual mission profiles
    colors = ["#0284c7", "#f97316", "#10b981", "#8b5cf6", "#f43f5e", "#06b6d4", "#eab308", "#ec4899"]
    for i, p in enumerate(comp.get("profiles", [])):
        series = [np.nan if x is None else x for x in p.get("interpolated_series", [])]
        c = colors[i % len(colors)]
        ax.plot(series, grid, label=f"{p.get('mission_id', '').upper()} ({p.get('instrument', '')})",
                linestyle="-", linewidth=1.8, color=c)

    # 3. Composite mean
    mean_v = [np.nan if x is None else x for x in comp.get("composite_mean", [])]
    ax.plot(mean_v, grid, label=r"Composite Mean $\mu(z)$", color="#0f172a", linewidth=2.8)

    ax.set_ylabel("Altitude Above Reference Surface $z$ (km)", fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=11, fontweight="bold")
    ax.set_title(f"{b.name} Atmospheric Soundings\nMulti-Mission Comparative Analysis", fontsize=12, pad=12)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    media_type = "image/png" if fmt == "png" else ("image/svg+xml" if fmt == "svg" else "application/pdf")
    filename = f"veda_pub_{body_id}_{variable}.{fmt}"
    return Response(content=buf.getvalue(), media_type=media_type,
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ---------------------------------------------------------------------------
# Universal File Ingestion & Parsing Endpoints
# ---------------------------------------------------------------------------

def ingest_planetary_file(
    file_path: Path,
    body_id: str = "venus",
    mission_id: Optional[str] = None,
    instrument: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest and parse any planetary science file (FITS image, PDS3, CSV, or ASCII table)."""
    b = get_body(body_id) or get_body("venus")
    suffix = file_path.suffix.lower()

    # 1. Astronomical Camera Image or FITS File
    if suffix in (".fit", ".fits", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
        fits_data = load_fits_image(str(file_path))
        return {
            "type": "image",
            "filename": file_path.name,
            "observation_id": file_path.stem,
            "body_id": b.id,
            "mission_id": mission_id or "user_imported",
            "instrument": instrument or (str(fits_data.header.get("INSTRUME", "Camera")) if suffix in (".fit", ".fits") else "Camera"),
            "time_utc": str(fits_data.header.get("DATE-OBS") or fits_data.header.get("DATE") or "2026-01-01T00:00:00Z"),
            "shape": [fits_data.stats.get("shape_y", 0), fits_data.stats.get("shape_x", 0)],
            "stats": fits_data.stats,
            "header": fits_data.header,
            "local_path": str(file_path),
        }

    # 2. Tabular Vertical Sounding / In-situ Data
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

    # Altitude mapping
    if alt_col:
        z_arr = tbl.series(alt_col)
        if z_arr is None or z_arr.size == 0:
            z_arr = np.linspace(0.0, float(tbl.row_count()), tbl.row_count())
        elif ("RADIUS" in alt_col.upper() or "RAD" in alt_col.upper()) and np.nanmean(z_arr) > 400.0:
            z_arr = z_arr - b.radius_km
    else:
        z_arr = np.linspace(0.0, float(tbl.row_count()), tbl.row_count())

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
    return {
        "type": "profile",
        "filename": file_path.name,
        "observation_id": file_path.stem,
        "body_id": b.id,
        "mission_id": mission_id or "user_imported",
        "instrument": prof.instrument,
        "columns_detected": list(tbl.columns.keys()),
        "data": prof.to_dict(decimate_max=0),
    }


class ParseFileRequest(BaseModel):
    file_path: Optional[str] = None
    file_content: Optional[str] = None
    filename: Optional[str] = None
    body_id: str = "venus"
    mission_id: Optional[str] = None
    instrument: Optional[str] = None


@router.post("/parse-file")
def parse_generic_file_endpoint(req: ParseFileRequest) -> dict:
    """Parse any local planetary file on disk or text/base64 payload."""
    import base64
    import tempfile

    if req.file_content and req.filename:
        suffix = Path(req.filename).suffix or ".tab"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            if req.file_content.startswith("data:") and ";base64," in req.file_content:
                header, b64_data = req.file_content.split(";base64,", 1)
                tmp.write(base64.b64decode(b64_data))
            else:
                tmp.write(req.file_content.encode("utf-8", errors="replace"))
            tmp_p = Path(tmp.name)
        try:
            res = ingest_planetary_file(tmp_p, body_id=req.body_id, mission_id=req.mission_id, instrument=req.instrument)
            res["filename"] = req.filename
            res["observation_id"] = Path(req.filename).stem
            return res
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Failed to ingest file '{req.filename}': {exc}")
        finally:
            try:
                tmp_p.unlink()
            except Exception:
                pass

    if not req.file_path:
        raise HTTPException(status_code=400, detail="file_path or (file_content and filename) is required")

    p = Path(req.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    try:
        return ingest_planetary_file(p, body_id=req.body_id, mission_id=req.mission_id, instrument=req.instrument)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to ingest file '{p.name}': {exc}")



