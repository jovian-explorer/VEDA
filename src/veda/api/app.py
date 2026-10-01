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
from .archive_routes import geometry_router, router as archive_router
from .routes import router as veda_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    yield


def create_app() -> FastAPI:
    ensure_dirs()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # The UI is served from this same origin, so no CORS headers are sent:
    # other websites open in the browser cannot call this unauthenticated API.
    # The Host check blocks DNS-rebinding; VEDA_ALLOWED_HOSTS adds more (for
    # `veda-server --host 0.0.0.0`, e.g. "myhost,192.168.1.20").
    extra_hosts = [h.strip() for h in os.environ.get("VEDA_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["127.0.0.1", "localhost", "testserver", *extra_hosts])

    # Mount VEDA multi-mission scientific router
    app.include_router(veda_router)
    app.include_router(archive_router)
    app.include_router(geometry_router)

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
        SETTINGS.save()
        return SETTINGS.to_dict()

    @app.post("/api/settings/reset")
    def reset_settings() -> Dict[str, Any]:
        SETTINGS.reset()
        SETTINGS.save()
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

    @app.get("/api/reveal-folder")
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
