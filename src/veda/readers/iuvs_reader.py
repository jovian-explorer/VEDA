"""MAVEN IUVS Level-2 stellar occultation retrievals (FITS, PDS Atmospheres iuvs_derived_bundle).

One retrieval per file, on the levels of the ``retrieved_geometry`` table (ALTITUDE,
UTC_TIME, LATITUDE_PC, LONGITUDE_PC, SZA, LOCAL_TIME; 13 to 39 levels).  The
``number_density`` PROFILE and UNCERTAINTY are (level, species) arrays with the species
named in the ``species`` table (CO2, O2, O3); ``temperature`` and ``pressure`` have one
value per level.  NaN is the fill value.  The ``HLP_geometry`` table gives the half light
point, the representative point the team quotes for an occultation (Groller et al. 2018,
Table 3), kept as HLP_* metadata.
"""
from __future__ import annotations

from typing import Dict

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
