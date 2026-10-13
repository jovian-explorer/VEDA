"""Universal file ingestion: FITS/camera images and tabular soundings (PDS3, CSV, ASCII)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..analysis.atmospheric import compute_atmospheric_diagnostics
from ..analysis.solar_geometry import circular_median
from ..core.models import ObservationProfile, ProvenanceRecord
from ..core.registry import get_body
from ..readers.fits_reader import load_fits_image
from ..readers.pds3_reader import Pds3Table, read_any_table


IMAGE_SUFFIXES = (".fit", ".fits", ".fts", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


def _profile_from_roles(file_path: Path, b, tbl: Pds3Table, roles: Dict[str, Dict[str, str]],
                        mission_id: Optional[str], instrument: Optional[str],
                        time_utc: Optional[str]) -> Tuple[ObservationProfile, Pds3Table]:
    by_role: Dict[str, np.ndarray] = {}
    for col, spec in roles.items():
        role, unit = (spec or {}).get("role"), (spec or {}).get("unit")
        if not role:
            continue
        if role not in ROLE_UNITS:
            raise ValueError(f"Unknown role {role!r} for column {col!r}")
        if col not in tbl.columns:
            raise ValueError(f"{file_path.name} has no column {col!r}")
        unit = unit or ROLE_UNITS[role][0]
        if unit not in ROLE_UNITS[role]:
            raise ValueError(f"{unit!r} is not a unit for {role} (use {', '.join(ROLE_UNITS[role])})")
        by_role[role] = to_standard(role, tbl.columns[col], unit, b)
    z = by_role.get("altitude", by_role.get("radius"))
    if z is None:
        raise ValueError("Choose the column that holds altitude or radius")
    if not any(k in by_role for k in ("temperature", "pressure", "electron_density", "number_density", "mass_density",
                                      "refractivity")):
        raise ValueError("Choose at least one measured column (temperature, pressure, electron, number or mass "
                         "density, refractivity)")
    t_k = by_role.get("temperature")
    p = by_role.get("pressure")
    for a in (t_k, p):
        if a is not None:
            a[a <= 0] = np.nan                       # absolute T and p are positive
    unc = {k: by_role[f"{k}_sigma"] for k in ("temperature", "pressure", "electron_density")
           if f"{k}_sigma" in by_role}
    unc = {{"temperature": "temperature_k", "pressure": "pressure_hpa",
            "electron_density": "electron_density_cm3"}[k]: v for k, v in unc.items()}
    if "temperature_k" in unc:
        unc["temperature_c"] = unc["temperature_k"]
    track = {k: by_role[k] for k in ("latitude", "longitude", "lst", "sza") if k in by_role}
    med = lambda a: float(np.nanmedian(a)) if a is not None and np.isfinite(a).any() else None  # noqa: E731
    z_ref = (f"a sphere of radius {b.radius_km:g} km (from the radius column)" if "radius" in by_role
             else "as given in the file")
    prof = ObservationProfile(
        observation_id=file_path.stem, mission_id=mission_id or "user_imported", body_id=b.id,
        instrument=instrument or "Loaded file", time_utc=time_utc or _file_time(tbl) or "",
        latitude=med(track.get("latitude")), longitude=circular_median(track.get("longitude"), 360.0),
        altitude_km=z, pressure_hpa=p, temperature_k=t_k,
        temperature_c=t_k - 273.15 if t_k is not None else None,
        electron_density_cm3=by_role.get("electron_density"), refractivity=by_role.get("refractivity"),
        provenance=ProvenanceRecord(
            mission_id=mission_id or "user_imported", instrument=instrument or "Loaded file",
            product_level="User file", original_file=file_path.name, archive_source="Loaded from this computer",
            archive_url="", doi_or_citation="", retrieval_method="Columns assigned when loading"),
        raw_attributes={**tbl.metadata, "ALTITUDE_REFERENCE": z_ref, "COLUMN_ROLES": roles},
        uncertainty=unc, track=track,
    )
    if "number_density" in by_role:
        prof.derived["number_density_m3"] = by_role["number_density"]
    if "mass_density" in by_role:
        # measured mass density (accelerometer, entry and occultation profiles): compared as
        # "Mass density (archive)", like the archive data sets that publish one
        rho = by_role["mass_density"]
        rho[rho <= 0] = np.nan
        prof.derived["density_measured"] = rho
        if "mass_density_sigma" in by_role:
            prof.uncertainty["density_measured"] = by_role["mass_density_sigma"]
    # local time, zenith angle and Ls from the time and position, as for archive profiles:
    # loaded files had none, and comparisons filtered on them left loaded files out
    from ..archives.profiles import _add_solar_geometry
    _add_solar_geometry(prof, None)
    prof.derived.update(compute_atmospheric_diagnostics(prof, b))
    return prof, tbl


def _file_time(tbl: Pds3Table) -> str:
    """Observation start time from the label or header, '' if it gives none."""
    for k in ("START_TIME", "OBSERVATION_TIME", "DATE_OBS", "DATE-OBS", "TIME_UTC"):
        v = str(tbl.metadata.get(k) or "").strip().strip('"')
        if v and v.upper() not in ("N/A", "UNK", "NULL"):
            return v
    return ""


def ingest_planetary_file(
    file_path: Path,
    body_id: str = "venus",
    mission_id: Optional[str] = None,
    instrument: Optional[str] = None,
    decimate_max: int = 0,
    roles: Optional[Dict[str, Dict[str, str]]] = None,
    time_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest and parse any planetary science file (FITS image, PDS3, CSV, or ASCII table)."""
    b = get_body(body_id) or get_body("venus")
    suffix = file_path.suffix.lower()

    # 1. Astronomical Camera Image or FITS File
    if suffix in IMAGE_SUFFIXES:
        fits_data = load_fits_image(str(file_path))
        return {
            "type": "image",
            "filename": file_path.name,
            "observation_id": file_path.stem,
            "body_id": b.id,
            "mission_id": mission_id or "user_imported",
            "instrument": instrument or (str(fits_data.header.get("INSTRUME", "Camera")) if suffix in (".fit", ".fits", ".fts") else "Camera"),
            # (FITS DATE is when the file was written, not the observation)
            "time_utc": time_utc or str(fits_data.header.get("DATE-OBS") or ""),
            "shape": [fits_data.stats.get("shape_y", 0), fits_data.stats.get("shape_x", 0)],
            "stats": fits_data.stats,
            "header": fits_data.header,
            "local_path": str(file_path),
        }

    prof, tbl = build_profile(file_path, b, mission_id=mission_id, instrument=instrument, roles=roles,
                              time_utc=time_utc)
    return {
        "type": "profile",
        "filename": file_path.name,
        "observation_id": file_path.stem,
        "body_id": b.id,
        "mission_id": mission_id or "user_imported",
        "instrument": prof.instrument,
        "columns_detected": list(tbl.columns.keys()),
        "data": prof.to_dict(decimate_max=decimate_max),
    }


# Column roles a user can assign when loading a file, and the units each accepts.
ROLE_UNITS: Dict[str, Tuple[str, ...]] = {
    "altitude": ("km", "m"),
    "radius": ("km", "m"),
    "temperature": ("K", "C"),
    "temperature_sigma": ("K",),
    "pressure": ("hPa", "Pa", "bar", "mbar", "kPa"),
    "pressure_sigma": ("hPa", "Pa", "bar", "mbar", "kPa"),
    "electron_density": ("cm-3", "m-3"),
    "electron_density_sigma": ("cm-3", "m-3"),
    "number_density": ("m-3", "cm-3"),
    "refractivity": ("N-units",),
    "mass_density": ("kg/m3", "g/cm3", "kg/km3"),
    "mass_density_sigma": ("kg/m3", "g/cm3", "kg/km3"),
    "latitude": ("deg",),
    "longitude": ("deg",),
    "lst": ("h",),
    "sza": ("deg",),
}


def unit_from_label(role: str, label_unit: str) -> Optional[str]:
    """The ROLE_UNITS entry a label's unit string means, or None if it does not say."""
    u = (label_unit or "").upper().replace(" ", "").replace('"', "")
    if not u or u in ("N/A", "NONE", "UNK", "UNITLESS", "DIMENSIONLESS"):
        return None
    if role in ("altitude", "radius"):
        return "m" if u in ("M", "METER", "METERS", "METRE", "METRES") else "km" if "K" in u else None
    if role.startswith("temperature"):
        return "C" if u in ("C", "DEGC", "CELSIUS", "DEGREECELSIUS", "°C") else "K"
    if role.startswith("pressure"):
        # (test HPA before PA: "HPA" contains "PA"; that mistake divided hPa by 100)
        if "HPA" in u or "HECTOPASCAL" in u:
            return "hPa"
        if "KPA" in u or "KILOPASCAL" in u:
            return "kPa"
        if "MBAR" in u or "MILLIBAR" in u:
            return "mbar"
        if "BAR" in u:
            return "bar"
        if "PA" in u or "PASCAL" in u:
            return "Pa"
        return None
    if role.startswith("mass_density"):
        if "KM" in u or "KILOMET" in u:
            return "kg/km3"
        if u.startswith("G") or "GRAM/CM" in u or "G/CM" in u:
            return "g/cm3"
        if "KG" in u or "KILOGRAM" in u:
            return "kg/m3"
        return None
    if "density" in role:
        # "1 PER CUBIC METER" (MEX radio science) contains "CM" and was read as cm-3
        if u.startswith("10^6") or "CENTIMET" in u or "CM" in u.replace("CUBICM", ""):
            return "cm-3"
        if "M" in u or "METER" in u:
            return "m-3"
    return None


def to_standard(role: str, values: np.ndarray, unit: str, body) -> np.ndarray:
    """Convert a column to VEDA's units: km (altitude above the body's reference radius),
    K, hPa, cm^-3 (electrons), m^-3 (neutral number density), degrees, hours."""
    v = np.asarray(values, dtype=float)
    if role == "altitude":
        return v / 1000.0 if unit == "m" else v
    if role == "radius":
        return (v / 1000.0 if unit == "m" else v) - body.radius_km
    if role == "temperature":
        return v + 273.15 if unit == "C" else v
    if role.startswith("pressure"):
        return v * {"Pa": 0.01, "kPa": 10.0, "bar": 1000.0, "mbar": 1.0, "hPa": 1.0}[unit]
    if role.startswith("electron_density"):
        return v * 1e-6 if unit == "m-3" else v
    if role == "number_density":
        return v * 1e6 if unit == "cm-3" else v
    if role.startswith("mass_density"):
        return v * {"kg/m3": 1.0, "g/cm3": 1000.0, "kg/km3": 1e-9}[unit]
    return v


def _name_unit(role: str, column: str) -> Optional[str]:
    """A unit at the end of a column name (ALT_M, PRESS_PA, T_K), if it is one of the role's:
    ALT_M was read as kilometres and PRESS_PA as hPa."""
    name = column.upper().strip('"').replace(" ", "_")
    tail = name.rsplit("_", 1)[1] if "_" in name else ""
    return next((u for u in ROLE_UNITS.get(role, ()) if u.upper() == tail), None)


def suggest_roles(tbl: Pds3Table) -> Dict[str, Dict[str, Optional[str]]]:
    """Column -> {role, unit} guessed from names and label units (a starting point the
    user can change)."""
    import re as _re
    patterns = [
        ("temperature_sigma", r"(SIGMA|ERR|DEV|UNC).*TEMP|TEMP.*(SIGMA|ERR|DEV|UNC)"),
        ("pressure_sigma", r"(SIGMA|ERR|DEV|UNC).*PRES|PRES.*(SIGMA|ERR|DEV|UNC)"),
        ("electron_density_sigma", r"(SIGMA|ERR|DEV|UNC|NOISE).*(ELEC|NE\b)|(ELEC|EDEN).*(SIGMA|ERR|DEV|UNC)"),
        ("electron_density", r"ELECTRON|^NE$|^N_E$|EDEN|ELECDEN"),
        ("number_density", r"NUMBER.?DENS|^N$|NUM.?DENS|TOTAL.?DENS"),
        ("refractivity", r"REFRACTIV|^N_UNITS$"),
        ("mass_density_sigma", r"(SIGMA|ERR|DEV|UNC).*(RHO|MASS.?DENS)|(RHO|MASS.?DENS).*(SIGMA|ERR|DEV|UNC)"),
        ("mass_density", r"^RHO|MASS.?DENS"),
        ("temperature", r"^T$|TEMP|^T_K$|^TK$"),
        ("pressure", r"^P$|PRESS|^P_(HPA|PA|BAR)$"),
        ("radius", r"RADIUS|^R$|RADIAL"),
        ("altitude", r"ALT|HEIGHT|^Z$|^H$"),
        ("latitude", r"^LAT|LATITUDE"),
        ("longitude", r"^LON|LONGITUDE"),
        ("lst", r"LOCAL.?(SOLAR.?)?TIME|^LST$|^LT$"),
        ("sza", r"ZENITH|^SZA$"),
    ]
    out: Dict[str, Dict[str, Optional[str]]] = {}
    taken = set()
    guessed = set()                 # columns whose unit neither the label nor the values gave
    # the nominal retrieval first (Akatsuki gives LOWER, MEDIUM and HIGHER variants)
    for col in sorted(tbl.columns, key=lambda c: not _re.search("MEDIUM|NOMINAL", c.upper())):
        name = col.upper().strip('"').replace(" ", "_")
        # match on the quantity, not a note in brackets: "PRESSURE (LOWER TEMPERATURE
        # AT BOUNDARY)" was offered as the temperature
        quantity = name.split("(")[0].rstrip("_") or name
        for role, rx in patterns:
            if role in taken or not _re.search(rx, quantity):
                continue
            unit = unit_from_label(role, tbl.units.get(col, "")) if role in ROLE_UNITS else None
            if unit is None and role in ROLE_UNITS:
                unit = _name_unit(role, name)
            vals = np.asarray(tbl.columns[col], dtype=float)
            finite = vals[np.isfinite(vals)]
            if unit is None and finite.size:
                # values decide only where they cannot be wrong
                if role == "temperature":
                    unit = "C" if np.nanmin(finite) < 0 else "K"
                elif role in ("altitude", "radius"):
                    unit = "km"
            if unit is None:
                guessed.add(col)
            out[col] = {"role": role, "unit": unit or (ROLE_UNITS.get(role, (None,))[0])}
            taken.add(role)
            break
    # An uncertainty column whose unit the file does not give is in its quantity's unit
    for col, r in out.items():
        if col in guessed and r["role"].endswith("_sigma"):
            base = next((v["unit"] for v in out.values() if v["role"] == r["role"][:-6]), None)
            if base in ROLE_UNITS[r["role"]]:
                r["unit"] = base
    if "radius" in taken and "altitude" in taken:          # one vertical coordinate
        # the geometric one: a geopotential height is not an altitude (3 km lower at 100 km
        # on Mars) and would not line up with the archive profiles, which use the radius
        alt = next(c for c, r in out.items() if r["role"] == "altitude")
        drop = "altitude" if "GEOPOTENTIAL" in alt.upper() else "radius"
        for col, r in list(out.items()):
            if r["role"] == drop:
                del out[col]
    return {c: out[c] for c in tbl.columns if c in out}


def build_profile(file_path: Path, b, mission_id: Optional[str] = None,
                  instrument: Optional[str] = None, roles: Optional[Dict[str, Dict[str, str]]] = None,
                  time_utc: Optional[str] = None) -> Tuple[ObservationProfile, Pds3Table]:
    """Parse a tabular sounding into an ObservationProfile with derived diagnostics.

    ``roles`` maps column name -> {"role": ..., "unit": ...} as chosen when loading
    the file (see ROLE_UNITS); without it the roles are guessed (suggest_roles).
    """
    tbl = read_any_table(str(file_path))
    if not tbl.columns:
        raise ValueError(f"No numeric columns could be extracted from {file_path.name}")
    if roles is not None:
        return _profile_from_roles(file_path, b, tbl, roles, mission_id, instrument, time_utc)
    roles = suggest_roles(tbl)
    if not any(r["role"] in ("altitude", "radius") for r in roles.values()):
        found = ", ".join(tbl.columns.keys()) or "none"
        hint = (" If this is a PDS3 .tab file, select it together with its .lbl label."
                if all(k.startswith("COL_") for k in tbl.columns) else "")
        raise ValueError(
            "No altitude column found (looked for ALTITUDE, ALT, HEIGHT, Z or RADIUS; "
            f"columns in the file: {found}).{hint}")
    return _profile_from_roles(file_path, b, tbl, roles, mission_id, instrument, time_utc)
