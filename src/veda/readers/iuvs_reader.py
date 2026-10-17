"""MAVEN IUVS Level-2 retrievals (FITS, PDS Atmospheres iuvs_derived_bundle): stellar
occultations and, further down, periapse limb scans.

Occultations: one retrieval per file, on the levels of the ``retrieved_geometry`` table (ALTITUDE,
UTC_TIME, LATITUDE_PC, LONGITUDE_PC, SZA, LOCAL_TIME; 13 to 39 levels).  The
``number_density`` PROFILE and UNCERTAINTY are (level, species) arrays with the species
named in the ``species`` table (CO2, O2, O3); ``temperature`` and ``pressure`` have one
value per level.  NaN is the fill value.  The ``HLP_geometry`` table gives the half light
point, the representative point the team quotes for an occultation (Groller et al. 2018,
Table 3), kept as HLP_* metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .pds3_reader import Pds3Table


def read_iuvs_occultation(path: str, meta: Dict[str, object]) -> Pds3Table:
    from astropy.io import fits
    with fits.open(path) as h:
        g = h["retrieved_geometry"].data
        n_lev = len(g)
        cols: Dict[str, np.ndarray] = {}
        units: Dict[str, str] = {}
        for c in h["retrieved_geometry"].columns:
            if c.name not in ("UTC_TIME", "ET_TIME"):
                cols[c.name] = np.asarray(g[c.name], dtype=float)
                units[c.name] = c.unit or ""
        units.update(ALTITUDE="km", SZA="deg", LOCAL_TIME="hr")
        species = [str(s).strip().upper() for s in np.ravel(h["species"].data["ID"][0])]
        nd = h["number_density"]
        prof = np.asarray(nd.data["PROFILE"][0], dtype=float).reshape(n_lev, len(species))
        unc = np.asarray(nd.data["UNCERTAINTY"][0], dtype=float).reshape(n_lev, len(species))
        for i, sp in enumerate(species):
            cols[f"N_{sp}"], cols[f"SIGMA_N_{sp}"] = prof[:, i], unc[:, i]
            units[f"N_{sp}"] = units[f"SIGMA_N_{sp}"] = nd.columns["PROFILE"].unit or "cm-3"
        for ext in ("temperature", "pressure"):
            d, name = h[ext], ext.upper()
            cols[name] = np.asarray(d.data["PROFILE"][0], dtype=float)
            cols["SIGMA_" + name] = np.asarray(d.data["UNCERTAINTY"][0], dtype=float)
            units[name] = units["SIGMA_" + name] = d.columns["PROFILE"].unit or ""
        hlp = h["HLP_geometry"].data
        meta.update({k: float(hlp[k][0]) for k in hlp.columns.names if np.isfinite(hlp[k][0])})
        obs = h["Observation"].data
        meta["SOLAR_LONGITUDE"] = float(obs["SOLAR_LONGITUDE"][0])
        meta["ORBIT_NUMBER"] = int(obs["ORBIT_NUMBER"][0])
        text = {"UTC_TIME": [str(t).strip() for t in g["UTC_TIME"]]}
    meta["TABLE_FILE"] = path.replace("\\", "/").rsplit("/", 1)[-1]
    t = Pds3Table(label_path=path, table_path=path, metadata=meta, columns=cols, units=units)
    t.text_columns = text
    return t


# ------------------------------------------------------------------ periapse limb scans
# MAVEN IUVS Level-2 periapse files (l2/limb): up to 12 limb scans of one periapsis pass,
# each a profile of its own (archives/row_files.py).  DENSITY has per scan an ALT and a
# PROFILE (level, species) with RANDOM_UNC and SYSTEMATIC_UNC, each species on its own
# altitudes (CO2, N2, O); TEMPERATURE has a PROFILE on its ALT levels; GEOMETRY_RETRIEVAL
# gives each scan's LAT, LON, SZA and LOCAL_TIME.  Scans without a latitude were not retrieved.

ROW_TYPE = "IUVS limb scan: CO2, N2 and O density and temperature"


def _fits_of(path) -> Path:
    """The FITS file of a PDS4 label (or the path itself)."""
    import re
    path = Path(path)
    if path.suffix.lower() != ".xml":
        return path
    m = re.search(r"<file_name>\s*([^<]+?\.fits)\s*</file_name>", path.read_text(encoding="utf-8", errors="replace"))
    if not m:
        raise ValueError(f"{path.name} names no FITS file")
    return path.parent / m.group(1)


def read_file(path) -> Dict[str, object]:
    from astropy.io import fits
    with fits.open(str(_fits_of(path))) as h:
        sp = [str(s).strip().upper() for s in np.ravel(h["SPECIES"].data["ID"])]
        d, t, g = h["DENSITY"].data, h["TEMPERATURE"].data, h["GEOMETRY_RETRIEVAL"].data
        out: Dict[str, object] = {"rows": len(g), "species": sp,
                                  "ls": float(h["OBSERVATION"].data["SOLAR_LONGITUDE"][0])}
        for k in ("ALT", "PROFILE", "RANDOM_UNC", "SYSTEMATIC_UNC"):
            out["n_" + k] = np.asarray(d[k], dtype=float).reshape(len(d), -1, len(sp))
        for k in ("ALT", "PROFILE", "RANDOM_UNC", "SYSTEMATIC_UNC"):
            out["t_" + k] = np.asarray(t[k], dtype=float)
        for k in ("LAT", "LON", "SZA", "LOCAL_TIME"):
            out[k] = np.asarray(g[k], dtype=float)
    return out


def valid_rows(d) -> list:
    """Scans with a place and at least two CO2 densities."""
    co2 = d["species"].index("CO2")
    return [i for i in range(d["rows"]) if np.isfinite(d["LAT"][i])
            and np.isfinite(d["n_PROFILE"][i][:, co2]).sum() >= 2]


def row_geometry(d, row: int) -> Dict[str, Optional[float]]:
    def g(k):
        v = float(d[k][row])
        return v if np.isfinite(v) else None
    return {"latitude": g("LAT"), "lst": g("LOCAL_TIME"), "sza": g("SZA"), "ls": d["ls"]}


def _on(z, alt, val, log: bool):
    """``val`` given at ``alt`` put on the levels ``z``: exact at its own levels,
    interpolated between neighbouring levels of its own (in log for densities), empty
    outside them."""
    ok = np.isfinite(alt) & np.isfinite(val) & ((val > 0) if log else True)
    out = np.full(z.shape, np.nan)
    if ok.sum() == 0:
        return out
    a, v = alt[ok], val[ok]
    o = np.argsort(a)
    a, v = a[o], (np.log(v[o]) if log else v[o])
    inside = (z >= a[0]) & (z <= a[-1])
    out[inside] = np.interp(z[inside], a, v)
    return np.exp(out) if log else out


def row_profile(ds, prod, path, row: int):
    """One limb scan as an ObservationProfile: the levels of every species and of the
    temperature together, each quantity on the others' levels by interpolation between
    its own neighbouring levels (log for densities), never beyond its own range."""
    from ..core.models import ObservationProfile, ProvenanceRecord
    d = read_file(path)
    if row not in valid_rows(d):
        raise ValueError(f"{prod['product_id']}: scan {row} of {Path(path).name} holds no retrieved profile")
    sp = d["species"]
    na, nv = d["n_ALT"][row], d["n_PROFILE"][row]
    used = [np.where(np.isfinite(nv[:, k]), na[:, k], np.nan) for k in range(len(sp))]
    used.append(np.where(np.isfinite(d["t_PROFILE"][row]), d["t_ALT"][row], np.nan))
    z = np.concatenate(used)
    z = np.unique(z[np.isfinite(z)])[::-1]
    derived, unc, syst = {}, {}, {}
    for k, s in enumerate(sp):
        key = f"n_{s.lower()}_m3"
        derived[key] = _on(z, na[:, k], nv[:, k], True) * 1e6
        unc[key] = _on(z, na[:, k], d["n_RANDOM_UNC"][row][:, k], False) * 1e6
        syst[key] = _on(z, na[:, k], d["n_SYSTEMATIC_UNC"][row][:, k], False) * 1e6
    derived["number_density_m3"] = derived["n_co2_m3"]
    unc["number_density_m3"], syst["number_density_m3"] = unc["n_co2_m3"], syst["n_co2_m3"]
    t = _on(z, d["t_ALT"][row], d["t_PROFILE"][row], False)
    unc["temperature_k"] = unc["temperature_c"] = _on(z, d["t_ALT"][row], d["t_RANDOM_UNC"][row], False)
    syst["temperature_k"] = _on(z, d["t_ALT"][row], d["t_SYSTEMATIC_UNC"][row], False)
    geom = row_geometry(d, row)
    # altitudes and the geodetic latitude are on the IAU Mars ellipsoid: put on VEDA's sphere
    from ..archives.profiles import above_spheroid
    from ..core.registry import get_body
    body = get_body(ds.body_ids[0])
    a, f = ds.altitude_spheroid
    r, lat_c = above_spheroid(z, np.full(z.shape, geom["latitude"]), a, f)
    z_sphere = r - body.radius_km
    geom["latitude"] = float(np.median(lat_c))
    prof = ObservationProfile(
        observation_id=prod["product_id"], mission_id=ds.mission_id, body_id=ds.body_ids[0],
        instrument=ds.instrument, time_utc=prod.get("start_time") or "",
        latitude=geom["latitude"], longitude=float(d["LON"][row]), altitude_km=z_sphere,
        temperature_k=t, temperature_c=t - 273.15,
        provenance=ProvenanceRecord(mission_id=ds.mission_id, instrument=ds.instrument, product_level=ds.level,
                                    original_file=Path(path).name, archive_source=ds.archive,
                                    archive_url=prod.get("url", ""), doi_or_citation=ds.citation or ds.doi,
                                    retrieval_method=prod.get("product_type", "")),
        raw_attributes={"DATASET_ID": ds.id, "VOLUME": prod.get("volume"), "IUVS_SCAN": row,
                        "ALTITUDE_REFERENCE": f"a sphere of radius {body.radius_km:g} km (archive altitudes are above the spheroid a = {a:g} km, f = {f:.4g}; converted with the latitude)", "DENSITY_MOLAR_MASS": ds.density_molar_mass,
                        "TIME_NOTE": "the start of the periapsis segment; its 12 scans follow within about 22 minutes",
                        **{k.upper(): v for k, v in geom.items() if k != "latitude" and v is not None}},
        uncertainty=unc, systematic=syst)
    prof.derived.update(derived)
    return prof
