"""Human-readable vocabulary for CDAAC variables.

Two audiences are served from one table: ``label``/``units`` for the
scientist, ``plain`` for the curious visitor.  ``role`` tells the UI whether a
variable is a sensible vertical coordinate, a plottable field, or metadata.
"""
from __future__ import annotations

VERTICAL = "vertical"      # usable as the y-axis of a profile plot
FIELD = "field"            # usable as the x-axis of a profile plot
COORD = "coord"            # geolocation / time, plottable but rarely the point
AUX = "aux"                # flags, diagnostics, ancillary geometry

VAR_INFO: dict[str, dict] = {
    # ---- vertical coordinates ----------------------------------------
    "MSL_alt": dict(label="Altitude above mean sea level", units="km",
                    plain="Height above sea level.", role=VERTICAL),
    "gph": dict(label="Geopotential height", units="km",
                plain="Height corrected for how gravity weakens with altitude.",
                role=VERTICAL),
    "Impact_height": dict(label="Impact height", units="km",
                          plain="Height of the straight-line ray path - the natural "
                               "vertical scale for bending angle.", role=VERTICAL),
    "Imp_height_corr": dict(label="Impact height (corrected)", units="km",
                            plain="Impact height after a geometry correction.",
                            role=VERTICAL),
    "occheight": dict(label="Occultation (tangent point) height", units="km",
                      plain="Height of the point where the ray grazes closest to Earth.",
                      role=VERTICAL),
    "alt": dict(label="Spacecraft altitude", units="km",
                plain="How high the satellite itself was flying.", role=VERTICAL),
    "Pres": dict(label="Pressure", units="hPa",
                 plain="Air pressure - the weight of the atmosphere above you.",
                 role=FIELD),
    "pres_dry": dict(label="Dry pressure", units="hPa",
                     plain="Pressure worked out while ignoring water vapour.",
                     role=FIELD),

    # ---- neutral atmosphere fields -----------------------------------
    "Temp": dict(label="Temperature", units="C",
                 plain="How warm the air is.", role=FIELD),
    "temp_dry": dict(label="Dry temperature", units="C",
                     plain="Temperature assuming the air holds no water vapour. Above "
                          "about 10 km that assumption is excellent.", role=FIELD),
    "Vp": dict(label="Water-vapour partial pressure", units="hPa",
               plain="The share of the air pressure contributed by water vapour.",
               role=FIELD),
    "sph": dict(label="Specific humidity", units="g/kg",
                plain="Grams of water vapour in each kilogram of air.", role=FIELD),
    "rh": dict(label="Relative humidity", units="%",
               plain="How close the air is to being saturated with water.", role=FIELD),
    "ref": dict(label="Refractivity", units="N-units",
                plain="How strongly the air bends radio waves.", role=FIELD),
    "Ref": dict(label="Refractivity", units="N-units",
                plain="How strongly the air bends radio waves.", role=FIELD),
    "Ref_L1": dict(label="Refractivity from L1 only", units="N-units",
                   plain="Refractivity from just one of the two radio frequencies.",
                   role=FIELD),
    "Bend_ang": dict(label="Bending angle (ionosphere-corrected)", units="rad",
                     plain="The angle by which the atmosphere bent the radio ray. "
                          "This is the fundamental measurement.", role=FIELD),
    "Bend_ang1": dict(label="Bending angle, L1", units="rad",
                      plain="Bending measured on the first radio frequency.", role=FIELD),
    "Bend_ang2": dict(label="Bending angle, L2", units="rad",
                      plain="Bending measured on the second radio frequency.", role=FIELD),
    "Bend_ang_stdv": dict(label="Bending-angle standard deviation", units="rad",
                          plain="Uncertainty on the bending angle.", role=AUX),
    "Bend_ang_conf": dict(label="Bending-angle confidence", units="%",
                          plain="A quality score for the bending angle.", role=AUX),

    # ---- ionosphere ---------------------------------------------------
    "ELEC_dens": dict(label="Electron density", units="el/cm3",
                      plain="How many free electrons sit in each cubic centimetre.",
                      role=FIELD),
    "TEC_cal": dict(label="Calibrated TEC", units="TECU",
                    plain="Total electrons along the signal path.", role=FIELD),
    "ion_dens": dict(label="Ion density (in-situ)", units="N/cc",
                     plain="Plasma density measured right at the spacecraft.",
                     role=FIELD),
    "ion_temp": dict(label="Ion temperature", units="K",
                     plain="Temperature of the charged particles.", role=FIELD),
    "ap_pot": dict(label="Spacecraft potential", units="V",
                   plain="Electrical charge the spacecraft built up.", role=AUX),
    "iv_zon": dict(label="Zonal ion drift", units="m/s",
                   plain="East-west speed of the plasma.", role=FIELD),
    "iv_mer": dict(label="Meridional ion drift", units="m/s",
                   plain="North-south speed of the plasma.", role=FIELD),
    "iv_par": dict(label="Field-parallel ion drift", units="m/s",
                   plain="Plasma speed along the magnetic field.", role=FIELD),
    "iv_ew": dict(label="Ion drift, east", units="m/s", plain="Eastward plasma speed.",
                  role=FIELD),
    "iv_ns": dict(label="Ion drift, north", units="m/s", plain="Northward plasma speed.",
                  role=FIELD),
    "iv_ud": dict(label="Ion drift, up", units="m/s", plain="Upward plasma speed.",
                  role=FIELD),
    "mlt": dict(label="Magnetic local time", units="h",
                plain="Local time measured against the magnetic pole.", role=COORD),
    "mlat": dict(label="Magnetic latitude", units="deg",
                 plain="Latitude measured from the magnetic equator.", role=COORD),

    # ---- scintillation -------------------------------------------------
    "s4_L1": dict(label="S4 index, L1", units="-",
                  plain="How much the signal strength flickered (0 = steady, "
                       ">0.3 = strong turbulence).", role=FIELD),
    "s4_L2": dict(label="S4 index, L2", units="-",
                  plain="Signal flicker on the second frequency.", role=FIELD),
    "sigma_phi_L1": dict(label="Phase scintillation sigma-phi, L1", units="m",
                         plain="How much the signal's phase jittered.", role=FIELD),
    "sigma_phi_L2": dict(label="Phase scintillation sigma-phi, L2", units="m",
                         plain="Phase jitter on the second frequency.", role=FIELD),
    "L1_SNR": dict(label="L1 signal-to-noise ratio", units="0.1 V/V",
                   plain="How strong the received signal was.", role=FIELD),
    "L2_SNR": dict(label="L2 signal-to-noise ratio", units="0.1 V/V",
                   plain="Strength of the second frequency.", role=FIELD),
    "elevation": dict(label="Elevation angle", units="deg",
                      plain="How high above the horizon the transmitter appeared.",
                      role=COORD),
    "slip_L1": dict(label="Cycle slips, L1", units="count",
                    plain="Times the receiver lost lock on the signal.", role=AUX),
    "slip_L2": dict(label="Cycle slips, L2", units="count",
                    plain="Lock losses on the second frequency.", role=AUX),
    "RFI": dict(label="Radio-frequency interference flag", units="-",
                plain="Marks samples contaminated by interference.", role=AUX),

    # ---- geolocation ---------------------------------------------------
    "Lat": dict(label="Latitude", units="deg N", plain="North-south position.",
                role=COORD),
    "Lon": dict(label="Longitude", units="deg E", plain="East-west position.",
                role=COORD),
    "lat": dict(label="Latitude", units="deg N", plain="North-south position.",
                role=COORD),
    "lon": dict(label="Longitude", units="deg E", plain="East-west position.",
                role=COORD),
    "GEO_lat": dict(label="Latitude", units="deg N", plain="North-south position.",
                    role=COORD),
    "GEO_lon": dict(label="Longitude", units="deg E", plain="East-west position.",
                    role=COORD),
    "Azim": dict(label="Ray azimuth", units="deg",
                 plain="Compass direction the ray travelled.", role=AUX),
    "OCC_azi": dict(label="Occultation azimuth", units="deg",
                    plain="Compass direction of the measurement.", role=AUX),
    "time": dict(label="Time", units="s", plain="Seconds since the start of the record.",
                 role=COORD),
    "uts": dict(label="Time (UTC)", units="s since 1970-01-01",
                plain="Clock time of each sample.", role=COORD),

    # ---- derived by this application -----------------------------------
    "theta": dict(label="Potential temperature", units="K",
                  plain="Temperature an air parcel would have if brought to 1000 hPa. "
                       "Constant along adiabatic motion.", role=FIELD),
    "lapse_rate": dict(label="Lapse rate", units="K/km",
                       plain="How fast temperature falls with height.", role=FIELD),
    "dNdz": dict(label="Refractivity gradient", units="N-units/km",
                 plain="How quickly the bending power changes with height. Below "
                      "-157 the atmosphere traps radio waves (ducting).", role=FIELD),
    "N_anom_pct": dict(label="Refractivity anomaly", units="%",
                       plain="Departure from the profile set's own mean.", role=FIELD),
    "buoyancy_freq_sq": dict(label="Squared buoyancy frequency N^2", units="s^-2",
                             plain="Atmospheric stiffness against vertical motion; "
                                  "controls gravity-wave propagation.", role=FIELD),
    "density": dict(label="Atmospheric Density", units="kg/m^3",
                    plain="Mass of the air per cubic metre, derived from dry temperature and pressure.", role=FIELD),
    "scale_height": dict(label="Scale Height", units="km",
                         plain="Vertical distance over which atmospheric pressure drops by a factor of e.", role=FIELD),
}

# Preferred x-axis for a quick look at each product.
DEFAULT_FIELD = {
    "atmPrf": "Temp",
    "wetPf2": "Temp",
    "ionPrf": "ELEC_dens",
    "scnLv2": "s4_L1",
    "ivmL2m": "ion_dens",
}
DEFAULT_VERTICAL = {
    "atmPrf": "MSL_alt",
    "wetPf2": "MSL_alt",
    "ionPrf": "MSL_alt",
    "scnLv2": "occheight",
    "ivmL2m": "alt",
}


def info(name: str) -> dict:
    """Vocabulary entry for ``name``, with a safe fallback."""
    d = VAR_INFO.get(name)
    if d:
        return dict(d, name=name)
    return dict(name=name, label=name, units="", plain="", role=FIELD)


# Normalise verbose or non-standard unit strings that CDAAC files sometimes
# carry, so that axis labels are always human-readable.
_UNIT_MAP: dict[str, str] = {
    "Celsius_degree": "°C",
    "celsius_degree": "°C",
    "celsius": "°C",
    "degree_Celsius": "°C",
    "degreesC": "°C",
    "degC": "°C",
    "kelvin": "K",
    "Kelvin": "K",
    "degrees_north": "°N",
    "degrees_east": "°E",
    "degrees": "°",
    "radian": "rad",
    "radians": "rad",
    "hpa": "hPa",
    "Pa": "Pa",
    "kilogram/kilogram": "kg/kg",
    "meters": "m",
    "meter": "m",
    "kilometers": "km",
    "kilometre": "km",
    "km/s": "km/s",
    "m/s": "m/s",
    "1/cm3": "el/cm³",
    "el/cm3": "el/cm³",
    "electrons/cm3": "el/cm³",
    "TECU": "TECU",
}


def normalise_units(raw: str) -> str:
    """Return a clean display string for a raw unit attribute value."""
    if not raw:
        return raw
    return _UNIT_MAP.get(raw, raw)


def axis_title(name: str, units: str | None = None) -> str:
    d = info(name)
    u = normalise_units(units if units is not None else d["units"])
    return f"{d['label']} [{u}]" if u and u != "-" else d["label"]
