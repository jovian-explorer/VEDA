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
    text_columns: Dict[str, List[str]] = field(default_factory=dict)   # CHARACTER columns, as text

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



@dataclass
class TableDef:
    """One TABLE object of a PDS3 label and where its rows are."""
    name: str
    rows: int
    columns: List[ColumnDef]
    file: Optional[str] = None      # data file from the ^NAME pointer
    record: int = 1                 # first record (1-based) of the table in that file


def _label_lines(label_text: str) -> List[str]:
    """Label statements, one per KEY = VALUE, however the value is wrapped.

    A statement ends at a newline outside quotes, so quoted values spanning
    lines stay whole even when a continuation line starts with '=' (the
    Magellan labels quote an SQL query). A keyword whose value starts on the
    next line ("DESCRIPTION =" then the text) is joined to that value.
    """
    text = _strip_comments(label_text)
    stmts, buf, in_quote = [], [], False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
        if ch in "\r\n" and not in_quote:
            line = " ".join("".join(buf).split())
            if line:
                stmts.append(line)
            buf = []
            continue
        buf.append(" " if ch in "\r\n" else ch)
    tail = " ".join("".join(buf).split())
    if tail:
        stmts.append(tail + ('"' if in_quote else ""))
    out: List[str] = []
    for s in stmts:
        if out and out[-1].endswith("=") and "=" not in s.split('"', 1)[0]:
            out[-1] = out[-1] + " " + s          # value on the line after the keyword
        else:
            out.append(s)
    return out


def _pointer(value: str) -> Tuple[Optional[str], int]:
    """^X = "f.tab" | ("f.tab", 4) | ("f.tab", 1200 <BYTES>) | 4 -> (file, record)."""
    v = value.strip()
    m = re.match(r'^\(?\s*"?([^",)\s]+)"?\s*(?:,\s*(\d+)\s*(<BYTES>)?)?\s*\)?$', v)
    if not m:
        return None, 1
    first = m.group(1)
    if first.isdigit() and m.group(2) is None:
        return None, int(first)           # record in the label's own file
    rec = int(m.group(2)) if m.group(2) and not m.group(3) else 1
    return first, rec


def parse_pds3_tables(label_text: str) -> List[TableDef]:
    """TABLE / SERIES / SPREADSHEET objects with their own columns and pointers."""
    lines = _label_lines(label_text)
    pointers: Dict[str, str] = {}
    for l in lines:
        if l.startswith("^") and "=" in l:
            k, v = l.split("=", 1)
            pointers[k.strip()[1:].upper()] = v.strip()
    tables: List[TableDef] = []
    stack: List[Tuple[str, Dict[str, Any], List[ColumnDef]]] = []
    for l in lines:
        key, sep, val = (x.strip() for x in l.partition("="))
        key = key.upper()
        if not sep and key != "END_OBJECT":
            continue
        val_c = val.strip('"').strip()
        if key == "OBJECT":
            stack.append((val_c.upper(), {}, []))
        elif key == "END_OBJECT":
            if not stack:
                continue
            name, attrs, cols = stack.pop()
            if name == "COLUMN" and stack:
                try:
                    stack[-1][2].append(ColumnDef(
                        name=attrs.get("NAME", f"COL_{len(stack[-1][2]) + 1}"),
                        column_number=int(attrs.get("COLUMN_NUMBER", len(stack[-1][2]) + 1)),
                        start_byte=int(attrs.get("START_BYTE", 1)), bytes_count=int(attrs.get("BYTES", 10)),
                        data_type=attrs.get("DATA_TYPE", "ASCII_REAL"), unit=attrs.get("UNIT", ""),
                        invalid_constant=_num(attrs.get("INVALID_CONSTANT")),
                        missing_constant=_num(attrs.get("MISSING_CONSTANT"))))
                except ValueError:
                    pass
            elif cols and (name.endswith("TABLE") or name.endswith("SERIES") or name.endswith("SPREADSHEET")):
                f, rec = _pointer(pointers.get(name, ""))
                try:
                    rows = int(attrs.get("ROWS", 0))
                except ValueError:
                    rows = 0
                tables.append(TableDef(name=name, rows=rows, columns=cols, file=f, record=rec))
        elif stack:
            stack[-1][1][key] = val_c
    return tables


def _num(v: Optional[str]) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def parse_pds3_label(label_text: str) -> Tuple[Dict[str, Any], List[ColumnDef]]:
    """Top-level keywords and every COLUMN object of a PDS3 label.

    Objects are tracked with a stack, so a bare END_OBJECT (allowed by PDS3,
    used e.g. by the Galileo probe volumes) closes the current object, and
    keywords inside objects never overwrite top-level metadata.
    """
    metadata: Dict[str, Any] = {}
    columns: List[ColumnDef] = []
    stack: List[Tuple[str, Dict[str, str]]] = []
    for line in _label_lines(label_text):
        key, sep, val = line.partition("=")
        key = key.strip().upper()
        val = val.strip()
        val_clean = val[1:-1] if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'" else val
        if key == "END":
            break
        if key == "OBJECT" and sep:
            stack.append((val_clean.strip().upper(), {}))
        elif key == "END_OBJECT":
            if not stack:
                continue
            name, attrs = stack.pop()
            if name == "COLUMN":
                try:
                    columns.append(ColumnDef(
                        name=attrs.get("NAME", f"COL_{len(columns) + 1}"),
                        column_number=int(attrs.get("COLUMN_NUMBER", len(columns) + 1)),
                        start_byte=int(attrs.get("START_BYTE", 1)),
                        bytes_count=int(attrs.get("BYTES", 10)),
                        data_type=attrs.get("DATA_TYPE", "ASCII_REAL"),
                        unit=attrs.get("UNIT", ""),
                        invalid_constant=_num(attrs.get("INVALID_CONSTANT")),
                        missing_constant=_num(attrs.get("MISSING_CONSTANT"))))
                except ValueError:
                    pass
        elif sep:
            if stack:
                stack[-1][1][key] = val_clean
            else:
                metadata[key] = val_clean
    return metadata, columns


def _find_file(folder: Path, name: str) -> Optional[Path]:
    for cand in (name, name.lower(), name.upper()):
        p = folder / cand
        if p.exists():
            return p
    return None


def _parse_value(chunk: str, c: ColumnDef) -> float:
    f_val = float(chunk)
    if c.invalid_constant is not None and abs(f_val - c.invalid_constant) < 1e-4:
        return np.nan
    if c.missing_constant is not None and abs(f_val - c.missing_constant) < 1e-4:
        return np.nan
    if c.invalid_constant is None and c.missing_constant is None and             (abs(f_val + 999.0) < 1e-3 or abs(f_val + 9999.0) < 1e-3):
        return np.nan            # common undeclared fill values
    return f_val


def _read_rows(lines: List[str], cols: List[ColumnDef]) -> Dict[str, np.ndarray]:
    """Numeric columns of a table, by CSV when the rows are comma separated, else by byte position."""
    n = len(lines)
    out: Dict[str, np.ndarray] = {}
    first = lines[0] if lines else ""
    import csv
    rows = list(csv.reader(lines)) if ("," in first and len(first.split(",")) >= len(cols)) else None
    for idx, c in enumerate(cols):
        arr = np.full(n, np.nan, dtype=np.float64)
        for r_i in range(n):
            if rows is not None:
                c_idx = c.column_number - 1 if 0 <= c.column_number - 1 < len(rows[r_i]) else idx
                chunk = rows[r_i][c_idx] if c_idx < len(rows[r_i]) else ""
            else:
                s = c.start_byte - 1
                chunk = lines[r_i][s:s + c.bytes_count] if s < len(lines[r_i]) else ""
            chunk = chunk.strip().strip(",").strip('"').strip("'")
            if chunk:
                try:
                    arr[r_i] = _parse_value(chunk, c)
                except ValueError:
                    pass
        out[c.name] = arr
    return out


def _read_text(lines: List[str], cols: List[ColumnDef]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for c in cols:
        if "CHAR" not in (c.data_type or "").upper():
            continue
        s = c.start_byte - 1
        out[c.name] = [ln[s:s + c.bytes_count].strip().strip('"').strip() for ln in lines]
    return out


def _rejoin_broken_records(lines: List[str]) -> List[str]:
    """Repair fixed-length records split by stray line breaks.

    Some archive copies have a newline inserted mid-record about every 32 KB
    (seen in Magellan MGN_RTPD.DAT: 117-character records split 81 + 36). A
    short line is joined to the next one when together they make exactly the
    usual record length, so genuine short records are left alone.
    """
    from collections import Counter
    lengths = Counter(len(l) for l in lines if l.strip())
    if not lengths:
        return lines
    target, count = lengths.most_common(1)[0]
    if count < 0.8 * sum(lengths.values()):
        return lines            # not a fixed-length table
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if 0 < len(line) < target and i + 1 < len(lines) and len(line) + len(lines[i + 1]) == target:
            out.append(line + lines[i + 1])
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def read_pds3_table(table_or_label_path: str) -> Pds3Table:
    """Read the main table of a PDS3 product (label + data file).

    The data file is found through the table's pointer (any extension, either
    case), falling back to <label>.tab. Labels with several tables (e.g. a
    one-row header table and the profile table in the same file, MGS RS) are
    read table by table from their starting record; the largest table is
    returned and one-row tables are kept in ``metadata['HEADER_TABLES']``.
    """
    p = Path(table_or_label_path)
    if p.suffix.lower() == ".lbl":
        lbl_p = p
    else:
        lbl_p = _find_file(p.parent, p.with_suffix(".lbl").name) or p.with_suffix(".lbl")
    if not lbl_p.exists():
        raise FileNotFoundError(f"PDS3 label not found at {lbl_p}")

    lbl_text = lbl_p.read_text(encoding="utf-8", errors="replace")
    metadata, col_defs = parse_pds3_label(lbl_text)
    tables = parse_pds3_tables(lbl_text)
    if not tables and col_defs:
        # Loosely written labels put COLUMN objects outside any TABLE object.
        ptr = next((metadata[k] for k in metadata if k.startswith("^") and
                    (k.endswith("TABLE") or k.endswith("SPREADSHEET") or k.endswith("SERIES"))), "")
        f, rec = _pointer(str(ptr)) if ptr else (None, 1)
        tables = [TableDef(name="TABLE", rows=0, columns=col_defs, file=f, record=rec)]

    if not tables:
        is_img = any(k.endswith("_IMAGE") or k.endswith("_HEADER") for k in metadata) or             str(metadata.get("FILE_NAME", "")).lower().endswith((".fit", ".fits"))
        if is_img or metadata.get("^IMAGE"):
            raise ValueError(f"PDS3 label references an image file ({metadata.get('FILE_NAME') or metadata.get('^IMAGE')}), not a tabular dataset")
        raise ValueError(f"{lbl_p.name} describes no table")

    main = max(tables, key=lambda t: (t.rows, len(t.columns)))
    data_p = None
    if main.file:
        data_p = _find_file(lbl_p.parent, main.file)
    if data_p is None and p.suffix.lower() != ".lbl" and p.exists():
        data_p = p
    if data_p is None:
        data_p = _find_file(lbl_p.parent, lbl_p.with_suffix(".tab").name)
    if data_p is None:
        raise FileNotFoundError(f"PDS3 table not found at {lbl_p.parent / (main.file or lbl_p.with_suffix('.tab').name)}")

    all_lines = _rejoin_broken_records(data_p.read_text(encoding="utf-8", errors="replace").splitlines())

    def table_lines(t: TableDef) -> List[str]:
        if t.file and t.file.lower() != data_p.name.lower():
            return []
        start = max(t.record - 1, 0)
        chunk = all_lines[start:start + t.rows] if t.rows else all_lines[start:]
        return [ln for ln in chunk if ln.strip()]

    lines = table_lines(main)
    if not lines and main.rows == 0:
        lines = [ln for ln in all_lines if ln.strip()]
    columns_data = _read_rows(lines, main.columns)
    units_dict = {c.name: c.unit for c in main.columns}
    text_data = _read_text(lines, main.columns)

    headers = {}
    for t in tables:
        if t is main or t.rows != 1:
            continue
        hl = table_lines(t)
        if hl:
            vals = _read_rows(hl[:1], t.columns)
            headers[t.name] = {c.name: (float(vals[c.name][0]) if np.isfinite(vals[c.name][0]) else None) for c in t.columns}
    if headers:
        metadata["HEADER_TABLES"] = headers

    return Pds3Table(
        label_path=str(lbl_p),
        table_path=str(data_p),
        metadata=metadata,
        columns=columns_data,
        units=units_dict,
        text_columns=text_data,
    )


def read_any_table(file_path: str) -> Pds3Table:
    """Read any tabular data file (PDS3 table, CSV, TSV, or whitespace-delimited ASCII).

    If a PDS3 label is found, delegates to read_pds3_table. Otherwise parses header
    and numeric columns automatically.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if p.suffix.lower() == ".xml":
        from .pds4_reader import is_pds4_label, read_pds4_table
        if is_pds4_label(p):
            return read_pds4_table(str(p))
        raise ValueError(f"{p.name} is not a PDS4 product label")

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
