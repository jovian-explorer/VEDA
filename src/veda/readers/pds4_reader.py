"""Read PDS4 tables (XML label + character or delimited table).

PDS4 is the format of current archives (ISRO ISSDC/PRADAN, MAVEN, New
Horizons, BepiColombo, ...). Supported: Table_Character (fixed width) and
Table_Delimited (CSV etc.); the first table in the label is read, its
numeric fields become columns, character fields are kept as text.
Binary tables and arrays are not handled here.
"""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .pds3_reader import Pds3Table


def _strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _text(el: Optional[ET.Element], path: str, default: str = "") -> str:
    if el is None:
        return default
    found = el.find(path)
    return (found.text or "").strip() if found is not None and found.text else default


def is_pds4_label(path: Path) -> bool:
    if path.suffix.lower() != ".xml":
        return False
    head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    return "Product_Observational" in head or "pds.nasa.gov/pds4" in head


_NUMERIC = ("ASCII_Real", "ASCII_Integer", "ASCII_NonNegative_Integer", "ASCII_Numeric_Base")


def read_pds4_table(xml_path: str) -> Pds3Table:
    p = Path(xml_path)
    root = _strip_ns(ET.parse(p).getroot())
    meta: Dict[str, object] = {}
    obs = root.find("Observation_Area")
    if obs is not None:
        meta["START_TIME"] = _text(obs, "Time_Coordinates/start_date_time")
        meta["STOP_TIME"] = _text(obs, "Time_Coordinates/stop_date_time")
        meta["TARGET_NAME"] = _text(obs, "Target_Identification/name").upper()
        meta["INSTRUMENT_NAME"] = _text(obs, "Observing_System/Observing_System_Component[type='Instrument']/name") or \
            _text(obs, "Observing_System/Observing_System_Component/name")
        meta["INVESTIGATION"] = _text(obs, "Investigation_Area/name")
    meta["LOGICAL_IDENTIFIER"] = _text(root, "Identification_Area/logical_identifier")
    meta["TITLE"] = _text(root, "Identification_Area/title")

    # Every character/delimited table of the label; the one with the most records is
    # the data (a profile), one-record tables are headers whose values become metadata
    # (PVO radio occultations: observing conditions, then the profile).
    tables = []
    for fao in root.findall("File_Area_Observational"):
        fname = _text(fao, "File/file_name")
        for table in list(fao):
            if table.tag in ("Table_Character", "Table_Delimited") and fname:
                tables.append((fname, table, "character" if table.tag == "Table_Character" else "delimited"))
    if not tables:
        raise ValueError(f"{p.name}: no character or delimited table found (binary tables are not supported)")
    main = max(tables, key=lambda x: int(_text(x[1], "records", "0") or 0))
    for fname, table, kind in tables:
        if table is main[1] or int(_text(table, "records", "0") or 0) != 1:
            continue
        try:
            h = _read_table(p, fname, table, kind, {})
        except (FileNotFoundError, ValueError, IndexError):
            continue
        meta.update({k: float(v[0]) for k, v in h.columns.items() if v.size and np.isfinite(v[0])})
        meta.update({k: v[0] for k, v in h.text_columns.items() if v and k not in meta})
    return _read_table(p, *main, meta)


def _read_table(p: Path, fname: str, table, kind: str, meta: Dict[str, object]) -> Pds3Table:
    data_p = next((c for c in (p.parent / fname, p.parent / fname.lower(), p.parent / fname.upper()) if c.exists()), None)
    if data_p is None:
        raise FileNotFoundError(f"{fname} (named in {p.name}) was not loaded with the label")
    offset = int(_text(table, "offset", "0") or 0)
    records = int(_text(table, "records", "0") or 0)
    raw = data_p.read_bytes()[offset:].decode("utf-8", errors="replace")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if records:
        lines = lines[:records] if kind == "character" else lines
    columns: Dict[str, np.ndarray] = {}
    units: Dict[str, str] = {}
    text_cols: Dict[str, List[str]] = {}
    if kind == "character":
        fields = table.findall("Record_Character/Field_Character")
        for f in fields:
            name = _text(f, "name")
            start = int(_text(f, "field_location", "1")) - 1
            length = int(_text(f, "field_length", "0"))
            cells = [ln[start:start + length].strip() for ln in lines]
            _store(name, cells, _text(f, "data_type"), _text(f, "unit"), f, columns, units, text_cols)
    else:
        delim = {"Comma": ",", "Horizontal Tab": "\t", "Semicolon": ";", "Vertical Bar": "|"}.get(
            _text(table, "field_delimiter", "Comma"), ",")
        rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
        fields = table.findall("Record_Delimited/Field_Delimited")
        names = [_text(f, "name") for f in fields]
        if rows and [c.strip() for c in rows[0]][:len(names)] == names:
            rows = rows[1:]                        # header row repeats the field names
        for i, f in enumerate(fields):
            num = int(_text(f, "field_number", str(i + 1))) - 1
            cells = [r[num].strip() if num < len(r) else "" for r in rows]
            _store(names[i], cells, _text(f, "data_type"), _text(f, "unit"), f, columns, units, text_cols)
    meta["TABLE_FILE"] = data_p.name
    t = Pds3Table(label_path=str(p), table_path=str(data_p), metadata=meta, columns=columns, units=units)
    t.text_columns = text_cols
    return t


def _store(name, cells, dtype, unit, field, columns, units, text_cols):
    missing = set()
    for sc in field.findall("Special_Constants/*"):
        if sc.text:
            missing.add(sc.text.strip())
    if dtype in _NUMERIC or dtype.startswith("ASCII_Real") or dtype.startswith("ASCII_Integer"):
        arr = np.full(len(cells), np.nan)
        for i, c in enumerate(cells):
            if c and c not in missing:
                try:
                    arr[i] = float(c)
                except ValueError:
                    pass
        columns[name] = arr
        units[name] = unit
    else:
        text_cols[name] = cells
