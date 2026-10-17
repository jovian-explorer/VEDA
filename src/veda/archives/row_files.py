"""Files that hold many profiles, one per row, offered as profiles of their own.

A data set with ``profile_rows`` lists the files in the catalogue (kind "table"); each
valid row is the profile ``<file>_P<row>`` (``2006120120_DDR_P017``), read from the file,
which is downloaded once, and never stored in the catalogue.  ``profile_rows`` names the
module that reads the rows, with four functions:

* ``read_file(path)``: the file's rows (cached), a dict with "rows";
* ``valid_rows(d)``: the rows that hold a profile;
* ``row_geometry(d, row)``: latitude, lst, sza and ls of a row, for the comparison filter;
* ``row_profile(ds, prod, path, row)``: the row as an ObservationProfile;

and ``ROW_TYPE``, the product type of a row.  Readers: "mcs_ddr" (MRO MCS, archives/mcs.py),
"iuvs_periapse" (MAVEN IUVS limb scans, readers/iuvs_reader.py), "juno_mwr" (Juno MWR NH3 and
H2O, one column per latitude, archives/juno_mwr.py).
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROW_ID = re.compile(r"^(?P<file>.+)_P(?P<row>\d{3,4})$", re.IGNORECASE)

_READERS = {"mcs_ddr": "veda.archives.mcs", "iuvs_periapse": "veda.readers.iuvs_reader",
            "juno_mwr": "veda.archives.juno_mwr"}


def reader(ds):
    """The module reading the rows of the data set's files."""
    return importlib.import_module(_READERS[ds.profile_rows])


def split_id(product_id: str) -> Optional[Tuple[str, int]]:
    """(file product id, row) of a row profile id, or None."""
    m = ROW_ID.match(product_id or "")
    return (m.group("file"), int(m.group("row"))) if m else None


def row_id(file_id: str, row: int) -> str:
    return f"{file_id}_P{row:03d}"


def sub_product(ds, file_prod: Dict[str, Any], row: int) -> Dict[str, Any]:
    """The catalogue entry of one row (the file's own entry, as a profile)."""
    return {**file_prod, "product_id": row_id(file_prod["product_id"], row), "kind": "profile",
            "product_type": f"{reader(ds).ROW_TYPE} (row {row} of the file)", "row": row,
            "file_product_id": file_prod["product_id"]}


def row_profile(ds, prod: Dict[str, Any], path: Path, row: int):
    return reader(ds).row_profile(ds, prod, path, row)


def candidates(ds, files: List[Dict[str, Any]], fetch, geometry_ok, per_file: int) -> List[Dict[str, Any]]:
    """Profile entries from the data set's ``files`` (catalogue rows), up to ``per_file``
    rows each, spread over the file, of the valid rows whose geometry ``geometry_ok``
    accepts; ``fetch(file)`` gives the downloaded path (or raises).  The files' rows are
    interleaved, so the first entries span all the files' dates."""
    from ..missions.selection import spread_order
    mod = reader(ds)
    per: List[List[Dict[str, Any]]] = []
    for f in files:
        try:
            d = mod.read_file(Path(fetch(f)))
        except Exception:  # noqa: BLE001 - a file that cannot be read gives no candidates
            continue
        rows = [r for r in mod.valid_rows(d) if geometry_ok(mod.row_geometry(d, r))]
        rows = [rows[i] for i in spread_order(len(rows))][:per_file]
        per.append([sub_product(ds, f, r) for r in rows])
    out = []
    for k in range(max((len(x) for x in per), default=0)):
        out += [x[k] for x in per if k < len(x)]
    return out
