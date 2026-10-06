"""FastAPI route definitions for VEDA multi-mission scientific platform."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Annotated, Dict, List, Optional
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from ..core.registry import (
    BODIES, DATA_LICENSES, LEAD_RESEARCHER,
    DATA_AVAILABILITY_STATEMENT, get_body, get_mission, list_bodies, list_missions,
    get_missions_for_body, list_variables, get_variable_info, list_data_portals,
)
from ..missions.manager import get_mission_manager
from ..analysis.atmospheric import (
    export_profile_to_csv,
    export_comparison_to_csv,
)
from ..readers.fits_reader import (
    compute_image_histogram,
    extract_photometric_transect,
    load_fits_image,
    render_to_png,
)
from ..analysis.thermo import cp_model
from ..config import APP_VERSION, CACHE_DIR, sampledata_dir

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
        "version": APP_VERSION,
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
        "mission_type": m.mission_type,
        "target_encounters": m.target_encounters,
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
        "isobaric_heat_capacity_cp": b.isobaric_heat_capacity_cp,
        "cp_model": cp_model(b),
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
    limit: Annotated[int, Query(ge=1, le=2000)] = 50,
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
    limit_per_mission: Annotated[int, Query(ge=1, le=500)] = 25,
) -> dict:
    """Retrieve multi-mission observations for a selected target body."""
    mgr = get_mission_manager()
    b = get_body(body_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Body '{body_id}' not found")

    mission_list = [m.strip() for m in missions.split(",")] if missions else None
    return mgr.discover_by_body(body_id, mission_ids=mission_list, limit_per_mission=limit_per_mission)


class CompareFilter(BaseModel):
    """Which profiles to compare when none are hand-picked (see missions/selection.py)."""
    # Dates as YYYY-MM-DD: they are compared with the profiles' ISO times as text, so
    # "2020-1-31" would select the wrong profiles.
    start: Optional[str] = None
    end: Optional[str] = None
    lat_min: Optional[float] = Field(None, ge=-90, le=90)
    lat_max: Optional[float] = Field(None, ge=-90, le=90)
    lst_min: Optional[float] = Field(None, ge=0, le=24)
    lst_max: Optional[float] = Field(None, ge=0, le=24)
    sza_min: Optional[float] = Field(None, ge=0, le=180)
    sza_max: Optional[float] = Field(None, ge=0, le=180)
    ls_min: Optional[float] = Field(None, ge=0, le=360)
    ls_max: Optional[float] = Field(None, ge=0, le=360)
    per_mission: int = Field(10, ge=1, le=100)
    download: bool = True
    include_uploads: bool = True
    cover_min_km: Optional[float] = Field(None, ge=-1000, le=100000)
    cover_max_km: Optional[float] = Field(None, ge=-1000, le=100000)
    max_spacing_km: Optional[float] = Field(None, gt=0, le=1000)
    max_sigma: Optional[float] = Field(None, gt=0, le=1e30)
    max_sigma_pct: Optional[float] = Field(None, gt=0, le=1000)
    datasets: Optional[List[str]] = Field(None, max_length=200)
    instruments: Optional[List[str]] = Field(None, max_length=100)

    @field_validator("start", "end")
    @classmethod
    def _iso_date(cls, v: Optional[str]) -> Optional[str]:
        import datetime as _dt
        if v in (None, ""):
            return None
        try:
            if len(v) != 10:
                raise ValueError
            _dt.date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"dates must be written YYYY-MM-DD, not {v!r}")
        return v


class CrossCompareRequest(BaseModel):
    # list of {"mission_id": ..., "observation_id": ...}
    observations: Optional[List[Dict[str, str]]] = Field(None, max_length=5000)
    missions: Optional[List[str]] = None  # e.g. ["akatsuki", "vex"]
    variable: str = "temperature_k"  # "temperature_k", "temperature_c", "pressure_hpa", "lapse_rate", "buoyancy_freq_sq"
    filter: Optional[CompareFilter] = None
    # climatology bins: latitude | lst | sza | year | month | month_of_year | mission
    group_by: Optional[str] = Field(None, max_length=20)
    group_width: float = Field(0.0, ge=0.0, le=360.0)
    # spacing of the common altitude grid; None: 0.5 km on Venus, Mars and Pluto, 2 km elsewhere
    altitude_step_km: Optional[float] = Field(None, ge=0.01, le=100.0)
    # vertical coordinate of the common grid: altitude, or pressure (uniform in log p)
    vertical: str = Field("altitude", pattern="^(altitude|pressure)$")
    pressure_step_decades: float = Field(0.02, ge=0.001, le=1.0)
    # composite weights: equal, or 1/sigma^2 from each profile's uncertainty
    weighting: str = Field("equal", pattern="^(equal|inverse_variance)$")
    # outlier screen: robust z threshold (None: off); leave flagged profiles out of the composites
    outlier_z: Optional[float] = Field(None, ge=1.0, le=20.0)
    drop_outliers: bool = False


@router.post("/compare/body/{body_id}")
def compare_missions_on_body(
    body_id: str,
    req: CrossCompareRequest,
) -> dict:
    """Multi-mission comparative vertical profile overlay and composite calculation."""
    return _compare_or_404(body_id, req)


def _checked_selection(body_id: str, req: "CrossCompareRequest"):
    """The request's profile filter, after the checks every comparison endpoint makes."""
    if not get_body(body_id):
        raise HTTPException(status_code=404, detail=f"Body '{body_id}' not found")
    from ..missions.selection import ProfileFilter
    sel = ProfileFilter(**req.filter.model_dump()) if req.filter else None
    if sel and sel.start and sel.end and sel.start > sel.end:
        raise HTTPException(status_code=422, detail="The start date is after the end date")
    if sel and sel.cover_min_km is not None and sel.cover_max_km is not None and sel.cover_min_km > sel.cover_max_km:
        raise HTTPException(status_code=422, detail="The altitude range to cover is reversed")
    from ..analysis.atmospheric import GROUPINGS
    if req.group_by and req.group_by not in GROUPINGS:
        raise HTTPException(status_code=422, detail=f"group_by must be one of: {', '.join(GROUPINGS)}")
    return sel


def _compare_or_404(body_id: str, req: "CrossCompareRequest") -> dict:
    sel = _checked_selection(body_id, req)
    comp = get_mission_manager().compare_on_body(
        body_id, req.observations, mission_ids=req.missions, variable_name=req.variable, selection=sel,
        group_by=req.group_by or "", group_width=req.group_width, altitude_step_km=req.altitude_step_km,
        vertical=req.vertical, pressure_step_decades=req.pressure_step_decades, weighting=req.weighting,
        outlier_z=req.outlier_z, drop_outliers=req.drop_outliers)
    if isinstance(comp, dict) and comp.get("error"):
        raise HTTPException(status_code=400, detail=comp["error"])
    return comp


class PointStatisticsRequest(BaseModel):
    """One value per profile (an altitude cut, a layer statistic, a diagnostic)."""
    values: List[Optional[float]] = Field(..., max_length=100000)
    log: bool = False                                        # statistics of ln y (densities, pressure)
    groups: Optional[List[str]] = Field(None, max_length=100000)


@router.post("/analysis/point-statistics")
def point_statistics(req: PointStatisticsRequest) -> dict:
    """Mean, standard error and 95 % bootstrap intervals of the mean and median of the
    points, overall and per group (analysis/resampling.py)."""
    from ..analysis.resampling import bootstrap_statistics
    try:
        return bootstrap_statistics([float("nan") if v is None else v for v in req.values], req.log, req.groups)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Harmonic fits of altitude cuts (thermal tides, waves)
# ---------------------------------------------------------------------------

class HarmonicFitRequest(BaseModel):
    """Points of an altitude cut (one per profile) to fit with harmonics of a period."""
    x: List[Optional[float]] = Field(..., max_length=100000)
    y: List[Optional[float]] = Field(..., max_length=100000)
    period: float = Field(24.0, gt=0.0, le=100000.0)       # 24 h (local time), 360 deg (longitude)
    harmonics: int = Field(2, ge=1, le=6)
    log: bool = False                                        # fit ln y (densities, pressure)
    y_sigma: Optional[List[Optional[float]]] = Field(None, max_length=100000)   # 1-sigma of each y: weighted fit
    bootstrap: bool = True                                   # 95 % bootstrap intervals


@router.post("/analysis/harmonic-fit")
def harmonic_fit_of_points(req: HarmonicFitRequest) -> dict:
    """Thermal tide / wave fit of one value per profile against local time or longitude
    (analysis/tides.py)."""
    from ..analysis.tides import harmonic_fit
    if len(req.x) != len(req.y):
        raise HTTPException(status_code=400, detail="x and y must have the same length")
    nan = float("nan")
    try:
        sig = None if req.y_sigma is None else [nan if v is None else v for v in req.y_sigma]
        return harmonic_fit([nan if v is None else v for v in req.x], [nan if v is None else v for v in req.y],
                            req.period, req.harmonics, req.log, y_sigma=sig, bootstrap=req.bootstrap)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Observation Data Retrieval (Profiles & Images)
# ---------------------------------------------------------------------------

def _load_observation(load, mission_id: str, observation_id: str):
    """``load(mission_id, observation_id)``, with failures as answers the user can read:
    an archive that cannot be reached (502), an account needed (401), a file that cannot
    be read (422), instead of a bare "Internal Server Error".  None stays None (404)."""
    from ..archives import net
    try:
        return load(mission_id, observation_id)
    except HTTPException:
        raise
    except net.LoginRequired as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except net.ArchiveError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except LookupError:
        return None
    except Exception as exc:  # noqa: BLE001 - a product VEDA cannot read
        raise HTTPException(status_code=422, detail=_friendly_ingest_error(observation_id, exc))


@router.get("/profile/{mission_id}/{observation_id:path}")
def get_observation_profile(
    mission_id: str,
    observation_id: str,
    decimate_max: int = 600,
) -> dict:
    """Load normalized 1D profile with body-specific derived thermodynamics."""
    mgr = get_mission_manager()
    prof = _load_observation(mgr.load_profile, mission_id, observation_id)
    if not prof:
        raise HTTPException(status_code=404, detail=f"Profile '{observation_id}' for mission '{mission_id}' not found")
    return prof.to_dict(decimate_max=decimate_max)


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
    if stretch not in IMAGE_STRETCHES:
        raise HTTPException(status_code=400, detail=f"Unknown stretch '{stretch}'. Use one of: {', '.join(IMAGE_STRETCHES)}")
    if colormap not in IMAGE_COLORMAPS:
        raise HTTPException(status_code=400, detail=f"Unknown colormap '{colormap}'. Use one of: {', '.join(IMAGE_COLORMAPS)}")
    max_dim = max(64, min(int(max_dim), 4096))
    mgr = get_mission_manager()
    img = _load_observation(mgr.load_image, mission_id, observation_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image observation not found")

    # FITS images are rendered with the requested stretch (loaded files may be .FITS or .fts)
    if img.local_path and Path(img.local_path).suffix.lower() in (".fit", ".fits", ".fts"):
        try:
            fits_data = load_fits_image(img.local_path)
            png_bytes = render_to_png(fits_data.primary_data, stretch_method=stretch,
                                      colormap=colormap, vmin=vmin, vmax=vmax, max_dimension=max_dim)
            return Response(content=png_bytes, media_type="image/png")
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Could not render image: {e}")

    # If browse image is available locally, serve it
    if img.local_path and img.local_path.lower().endswith((".jpg", ".jpeg", ".png")):
        with open(img.local_path, "rb") as f:
            is_png = img.local_path.lower().endswith(".png")
            return Response(content=f.read(), media_type="image/png" if is_png else "image/jpeg")

    raise HTTPException(status_code=404, detail="Image data unavailable")


IMAGE_STRETCHES = ("zscale", "percentile", "linear", "log", "sqrt", "asinh", "histeq")
IMAGE_COLORMAPS = ("inferno", "viridis", "plasma", "gray", "magma", "cividis", "twilight")


class TransectRequest(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    num_samples: int = Field(200, ge=2, le=5000)


@router.post("/image/{mission_id}/{observation_id:path}/transect")
def get_image_transect(
    mission_id: str,
    observation_id: str,
    req: TransectRequest,
) -> dict:
    """Compute 1D photometric line slice along (x0, y0) -> (x1, y1)."""
    mgr = get_mission_manager()
    img = _load_observation(mgr.load_image, mission_id, observation_id)
    if not img or not img.local_path:
        raise HTTPException(status_code=404, detail="Image not found for transect")

    try:
        fits_data = load_fits_image(img.local_path)
        return extract_photometric_transect(fits_data.primary_data, req.x0, req.y0, req.x1, req.y1, req.num_samples)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Transect computation failed: {e}")


@router.get("/image/{mission_id}/{observation_id:path}/histogram")
def get_image_histogram_endpoint(
    mission_id: str,
    observation_id: str,
    bins: int = 100,
) -> dict:
    """Compute pixel intensity histogram and CDF."""
    if not 2 <= bins <= 1000:
        raise HTTPException(status_code=400, detail="bins must be between 2 and 1000")
    mgr = get_mission_manager()
    img = _load_observation(mgr.load_image, mission_id, observation_id)
    if not img or not img.local_path:
        raise HTTPException(status_code=404, detail="Image not found for histogram")

    try:
        fits_data = load_fits_image(img.local_path)
        return compute_image_histogram(fits_data.primary_data, num_bins=bins)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Histogram computation failed: {e}")


# Declared after the sub-resource routes above: {observation_id:path} is
# greedy and would otherwise capture ".../render" and ".../histogram".
@router.get("/image/{mission_id}/{observation_id:path}")
def get_image_metadata(
    mission_id: str,
    observation_id: str,
) -> dict:
    """Get metadata for an astronomical camera observation."""
    mgr = get_mission_manager()
    img = _load_observation(mgr.load_image, mission_id, observation_id)
    if not img:
        raise HTTPException(status_code=404, detail=f"Image observation '{observation_id}' not found")
    return img.to_dict()


# ---------------------------------------------------------------------------
# Data Export Endpoints
# ---------------------------------------------------------------------------

@router.get("/export/profile/{mission_id}/{observation_id:path}/csv")
def export_profile_csv(mission_id: str, observation_id: str):
    """Download vertical profile observation as RFC 4180 CSV with metadata header."""
    mgr = get_mission_manager()
    prof = _load_observation(mgr.load_profile, mission_id, observation_id)
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
    prof = _load_observation(mgr.load_profile, mission_id, observation_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    filename = f"{mission_id}_{observation_id.replace('/', '_')}.json"
    return Response(
        content=json.dumps(prof.to_dict(decimate_max=0), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


def comparison_recipe(body_id: str, req: "CrossCompareRequest", comp: dict) -> dict:
    """Everything needed to redo a comparison: its settings and the profiles it used,
    as hand-picked observations (the archive's own product ids)."""
    from .. import __version__
    return {"veda_recipe": 1, "veda_version": __version__, "body_id": body_id, "variable": req.variable,
            "group_by": req.group_by or None, "group_width": req.group_width,
            "altitude_step_km": req.altitude_step_km, "vertical": req.vertical,
            "pressure_step_decades": req.pressure_step_decades, "weighting": req.weighting,
            "outlier_z": req.outlier_z, "drop_outliers": req.drop_outliers,
            # the filter that chose the profiles, for the record (the profiles are listed below)
            **({"filter": req.filter.model_dump(exclude_none=True)} if req.filter else {}),
            "observations": [{"mission_id": p["mission_id"], "observation_id": p["observation_id"]}
                             for p in comp.get("profiles", [])]}


@router.post("/export/compare/{body_id}/csv")
def export_compare_csv(body_id: str, req: CrossCompareRequest):
    """Download cross-mission comparative analysis data as CSV."""
    comp = _compare_or_404(body_id, req)
    csv_text = export_comparison_to_csv(comp)
    # The comparison as a request with the exact profiles it used: posting this JSON
    # to /compare/body/{body_id} (or opening the CSV with "Open comparison") redoes it.
    recipe = comparison_recipe(body_id, req, comp)
    first, rest = csv_text.split("\n", 1)
    csv_text = f"{first}\n# recipe: {json.dumps(recipe, separators=(',', ':'))}\n{rest}"
    filename = f"veda_comparison_{body_id}_{req.variable}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/export/compare/{body_id}/profiles")
def export_compare_profiles(body_id: str, req: CrossCompareRequest):
    """The compared profiles at their own levels with every archived and derived
    quantity (long format), instead of one variable on the common grid."""
    from ..analysis.atmospheric import export_profiles_long_csv
    sel = _checked_selection(body_id, req)
    body = get_body(body_id)
    profiles, _ = get_mission_manager().profiles_for_comparison(
        body_id, req.observations, mission_ids=req.missions, variable_name=req.variable, selection=sel)
    # the profiles on screen: those that carry the compared variable
    has = (lambda p: getattr(p, req.variable, None) is not None or req.variable in p.derived)
    profiles = [p for p in profiles if has(p)]
    if not profiles:
        raise HTTPException(status_code=400, detail=f"No {body.name} profiles with '{req.variable}' to export")
    return Response(content=export_profiles_long_csv(profiles, body), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="veda_profiles_{body_id}.csv"'})


# ---------------------------------------------------------------------------
# Publication-Quality Figure Generator (Journal-Ready Vector / High-DPI)
# ---------------------------------------------------------------------------

# Mirrors VARIABLE_CONFIGS in frontend/js/veda_app.js
PUBLICATION_VARIABLES = (
    "temperature_k", "temperature_c", "pressure_hpa", "lapse_rate", "potential_temperature",
    "buoyancy_freq_sq", "density", "scale_height", "electron_density_cm3", "refractivity",
    "temperature_from_density", "pressure_from_density",
)


@router.get("/figure/publication")
def generate_publication_figure(
    body_id: str,
    variable: str = "temperature_k",
    missions: Optional[str] = None,
    dpi: int = 300,
    fmt: str = "png",
) -> Response:
    """Generate high-resolution publication-quality figure with journal typography."""
    b = get_body(body_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Unknown body: {body_id}")
    if variable not in PUBLICATION_VARIABLES:
        raise HTTPException(status_code=400, detail=f"Unknown variable '{variable}'. Use one of: {', '.join(PUBLICATION_VARIABLES)}")
    if not 50 <= dpi <= 1200:
        raise HTTPException(status_code=400, detail="dpi must be between 50 and 1200")
    if fmt not in ("png", "svg", "pdf"):
        raise HTTPException(status_code=400, detail="fmt must be png, svg or pdf")

    mission_list = [m.strip() for m in missions.split(",")] if missions else None
    comp = get_mission_manager().compare_on_body(body_id, None, mission_ids=mission_list, variable_name=variable)
    return _publication_figure(b, comp, variable, dpi, fmt)


class PublicationFigureRequest(CrossCompareRequest):
    dpi: int = Field(300, ge=50, le=1200)
    fmt: str = Field("png", pattern="^(png|svg|pdf)$")


@router.post("/figure/publication")
def publication_figure_of_comparison(body_id: str, req: PublicationFigureRequest) -> Response:
    """The publication figure of exactly the comparison on screen: the same hand-picked
    profiles, or the same dates and geometry limits."""
    b = get_body(body_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Unknown body: {body_id}")
    if req.variable not in PUBLICATION_VARIABLES:
        raise HTTPException(status_code=400, detail=f"Unknown variable '{req.variable}'. Use one of: {', '.join(PUBLICATION_VARIABLES)}")
    return _publication_figure(b, _compare_or_404(body_id, req), req.variable, req.dpi, req.fmt)


def _publication_figure(b, comp: dict, variable: str, dpi: int, fmt: str) -> Response:
    # The object-oriented API, not pyplot: pyplot keeps global state and is not
    # safe in the server's worker threads (two figures at once could crash it).
    from matplotlib.figure import Figure
    from ..analysis.atmospheric import LOG_VARIABLES
    body_id = b.id

    by_pressure = comp.get("vertical") == "pressure"
    grid = comp.get("grid_hpa" if by_pressure else "grid_km", [])
    if not grid or not comp.get("profile_count"):
        # A grid alone is returned when profiles exist but none carry this
        # variable; plotting the empty composite against it used to crash (500).
        raise HTTPException(status_code=400, detail=(
            f"None of the selected {b.name} profiles contain '{variable}'. "
            "Choose another variable or add profiles that measure it."))

    fig = Figure(figsize=(6.5, 7.5), dpi=dpi)
    ax = fig.add_subplot(111)

    var_labels = {
        "temperature_k": "Temperature $T$ (K)",
        "temperature_c": r"Temperature $T$ ($^\circ\mathrm{C}$)",
        "pressure_hpa": "Pressure $P$ (hPa)",
        "lapse_rate": r"Lapse Rate $-\partial T/\partial z$ (K/km)",
        "potential_temperature": r"Potential Temperature $\theta$ (K)",
        "buoyancy_freq_sq": r"Buoyancy Frequency $N^2$ ($\mathrm{s^{-2}}$)",
        "density": r"Density $\rho$ ($\mathrm{kg/m^3}$)",
        "scale_height": "Scale Height $H$ (km)",
        "electron_density_cm3": r"Electron Density $N_e$ ($\mathrm{cm^{-3}}$)",
        "refractivity": "Radio Refractivity $N$",
        "temperature_from_density": "Temperature from density (hydrostatic) $T$ (K)",
        "pressure_from_density": "Pressure from density (hydrostatic) $P$ (hPa)",
    }
    xlabel = var_labels.get(variable, variable)

    groups = [g for g in comp.get("groups") or [] if not g.get("ungrouped") and g.get("mean")]
    nan = (lambda seq: [np.nan if x is None else x for x in seq])

    # 1. Shaded +/- 1 sigma band (each group's own band when grouped)
    plus_sigma = comp.get("composite_plus_1sigma", [])
    minus_sigma = comp.get("composite_minus_1sigma", [])
    if plus_sigma and minus_sigma and not groups:
        p_sig = [np.nan if x is None else x for x in plus_sigma]
        m_sig = [np.nan if x is None else x for x in minus_sigma]
        ax.fill_betweenx(grid, m_sig, p_sig, color="#38bdf8", alpha=0.22, label=r"$\pm 1\sigma$ Multi-Mission Spread")

    # 2. Individual profiles: one colour and legend entry per mission, or, when grouped,
    #    faded in their group's colour under the group composites
    colors = ["#0284c7", "#f97316", "#10b981", "#8b5cf6", "#f43f5e", "#06b6d4", "#eab308", "#ec4899"]
    profiles = comp.get("profiles", [])
    mission_of = (lambda p: p.get("mission_label") or p.get("mission_id", ""))
    mission_order = list(dict.fromkeys(mission_of(p) for p in profiles))
    counts = {m: sum(1 for p in profiles if mission_of(p) == m) for m in mission_order}
    group_of = {oid: gi for gi, g in enumerate(groups) for oid in g["observation_ids"]}
    labelled = set()
    for p in profiles:
        mid = mission_of(p)
        series = nan(p.get("interpolated_series", []))
        if groups:
            gi = group_of.get(p.get("observation_id"))
            ax.plot(series, grid, linewidth=0.8, alpha=0.3,
                    color=colors[gi % len(colors)] if gi is not None else "#94a3b8")
            continue
        label = None
        if mid not in labelled:
            labelled.add(mid)
            label = f"{mid.upper()} {p.get('instrument', '')} (n = {counts[mid]})"
        ax.plot(series, grid, label=label, linestyle="-", linewidth=1.2 if len(profiles) > 6 else 1.8,
                alpha=0.75 if len(profiles) > 6 else 1.0, color=colors[mission_order.index(mid) % len(colors)])
        sig = p.get("interpolated_sigma")
        if sig and len(profiles) <= 8:          # each profile's own 1-sigma when few are drawn
            v, e = np.array(series, dtype=float), np.array(nan(sig), dtype=float)
            ax.fill_betweenx(grid, v - e, v + e, color=colors[mission_order.index(mid) % len(colors)],
                             alpha=0.18, linewidth=0)
    for gi, g in enumerate(groups):
        c = colors[gi % len(colors)]
        if any(x is not None for x in g["plus_1sigma"]):
            ax.fill_betweenx(grid, nan(g["minus_1sigma"]), nan(g["plus_1sigma"]), color=c, alpha=0.15, linewidth=0)
        ax.plot(nan(g["mean"]), grid, color=c, linewidth=2.6, label=f"{g['label']} (n = {g['n']})")

    # 3. Composite mean, with its standard error as a darker band
    mean_v = nan(comp.get("composite_mean", []))
    if not groups and comp.get("composite_plus_sem"):
        ax.fill_betweenx(grid, nan(comp.get("composite_minus_sem", [])), nan(comp["composite_plus_sem"]),
                         color="#0f172a", alpha=0.18, linewidth=0, label="Standard error of the mean")
    ax.plot(mean_v, grid, label=r"Composite Mean $\mu(z)$", color="#0f172a", linewidth=2.8 if not groups else 1.6,
            linestyle="-" if not groups else "--")

    finite_mean = [v for v in mean_v if np.isfinite(v)]
    if variable in LOG_VARIABLES and finite_mean and min(finite_mean) > 0:
        ax.set_xscale("log")              # pressure and densities span orders of magnitude
    if by_pressure:
        ax.set_yscale("log")
        ax.invert_yaxis()                 # high pressure (low altitude) at the bottom
        ax.set_ylabel("Pressure $P$ (hPa)", fontsize=11, fontweight="bold")
    else:
        ax.set_ylabel("Altitude $z$ (km)", fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=11, fontweight="bold")
    times = sorted(p.get("time_utc", "")[:10] for p in profiles if p.get("time_utc"))
    span = (times[0] if times[0] == times[-1] else f"{times[0]} to {times[-1]}") if times else ""
    ax.set_title(f"{b.name}: {len(profiles)} profile{'s' if len(profiles) != 1 else ''}"
                 + (f", {span}" if span else ""), fontsize=12, pad=12)
    if comp.get("vertical_reference_warning"):
        fig.text(0.01, 0.005, comp["vertical_reference_warning"], fontsize=6.5, wrap=True, va="bottom")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)

    # Room below the axis label for the altitude-reference note (it overlapped the label)
    fig.tight_layout(rect=(0, 0.05, 1, 1) if comp.get("vertical_reference_warning") else (0, 0, 1, 1))

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    buf.seek(0)

    media_type = "image/png" if fmt == "png" else ("image/svg+xml" if fmt == "svg" else "application/pdf")
    filename = f"veda_pub_{body_id}_{variable}.{fmt}"
    return Response(content=buf.getvalue(), media_type=media_type,
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ---------------------------------------------------------------------------
# Universal File Ingestion & Parsing Endpoints
# ---------------------------------------------------------------------------

SUPPORTED_UPLOAD_SUFFIXES = (
    ".tab", ".lbl", ".xml", ".csv", ".txt", ".dat", ".asc",
    ".fit", ".fits", ".fts", ".jpg", ".jpeg", ".png",
)
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class UploadedFile(BaseModel):
    filename: str
    file_content: str  # plain text, or a data: URL with base64 payload for binary files


class ParseFileRequest(BaseModel):
    file_path: Optional[str] = None
    file_content: Optional[str] = None
    filename: Optional[str] = None
    # Other files uploaded together with the primary one, e.g. the .tab that a
    # PDS3 .lbl points at.  They are stored next to it before parsing.
    companion_files: List[UploadedFile] = Field(default_factory=list, max_length=8)
    body_id: str = "venus"
    mission_id: Optional[str] = None
    instrument: Optional[str] = None
    # What the file is, as chosen when loading it: the mission it comes from (a VEDA
    # mission id or free text), the observation time, and each column's role and unit.
    source_mission: Optional[str] = Field(None, max_length=80)
    time_utc: Optional[str] = Field(None, max_length=40)
    roles: Optional[Dict[str, Dict[str, Optional[str]]]] = None
    # Profiles are thinned to this many levels for display (0 keeps all).
    decimate_max: int = Field(5000, ge=0, le=500000)


def _safe_upload_name(name: str) -> str:
    safe = Path(str(name).replace("\\", "/")).name
    # meta.json is the upload's own bookkeeping file (see uploads_adapter).
    if not safe or safe in (".", "..") or safe.lower() == "meta.json":
        raise HTTPException(status_code=400, detail=f"Invalid file name: {name!r}")
    return safe


def _decode_upload(name: str, content: str) -> bytes:
    import base64
    import binascii
    if content.startswith("data:") and ";base64," in content:
        try:
            data = base64.b64decode(content.split(";base64,", 1)[1], validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail=f"{name}: content is not valid base64")
    else:
        data = content.encode("utf-8", errors="replace")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{name} is larger than {MAX_UPLOAD_BYTES // 2**20} MB")
    return data


def _friendly_ingest_error(name: str, exc: Exception) -> str:
    """User-facing message; never exposes server-side paths."""
    import re
    if isinstance(exc, FileNotFoundError) and name.lower().endswith(".lbl"):
        return (f"{name} is a PDS3 label and its data table was not included. "
                "Select the .lbl and its .tab together.")
    msg = re.sub(r"(?:[A-Za-z]:)?[\\/][^\s'\"]*[\\/]", "", str(exc))
    return f"Could not read {name}: {msg}"


def _allowed_local_roots() -> List[Path]:
    return [sampledata_dir().resolve(), CACHE_DIR.resolve()]


@router.post("/parse-file")
def parse_generic_file_endpoint(req: ParseFileRequest) -> dict:
    """Parse an uploaded file (plus companions), or a bundled/cached file on disk."""
    from ..missions.uploads_adapter import MISSION_ID as UPLOADS, commit_upload, discard_upload, stage_upload
    from ..pipeline.ingest import ingest_planetary_file

    if get_body(req.body_id) is None:
        raise HTTPException(status_code=404, detail=f"Body '{req.body_id}' not found")
    common = dict(body_id=req.body_id, mission_id=req.mission_id,
                  instrument=req.instrument, decimate_max=req.decimate_max)

    if req.filename is not None and req.file_content is not None:
        name = _safe_upload_name(req.filename)
        if Path(name).suffix.lower() not in SUPPORTED_UPLOAD_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{Path(name).suffix or name}'. "
                       f"Supported: {', '.join(SUPPORTED_UPLOAD_SUFFIXES)}")
        payload = _decode_upload(name, req.file_content)
        if not payload.strip():
            raise HTTPException(status_code=422, detail=f"{name} is empty")
        companions = {_safe_upload_name(c.filename): _decode_upload(c.filename, c.file_content)
                      for c in req.companion_files}
        from ..missions.uploads_adapter import describe
        info = {"source_mission": req.source_mission or "", "instrument": req.instrument or "",
                "time_utc": req.time_utc or "", "roles": req.roles}
        # Read the file from a staging folder first: a file that cannot be read must not
        # replace an earlier good upload of the same name (nor delete one of the same id).
        try:
            staged = stage_upload(name, payload, companions)
        except OSError as exc:            # a name the file system refuses ("a|b.csv", too long)
            raise HTTPException(status_code=400, detail=f"{name} cannot be stored under this name: {exc.strerror or exc}")
        try:
            res = ingest_planetary_file(staged, **{**common, "mission_id": req.mission_id or UPLOADS,
                                                   "instrument": describe(info), "roles": req.roles,
                                                   "time_utc": req.time_utc or None})
        except Exception as exc:  # noqa: BLE001
            discard_upload(staged)
            raise HTTPException(status_code=422, detail=_friendly_ingest_error(name, exc))
        commit_upload(staged, req.body_id, info)
        res.pop("local_path", None)
        return res

    if not req.file_path:
        raise HTTPException(status_code=400, detail="Provide filename and file_content (upload), or file_path")

    # file_path is limited to VEDA's own bundled samples and download cache so
    # the API cannot be used to read arbitrary files on the machine.
    p = Path(req.file_path).expanduser().resolve()
    if not any(p == root or root in p.parents for root in _allowed_local_roots()):
        raise HTTPException(status_code=403, detail="file_path must point inside the VEDA sample data or cache folder")
    if not p.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {p.name}")
    try:
        res = ingest_planetary_file(p, **common)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_friendly_ingest_error(p.name, exc))
    res.pop("local_path", None)
    return res


@router.post("/upload/preview")
def preview_upload(req: ParseFileRequest) -> dict:
    """What a file contains before it is loaded: its columns (units, first values,
    range), suggested roles, and what its label says about body, mission, instrument
    and time.  Nothing is kept."""
    import shutil
    import tempfile
    from ..core.registry import MISSIONS
    from ..pipeline.ingest import IMAGE_SUFFIXES, ROLE_UNITS, suggest_roles
    from ..readers.pds3_reader import read_any_table
    if req.filename is None or req.file_content is None:
        raise HTTPException(status_code=400, detail="Provide filename and file_content")
    name = _safe_upload_name(req.filename)
    if Path(name).suffix.lower() not in SUPPORTED_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{Path(name).suffix or name}'")
    tmp = Path(tempfile.mkdtemp(prefix="veda-preview-"))
    try:
        (tmp / name).write_bytes(_decode_upload(name, req.file_content))
        for c in req.companion_files:
            (tmp / _safe_upload_name(c.filename)).write_bytes(_decode_upload(c.filename, c.file_content))
        if Path(name).suffix.lower() in IMAGE_SUFFIXES:
            return {"type": "image", "filename": name, "role_units": ROLE_UNITS}
        try:
            tbl = read_any_table(str(tmp / name))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=_friendly_ingest_error(name, exc))
        cols = []
        for col, vals in tbl.columns.items():
            a = np.asarray(vals, dtype=float)
            fin = a[np.isfinite(a)]
            cols.append({"name": col, "unit": tbl.units.get(col, ""),
                         "description": str((tbl.descriptions or {}).get(col, ""))[:200],
                         "first": [None if not np.isfinite(x) else float(f"{x:.6g}") for x in a[:5]],
                         "min": float(fin.min()) if fin.size else None, "max": float(fin.max()) if fin.size else None,
                         "n": int(a.size)})
        keys = ("START_TIME", "STOP_TIME", "TARGET_NAME", "INSTRUMENT_NAME", "INSTRUMENT_ID",
                "INSTRUMENT_HOST_NAME", "SPACECRAFT_NAME", "MISSION_NAME", "PRODUCT_ID", "DATA_SET_ID")
        meta = {k: str(v).strip('"') for k, v in tbl.metadata.items() if isinstance(v, (str, int, float)) and k in keys}
        host = " ".join(meta.get(k, "") for k in ("INSTRUMENT_HOST_NAME", "SPACECRAFT_NAME", "MISSION_NAME")).upper()
        mission = next((m.id for m in MISSIONS.values()
                        if host and (m.id.upper() in host.split() or m.name.upper().split(" (")[0] in host)), None)
        target = (meta.get("TARGET_NAME") or "").lower()
        body = next((b for b in ("venus", "mars", "jupiter", "saturn", "titan", "pluto", "mercury", "moon",
                                 "ceres", "vesta") if b in target), None)
        return {"type": "table", "filename": name, "columns": cols, "suggested_roles": suggest_roles(tbl),
                "role_units": ROLE_UNITS, "label": meta,
                "suggested": {"body_id": body, "mission_id": mission,
                              "instrument": meta.get("INSTRUMENT_ID") or meta.get("INSTRUMENT_NAME") or "",
                              "time_utc": meta.get("START_TIME") or ""}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.get("/uploads")
def list_recent_uploads() -> List[dict]:
    """Files loaded into VEDA recently (newest first)."""
    from ..missions.uploads_adapter import list_uploads
    return list_uploads()


@router.delete("/uploads/{observation_id}")
def delete_recent_upload(observation_id: str) -> dict:
    from ..missions.uploads_adapter import delete_upload
    if not delete_upload(observation_id):
        raise HTTPException(status_code=404, detail=f"Upload '{observation_id}' not found")
    return {"deleted": observation_id}
