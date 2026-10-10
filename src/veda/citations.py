"""What to cite: references for the data sets and features a user actually used.

The bibliography (archives/references.json) was checked against Crossref: every
DOI resolves to the title, first author, year and journal given.  Entries
without a DOI (ESA SP-1240 chapters, Plotly) say so.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import __version__
from .archives.datasets import get_dataset

REPO_URL = "https://github.com/jovian-explorer/VEDA"
# Zenodo concept DOI: every archived release; resolves to the newest one
VEDA_DOI = "10.5281/zenodo.23215291"

# Acknowledgements the archives ask for (wording kept short and factual)
ARCHIVE_NOTES = {
    "NASA PDS": ("NASA Planetary Data System", "This work used data from the NASA Planetary Data System (PDS), "
                 "https://pds.nasa.gov/."),
    "ESA PSA": ("ESA Planetary Science Archive", "This work used data from the ESA Planetary Science Archive (PSA), "
                "https://archives.esac.esa.int/psa/."),
    "JAXA DARTS": ("JAXA DARTS", "Data were provided by ISAS/JAXA through the Data Archives and Transmission System "
                   "(DARTS), https://darts.isas.jaxa.jp/."),
    "ISRO ISSDC": ("ISRO ISSDC / PRADAN", "Data were provided by the Indian Space Science Data Centre (ISSDC), ISRO, "
                   "through PRADAN, https://pradan.issdc.gov.in/."),
    "OPUS": ("PDS Rings Node (OPUS)", "This work used data from the NASA PDS Ring-Moon Systems Node, found with OPUS, "
             "https://opus.pds-rings.seti.org/."),
}

# Features -> reference keys
FEATURE_REFS = {
    "geometry": ["acton1996", "acton2018", "annex2020"],
    "derived": ["harris2020", "virtanen2020"],
    "comparison": ["harris2020", "virtanen2020"],
    "image": ["astropy2022"],
    "fits": ["astropy2022"],
    "publication_figure": ["hunter2007"],
    "figure_export": ["plotly2015"],
    "gravity_waves": ["tsuda2000"],
    "venus_reference": ["justh2021", "seiff1985"],
    "mars_reference": ["justh2024"],
    "co2_frost_point": ["james1992", "greve2010"],
    "mars_gravity": ["konopliv2016"],
    "titan_real_gas": ["tsonopoulos1974", "gillis1996"],
    "venus_potential_temperature": ["lebonnois2010"],
}
FEATURE_TITLES = {
    "geometry": "Observation geometry (NAIF SPICE, SpiceyPy)",
    "derived": "Derived quantities and interpolation (NumPy, SciPy)",
    "comparison": "Derived quantities and interpolation (NumPy, SciPy)",
    "image": "Image and FITS handling (Astropy)",
    "fits": "Image and FITS handling (Astropy)",
    "publication_figure": "Publication figures (Matplotlib)",
    "figure_export": "Interactive figures (Plotly)",
    "gravity_waves": "Methods",
    "venus_reference": "Methods",
    "mars_reference": "Methods",
    "co2_frost_point": "Methods",
    "mars_gravity": "Methods",
    "titan_real_gas": "Methods",
    "venus_potential_temperature": "Methods",
}


@lru_cache(maxsize=1)
def references() -> Dict[str, Dict[str, Any]]:
    path = Path(__file__).parent / "archives" / "references.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["key"]: r for r in data["refs"]}


def _authors_text(r: Dict[str, Any]) -> str:
    a = [x for x in r.get("authors") or [] if x]
    if not a:
        return ""
    if r.get("et_al") or len(a) > 3:
        return f"{a[0]}, et al."
    return ", ".join(a[:-1]) + (", & " if len(a) > 1 else "") + a[-1] if len(a) > 1 else a[0]


def _pages(r: Dict[str, Any]) -> str:
    """Page range, or the article number for AGU papers (Crossref stores the DOI suffix as the page)."""
    p = (r.get("pages") or "").strip()
    if re.fullmatch(r"\d{4}[A-Z]{2}\d{6}", p, re.I):
        m = re.search(r"\b([A-Z]\d{2}[A-Z]?\d{2,3})\b", r.get("note") or "")
        return m.group(1) if m else ""
    return p


def ref_text(r: Dict[str, Any]) -> str:
    """AGU-style one-line reference."""
    parts = [f"{_authors_text(r)} ({r.get('year')}). {r.get('title', '').rstrip('.')}."]
    venue = r.get("journal") or ""
    if venue:
        vol = r.get("volume") or ""
        issue = f"({r['issue']})" if r.get("issue") else ""
        pages = _pages(r)
        parts.append(f" {venue}" + (f", {vol}{issue}" if vol else "") + (f", {pages}" if pages else "") + ".")
    if r.get("doi"):
        parts.append(f" https://doi.org/{r['doi']}")
    elif r.get("url"):
        parts.append(f" {r['url']}")
    elif r.get("type") != "software":
        parts.append(" (No DOI; check the page numbers in the printed volume.)")
    return "".join(parts).strip()


def _bib_escape(s: str) -> str:
    return (s or "").replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


def ref_bibtex(r: Dict[str, Any]) -> str:
    kind = {"article": "article", "inproceedings": "inproceedings", "book": "book", "software": "software",
            "techreport": "techreport", "incollection": "incollection"}.get(r.get("type") or "article", "misc")
    authors = list(r.get("authors") or [])
    if r.get("et_al"):
        authors.append("others")
    fields = [("author", " and ".join(authors)), ("title", "{" + (r.get("title") or "") + "}"), ("year", str(r.get("year") or ""))]
    if r.get("journal"):
        fields.append(({"article": "journal", "misc": "howpublished", "techreport": "institution"}.get(kind, "booktitle"),
                       r["journal"]))
    for k in ("volume", "issue", "pages", "doi"):
        v = _pages(r) if k == "pages" else r.get(k)
        if v:
            fields.append(("number" if k == "issue" else k, str(v)))
    if r.get("url") and not r.get("doi"):
        fields.append(("url", r["url"]))
    elif not r.get("doi") and r.get("type") != "software":
        fields.append(("note", "No DOI; page numbers not verified"))
    body = ",\n".join(f"  {k:<8} = {{{_bib_escape(v) if k not in ('title', 'doi') else v}}}" for k, v in fields if v)
    return f"@{kind}{{{r['key']},\n{body}\n}}"


def veda_bibtex() -> str:
    return ("@software{Aggarwal_VEDA_2026,\n  author    = {Keshav Aggarwal},\n"
            "  title     = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},\n"
            f"  year      = {{2026}},\n  version   = {{{__version__}}},\n"
            f"  doi       = {{{VEDA_DOI}}},\n"
            f"  url       = {{{REPO_URL}}}\n}}")


def _archive_key(archive: str) -> Optional[str]:
    a = archive.upper()
    for key in ("OPUS", "NASA PDS", "ESA PSA", "JAXA DARTS", "ISRO ISSDC"):
        if key in a or (key == "ISRO ISSDC" and "ISSDC" in a):
            return key
    return None


def build(dataset_ids: Iterable[str], features: Iterable[str],
          volumes: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    """``volumes``: archive data set / bundle identifiers seen per VEDA data set (from opened products)."""
    volumes = volumes or {}
    refs = references()
    used_refs: Dict[str, Dict[str, Any]] = {}
    data_items: List[Dict[str, Any]] = []
    archives: Dict[str, None] = {}
    missions: Dict[str, None] = {}
    for ds_id in dict.fromkeys(dataset_ids):
        ds = get_dataset(ds_id)
        if ds is None:
            continue
        missions[ds.mission_id] = None
        ak = _archive_key(ds.archive)
        if ak:
            archives[ak] = None
        papers = [refs[k] for k in ds.refs if k in refs]
        for p in papers:
            used_refs[p["key"]] = p
        from .core.registry import get_mission
        mission = get_mission(ds.mission_id)
        mname = mission.name if mission else ds.mission_id.upper()
        archive = ds.archive.replace(" (live search)", "")
        # VEDA's data set ids are not always the archive's DATA_SET_ID (versions differ), so the
        # citation names the archive and lists the identifiers read from the products' own labels.
        level = "" if ds.service else f" ({ds.level})"
        cite = (f"{mname} {ds.instrument}{level} data, {archive}"
                + (f", https://doi.org/{ds.doi}" if ds.doi else f" ({ds.base_url})") + ".")
        data_items.append({
            "dataset_id": ds.id, "mission_id": ds.mission_id, "mission": mname, "instrument": ds.instrument,
            "level": ds.level, "title": ds.title, "archive": archive, "url": ds.base_url,
            "data_citation": cite,
            "archive_ids": sorted({v for v in volumes.get(ds.id, []) if v})[:40],
            "papers": [{"key": p["key"], "text": ref_text(p), "doi": p.get("doi", "")} for p in papers],
        })
    feats = [f for f in dict.fromkeys(features) if f in FEATURE_REFS]
    feature_sections: Dict[str, List[Dict[str, Any]]] = {}
    for f in feats:
        title = FEATURE_TITLES[f]
        for k in FEATURE_REFS[f]:
            if k in refs:
                used_refs[k] = refs[k]
                lst = feature_sections.setdefault(title, [])
                if all(x["key"] != k for x in lst):
                    lst.append({"key": k, "text": ref_text(refs[k]), "doi": refs[k].get("doi", "")})
    acks = [{"archive": ARCHIVE_NOTES[a][0], "text": ARCHIVE_NOTES[a][1]} for a in archives]
    if "geometry" in feats:
        acks.append({"archive": "NASA NAIF", "text": "Observation geometry was computed with the NAIF SPICE toolkit "
                     "(Acton, 1996; Acton et al., 2018) through SpiceyPy (Annex et al., 2020), using the mission's "
                     "reconstructed SPICE kernels."})
    statement = availability_statement(list(archives), "geometry" in feats)
    bib = [veda_bibtex()] + [ref_bibtex(r) for r in used_refs.values()]
    return {
        "veda": {"text": f"Aggarwal, K. (2026). VEDA: Visualization, Exploration, and Data Analysis (version "
                         f"{__version__}). Zenodo. https://doi.org/{VEDA_DOI}",
                 "bibtex": veda_bibtex()},
        "data": data_items, "acknowledgements": acks,
        "features": [{"title": t, "items": items} for t, items in feature_sections.items()],
        "statement": statement, "bibtex": "\n\n".join(bib),
        "missions": list(missions), "n_references": len(used_refs) + 1,
    }


def availability_statement(archives: List[str], geometry: bool) -> str:
    names = {"NASA PDS": "the NASA Planetary Data System (PDS, https://pds.nasa.gov/)",
             "ESA PSA": "the ESA Planetary Science Archive (PSA, https://archives.esac.esa.int/psa/)",
             "JAXA DARTS": "the JAXA Data Archives and Transmission System (DARTS, https://darts.isas.jaxa.jp/)",
             "ISRO ISSDC": "the ISRO Indian Space Science Data Centre (ISSDC/PRADAN, https://pradan.issdc.gov.in/; "
                           "registered users)",
             "OPUS": "the NASA PDS Ring-Moon Systems Node (https://pds-rings.seti.org/)"}
    srcs = [names[a] for a in archives if a in names]
    if not srcs:
        srcs = [names["NASA PDS"], names["ESA PSA"], names["JAXA DARTS"]]
    listed = srcs[0] if len(srcs) == 1 else ", ".join(srcs[:-1]) + " and " + srcs[-1]
    s = f"The spacecraft data analysed in this study are publicly available from {listed}."
    if geometry:
        s += (" Spacecraft and planetary ephemerides were obtained from the NASA NAIF SPICE archive "
              "(https://naif.jpl.nasa.gov/) and the mission SPICE archives.")
    s += (f" Data were read, unit-converted and compared with VEDA version {__version__} ({REPO_URL}).")
    return re.sub(r"\s+", " ", s)
