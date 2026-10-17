"""Juno MWR ammonia and water distributions (JNOMWR_2100, NASA PDS Atmospheres Node).

Each NH3A / H2OA file is a CSV table: a header row (``pressure_bar``, ``PC_lat-49.3``, ...),
then one row per pressure level (0.1 to 198 bar) with the mole fraction at each
planetocentric latitude.  The NH3U / H2OU file of the same name holds the 1-sigma.  The
files are composites of the first perijoves (Li et al. 2017, 2020).  Each latitude column
is offered as a profile of its own (archives/row_files.py): it has pressure levels only,
no altitudes, so it is compared on pressure.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

ROW_TYPE = "Juno MWR mole fraction profile at one latitude"

_VAR = {"NH3": "nh3_ppm", "H2O": "h2o_ppm"}


def _csv(path: Path):
    rows = list(csv.reader(path.read_text(encoding="utf-8", errors="replace").splitlines()))
    head = [h.strip() for h in rows[0]]

    def num(c):
        try:
            return float(c)
        except ValueError:
            return np.nan
    a = np.array([[num(c) for c in r] for r in rows[1:] if len(r) == len(head)], dtype=float)
    return head, a


def read_file(path) -> Dict[str, Any]:
    """The table of a NH3A or H2OA label (its CSV next to it) and of its uncertainty file."""
    path = Path(path)
    data = path.with_suffix(".CSV") if path.with_suffix(".CSV").exists() else path.with_suffix(".csv")
    head, a = _csv(data)
    lats = [float(h.replace("PC_lat", "")) for h in head[1:]]
    species = "NH3" if "NH3" in path.name.upper() else "H2O"
    out = {"rows": len(lats), "lat": lats, "p_bar": a[:, 0], "x": a[:, 1:], "species": species, "sigma": None}
    u = data.with_name(data.name.replace(f"{species}A", f"{species}U"))
    if u.exists():
        _, b = _csv(u)
        if b.shape == a.shape:
            out["sigma"] = b[:, 1:]
    return out


def valid_rows(d) -> List[int]:
    return [j for j in range(d["rows"]) if np.isfinite(d["x"][:, j]).sum() >= 2]


def row_geometry(d, row: int) -> Dict[str, Optional[float]]:
    return {"latitude": d["lat"][row], "lst": None, "sza": None, "ls": None}


def row_profile(ds, prod, path, row: int):
    from ..core.models import ObservationProfile, ProvenanceRecord
    from .catalog import fetch_product
    d = read_file(path)
    if d["sigma"] is None:
        # the uncertainty file, a product of its own: downloaded next to this one
        sp = d["species"]
        try:
            fetch_product(ds.id, prod.get("file_product_id", "").replace(f"{sp}A", f"{sp}U"))
            d = read_file(path)
        except Exception:  # noqa: BLE001 - the profile without its 1-sigma
            pass
    if row not in valid_rows(d):
        raise ValueError(f"{prod['product_id']}: column {row} of {Path(path).name} holds no profile")
    key = _VAR[d["species"]]
    p_hpa = d["p_bar"] * 1000.0
    prof = ObservationProfile(
        observation_id=prod["product_id"], mission_id=ds.mission_id, body_id=ds.body_ids[0],
        instrument=ds.instrument, time_utc=prod.get("start_time") or "", latitude=d["lat"][row], longitude=None,
        altitude_km=np.full(p_hpa.shape, np.nan), pressure_hpa=p_hpa,
        provenance=ProvenanceRecord(mission_id=ds.mission_id, instrument=ds.instrument, product_level=ds.level,
                                    original_file=Path(path).name, archive_source=ds.archive,
                                    archive_url=prod.get("url", ""), doi_or_citation=ds.citation or ds.doi,
                                    retrieval_method=prod.get("product_type", "")),
        raw_attributes={"DATASET_ID": ds.id, "VOLUME": prod.get("volume"), "MWR_LATITUDE_COLUMN": row,
                        "ALTITUDE_REFERENCE": "none: pressure levels only (compare on pressure)",
                        "TIME_NOTE": f"composite of the perijoves from {prod.get('start_time', '')[:10]} "
                                     f"to {prod.get('stop_time', '')[:10]}; zonal, no longitude"})
    prof.derived[key] = d["x"][:, row] * 1e6
    if d["sigma"] is not None:
        prof.uncertainty[key] = d["sigma"][:, row] * 1e6
    return prof
