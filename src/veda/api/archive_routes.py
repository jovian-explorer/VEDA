"""Real archive search and download: /api/veda/archive/*"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..archives import catalog, net
from ..archives.datasets import datasets_for, get_dataset
from ..archives.profiles import load_profile

router = APIRouter(prefix="/api/veda/archive", tags=["archive"])

# ------------------------------------------------------------------ jobs

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _new_job(kind: str, total: int = 0) -> Dict[str, Any]:
    job = {"id": uuid.uuid4().hex[:12], "kind": kind, "status": "running", "done": 0, "total": total,
           "message": "", "errors": [], "result": None, "started": time.time()}
    with _jobs_lock:
        _jobs[job["id"]] = job
        # keep the registry small (finished jobs only: a running one is still polled)
        for old in sorted(_jobs.values(), key=lambda j: j["started"])[:-50]:
            if old["status"] != "running":
                _jobs.pop(old["id"], None)
    return job


def _run(job: Dict[str, Any], fn) -> None:
    def target():
        try:
            job["result"] = fn(job)
            # a job whose every item failed (job["succeeded"] == 0) failed, although it
            # returns a result (e.g. {"fetched": []})
            job["status"] = "failed" if job["errors"] and not job.get("succeeded", 1) else "completed"
        except net.LoginRequired as exc:
            job.update(status="login_required", message=str(exc), login_url=exc.login_url)
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            job.update(status="failed", message=str(exc))
    threading.Thread(target=target, daemon=True).start()


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> Dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found (it may have finished long ago)")
    snap = dict(job)          # one copy: the worker thread keeps updating the job
    snap.pop("started", None)
    return snap


# ------------------------------------------------------------------ datasets

@router.get("/datasets")
def list_datasets(mission_id: Optional[str] = None, body_id: Optional[str] = None) -> Dict[str, Any]:
    out = []
    for ds in datasets_for(mission_id, body_id):
        out.append({**ds.to_dict(), **catalog.dataset_status(ds)})
    return {"datasets": out}


@router.post("/datasets/{dataset_id}/index")
def index_dataset(dataset_id: str, force: bool = False) -> Dict[str, Any]:
    ds = get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Unknown dataset '{dataset_id}'")
    job = _new_job("index")

    def work(j):
        def progress(i, n, vol):
            j.update(done=i, total=n, message=f"Reading index of {vol}" if vol != "done" else "Done")
        count = catalog.refresh_dataset(ds, force=force, progress=progress)
        j["message"] = f"{count} products indexed"
        return {"indexed_products": count}

    _run(job, work)
    return {"job_id": job["id"]}


# ------------------------------------------------------------------ search

@router.get("/search")
def search(
    mission_id: Optional[str] = None,
    body_id: Optional[str] = None,
    dataset_id: Optional[List[str]] = Query(None),
    target: Optional[str] = None,
    start: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    kind: Optional[str] = Query(None, pattern=r"^(profile|timeseries|image|geometry|table|spectrum|cube|other)$"),
    product_type: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0, le=10_000_000),
    newest_first: bool = False,
    downloaded_only: bool = False,
) -> Dict[str, Any]:
    if dataset_id:
        unknown = [d for d in dataset_id if not get_dataset(d)]
        if unknown:
            raise HTTPException(404, f"Unknown dataset(s): {', '.join(unknown)}")
    if start and end and end < start:
        raise HTTPException(400, "End date is before start date")
    return catalog.search(catalog.SearchQuery(
        mission_id=mission_id, body_id=body_id, dataset_ids=dataset_id, target=target, start=start, end=end,
        kind=kind, product_type=product_type, text=q, limit=limit, offset=offset,
        newest_first=newest_first, downloaded_only=downloaded_only))


# ------------------------------------------------------------------ live search (PSA, PDS Registry, OPUS)

class LiveRequest(BaseModel):
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    mission_id: Optional[str] = None
    body_id: Optional[str] = None
    dataset_ids: Optional[List[str]] = Field(None, max_length=200)
    force: bool = False


@router.post("/live")
def live_search(req: LiveRequest) -> Dict[str, Any]:
    """Query the live archive services for a date window (background job); then use /search as usual."""
    from ..archives import services
    if req.end < req.start:
        raise HTTPException(400, "End date is before start date")
    if req.dataset_ids:
        sets = [get_dataset(d) for d in req.dataset_ids]
        if any(s is None for s in sets):
            raise HTTPException(404, "Unknown dataset")
        sets = [s for s in sets if s.service]
    else:
        sets = [d for d in datasets_for(req.mission_id, req.body_id) if d.service]
    job = _new_job("live", total=len(sets))

    def work(j):
        results = []
        for i, ds in enumerate(sets):
            j.update(done=i, message=f"Searching {ds.archive.replace(' (live search)', '')}: "
                                     f"{ds.mission_id.upper()} {ds.instrument}")
            try:
                results.append(services.search_window(ds, req.start, req.end, catalog._connect, catalog._db_lock,
                                                       force=req.force))
            except net.LoginRequired:
                raise
            except net.ArchiveError as exc:
                j["errors"].append(f"{ds.mission_id.upper()} {ds.instrument}: {exc}")
        j["succeeded"] = len(results)
        listed = sum(r["listed"] for r in results)
        more = [r for r in results if r["available"] > r["listed"]]
        j.update(done=len(sets), message=f"{listed} products listed from {len(results)} live data sets" +
                 (f"; {len(more)} have more than {services.MAX_PER_QUERY} in this range, narrow the dates to see all"
                  if more else ""))
        return {"results": results, "listed": listed, "truncated": [r["dataset_id"] for r in more]}

    _run(job, work)
    return {"job_id": job["id"], "datasets": len(sets)}


# ------------------------------------------------------------------ download

class ProductRef(BaseModel):
    dataset_id: str
    product_id: str = Field(max_length=200)


class FetchRequest(BaseModel):
    items: List[ProductRef] = Field(min_length=1, max_length=500)


@router.post("/fetch")
def fetch(req: FetchRequest) -> Dict[str, Any]:
    for it in req.items:
        if not catalog.get_product(it.dataset_id, it.product_id):
            raise HTTPException(404, f"Unknown product {it.dataset_id}/{it.product_id}; index the dataset first")
    job = _new_job("fetch", total=len(req.items))

    def work(j):
        # several products at a time (Settings > Performance > parallel downloads)
        from ..parallel import thread_map
        fetched = []
        count = [0]

        def done(i, res):
            it = req.items[i]
            count[0] += 1
            if isinstance(res, Exception):
                j["errors"].append(f"{it.product_id}: {res}")
            else:
                fetched.append(it.product_id)
            j.update(done=count[0], message=f"Downloaded {len(fetched)} of {len(req.items)}")
        results = thread_map(catalog.fetch_product, [(it.dataset_id, it.product_id) for it in req.items], on_done=done)
        login = next((r for r in results if isinstance(r, net.LoginRequired)), None)
        if login is not None and not fetched:
            raise login
        j.update(done=len(req.items), message=f"Downloaded {len(fetched)} of {len(req.items)}",
                 succeeded=len(fetched))
        return {"fetched": fetched}

    _run(job, work)
    return {"job_id": job["id"]}


@router.get("/downloaded")
def downloaded(mission_id: Optional[str] = None) -> Dict[str, Any]:
    ids = [d.id for d in datasets_for(mission_id)]
    return {"products": catalog.downloaded_products(ids)}


@router.get("/profile/{dataset_id}/{product_id}")
def profile(dataset_id: str, product_id: str,
            decimate_max: int = Query(2000, ge=0, le=100000)) -> Dict[str, Any]:
    """Load a product as a profile (downloads it first if needed)."""
    try:
        prof = load_profile(dataset_id, product_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except net.LoginRequired as exc:
        raise HTTPException(401, str(exc))
    except net.ArchiveError as exc:
        raise HTTPException(502, str(exc))
    d = prof.to_dict(decimate_max=decimate_max)
    d["dataset_id"] = dataset_id
    d["product"] = catalog.get_product(dataset_id, product_id)
    return d


# ------------------------------------------------------------------ geometry (SPICE)

geometry_router = APIRouter(prefix="/api/veda/geometry", tags=["geometry"])


_TARGET_BODY = {"67P": "comet_67p", "CHURYUMOV": "comet_67p", "C-G": "comet_67p"}


def target_body(ds, prod) -> str:
    """The product's target when VEDA knows it (Titan for a Cassini Titan product), else the data set's body."""
    from ..geometry.compute import NAIF_BODY
    t = (prod.get("target") or "").upper()
    for key, body in _TARGET_BODY.items():
        if key in t:
            return body
    for body in NAIF_BODY:
        if body.upper() == t.strip() or body.upper() in t.split():
            return body
    return ds.body_ids[0]


def _geometry_inputs(dataset_id: str, product_id: str):
    import datetime as dt
    from ..geometry import kernels
    ds = get_dataset(dataset_id)
    prod = catalog.get_product(dataset_id, product_id)
    if not ds or not prod:
        raise HTTPException(404, f"Unknown product {dataset_id}/{product_id}")
    if ds.mission_id not in kernels.MISSION_SPICE:
        raise HTTPException(404, f"No public SPICE kernels are known for {ds.mission_id}, so its geometry "
                                 "cannot be computed")
    if not prod.get("start_time"):
        raise HTTPException(422, "This product has no observation time")
    try:
        plan = kernels.plan(ds.mission_id, target_body(ds, prod), dt.date.fromisoformat(prod["start_time"][:10]))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except net.ArchiveError as exc:
        raise HTTPException(502, str(exc))
    return ds, prod, plan


@geometry_router.get("/{dataset_id}/{product_id}")
def geometry(dataset_id: str, product_id: str, span_min: float = Query(90, ge=5, le=1440)) -> Dict[str, Any]:
    """Observation geometry, or {"kernels_needed": true, ...} listing the SPICE kernels to download.

    Occultation profiles with per-sample ephemeris times get the occultation geometry
    (tangent points, view from Earth); every other product gets the spacecraft's
    orbit and the sub-spacecraft geometry over the observation.
    """
    from ..config import SETTINGS
    from ..core.registry import get_body
    from ..geometry import kernels
    from ..geometry.compute import observation_geometry, orbit_geometry
    ds, prod, plan = _geometry_inputs(dataset_id, product_id)
    if plan.missing:
        files = [{"name": u.rsplit("/", 1)[1], "url": u, "bytes": kernels.remote_size(u)} for u in plan.missing]
        total = kernels.total_mb(plan.missing)
        # automatic download only when the total is known to be within the limit
        return {"kernels_needed": True, "kernels": files, "total_mb": None if total is None else round(total, 1),
                "auto": bool(SETTINGS.spice_auto_download and total is not None
                             and total <= SETTINGS.spice_auto_limit_mb)}
    body_id = target_body(ds, prod)
    tr: Dict[str, Any] = {}
    prof = None
    if prod.get("kind") == "profile":
        try:
            prof = load_profile(dataset_id, product_id)
            tr = prof.track or {}
        except (LookupError, ValueError, net.ArchiveError):
            prof = None
    if "et" not in tr:
        try:
            g = orbit_geometry(plan, kernels.MISSION_SPICE[ds.mission_id].naif_id, body_id,
                               prod["start_time"], prod.get("stop_time") or prod["start_time"])
        except (LookupError, ValueError) as exc:
            raise HTTPException(422, str(exc))
        g["kernels"] = [u.rsplit("/", 1)[1] for u in plan.urls]
        g["ephemeris_source"] = kernels.MISSION_SPICE[ds.mission_id].source
        return g
    body = get_body(body_id)
    try:
        g = observation_geometry(plan, kernels.MISSION_SPICE[ds.mission_id].naif_id, body_id, tr["et"],
                                 span_min=span_min,
                                 product_track={"latitude": tr.get("latitude"), "longitude": tr.get("longitude"),
                                                "radius": prof.altitude_km + body.radius_km})
    except (LookupError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    g["kernels"] = [u.rsplit("/", 1)[1] for u in plan.urls]
    g["ephemeris_source"] = kernels.MISSION_SPICE[ds.mission_id].source
    return g


@geometry_router.post("/{dataset_id}/{product_id}/prepare")
def prepare_geometry(dataset_id: str, product_id: str) -> Dict[str, Any]:
    """Download the SPICE kernels this observation needs (background job)."""
    from ..geometry import kernels
    _, _, plan = _geometry_inputs(dataset_id, product_id)
    job = _new_job("kernels", total=len(plan.missing))

    def work(j):
        def progress(i, n, msg):
            j.update(done=i, total=n, message=f"Downloading {msg}")
        kernels.download(plan, progress=progress)
        j.update(done=j["total"], message="SPICE kernels ready")
        return {"kernels": [u.rsplit("/", 1)[1] for u in plan.urls]}

    _run(job, work)
    return {"job_id": job["id"]}


@geometry_router.get("/{dataset_id}/{product_id}/kernels")
def geometry_kernels(dataset_id: str, product_id: str) -> Dict[str, Any]:
    """Which SPICE kernels this observation needs and which are already here (no computation)."""
    from ..config import SETTINGS
    from ..geometry import kernels
    _, _, plan = _geometry_inputs(dataset_id, product_id)
    files = [{"name": u.rsplit("/", 1)[1], "bytes": kernels.remote_size(u)} for u in plan.missing]
    total = kernels.total_mb(plan.missing)
    return {"needed": [u.rsplit("/", 1)[1] for u in plan.urls], "missing": files,
            "missing_mb": None if total is None else round(total, 1),
            "auto": bool(SETTINGS.spice_auto_download and total is not None
                         and total <= SETTINGS.spice_auto_limit_mb)}


class PrefetchRequest(BaseModel):
    mission_id: str = Field(max_length=40)
    body_id: Optional[str] = Field(None, max_length=40)


@geometry_router.post("/prefetch")
def prefetch_kernels(req: PrefetchRequest) -> Dict[str, Any]:
    """Download the generic and body kernels for a mission in the background (when automatic
    downloads are on), so its first geometry is ready sooner.  The spacecraft SPK depends on
    the observation date and is fetched when an observation is opened."""
    from ..config import SETTINGS
    from ..core.registry import get_mission
    from ..geometry import kernels
    m = get_mission(req.mission_id)
    if m is None:
        raise HTTPException(404, f"Unknown mission '{req.mission_id}'")
    if req.mission_id not in kernels.MISSION_SPICE:
        return {"job_id": None, "reason": "no public SPICE kernels for this mission"}
    if not SETTINGS.spice_auto_download or not SETTINGS.network_enabled:
        return {"job_id": None, "reason": "automatic SPICE downloads are off"}
    body = req.body_id or (m.primary_targets[0] if m.primary_targets else "")
    plan = kernels.base_plan(body)
    plan.urls += [u for u in kernels.MISSION_SPICE[req.mission_id].extra if u not in plan.urls]
    plan.missing = [u for u in plan.urls if not plan.local(u).is_file()]
    if not plan.missing:
        return {"job_id": None, "reason": "kernels already downloaded"}
    total = kernels.total_mb(plan.missing)
    if total is None:
        return {"job_id": None, "reason": "the size of the kernels is not known (archive not answering)"}
    if total > SETTINGS.spice_auto_limit_mb:
        return {"job_id": None, "reason": f"{total:.0f} MB is above the automatic download limit"}
    job = _new_job("kernels", total=len(plan.missing))

    def work(j):
        kernels.download(plan, progress=lambda i, n, msg: j.update(done=i, total=n, message=f"Downloading {msg}"))
        j.update(done=j["total"], message="SPICE kernels ready")
        return {"kernels": [u.rsplit("/", 1)[1] for u in plan.urls]}
    _run(job, work)
    return {"job_id": job["id"], "missing_mb": round(total, 1)}


# ------------------------------------------------------------------ citations

citation_router = APIRouter(prefix="/api/veda/citations", tags=["citations"])


class CitationRequest(BaseModel):
    datasets: List[str] = Field(default_factory=list, max_length=500)
    features: List[str] = Field(default_factory=list, max_length=50)
    volumes: Dict[str, List[str]] = Field(default_factory=dict)


@citation_router.post("")
def citations(req: CitationRequest) -> Dict[str, Any]:
    """References for exactly the data sets and features a user worked with."""
    from ..citations import build
    return build(req.datasets, req.features, req.volumes)
