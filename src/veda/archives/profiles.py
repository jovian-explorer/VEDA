"""Turn a downloaded archive product into an ObservationProfile."""
from __future__ import annotations

from pathlib import Path
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..analysis.atmospheric import compute_atmospheric_diagnostics
from ..analysis.solar_geometry import circular_median
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
    u = unit.upper().replace(" ", "")
    if "HPA" in u or "HECTOPASCAL" in u or "MBAR" in u or "MILLIBAR" in u:
        return values
    if u in ("BAR", "BARS"):
        return values * 1000.0
    if u in ("KPA", "KILOPASCAL", "KILOPASCALS"):
        return values * 10.0
    if u in ("UBAR", "MICROBAR", "MICROBARS", "µBAR"):
        return values * 1e-3
    if u in ("NBAR", "NANOBAR", "NANOBARS"):
        return values * 1e-6
    if "DYN" in u:                      # dyn/cm^2 = 0.1 Pa
        return values / 1000.0
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


def _grams_per_cm3(unit: str) -> bool:
    """A mass density unit in g/cm^3 (GM/CM**3, GRAM PER CUBIC CENTIMETER), tested word by
    word: with the spaces squeezed out, KILOGRAM PER CUBIC METER contained both "GRAM"
    and "CM", and such densities were multiplied by 1000."""
    import re as _re
    u = unit.upper()
    gram = _re.search(r"(?<![A-Z])(G|GM|GRAMS?)(?![A-Z])", u)
    cm = "CENTIMET" in u or _re.search(r"(?<![A-Z])CM(?![A-Z])", u)
    return bool(gram and cm)


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


# Profiles already read in this session (a comparison re-plotted with another variable,
# or the same profile opened again, is not read and derived again).
_PROFILE_CACHE: "OrderedDict[Tuple[str, str], ObservationProfile]" = OrderedDict()
_PROFILE_CACHE_MAX = 512
_cache_lock = threading.Lock()


def load_profile_cached(dataset_id: str, product_id: str) -> ObservationProfile:
    key = (dataset_id, product_id)
    with _cache_lock:
        if key in _PROFILE_CACHE:
            _PROFILE_CACHE.move_to_end(key)
            return _PROFILE_CACHE[key]
    prof = load_profile(dataset_id, product_id)
    _remember(key, prof)
    return prof


def _remember(key, prof) -> None:
    with _cache_lock:
        _PROFILE_CACHE[key] = prof
        _PROFILE_CACHE.move_to_end(key)
        while len(_PROFILE_CACHE) > _PROFILE_CACHE_MAX:
            _PROFILE_CACHE.popitem(last=False)


def forget_dataset(dataset_id: str) -> None:
    """Drop cached profiles of a data set (after it is re-indexed)."""
    with _cache_lock:
        for k in [k for k in _PROFILE_CACHE if k[0] == dataset_id]:
            del _PROFILE_CACHE[k]


def load_profiles(pairs: List[Tuple[str, str]]) -> List[Any]:
    """Several profiles at once: cached ones directly, the others read (downloaded if
    needed) in the worker processes (Settings > Performance).  Each item of the result
    is the profile or the exception that reading it raised, in the order of ``pairs``."""
    from ..parallel import cpu_map
    out: List[Any] = [None] * len(pairs)
    todo = []
    with _cache_lock:
        for i, key in enumerate(pairs):
            if key in _PROFILE_CACHE:
                _PROFILE_CACHE.move_to_end(key)
                out[i] = _PROFILE_CACHE[key]
            else:
                todo.append(i)
    results = cpu_map(load_profile, [pairs[i] for i in todo])
    for i, res in zip(todo, results):
        out[i] = res
        if isinstance(res, ObservationProfile):
            _remember(pairs[i], res)
    return out


def load_profile(dataset_id: str, product_id: str) -> ObservationProfile:
    """One archive profile, downloaded first if it is not in the cache."""
    ds = get_dataset(dataset_id)
    prod = get_product(dataset_id, product_id)
    if ds is None or prod is None:
        raise LookupError(f"Unknown product {dataset_id}/{product_id}")
    if prod["kind"] != "profile":
        raise ValueError(f"{product_id} is a {prod['product_type']}, not a vertical profile")
    return profile_from_label(ds, prod, Path(fetch_product(dataset_id, product_id)))


def _meta_value(tbl, name) -> Optional[float]:
    """A number from the label metadata (e.g. a PDS4 header table), by column-style name."""
    headers = list((tbl.metadata.get("HEADER_TABLES") or {}).values())
    for n in ([name] if isinstance(name, str) else list(name or ())):
        for src in [tbl.metadata] + headers:       # the label, then one-row header tables
            v = src.get(n)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v):
                return float(v)
    return None


def _header_text(attrs: Dict, name: str) -> Optional[str]:
    for h in (attrs.get("HEADER_TABLES") or {}).values():
        v = h.get(name)
        if isinstance(v, str) and v:
            return v
    return None


def above_spheroid(h, lat_deg, a: float, f: float) -> Tuple[np.ndarray, np.ndarray]:
    """Radius (km) and planetocentric latitude (deg) of points at height ``h`` (km) along
    the normal of the spheroid (equatorial radius ``a`` km, flattening ``f``) at geodetic
    latitude ``lat_deg``.  With e^2 = f (2 - f) and N = a / sqrt(1 - e^2 sin^2 phi):
    x = (N + h) cos phi, z = (N (1 - e^2) + h) sin phi."""
    h = np.asarray(h, dtype=float)
    phi = np.radians(np.asarray(lat_deg, dtype=float))
    e2 = f * (2.0 - f)
    n = a / np.sqrt(1.0 - e2 * np.sin(phi) ** 2)
    x = (n + h) * np.cos(phi)
    zc = (n * (1.0 - e2) + h) * np.sin(phi)
    return np.hypot(x, zc), np.degrees(np.arctan2(zc, x))


def profile_from_label(ds: Dataset, prod: Dict, label: Path) -> ObservationProfile:
    cols = ds.profile_columns
    body = get_body(ds.body_ids[0])
    if ds.repository:
        from .repositories import read_normalised
        tbl = read_normalised(label)
    elif label.suffix.lower() == ".xml":
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

    time_utc = prod.get("start_time") or ""
    leg = prod.get("leg")
    if ds.pass_legs and leg and ds.pass_legs in tbl.columns:
        # One leg of an aerobraking pass: before periapsis (inbound) or from it on.  Both
        # legs take the periapsis time (the index time is the start of the file).
        t = np.asarray(tbl.columns[ds.pass_legs], dtype=float)
        from ..analysis.solar_geometry import parse_utc
        start = parse_utc(time_utc)
        if start is not None and t.size and np.isfinite(t[0]):
            import datetime as _dt
            time_utc = (start - _dt.timedelta(seconds=float(t[0]))).isoformat(timespec="milliseconds")
        mask = (t < 0) if leg == "inbound" else (t >= 0)
        tbl.columns = {k: v[mask] for k, v in tbl.columns.items()}
        tbl.text_columns = {k: [x for x, m in zip(v, mask) if m] for k, v in tbl.text_columns.items()}

    for col, fills in ds.fill_values.items():
        k = col if col in tbl.columns else _key(tbl, col)      # (exact name first: error columns)
        if k is not None and k in tbl.columns:
            a = tbl.columns[k] = np.array(tbl.columns[k], dtype=float)
            for f in fills:
                a[np.isclose(a, f, rtol=1e-9, atol=1e-9)] = np.nan

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
        z_ref = f"a sphere of radius {body.radius_km:g} km (from the radius column)"
    elif ds.altitude_spheroid and _key(tbl, cols.get("latitude")) is not None:
        a, f = ds.altitude_spheroid
        lat_key = _key(tbl, cols.get("latitude"))
        r, tbl.columns[lat_key] = above_spheroid(z, tbl.columns[lat_key], a, f)
        z = r - body.radius_km
        z_ref = (f"a sphere of radius {body.radius_km:g} km (archive altitudes are above the spheroid "
                 f"a = {a:g} km, f = {f:.4g}; converted with the latitude)")
    elif ds.altitude_reference_km is not None:
        shift = ds.altitude_reference_km - body.radius_km
        z = z + shift
        z_ref = (f"a sphere of radius {body.radius_km:g} km (archive altitudes are above "
                 f"{ds.altitude_reference_km:g} km; shifted by {shift:+.3g} km)")
    else:
        z_ref = ds.altitude_reference or "as given in the archive"

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
    # The neutral number density only: in ionospheric files (MaRS/VeRa "IID") the
    # whole-word search for NUMBER DENSITY finds ELECTRON NUMBER DENSITY instead.
    n_key = _key(tbl, cols.get("number_density"))
    n = _col(tbl, cols.get("number_density")) if n_key and "ELECTRON" not in n_key.upper() else None
    if n is not None:
        n_unit = _unit(tbl, cols.get("number_density"))
        if n_unit:                                       # stored as m^-3; Cassini gives cm^-3
            n = _to_per_cm3(n, n_unit) * 1e6
    # Absolute temperature, pressure and densities are positive: zero or negative
    # values are fill (MER and Phoenix entry profiles use -1 above their valid range
    # without declaring it).  Electron densities can be legitimately negative noise.
    for a in (t_k, p_hpa, n):
        if a is not None:
            with np.errstate(invalid="ignore"):
                a[a <= 0] = np.nan

    unc: Dict[str, np.ndarray] = {}
    s = _sigma(tbl, cols.get("temperature_sigma"))
    if s is not None:
        unc["temperature_k"] = s
        unc["temperature_c"] = s
    s = _sigma(tbl, cols.get("pressure_sigma"))
    if s is not None:
        unc["pressure_hpa"] = _to_hpa(s, p_unit)
    s = _sigma(tbl, cols.get("number_density_sigma"))
    if s is not None and n is not None:
        u = n_unit                                         # in the unit of the density itself
        unc["number_density_m3"] = _to_per_cm3(s, u) * 1e6 if u else s
    s = _sigma(tbl, cols.get("electron_density_sigma"))
    if s is not None:
        sig_key = next((k for k in tbl.columns if k.upper().strip('"').startswith(("SIGMA ELECTRON", "NOISE LEVEL ELECTRON"))), None)
        unc["electron_density_cm3"] = _to_per_cm3(s, (tbl.units.get(sig_key, "") or ne_unit).upper())

    for key, (ca, cb) in ds.sigma_from_bracket.items():
        a, b = _col(tbl, ca), _col(tbl, cb)
        if a is not None and b is not None and key not in unc:
            half = np.abs(a - b) / 2.0          # same units as the variable (K; mbar = hPa)
            unc[key] = half
            if key == "temperature_k":
                unc["temperature_c"] = half

    for key, parts in ds.sigma_from_siblings.items():
        sq = None
        for pattern, colname in parts:
            sib = next((t for f, t in getattr(tbl, "siblings", {}).items() if pattern.upper() in f.upper()), None)
            if sib is None or colname not in sib.columns:
                continue
            s = np.asarray(sib.columns[colname], dtype=float)
            u = (sib.units.get(colname) or "").upper()
            if key == "pressure_hpa":
                s = _to_hpa(s, u)
            elif key == "density_measured" and _grams_per_cm3(u):
                s = s * 1000.0                       # g/cm^3 -> kg/m^3
            if s.shape == tbl.columns[next(iter(tbl.columns))].shape:
                sq = s ** 2 if sq is None else sq + s ** 2
        if sq is not None:
            unc[key] = np.sqrt(sq)
            if key == "temperature_k":
                unc["temperature_c"] = unc[key]

    for key, f in ds.sigma_factor.items():
        if key in unc:
            unc[key] = unc[key] * f

    track: Dict[str, np.ndarray] = {}
    header: Dict[str, float] = {}
    for key in ("latitude", "longitude", "sza", "lst"):
        a = _col(tbl, cols.get(key))
        if a is not None:
            track[key] = a
        elif _meta_value(tbl, cols.get(key)) is not None:
            header[key] = _meta_value(tbl, cols.get(key))      # one value per profile (header table)
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
        time_utc=time_utc,
        latitude=float(np.nanmedian(lat)) if lat is not None else header.get("latitude"),
        longitude=circular_median(lon, 360.0) if lon is not None else header.get("longitude"),
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
        raw_attributes={**tbl.metadata, "DATASET_ID": ds.id, "VOLUME": prod["volume"], "ALTITUDE_REFERENCE": z_ref,
                        **({"LST": header["lst"]} if "lst" in header else {}),
                        **({"SZA": header["sza"]} if "sza" in header else {})},
        uncertainty=unc,
        track=track,
    )
    if n is not None:
        prof.derived["number_density_m3"] = n
    for key, (col, sig) in ds.extra_variables.items():
        v = _col(tbl, col)
        factor = 1.0
        if v is not None and key.startswith("density"):
            v = np.where(v > 0, v, np.nan)
            if _grams_per_cm3(_unit(tbl, col)):
                factor = 1000.0                          # g/cm^3 -> kg/m^3 (Cassini RSS)
        factor *= ds.value_factor.get(key, 1.0)
        if v is not None:
            prof.derived[key] = v * factor
            s = _col(tbl, sig) if sig else None
            if s is not None:
                prof.uncertainty[key] = s * factor
    # A 1-sigma uncertainty is never negative: negative values are fill (the Phoenix entry
    # profile writes -1 in its SIGMA columns where there is no value)
    for key, s in prof.uncertainty.items():
        s = np.array(s, dtype=float)
        with np.errstate(invalid="ignore"):
            s[s < 0] = np.nan
        prof.uncertainty[key] = s
    _add_solar_geometry(prof, ds)
    prof.derived.update(compute_atmospheric_diagnostics(prof, body))
    return prof


def _add_solar_geometry(prof: ObservationProfile, ds: Dataset) -> None:
    """Local true solar time and solar zenith angle (per level along the ray path when the
    track has positions) where the archive does not give them, and Mars' Ls, computed
    from the time and position (analysis/solar_geometry.py).  The measurement time is
    the lowest level's; when the archive's times are ground received times the light
    time is subtracted, and that time becomes the profile's time."""
    from ..analysis import solar_geometry as sg
    if not sg.supported(prof.body_id):
        return
    attrs = prof.raw_attributes
    track = prof.track
    time = prof.time_utc
    # The archive's own time of the measurement (radio science header tables: MRO
    # "SPACECRAFT TIME", MGS "OCCULTATION TIME"), when the label times are ground received times
    sc_time = _header_text(attrs, "SPACECRAFT TIME") or _header_text(attrs, "OCCULTATION TIME")
    if sc_time and sg.parse_utc(sc_time):
        attrs.setdefault("LABEL_TIME", prof.time_utc)
        prof.time_utc = time = sc_time
    archive_ls = next((h.get("SOLAR LONGITUDE") for h in (attrs.get("HEADER_TABLES") or {}).values()
                       if isinstance(h.get("SOLAR LONGITUDE"), (int, float))), None)
    if archive_ls is not None:
        attrs["LS"] = float(archive_ls)
    et = track.get("et")
    z = np.asarray(prof.altitude_km, float)
    if et is not None and np.isfinite(et).any():
        ok = np.isfinite(et) & np.isfinite(z) if z.size == et.size else np.isfinite(et)
        i = int(np.nanargmin(np.where(ok, z, np.nan))) if z.size == et.size and ok.any() else int(np.nanargmin(et))
        time = sg.et_to_utc(et[i])
        if ds.times_earth_received:
            lt = sg.light_time_s(prof.body_id, time)
            if lt:
                time = sg.et_to_utc(et[i] - lt)
                attrs["LIGHT_TIME_S"] = round(lt, 1)
                attrs.setdefault("LABEL_TIME", prof.time_utc)
                prof.time_utc = time             # the time of the measurement at the planet
    if len(time or "") < 13:
        return                                   # a date without a clock time gives no local time
    lat, lon = track.get("latitude"), track.get("longitude")
    have_lst = "lst" in track or isinstance(attrs.get("LST"), (int, float))
    have_sza = "sza" in track or isinstance(attrs.get("SZA"), (int, float))
    ss = sg.subsolar_point(prof.body_id, time)
    if ss is None:
        return
    attrs["SUBSOLAR_LATITUDE"] = round(ss["subsolar_latitude"], 3)
    attrs["SUBSOLAR_LONGITUDE"] = round(ss["subsolar_longitude"], 3)
    if "ls" in ss and archive_ls is None:
        attrs["LS"] = round(ss["ls"], 3)
    if have_lst and have_sza:
        return
    if lat is not None and lon is not None and np.size(lat) == np.size(lon):
        g = [sg.solar_geometry(prof.body_id, time, a, o) if np.isfinite(a) and np.isfinite(o) else None
             for a, o in zip(np.asarray(lat, float), np.asarray(lon, float))]
        if any(g):
            if not have_lst:
                track["lst"] = np.array([x["lst"] if x else np.nan for x in g])
            if not have_sza:
                track["sza"] = np.array([x["sza"] if x else np.nan for x in g])
            attrs["GEOMETRY_COMPUTED"] = "local time / solar zenith angle computed by VEDA from time and position"
        return
    g = sg.solar_geometry(prof.body_id, time, prof.latitude, prof.longitude)
    if g:
        if not have_lst:
            attrs["LST"] = round(g["lst"], 4)
        if not have_sza:
            attrs["SZA"] = round(g["sza"], 3)
        attrs["GEOMETRY_COMPUTED"] = "local time / solar zenith angle computed by VEDA from time and position"
