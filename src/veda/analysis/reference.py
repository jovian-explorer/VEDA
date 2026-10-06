"""Published reference atmospheres to compare profiles with.

Venus: the global-average profile of the NASA Venus Global Reference Atmospheric Model
(Venus-GRAM 2021, GRAM Suite 2.1; Justh et al. 2021, NASA/TM-20210022168), which below
100 km is the Venus International Reference Atmosphere (VIRA, Seiff et al. 1985, Adv.
Space Res. 5(11), 3-58) mean profile.  The table (0-150 km, temperature, pressure,
density at geometric altitudes above the 6051.8 km reference sphere) is the one
extracted from Venus-GRAM 2021 by NASA Glenn Research Center for the Aviary project
(github.com/OpenMDAO/Aviary, aviary/subsystems/atmosphere/data/VenusReference2021.py,
commit 897eee5, Apache License 2.0, copyright United States of America as represented
by the Administrator of NASA).  It is independent of latitude, season and local time:
VIRA's own latitude dependence above 33 km is not in it.

Mars: the global-average profile of the NASA Mars Global Reference Atmospheric Model
(Mars-GRAM 2024, GRAM Suite 2.1; NASA/TM-20240012934), extracted by NASA Glenn Research
Center for Aviary (aviary/subsystems/atmosphere/data/MarsReference2024.py, commit
fe9a988, same licence), "global average conditions, independent of year, season, or time
of day", checked by NASA Ames against Mars global climate model annual averages; dust
optical depth 0.3, -8 to 80 km.  Its altitudes are above the MOLA areoid (the table's
own docstring says geopotential, but its pressures are hydrostatic for geometric heights
with g falling as 1/r^2: within 3 % up to 80 km, against 20 % off with constant g).  The
areoid lies up to about 7 km above (equator) and 13 km below (poles) the 3389.5 km
sphere VEDA's Mars profiles are referred to, so on altitude levels the comparison is
only approximate; on pressure levels it is not affected.  The Mars Climate Database is
not used: its terms (www-mars.lmd.jussieu.fr/mars/access.html) allow scientific use but
no commercial use without authorisation, which VEDA's MIT licence could not pass on, and
the full version is given out on registration.

Between the tabulated levels temperature is interpolated linearly and pressure and
density in log space.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

# altitude (km), temperature (K), pressure (mbar = hPa), density (kg/m^3)
VENUS_GRAM_2021 = (
    (0, 735.3, 9.21e+04, 6.48e+01),
    (1, 727.7, 8.65e+04, 6.16e+01),
    (2, 720.2, 8.11e+04, 5.85e+01),
    (3, 712.4, 7.60e+04, 5.55e+01),
    (4, 704.6, 7.12e+04, 5.26e+01),
    (5, 696.8, 6.67e+04, 4.99e+01),
    (6, 688.8, 6.23e+04, 4.72e+01),
    (7, 681.1, 5.83e+04, 4.47e+01),
    (8, 673.6, 5.44e+04, 4.23e+01),
    (9, 665.8, 5.08e+04, 4.00e+01),
    (10, 658.2, 4.74e+04, 3.77e+01),
    (15, 620.8, 3.30e+04, 2.80e+01),
    (20, 580.7, 2.25e+04, 2.04e+01),
    (25, 539.2, 1.49e+04, 1.46e+01),
    (30, 496.9, 9.58e+03, 1.02e+01),
    (40, 417.6, 3.50e+03, 4.40e+00),
    (50, 350.5, 1.07e+03, 1.59e+00),
    (60, 262.8, 2.36e+02, 4.69e-01),
    (70, 229.8, 3.69e+01, 8.39e-02),
    (80, 197.1, 4.47e+00, 1.19e-02),
    (90, 169.4, 3.74e-01, 1.15e-03),
    (100, 173.95, 2.67e-02, 7.99e-05),
    (110, 158, 1.76e-03, 5.81e-06),
    (120, 159, 9.88e-05, 3.20e-07),
    (130, 166.8, 6.27e-06, 1.85e-08),
    (140, 176.2, 5.89e-07, 1.39e-09),
    (150, 194.22, 9.55e-08, 1.61e-10),
)

# altitude above the MOLA areoid (km), temperature (K), pressure (mbar = hPa), density (kg/m^3)
MARS_GRAM_2024 = (
    (-8, 214.0, 1.31E+01, 3.21E-02),
    (-7, 214.0, 1.20E+01, 2.94E-02),
    (-6.1151, 214.0, 1.10E+01, 2.71E-02),
    (-6.1051, 214.0, 1.10E+01, 2.71E-02),
    (-6, 214.0, 1.09E+01, 2.68E-02),
    (-5, 214.0, 1.00E+01, 2.45E-02),
    (-4, 214.0, 9.16E+00, 2.24E-02),
    (-3, 214.0, 8.36E+00, 2.04E-02),
    (-2, 214.0, 7.63E+00, 1.87E-02),
    (-1, 214.0, 6.96E+00, 1.70E-02),
    (0, 214.0, 6.36E+00, 1.55E-02),
    (1, 213.9, 5.80E+00, 1.42E-02),
    (2, 213.8, 5.30E+00, 1.30E-02),
    (3, 213.6, 4.84E+00, 1.18E-02),
    (4, 213.4, 4.41E+00, 1.08E-02),
    (5, 212.9, 4.03E+00, 9.90E-03),
    (6, 212.4, 3.68E+00, 9.06E-03),
    (7, 210.8, 3.35E+00, 8.32E-03),
    (8, 209.2, 3.06E+00, 7.65E-03),
    (9, 207.1, 2.79E+00, 7.04E-03),
    (10, 205.0, 2.54E+00, 6.47E-03),
    (15, 196.2, 1.56E+00, 4.17E-03),
    (20, 188.3, 9.47E-01, 2.63E-03),
    (25, 181.2, 5.62E-01, 1.62E-03),
    (30, 175.0, 3.28E-01, 9.80E-04),
    (40, 162.4, 1.06E-01, 3.40E-04),
    (50, 152.2, 3.15E-02, 1.08E-04),
    (60, 144.2, 8.78E-03, 3.18E-05),
    (70, 139.5, 2.33E-03, 8.73E-06),
    (80, 139.0, 6.08E-04, 2.29E-06),
)

REFERENCES: Dict[str, Dict[str, object]] = {
    "venus": {
        "name": "Venus-GRAM 2021 global average (VIRA below 100 km)",
        "citation": ("Justh, H. L., Dwyer Cianciolo, A. M., Hoffman, J. (2021). Venus Global Reference Atmospheric "
                     "Model (Venus-GRAM): User Guide. NASA/TM-20210022168. Based on Seiff, A., et al. (1985). "
                     "Models of the structure of the atmosphere of Venus from the surface to 100 km altitude. "
                     "Adv. Space Res. 5(11), 3-58. Table from the NASA Aviary project (Apache License 2.0)."),
        "table": VENUS_GRAM_2021,
    },
    "mars": {
        "name": "Mars-GRAM 2024 global average",
        "citation": ("Justh, H. L., et al. (2024). Mars Global Reference Atmospheric Model (Mars-GRAM) 2024: User "
                     "Guide. NASA/TM-20240012934. Global average conditions (dust optical depth 0.3). Table from the "
                     "NASA Aviary project (Apache License 2.0)."),
        "note": ("Altitudes above the MOLA areoid, up to about 7 km above (equator) and 13 km below (poles) the "
                 "3389.5 km sphere of VEDA's Mars profiles: compare on pressure levels (Vertical: Pressure)."),
        "table": MARS_GRAM_2024,
    },
}

# Variables a reference gives: from its columns, or derived from them with the body constants
REFERENCE_VARIABLES = ("temperature_k", "temperature_c", "pressure_hpa", "density", "scale_height")


def reference_profile(body_id: str, variable: str, z_km, body=None) -> Optional[np.ndarray]:
    """The reference atmosphere of ``body_id`` for ``variable`` at altitudes ``z_km``
    (NaN outside the table), or None when there is none."""
    ref = REFERENCES.get(body_id)
    if ref is None or variable not in REFERENCE_VARIABLES:
        return None
    t = np.array(ref["table"], dtype=float)
    z = np.asarray(z_km, dtype=float)
    inside = (z >= t[0, 0]) & (z <= t[-1, 0])
    temp = np.interp(z, t[:, 0], t[:, 1])
    if variable == "temperature_k":
        out = temp
    elif variable == "temperature_c":
        out = temp - 273.15
    elif variable == "pressure_hpa":
        out = np.exp(np.interp(z, t[:, 0], np.log(t[:, 2])))
    elif variable == "density":
        out = np.exp(np.interp(z, t[:, 0], np.log(t[:, 3])))
    else:                                                    # scale height R T / g(z), km
        from ..core.registry import get_body
        b = body or get_body(body_id)
        g = b.surface_gravity * (b.radius_km / (b.radius_km + z)) ** 2
        out = b.gas_constant_r * temp / (g * 1000.0)
    return np.where(inside, out, np.nan)


def reference_on_pressure(body_id: str, variable: str, p_hpa, body=None) -> Optional[np.ndarray]:
    """The reference at pressure levels ``p_hpa`` (its altitude there from its own
    pressure, log-interpolated), or None."""
    ref = REFERENCES.get(body_id)
    if ref is None or variable not in REFERENCE_VARIABLES or variable == "pressure_hpa":
        return None
    t = np.array(ref["table"], dtype=float)
    lp = np.log(np.asarray(p_hpa, dtype=float))
    order = np.argsort(np.log(t[:, 2]))
    z = np.interp(lp, np.log(t[order, 2]), t[order, 0], left=np.nan, right=np.nan)
    return reference_profile(body_id, variable, z, body)


def reference_info(body_id: str) -> Optional[Dict[str, object]]:
    ref = REFERENCES.get(body_id)
    return None if ref is None else {"name": ref["name"], "citation": ref["citation"],
                                      "altitude_range_km": [ref["table"][0][0], ref["table"][-1][0]],
                                      **({"altitude_note": ref["note"]} if ref.get("note") else {})}
