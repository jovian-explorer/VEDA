"""Time, latitude and longitude of Juno radio occultations of Jupiter at a given height.

The Juno ionosphere profiles of Caruso et al. (Zenodo 22706200) give the electron density
against height only.  For the perijove in each NAIF reconstructed Juno trajectory file, this
script finds when the straight Juno-Earth line passed ``--height`` km above Jupiter's 1-bar
ellipsoid (71492 x 66854 km) before the ingress and after the egress of Juno's Earth
occultation, and the planetocentric latitude and east longitude of the line's closest point
to the ellipsoid.  Its output is VEDA's JUNO_OCCULTATION_POINTS (archives/datasets.py).
Bending in the ionosphere is neglected.

    python scripts/juno_occultation_points.py <folder with naif0012.tls, pck00011.tpc, spk_rec_*.bsp>

(the trajectory files: https://naif.jpl.nasa.gov/pub/naif/JUNO/kernels/spk/).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import spiceypy as sp

A, C = 71492.0, 66854.0          # 1-bar ellipsoid of Caruso et al. and Coffin et al., km
HEIGHT = 1000.0


def tangent(et: float):
    """Height (km) of the Juno-Earth line above the ellipsoid, for the signal sent at ``et``,
    and the latitude and east longitude (deg) of its closest point; NaN height when that
    point is behind Juno."""
    juno = sp.spkpos("-61", et, "IAU_JUPITER", "NONE", "599")[0]
    earth = sp.spkpos("399", et, "IAU_JUPITER", "XCN", "-61")[0]     # towards the Earth, as received
    pnear, dist = sp.npedln(A, A, C, juno, earth)
    _, lon, lat = sp.reclat(pnear)
    behind = np.dot(pnear - juno, earth) < 0
    return (np.nan if behind else dist), float(np.degrees(lat)), float(np.degrees(lon) % 360.0)


def at_height(edge: float, sign: int) -> float:
    """Time when the line is HEIGHT km up, going away from the occultation edge."""
    lo, hi = 0.0, 3600.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        h = tangent(edge + sign * mid)[0]
        lo, hi = (lo, mid) if (not np.isfinite(h) or h > HEIGHT) else (mid, hi)
    return edge + sign * 0.5 * (lo + hi)


def main(folder: Path) -> None:
    sp.furnsh(str(folder / "naif0012.tls"))
    sp.furnsh(str(folder / "pck00011.tpc"))
    for f in sorted(folder.glob("spk_rec_*.bsp")):
        sp.furnsh(str(f))
        t0, t1 = sp.wnfetd(sp.spkcov(str(f), -61), 0)
        ets = np.arange(t0 + 60, t1 - 60, 300.0)
        pe = ets[int(np.argmin([np.linalg.norm(sp.spkpos("-61", e, "J2000", "NONE", "599")[0]) for e in ets]))]
        win, out = sp.cell_double(2), sp.cell_double(20)
        sp.wninsd(pe - 6 * 3600, pe + 6 * 3600, win)
        sp.gfoclt("ANY", "599", "ELLIPSOID", "IAU_JUPITER", "399", "POINT", "", "XCN", "-61", 10.0, win, out)
        if not sp.wncard(out):
            print(f"# {sp.et2utc(pe, 'ISOC', 0)}: no Earth occultation")
            continue
        ing, egr = sp.wnfetd(out, 0)[0], sp.wnfetd(out, sp.wncard(out) - 1)[1]
        for name, edge, sign in (("I", ing, -1), ("E", egr, +1)):
            et = at_height(edge, sign)
            h, lat, lon = tangent(et)
            print(f"{sp.et2utc(pe, 'ISOC', 0)} {name} {sp.et2utc(et, 'ISOC', 0)} {h:7.1f} {lat:7.2f} {lon:7.2f}")
        sp.unload(str(f))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
