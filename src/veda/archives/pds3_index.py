"""Read PDS3 volume index tables (index/index.lbl + index/index.tab).

Every PDS3 archive volume lists its products in an index table: one row per
product with its file path, start/stop time, target and so on.  VEDA reads
these to offer search by instrument, date and target without crawling data
directories.
"""
from __future__ import annotations

import csv
import io
from typing import Dict, List

from ..readers.pds3_reader import parse_pds3_label


def _clean(value: str) -> str:
    return value.strip().strip('"').strip()


def parse_index(label_text: str, table_text: str) -> List[Dict[str, str]]:
    """Rows of the index as {COLUMN_NAME: text}, column names upper-case."""
    _, columns = parse_pds3_label(label_text)
    columns = [c for c in columns if c.start_byte and c.bytes_count]
    lines = [ln for ln in table_text.splitlines() if ln.strip()]
    if not lines:
        return []

    rows: List[Dict[str, str]] = []
    if columns:
        names = [c.name.strip().strip('"').upper() for c in columns]
        # Most index tables are quoted CSV.  When every row splits into exactly
        # one field per column, trust that over the byte offsets: some labels
        # get the widths wrong (DARTS declares TARGET_NAME as 3 bytes for
        # "VENUS", which shifts every later column).
        csv_rows = list(csv.reader(io.StringIO("\n".join(lines)), skipinitialspace=True))
        if csv_rows and all(len(r) == len(names) for r in csv_rows):
            return [{n: _clean(v) for n, v in zip(names, r)} for r in csv_rows]
        widest = max(c.start_byte - 1 + c.bytes_count for c in columns)
        if all(len(ln) >= widest - 2 for ln in lines[:5]):
            for ln in lines:
                rows.append({n: _clean(ln[c.start_byte - 1:c.start_byte - 1 + c.bytes_count])
                             for n, c in zip(names, columns)})
            if _looks_valid(rows):
                return rows
        # Byte offsets do not fit (some volumes pad differently): fall back to
        # quote-aware comma splitting in label column order.
        rows = []
        for rec in csv.reader(io.StringIO("\n".join(lines)), skipinitialspace=True):
            if len(rec) >= len(names):
                rows.append({n: _clean(v) for n, v in zip(names, rec)})
        return rows

    # No usable label: assume a header row.
    reader = csv.reader(io.StringIO("\n".join(lines)), skipinitialspace=True)
    header = [h.strip().upper() for h in next(reader)]
    return [{h: _clean(v) for h, v in zip(header, rec)} for rec in reader]


def _looks_valid(rows: List[Dict[str, str]]) -> bool:
    """Byte slicing worked if file names look like paths, not fragments."""
    spec = next((k for k in rows[0] if "FILE_SPECIFICATION" in k or k == "FILE_NAME"), None)
    if spec is None:
        return True
    sample = [r[spec] for r in rows[:10]]
    return all("." in s and " " not in s and "," not in s for s in sample)
