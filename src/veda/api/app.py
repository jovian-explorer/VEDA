"""Standalone FastAPI application for VEDA Planetary Science Data Laboratory.

Serves the VEDA frontend interface and REST API endpoints for multi-mission
spacecraft exploration, remote PDS/PSA/DARTS discovery, FITS image inspection,
and comparative planetary science analysis.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager

from ..updates import build_info

from ..config import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    CACHE_DIR,
    DATA_ROOT,
    EXPORT_DIR,
    LOG_DIR,
    SETTINGS,
    SETTINGS_PATH,
    ensure_dirs,
    frontend_dir,
    sampledata_dir,
)
from .archive_routes import citation_router, geometry_router, router as archive_router
from .product_routes import router as product_router
from .routes import router as veda_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    # Import the heavy scientific modules in the background (scipy.signal alone takes
    # several seconds), so the first profile opened is not slowed down by imports.
    import threading
    threading.Thread(target=_warm_imports, name="veda-warmup", daemon=True).start()
    yield


def _warm_imports() -> None:
    try:
        import importlib
        for mod in ("veda.analysis.wave_and_stability", "veda.analysis.thermo", "matplotlib.figure",
                    "veda.readers.product", "veda.geometry.compute"):
            importlib.import_module(mod)
        from ..parallel import warm_up
        warm_up()                     # start the worker processes (Settings > Performance)
    except Exception:  # noqa: BLE001 - warm-up is only an optimisation
        pass


def _save_settings() -> None:
    try:
        SETTINGS.save()
    except OSError as exc:
        raise HTTPException(500, f"The settings apply until VEDA is closed but could not be saved to "
                                 f"{SETTINGS_PATH}: {exc.strerror or exc}")


_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
MAX_REQUEST_BYTES = 640 * 1024 * 1024


def _cross_site(request: Request) -> bool:
    """Whether a request comes from a page of another website.  Browsers mark every
    request with Sec-Fetch-Site ("same-origin" for VEDA's own page, "none" for an
    address typed or a desktop window); older ones send Origin on cross-origin POSTs,
    which must then name this server.  Scripts and other programs send neither and are
    let through: only a web page can be made to send requests without the user knowing."""
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site not in ("same-origin", "none")
    if request.method in _SAFE_METHODS:
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return False
    from urllib.parse import urlsplit
    return origin == "null" or urlsplit(origin).netloc.lower() != (request.headers.get("host") or "").lower()


def create_app() -> FastAPI:
    ensure_dirs()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # The UI is served from this same origin, so no CORS headers are sent and other
    # websites cannot read the API's answers.  They could still send requests (a form
    # POST, an <img> GET) that change settings or start downloads, so requests from
    # another site are refused (see _cross_site).  The Host check blocks DNS-rebinding;
    # VEDA_ALLOWED_HOSTS adds more (for `veda-server --host 0.0.0.0`, e.g.
    # "myhost,192.168.1.20").
    @app.middleware("http")
    async def refuse_cross_site(request: Request, call_next):
        if request.url.path.startswith("/api/") and _cross_site(request):
            return JSONResponse({"detail": "Requests from other websites are not accepted."}, status_code=403)
        # The whole request is read into memory (uploads arrive base64-encoded in JSON), so
        # its size is limited before reading: a file of 200 MB and its companions fit.
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > MAX_REQUEST_BYTES:
            return JSONResponse({"detail": f"The request is larger than {MAX_REQUEST_BYTES // 2**20} MB; "
                                           "load fewer or smaller files at a time."}, status_code=413)
        return await call_next(request)

    extra_hosts = [h.strip() for h in os.environ.get("VEDA_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["127.0.0.1", "localhost", "testserver", *extra_hosts])

    # Mount VEDA multi-mission scientific router
    app.include_router(veda_router)
    app.include_router(archive_router)
    app.include_router(geometry_router)
    app.include_router(product_router)
    app.include_router(citation_router)

    @app.get("/api/health")
    def health_check() -> Dict[str, Any]:
        return {
            "status": "ok",
            "app": APP_TITLE,
            "name": APP_NAME,
            "version": APP_VERSION,
        }

    from ..core.registry import (
        LEAD_RESEARCHER,
        DATA_AVAILABILITY_STATEMENT,
        list_variables,
        list_data_portals,
        DATA_LICENSES,
    )

    @app.get("/api/meta")
    def meta() -> Dict[str, Any]:
        return {
            "app": {
                "name": APP_NAME,
                "title": APP_TITLE,
                "version": APP_VERSION,
            },
            "settings": SETTINGS.to_dict(),
            "system": {"cpu_count": os.cpu_count() or 1},
            "build": build_info(),
            "paths": {
                "data_root": str(DATA_ROOT),
                "cache": str(CACHE_DIR),
                "exports": str(EXPORT_DIR),
                "logs": str(LOG_DIR),
                "settings_file": str(SETTINGS_PATH),
            },
            "repository": "https://github.com/jovian-explorer/VEDA",
            "lead_researcher": LEAD_RESEARCHER,
            "data_availability": DATA_AVAILABILITY_STATEMENT,
            "variables": list_variables(),
            "data_portals": list_data_portals(),
            "licenses": DATA_LICENSES,
        }

    @app.post("/api/settings")
    async def update_settings(request: Request) -> Dict[str, Any]:
        if not (request.headers.get("content-type") or "").lower().startswith("application/json"):
            raise HTTPException(415, "Settings must be sent as JSON (Content-Type: application/json)")
        try:
            patch = await request.json()
        except ValueError:
            raise HTTPException(400, "Settings must be sent as a JSON object")
        if not isinstance(patch, dict):
            raise HTTPException(400, "Settings must be sent as a JSON object")
        try:
            SETTINGS.update(patch)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        _save_settings()
        return SETTINGS.to_dict()

    @app.get("/api/update")
    def update_check(force: bool = False) -> Dict[str, Any]:
        """This build and the latest published one (Settings > Network > check for updates)."""
        from .. import updates
        return updates.check(force=force)

    @app.post("/api/settings/reset")
    def reset_settings() -> Dict[str, Any]:
        SETTINGS.reset()
        _save_settings()
        return SETTINGS.to_dict()

    @app.get("/api/exports")
    def list_exports() -> Dict[str, Any]:
        ensure_dirs()
        files = []
        for p in EXPORT_DIR.glob("*"):
            if p.is_file():
                files.append({
                    "name": p.name,
                    "size_bytes": p.stat().st_size,
                    "modified": p.stat().st_mtime,
                })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"exports": files}

    @app.get("/api/exports/{filename}")
    def get_export(filename: str):
        safe = Path(filename).name
        p = EXPORT_DIR / safe
        if not p.is_file():
            raise HTTPException(404, f"Export file {safe} not found")
        return FileResponse(p, filename=safe)

    @app.delete("/api/exports/{filename}")
    def delete_export(filename: str) -> Dict[str, Any]:
        safe = Path(filename).name
        p = EXPORT_DIR / safe
        if not p.is_file():
            raise HTTPException(404, f"Export file {safe} not found")
        p.unlink()
        return {"deleted": safe}

    @app.post("/api/reveal-folder")
    def reveal_folder(which: Literal["exports", "cache", "logs", "data"] = "exports") -> Dict[str, Any]:
        target = {"exports": EXPORT_DIR, "cache": CACHE_DIR, "logs": LOG_DIR, "data": DATA_ROOT}[which]
        ensure_dirs()
        try:
            if os.name == "nt":
                os.startfile(target)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(target)])
        except Exception as exc:
            raise HTTPException(500, f"Could not reveal folder {target}: {exc}")
        return {"opened": str(target)}

    # Static frontend assets
    fe = frontend_dir()
    if fe.is_dir():
        app.mount("/", StaticFiles(directory=str(fe), html=True), name="frontend")
    else:
        @app.get("/")
        def _no_frontend() -> JSONResponse:
            return JSONResponse(
                {"error": "Frontend assets not found", "looked_in": str(fe)},
                status_code=500,
            )

    return app


app = create_app()
