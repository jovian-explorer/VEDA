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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    CACHE_DIR,
    EXPORT_DIR,
    SETTINGS,
    ensure_dirs,
    frontend_dir,
    sampledata_dir,
)
from .routes import router as veda_router


def create_app() -> FastAPI:
    ensure_dirs()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount VEDA multi-mission scientific router
    app.include_router(veda_router)

    @app.on_event("startup")
    def _startup() -> None:
        ensure_dirs()

    @app.get("/api/health")
    def health_check() -> Dict[str, Any]:
        return {
            "status": "ok",
            "app": APP_TITLE,
            "name": APP_NAME,
            "version": APP_VERSION,
        }

    @app.get("/api/meta")
    def meta() -> Dict[str, Any]:
        return {
            "app": {
                "name": APP_NAME,
                "title": APP_TITLE,
                "version": APP_VERSION,
            },
            "settings": SETTINGS.to_dict(),
        }

    @app.post("/api/settings")
    async def update_settings(request: Request) -> Dict[str, Any]:
        try:
            patch = await request.json()
            for k, v in patch.items():
                if hasattr(SETTINGS, k):
                    setattr(SETTINGS, k, v)
            SETTINGS.save()
            return SETTINGS.to_dict()
        except Exception as exc:
            raise HTTPException(400, f"Invalid settings payload: {exc}")

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
    def reveal_folder(which: Literal["exports", "cache"] = "exports") -> Dict[str, Any]:
        target = EXPORT_DIR if which == "exports" else CACHE_DIR
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
