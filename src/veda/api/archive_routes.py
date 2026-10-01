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
        # keep the registry small
        for old in sorted(_jobs.values(), key=lambda j: j["started"])[:-50]:
            _jobs.pop(old["id"], None)
    return job


def _run(job: Dict[str, Any], fn) -> None:
    def target():
        try:
            job["result"] = fn(job)
            job["status"] = "failed" if job["errors"] and not job["result"] else "completed"
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
    return {k: v for k, v in job.items() if k != "started"}


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
    dataset_id: Optional[List[str]] = Query(None),
    target: Optional[str] = None,
    start: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}"),
    end: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}"),
    kind: Optional[str] = Query(None, pattern=r"^(profile|timeseries|other)$"),
    product_type: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    newest_first: bool = False,
) -> Dict[str, Any]:
    if dataset_id:
        unknown = [d for d in dataset_id if not get_dataset(d)]
        if unknown:
            raise HTTPException(404, f"Unknown dataset(s): {', '.join(unknown)}")
    if start and end and end < start:
        raise HTTPException(400, "End date is before start date")
    return catalog.search(catalog.SearchQuery(
        mission_id=mission_id, dataset_ids=dataset_id, target=target, start=start, end=end,
        kind=kind, product_type=product_type, text=q, limit=limit, offset=offset,
        newest_first=newest_first))


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
        fetched = []
        for i, it in enumerate(req.items):
            j.update(done=i, message=f"Downloading {it.product_id}")
            try:
                catalog.fetch_product(it.dataset_id, it.product_id)
                fetched.append(it.product_id)
            except net.LoginRequired:
                raise
            except net.ArchiveError as exc:
                j["errors"].append(f"{it.product_id}: {exc}")
        j.update(done=len(req.items), message=f"Downloaded {len(fetched)} of {len(req.items)}")
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
