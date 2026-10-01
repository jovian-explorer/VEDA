"""Pure-Python PDS3 Label (.LBL) and Table (.TAB) reader for VEDA.

Designed without third-party PVL dependencies so it operates reliably in any
standard Python environment. Handles fixed-width and comma-delimited PDS3 ASCII
tables with column offset parsing, units extraction, and sentinel masking.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class ColumnDef:
    name: str
    column_number: int
    start_byte: int  # 1-indexed
    bytes_count: int
    data_type: str = "ASCII_REAL"
    unit: str = ""
    invalid_constant: Optional[float] = None
    missing_constant: Optional[float] = None


@dataclass
class Pds3Table:
    label_path: str
    table_path: str
    metadata: Dict[str, Any]
    columns: Dict[str, np.ndarray]
    units: Dict[str, str]
    descriptions: Dict[str, str] = field(default_factory=dict)

    def row_count(self) -> int:
        """Number of rows in the longest column (0 for an empty table)."""
        return max((int(v.size) for v in self.columns.values()), default=0)

    def series(self, name: str) -> Optional[np.ndarray]:
        """Case-insensitive column lookup; see match_column for partial names."""
        key = match_column(self.columns.keys(), name)
        return self.columns[key] if key is not None else None


_UNCERTAINTY_PREFIXES = ("SIGMA", "ERROR", "ERR_", "UNCERTAINTY", "STD")


def match_column(names, query: str) -> Optional[str]:
    """Pick the column that best represents ``query`` (e.g. TEMPERATURE).

    An exact (case-insensitive) name wins.  Otherwise the query must appear as a
    whole word, and columns are ranked so that:
      * the quantity leads the name ("TEMPERATURE (MEDIUM ...)" beats
        "PRESSURE (LOWER TEMPERATURE AT BOUNDARY)", which only mentions it);
      * uncertainty columns ("SIGMA TEMPERATURE ...") come last;
      * of several retrieval variants the nominal MEDIUM one is preferred.
    """
    def norm(text: str) -> str:
        # "EPHEMERIS_SECONDS" and "EPHEMERIS SECONDS" are the same column.
        return re.sub(r"[\s_]+", " ", text.strip().strip('"').upper())

    q = norm(query)
    if not q:
        return None
    names = list(names)
    for k in names:
        if norm(k) == q:
            return k
    word = re.compile(r"(?<![A-Z0-9])" + re.escape(q) + r"(?![A-Z0-9])")
    ranked = []
    for i, k in enumerate(names):
        u = norm(k)
        if not word.search(u):
            continue
        uncertain = u.startswith(_UNCERTAINTY_PREFIXES)
        leading = bool(re.match(r"[^A-Z0-9]*" + re.escape(q) + r"(?![A-Z0-9])", u))
        nominal = "MEDIUM" in u or "NOMINAL" in u
        ranked.append((uncertain, not leading, not nominal, i, k))
    return min(ranked)[-1] if ranked else None


def _strip_comments(text: str) -> str:
    out = []
    i, n = 0, len(text)
    in_quote = in_comment = False
    while i < n:
        ch = text[i]
        if in_comment:
            if text.startswith("*/", i):
                in_comment = False
                i += 2
                continue
            if ch == "\n":
                out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote and text.startswith("/*", i):
            in_comment = True
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_pds3_label(label_text: str) -> Tuple[Dict[str, Any], List[ColumnDef]]:
    """Parse key-value pairs and COLUMN objects from a PDS3 label."""
    metadata: Dict[str, Any] = {}
    columns: List[ColumnDef] = []

    # Drop /* ... */ comments, but not "/*" inside quoted strings such as
    # INDEXED_FILE_NAME = {"BCK/*.LBL", ...}, which used to swallow the rest
    # of the label (and every COLUMN definition after it).
    clean_lines = [l.strip() for l in _strip_comments(label_text).splitlines() if l.strip()]

    # Join quoted values that wrap onto following lines, e.g.
    #   NAME = "SIGMA PRESSURE (LOWER TEMPERATURE AT
    #           BOUNDARY)"
    # Without this the name is truncated and text inside a wrapped DESCRIPTION
    # that happens to contain "=" is misread as a keyword.
    merged: List[str] = []
    pending: Optional[str] = None
    for l in clean_lines:
        if pending is not None:
            pending += " " + l
            if pending.count('"') % 2 == 0:
                merged.append(pending)
                pending = None
            continue
        if "=" in l and l.split("=", 1)[1].count('"') % 2 == 1:
            pending = l
            continue
        merged.append(l)
    if pending is not None:
        merged.append(pending + '"')
    clean_lines = merged

    # State machine to capture global keywords and COLUMN blocks
    curr_obj = None
    curr_col: Dict[str, Any] = {}

    for line in clean_lines:
        if "=" not in line:
            continue
        parts = line.split("=", 1)
        key = parts[0].strip().upper()
        val = parts[1].strip()

        # Clean value quotes and angle units e.g. "6051.8 <km>"
        if val.startswith('"') and val.endswith('"'):
            val_clean = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val_clean = val[1:-1]
        else:
            val_clean = val

        if key == "OBJECT":
            curr_obj = val_clean.upper()
            if curr_obj == "COLUMN":
                curr_col = {}
        elif key == "END_OBJECT":
            if val_clean.upper() == "COLUMN" and curr_col:
                col_name = curr_col.get("NAME", f"COL_{len(columns)+1}")
                c_num = int(curr_col.get("COLUMN_NUMBER", len(columns)+1))
                s_byte = int(curr_col.get("START_BYTE", 1))
                b_count = int(curr_col.get("BYTES", 10))
                dtype = curr_col.get("DATA_TYPE", "ASCII_REAL")
                unit = curr_col.get("UNIT", "")
                inv = None
                if "INVALID_CONSTANT" in curr_col:
                    try:
                        inv = float(curr_col["INVALID_CONSTANT"])
                    except (ValueError, TypeError):
                        pass
                miss = None
                if "MISSING_CONSTANT" in curr_col:
                    try:
                        miss = float(curr_col["MISSING_CONSTANT"])
                    except (ValueError, TypeError):
                        pass

                columns.append(ColumnDef(
                    name=col_name,
                    column_number=c_num,
                    start_byte=s_byte,
                    bytes_count=b_count,
                    data_type=dtype,
                    unit=unit,
                    invalid_constant=inv,
                    missing_constant=miss,
                ))
                curr_col = {}
            curr_obj = None
        else:
            if curr_obj == "COLUMN":
                curr_col[key] = val_clean
            else:
                metadata[key] = val_clean

    return metadata, columns


def read_pds3_table(table_or_label_path: str) -> Pds3Table:
    """Read a PDS3 label (.lbl) and its corresponding data table (.tab)."""
    p = Path(table_or_label_path)
    if p.suffix.lower() == ".tab":
        lbl_p = p.with_suffix(".lbl")
        if not lbl_p.exists():
            lbl_p = p.with_suffix(".LBL")
        tab_p = p
    else:
        lbl_p = p
        tab_p = p.with_suffix(".tab")
        if not tab_p.exists():
            tab_p = p.with_suffix(".TAB")

    if not lbl_p.exists():
        raise FileNotFoundError(f"PDS3 label not found at {lbl_p}")

    lbl_text = lbl_p.read_text(encoding="utf-8", errors="replace")
    metadata, col_defs = parse_pds3_label(lbl_text)

    if not col_defs:
        is_img = any(k.endswith("_IMAGE") or k.endswith("_HEADER") for k in metadata) or str(metadata.get("FILE_NAME", "")).lower().endswith((".fit", ".fits"))
        if is_img:
            raise ValueError(f"PDS3 label references an image file ({metadata.get('FILE_NAME')}), not a tabular dataset")

    if not tab_p.exists():
        # Check if ^TABLE or ^SPREADSHEET pointer specifies filename in directory
        table_pointer = metadata.get("^TABLE") or metadata.get("^SPREADSHEET")
        if table_pointer:
            ptr_name = str(table_pointer).strip('()"\' ')
            cand = lbl_p.parent / ptr_name
            if cand.exists():
                tab_p = cand
            elif (lbl_p.parent / ptr_name.lower()).exists():
                tab_p = lbl_p.parent / ptr_name.lower()
            elif (lbl_p.parent / ptr_name.upper()).exists():
                tab_p = lbl_p.parent / ptr_name.upper()

    if not tab_p.exists():
        if metadata.get("^IMAGE") or metadata.get("^HEADER"):
            raise ValueError(f"PDS3 label references an image object ({metadata.get('^IMAGE')}), not a table")
        raise FileNotFoundError(f"PDS3 table not found at {tab_p}")

    # Read the table file lines
    with tab_p.open("r", encoding="utf-8", errors="replace") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]

    n_rows = len(lines)
    columns_data: Dict[str, np.ndarray] = {}
    units_dict: Dict[str, str] = {}

    # Check if comma-delimited or fixed-width
    first_line = lines[0] if lines else ""
    is_csv = "," in first_line and len(first_line.split(",")) >= len(col_defs)

    if is_csv:
        import csv
        reader = csv.reader(lines)
        raw_rows = list(reader)
        for idx, c in enumerate(col_defs):
            c_idx = c.column_number - 1 if 0 <= c.column_number - 1 < len(raw_rows[0]) else idx
            arr = np.full(n_rows, np.nan, dtype=np.float64)
            for r_i, r_data in enumerate(raw_rows):
                if c_idx < len(r_data):
                    val_s = r_data[c_idx].strip().strip('"').strip("'")
                    try:
                        f_val = float(val_s)
                        if c.invalid_constant is not None and abs(f_val - c.invalid_constant) < 1e-4:
                            continue
                        if c.missing_constant is not None and abs(f_val - c.missing_constant) < 1e-4:
                            continue
                        if abs(f_val - (-999.0)) < 1e-3 or abs(f_val - (-9999.0)) < 1e-3:
                            continue
                        arr[r_i] = f_val
                    except ValueError:
                        pass
            columns_data[c.name] = arr
            units_dict[c.name] = c.unit
    else:
        # Fixed-width column slicing by START_BYTE and BYTES
        for c in col_defs:
            arr = np.full(n_rows, np.nan, dtype=np.float64)
            s_idx = c.start_byte - 1
            e_idx = s_idx + c.bytes_count

            for r_i, line in enumerate(lines):
                if s_idx < len(line):
                    chunk = line[s_idx:min(e_idx, len(line))].strip().strip(',').strip('"').strip("'")
                    if chunk:
                        try:
                            f_val = float(chunk)
                            if c.invalid_constant is not None and abs(f_val - c.invalid_constant) < 1e-4:
                                continue
                            if c.missing_constant is not None and abs(f_val - c.missing_constant) < 1e-4:
                                continue
                            if abs(f_val - (-999.0)) < 1e-3 or abs(f_val - (-9999.0)) < 1e-3:
                                continue
                            arr[r_i] = f_val
                        except ValueError:
                            pass
            columns_data[c.name] = arr
            units_dict[c.name] = c.unit

    return Pds3Table(
        label_path=str(lbl_p),
        table_path=str(tab_p),
        metadata=metadata,
        columns=columns_data,
        units=units_dict,
    )


def read_any_table(file_path: str) -> Pds3Table:
    """Read any tabular data file (PDS3 table, CSV, TSV, or whitespace-delimited ASCII).

    If a PDS3 label is found, delegates to read_pds3_table. Otherwise parses header
    and numeric columns automatically.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check for PDS3 label counterpart
    cand_lbl = [p.with_suffix(".lbl"), p.with_suffix(".LBL")]
    if p.suffix.lower() == ".lbl":
        cand_lbl = [p]
    for l in cand_lbl:
        if l.exists():
            return read_pds3_table(str(l))

    raw = p.read_bytes()
    if b"\x00" in raw[:4096]:
        raise ValueError(f"{p.name} looks like a binary file, not a text table")

    all_lines = [ln.strip() for ln in raw.decode("utf-8", errors="replace").splitlines() if ln.strip()]

    if not all_lines:
        return Pds3Table(label_path="", table_path=str(p), metadata={}, columns={}, units={})

    # Skip comments
    data_lines = [ln for ln in all_lines if not ln.startswith(("#", "%", ";", "/*"))]
    if not data_lines:
        return Pds3Table(label_path="", table_path=str(p), metadata={}, columns={}, units={})

    # Detect delimiter
    sample = data_lines[0]
    if "," in sample:
        delim = ","
    elif "\t" in sample:
        delim = "\t"
    elif ";" in sample:
        delim = ";"
    else:
        delim = None  # whitespace split

    def _split(line: str) -> List[str]:
        if delim:
            return [x.strip().strip('"\'') for x in line.split(delim)]
        return [x.strip().strip('"\'') for x in line.split()]

    first_row = _split(data_lines[0])
    # Check if first row is header
    has_header = False
    try:
        float(first_row[0])
    except ValueError:
        has_header = True

    if has_header:
        header_names = [name.upper() for name in first_row]
        body_lines = data_lines[1:]
    else:
        header_names = [f"COL_{i+1}" for i in range(len(first_row))]
        body_lines = data_lines

    n_rows = len(body_lines)
    rows = [_split(line) for line in body_lines]
    columns_data: Dict[str, np.ndarray] = {}
    for c_i, name in enumerate(header_names):
        cells = [r[c_i] if c_i < len(r) else "" for r in rows]
        try:
            # Fast path: a fully numeric column converts in one vectorised step.
            arr = np.array(cells, dtype=np.float64)
        except ValueError:
            arr = np.full(n_rows, np.nan, dtype=np.float64)
            for r_i, cell in enumerate(cells):
                try:
                    arr[r_i] = float(cell)
                except ValueError:
                    pass
        if np.isfinite(arr).any():
            columns_data[name] = arr
    units_dict: Dict[str, str] = {name: "" for name in columns_data}

    return Pds3Table(
        label_path="",
        table_path=str(p),
        metadata={"AUTO_PARSED": True, "ROW_COUNT": n_rows},
        columns=columns_data,
        units=units_dict,
    )
