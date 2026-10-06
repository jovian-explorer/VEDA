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

REFERENCES: Dict[str, Dict[str, object]] = {
    "venus": {
        "name": "Venus-GRAM 2021 global average (VIRA below 100 km)",
        "citation": ("Justh, H. L., Dwyer Cianciolo, A. M., Hoffman, J. (2021). Venus Global Reference Atmospheric "
                     "Model (Venus-GRAM): User Guide. NASA/TM-20210022168. Based on Seiff, A., et al. (1985). "
                     "Models of the structure of the atmosphere of Venus from the surface to 100 km altitude. "
                     "Adv. Space Res. 5(11), 3-58. Table from the NASA Aviary project (Apache License 2.0)."),
        "table": VENUS_GRAM_2021,
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
                                      "altitude_range_km": [ref["table"][0][0], ref["table"][-1][0]]}
