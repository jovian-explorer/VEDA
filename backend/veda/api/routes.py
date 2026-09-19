"""FastAPI route definitions for VEDA multi-mission scientific platform."""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..core.registry import BODIES, MISSIONS, get_body, get_mission, list_bodies, list_missions, get_missions_for_body
from ..missions.manager import get_mission_manager
from ..analysis.atmospheric import export_profile_to_csv, export_comparison_to_csv
from ..readers.fits_reader import (
    compute_image_histogram,
    extract_photometric_transect,
    load_fits_image,
    render_to_png,
)

router = APIRouter(prefix="/api/veda", tags=["VEDA Multi-Mission"])


# ---------------------------------------------------------------------------
# Platform & Metadata Endpoints
# ---------------------------------------------------------------------------

@router.get("/info")
def platform_info() -> dict:
    """Platform overview, version, and supported assets."""
    mgr = get_mission_manager()
    return {
        "title": "VEDA — Visualization, Exploration, and Data Analysis",
        "version": "2.0.0",
        "description": "Multi-Mission Planetary Science Visualization & Comparative Analysis Platform",
        "agencies_supported": ["NASA", "ESA", "JAXA", "NOAA"],
        "missions_count": len(mgr.list_missions()),
        "bodies_count": len(BODIES),
        "missions": mgr.list_missions(),
        "bodies": list(BODIES.keys()),
    }


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
        "temperature_c": "Temperature $T$ (°C)",
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
        ax.fill_betweenx(grid, m_sig, p_sig, color="#90caf9", alpha=0.3, label=r"$\pm 1\sigma$ Multi-Mission Spread")

    # 2. Individual mission profiles
    colors = ["#e53935", "#1e88e5", "#43a047", "#8e24aa", "#fb8c00", "#00acc1"]
    for i, p in enumerate(comp.get("profiles", [])):
        series = [np.nan if x is None else x for x in p.get("interpolated_series", [])]
        c = colors[i % len(colors)]
        ax.plot(series, grid, label=f"{p.get('mission_id', '').upper()} ({p.get('instrument', '')})",
                linestyle=":", linewidth=1.6, color=c)

    # 3. Composite mean
    mean_v = [np.nan if x is None else x for x in comp.get("composite_mean", [])]
    ax.plot(mean_v, grid, label=r"Composite Mean $\mu(z)$", color="#111111", linewidth=2.5)

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


