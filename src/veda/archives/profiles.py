"""Turn a downloaded archive product into an ObservationProfile."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np

from ..analysis.atmospheric import compute_atmospheric_diagnostics
from ..core.models import ObservationProfile, ProvenanceRecord
from ..core.registry import get_body
from ..readers.pds3_reader import match_column, read_pds3_table
from .catalog import fetch_product, get_product
from .datasets import Dataset, get_dataset


def _key(tbl, name) -> Optional[str]:
    """Column for ``name``; a tuple/list gives alternatives tried in order."""
    if not name:
        return None
    for cand in ([name] if isinstance(name, str) else name):
        key = match_column(tbl.columns.keys(), cand)
        if key is not None:
            return key
    return None


def _col(tbl, name) -> Optional[np.ndarray]:
    key = _key(tbl, name)
    if key is None:
        return None
    arr = np.asarray(tbl.columns[key], dtype=float)
    return arr if np.isfinite(arr).any() else None


_COLUMN_UNITS: Dict[str, str] = {}     # set per product from the data set's catalogue units


def _unit(tbl, name) -> str:
    key = _key(tbl, name)
    unit = (tbl.units.get(key, "") if key else "") or _COLUMN_UNITS.get((key or "").upper().strip('"'), "")
    return unit.upper().replace('"', "").strip()


def _scale(unit: str) -> float:
    """Leading power-of-ten factor, e.g. '10^6 PER CUBIC METER' -> 1e6."""
    import re as _re
    m = _re.search(r"10\s*(?:\^|\*\*)\s*([+-]?\d+)", unit) or _re.search(r"\b1E([+-]?\d+)\b", unit)
    return 10.0 ** int(m.group(1)) if m else 1.0


def _to_hpa(values: np.ndarray, unit: str) -> np.ndarray:
    u = unit.replace(" ", "")
    if "HPA" in u or "MBAR" in u or "MILLIBAR" in u:
        return values
    if u in ("BAR", "BARS"):
        return values * 1000.0
    return values / 100.0               # PASCAL (the PDS radio-science default)


def _to_per_cm3(values: np.ndarray, unit: str) -> np.ndarray:
    import re as _re
    values = values * _scale(unit)      # e.g. "10^6 PER CUBIC METER"
    # Word-level test: squeezing out spaces made "CUBIC METER" contain "CM".
    if "CENTIMETER" in unit or _re.search(r"(?<![A-Z])CM(?![A-Z])", unit):
        return values
    return values / 1e6                 # per cubic metre -> per cm^3


def _to_kelvin(values: np.ndarray, unit: str) -> np.ndarray:
    return values + 273.15 if "CELSIUS" in unit or unit in ("C", "DEGC") else values


def _sigma(tbl, name) -> Optional[np.ndarray]:
    """Uncertainty columns are skipped by match_column, so look them up directly."""
    if not name:
        return None
    for want in ([name] if isinstance(name, str) else name):
        want = want.upper().replace("_", " ")
        for k, v in tbl.columns.items():
            u = k.upper().replace("_", " ").strip('"')
            if u.startswith(want) and ("MEDIUM" in u or not any("MEDIUM" in c.upper() for c in tbl.columns)):
                arr = np.asarray(v, dtype=float)
                if np.isfinite(arr).any():
                    return arr
    return None


def load_profile(dataset_id: str, product_id: str, download: bool = True) -> ObservationProfile:
    ds = get_dataset(dataset_id)
    prod = get_product(dataset_id, product_id)
    if ds is None or prod is None:
        raise LookupError(f"Unknown product {dataset_id}/{product_id}")
    if prod["kind"] != "profile":
        raise ValueError(f"{product_id} is a {prod['product_type']}, not a vertical profile")
    label = fetch_product(dataset_id, product_id) if download else None
    return profile_from_label(ds, prod, Path(label))


def profile_from_label(ds: Dataset, prod: Dict, label: Path) -> ObservationProfile:
    cols = ds.profile_columns
    body = get_body(ds.body_ids[0])
    if label.suffix.lower() == ".xml":
        from ..readers.pds4_reader import read_pds4_table
        tbl = read_pds4_table(str(label))
    else:
        tbl = read_pds3_table(str(label))
    _COLUMN_UNITS.clear()
    _COLUMN_UNITS.update({k.upper(): v for k, v in ds.column_units.items()})
    split = prod.get("split")
    if split:
        # Keep only this product's rows of a multi-profile table.
        mask = np.ones(tbl.row_count(), dtype=bool)
        for col, val in split.items():
            if col in tbl.text_columns:
                mask &= np.array([v == val for v in tbl.text_columns[col]])
            else:
                mask &= np.isclose(tbl.columns[col], float(val))
        tbl.columns = {k: v[mask] for k, v in tbl.columns.items()}
        tbl.text_columns = {k: [x for x, m in zip(v, mask) if m] for k, v in tbl.text_columns.items()}

    z = _col(tbl, cols.get("altitude"))
    if z is not None:
        z_unit = _unit(tbl, cols.get("altitude"))
        if z_unit in ("M", "METER", "METERS", "METRE", "METRES"):
            z = z / 1000.0            # e.g. Huygens HASI gives altitude in metres
    if z is None:
        r = _col(tbl, cols.get("radius"))
        if r is None:
            raise ValueError(f"{label.name}: no altitude or radius column")
        r_unit = _unit(tbl, cols.get("radius"))
        if "METER" in r_unit and "KILO" not in r_unit:
            r = r / 1000.0            # e.g. MGS radio science gives RADIUS in metres
        z = r - body.radius_km

    # Units come from the label, so Pa/hPa/bar and m^-3/cm^-3 are all handled.
    t_unit = _unit(tbl, cols.get("temperature"))
    p_unit = _unit(tbl, cols.get("pressure"))
    ne_unit = _unit(tbl, cols.get("electron_density"))
    t_k = _col(tbl, cols.get("temperature"))
    if t_k is not None:
        t_k = _to_kelvin(t_k, t_unit)
    p = _col(tbl, cols.get("pressure"))
    p_hpa = _to_hpa(p, p_unit) if p is not None else None
    ne = _col(tbl, cols.get("electron_density"))
    ne_cm3 = _to_per_cm3(ne, ne_unit) if ne is not None else None
    n = _col(tbl, cols.get("number_density"))

    unc: Dict[str, np.ndarray] = {}
    s = _sigma(tbl, cols.get("temperature_sigma"))
    if s is not None:
        unc["temperature_k"] = s
        unc["temperature_c"] = s
    s = _sigma(tbl, cols.get("pressure_sigma"))
    if s is not None:
        unc["pressure_hpa"] = _to_hpa(s, p_unit)
    s = _sigma(tbl, cols.get("electron_density_sigma"))
    if s is not None:
        sig_key = next((k for k in tbl.columns if k.upper().strip('"').startswith(("SIGMA ELECTRON", "NOISE LEVEL ELECTRON"))), None)
        unc["electron_density_cm3"] = _to_per_cm3(s, (tbl.units.get(sig_key, "") or ne_unit).upper())

    track: Dict[str, np.ndarray] = {}
    for key in ("latitude", "longitude", "sza", "lst"):
        a = _col(tbl, cols.get(key))
        if a is not None:
            track[key] = a
    et = _col(tbl, cols.get("et"))
    if et is not None:
        track["et"] = et
        track["time_s"] = et - np.nanmin(et)

    lat = track.get("latitude")
    lon = track.get("longitude")
    prof = ObservationProfile(
        observation_id=prod["product_id"],
        mission_id=ds.mission_id,
        body_id=body.id,
        instrument=ds.instrument,
        time_utc=prod.get("start_time") or "",
        latitude=float(np.nanmedian(lat)) if lat is not None else None,
        longitude=float(np.nanmedian(lon)) if lon is not None else None,
        altitude_km=z,
        pressure_hpa=p_hpa,
        temperature_k=t_k,
        temperature_c=t_k - 273.15 if t_k is not None else None,
        electron_density_cm3=ne_cm3,
        refractivity=_col(tbl, cols.get("refractivity")),
        provenance=ProvenanceRecord(
            mission_id=ds.mission_id, instrument=ds.instrument,
            product_level=ds.level, original_file=label.name,
            archive_source=ds.archive, archive_url=prod["url"],
            doi_or_citation=ds.citation or ds.doi,
            retrieval_method=prod["product_type"],
        ),
        raw_attributes={**tbl.metadata, "DATASET_ID": ds.id, "VOLUME": prod["volume"]},
        uncertainty=unc,
        track=track,
    )
    if n is not None:
        prof.derived["number_density_m3"] = n
    for key, (col, sig) in ds.extra_variables.items():
        v = _col(tbl, col)
        if v is not None:
            prof.derived[key] = v
            s = _col(tbl, sig) if sig else None
            if s is not None:
                prof.uncertainty[key] = s
    prof.derived.update(compute_atmospheric_diagnostics(prof, body))
    return prof
