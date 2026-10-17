"""Archive datasets VEDA can search.

Each entry points at a real, publicly served PDS3 data set: a directory of
volumes, each with an index/index.tab.  Every URL here was checked against the
archive; add new entries the same way (open the URL, confirm the volumes and
the index exist) rather than guessing paths.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

# (filename regex, product type shown to the user, kind)
#   kind: "profile"    vertical profile VEDA can plot and compare
#         "timeseries" e.g. Doppler / frequency residuals vs time
#         "other"      listed and downloadable, not plotted
Rule = Tuple[str, str, str]


@dataclass(frozen=True)
class Dataset:
    id: str                      # PDS3 DATA_SET_ID, lower case
    mission_id: str
    instrument: str              # payload as the user knows it
    level: str                   # e.g. "L2", "L4"
    title: str
    body_ids: Tuple[str, ...]
    archive: str                 # "JAXA DARTS", "ESA PSA", "NASA PDS ..."
    base_url: str                # directory holding the volumes, ends with /
    volume_pattern: str          # regex for volume directory names
    index_path: Optional[str] = None   # found automatically when None
    rules: Tuple[Rule, ...] = ()
    # Column names in the product label for loadable profiles (match_column
    # handles variants such as "TEMPERATURE (MEDIUM ...)").
    profile_columns: Dict[str, Union[str, Tuple[str, ...]]] = field(default_factory=dict)
    citation: str = ""
    doi: str = ""
    login_url: Optional[str] = None   # portal needing an account
    # Regex on the file name giving the observation time when the index has
    # no START_TIME. Named groups: year (4 digits) or yy, doy or month+day,
    # and optional hh, mm, ss.
    time_from_name: Optional[str] = None
    # Read START_TIME from each product label when the index has no observation
    # time (only for small data sets: one request per product while indexing).
    times_from_labels: bool = False
    # The index lists data files whose labels are detached (same name, .lbl).
    label_from_data: bool = False
    # Documented event time used when neither index nor labels give one
    # (e.g. the Galileo probe labels say START_TIME = "UNK").
    fixed_time: Optional[str] = None
    # Volumes without an index: label paths (inside the volume) to list as products.
    static_labels: Tuple[str, ...] = ()
    # Multi-profile tables: one product per distinct value of these columns.
    split_by: Tuple[str, ...] = ()
    # How a split product's time is found: "ert_rollover" = fixed_time's date plus the
    # first ERT (UT seconds of day) of the group, moving to the next day when ERT wraps.
    split_time: Optional[str] = None
    # Units for columns whose labels give none (taken from the data set's catalogue).
    column_units: Dict[str, str] = field(default_factory=dict)
    # Extra measured variables: key -> (column, uncertainty column or None, label, units)
    extra_variables: Dict[str, Tuple[str, Optional[str]]] = field(default_factory=dict)
    # Vertical reference of an ALTITUDE column.  A number is the radius (km) of the
    # archive's reference sphere: altitudes are moved onto the body's own reference
    # radius, so profiles of different missions share one vertical coordinate.  Text
    # names a reference that is not a sphere (the 1-bar level of a giant planet).
    altitude_reference_km: Optional[float] = None
    altitude_reference: str = ""
    # (equatorial radius km, flattening) of a reference spheroid the ALTITUDE column is
    # measured above, along the normal at the (geodetic) latitude column: altitudes are
    # turned into radii and put on the body's reference sphere, and latitudes become
    # planetocentric (MRO accelerometer: the areodetic spheroid a = 3396.19 km).
    altitude_spheroid: Optional[Tuple[float, float]] = None
    # Other archives holding the same volumes, tried when the primary fails:
    # (base URL, regex on the volume name, replacement), e.g. ESA PSA volume
    # MEX-M-MRS-5-OCC-9103-V1.0 is mexmrs_9103 at the PDS Geosciences Node.
    mirrors: Tuple[Tuple[str, str, str], ...] = ()
    # Fill values that a label states only in prose: column -> values meaning "undefined"
    fill_values: Dict[str, Tuple[float, ...]] = field(default_factory=dict)
    # Uncertainty from two bracketing retrievals: variable -> (column A, column B);
    # sigma = |A - B| / 2 (e.g. PVO temperatures with 150 K and 250 K upper boundaries)
    sigma_from_bracket: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # Uncertainty from independent error tables of the same rows (PDS4 sibling files),
    # added in quadrature: variable -> ((file-name pattern, column), ...)
    sigma_from_siblings: Dict[str, Tuple[Tuple[str, str], ...]] = field(default_factory=dict)
    # Systematic uncertainty from two retrievals with different assumptions, kept apart from
    # the random 1-sigma: variable -> (column A, column B); systematic = |A - B| / 2, and
    # derived quantities get half the difference of their values from A and B
    # (radio occultations: the lower and upper boundary temperature at the top)
    systematic_from_bracket: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # Molar mass (g/mol) of the one gas a number density column is of, where it is not the
    # whole atmosphere (Cassini UVIS: H2): used for the hydrostatic temperature from it
    density_molar_mass: Optional[float] = None
    # The archive's pressures are integrated in its GEOPOTENTIAL column (m^2/s^2 at each
    # tangent point, from a full gravity field with rotation), which VEDA then uses for its
    # hydrostatic integrals instead of g dz (MGS and MRO, D. Hinson: the tangent point
    # drifts in latitude along a profile).  Mars Express gives the column too but integrates
    # with the local gravity at the tangent point; Akatsuki's is GM/r.
    hydrostatic_in_geopotential: bool = False
    # Factor turning the archive's error column into 1 sigma (0.5 for a full error-bar width)
    sigma_factor: Dict[str, float] = field(default_factory=dict)
    # Vertical correlation length (km) of the archived 1-sigma errors, where the archive
    # documents one; 0: the shortest length that each profile's own scatter allows (analysis/uncertainty.py)
    uncertainty_correlation_km: float = 0.0
    # Factor for an extra variable (and its uncertainty) whose label unit is wrong: the
    # Odyssey accelerometer densities are labelled kg/m^3 but are in kg/km^3 (1e-9)
    value_factor: Dict[str, float] = field(default_factory=dict)
    # Aerobraking passes: column of the time from periapsis (s).  Each pass is listed as
    # two profiles, the inbound leg (before periapsis) and the outbound leg, which are at
    # different places and local times and would zigzag if compared as one profile.
    pass_legs: Optional[str] = None
    # Pass legs: the measured density is kept from periapsis outward while it is at least
    # this many times its 1-sigma, and left out beyond (MAVEN accelerometer files run to
    # 300 s from periapsis, 200-230 km, where the density is noise).  0: all levels.
    leg_min_snr: float = 0.0
    # The times (the "et" column, else the catalogue's) are when the signal reached the
    # ground station, not when it crossed the atmosphere (Mars Express MaRS, Akatsuki:
    # "UTC receiver date and time", Magellan: ERT); VEDA subtracts the one-way light time
    # for the profile's time, its local time and the Geometry tab.
    times_earth_received: bool = False
    # Profiles published in a research data repository (Zenodo, BIRA-IASB) without PDS
    # labels: how to list and read them (see archives/repositories.py)
    repository: Dict[str, Any] = field(default_factory=dict)
    # Files holding many profiles, one per table row, offered as profiles <file>_P<row>
    # without listing them in the catalogue ("mcs_ddr": MRO MCS, archives/mcs.py)
    profile_rows: str = ""
    # The gravity the archive's own hydrostatic integration used, where it is not VEDA's
    # ("gm_r2": GM/r^2 without J2 or rotation, MRO MCS), for VEDA's hydrostatic check and
    # temperature from density; the other derived quantities keep VEDA's gravity
    hydrostatic_gravity: str = ""
    # PDS4 bundle: folder (inside the bundle) holding the product XML labels; a tuple
    # gives several folders (Akatsuki LIR: calibrated levels, maps, geometry).
    pds4_product_dir: Optional[Union[str, Tuple[str, ...]]] = None
    # Products sit one level further down, in subfolders listed by the server
    # (Akatsuki: one folder per orbit, r0001 ...): list those too; a number gives the
    # depth (MAVEN accelerometer: 2, year and month folders).
    pds4_walk: Union[bool, int] = False
    # The catalogue time comes from the file name, which gives the date only (MAVEN
    # accelerometer): the label's start time is used when the profile is read.
    label_time: bool = False
    # Header-table fields giving the profile's representative point (time, latitude,
    # longitude, lst, sza), used instead of the medians along the ray path: MAVEN ROSE
    # profiles run to 1000 km and more, and the team gives the point where the ray passes
    # 3550 km from the centre of Mars (about 160 km up, near the electron density peak)
    representative: Dict[str, str] = field(default_factory=dict)
    # Electron densities up to the highest level below this altitude (km) where they are
    # negative beyond 3 sigma are left out: MAVEN ROSE takes all refraction as plasma's,
    # so the neutral atmosphere below about 80 km gives large negative values (its SIS)
    neutral_below_km: Optional[float] = None
    # (label pointer, line name) of a companion text whose line gives the radius (km) below
    # which the electron densities are not valid; where it has a value it replaces the rule
    # above.  MaRS L4 ionosphere: ^ION_INFO, "Lowest valid altitude of ionospheric profile",
    # where the X-band density first rises above -3 sigma going up from the neutral
    # atmosphere, copied into the differential Doppler products (MEX-MRS-RIU-IS-3050, item 16)
    ne_lowest_valid_info: Tuple[str, str] = ()
    # Electron density profiles end at the first level above their peak (the largest density
    # below peak_below_km) where the density is below this many times its 1-sigma; profiles
    # with no such peak above it are left out whole (MAVEN ROSE runs to 1000-2500 km, far
    # into the noise, and some of its occultations start above the ionosphere, where the
    # largest of a thousand noisy levels is 3 or 4 sigma).  0: all levels.
    topside_min_snr: float = 0.0
    peak_below_km: float = 300.0
    # Archive that only works through its own website with an account (no
    # public index): VEDA links to the login page and imports what is downloaded.
    portal_only: bool = False
    portal_help: str = ""
    # Index rows giving PATH + FILENAME relative to a data folder (MRO MCS: "DATA/")
    data_prefix: str = ""
    # Read one cumulative index (in the newest volume) instead of every volume's index
    cumulative_index: Optional[str] = None
    # Index automatically on first search; False for very large indexes (indexed on request)
    auto_index: bool = True
    index_note: str = ""
    # Live search (no index copy): "psa_tap" | "pds_api" | "opus", with the service query
    # (see veda.archives.services).  Products are listed per date window.
    service: Optional[str] = None
    service_query: Dict[str, object] = field(default_factory=dict)
    # Reference keys (veda/archives/references.json): instrument papers first, then the mission paper.
    refs: Tuple[str, ...] = ()
    # First and last observation date in the archive ("" last: still growing), so that a
    # first search for other dates need not read the data set's catalogue (COVERAGE below)
    coverage: Tuple[str, str] = ()
    # Index rows without a time take the earliest time of the other files in their folder
    # (MRO aerobraking: each pass folder's orbital elements file has START_TIME = N/A)
    folder_time: bool = False
    # The longitude column is west-positive (Huygens DTWG): VEDA uses east
    west_longitude: bool = False
    # Where the instrument was during a probe's descent, when its own files have no
    # position: (data set id, product id) of the probe's trajectory (Huygens HASI -> DTWG;
    # Galileo probe -> the DWE trajectory file), for the Geometry tab
    descent_trajectory: Tuple[str, str] = ()

    def classify(self, file_name: str) -> Tuple[str, str]:
        name = file_name.lower()
        for rx, label, kind in self.rules:
            if re.search(rx, name):
                return label, kind
        return "Product", "other"

    def time_from_filename(self, file_name: str) -> str:
        if not self.time_from_name:
            return ""
        m = re.search(self.time_from_name, file_name, re.I)
        if not m:
            return ""
        import datetime as _dt
        g = m.groupdict()
        year = int(g["year"]) if g.get("year") else 2000 + int(g["yy"]) if int(g["yy"]) < 70 else 1900 + int(g["yy"])
        if g.get("doy"):
            day = _dt.date(year, 1, 1) + _dt.timedelta(days=int(g["doy"]) - 1)
        else:
            day = _dt.date(year, int(g["month"]), int(g["day"]))
        hms = [int(g.get(k) or 0) for k in ("hh", "mm", "ss")]
        return f"{day.isoformat()}T{hms[0]:02d}:{hms[1]:02d}:{hms[2]:02d}"

    @property
    def page_url(self) -> str:
        """The data set's page for people: the archive folder, or a research repository's
        record page, which Zenodo and BIRA-IASB answer with 404 when it ends in a slash."""
        return self.base_url.rstrip("/") if self.repository else self.base_url

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id, "mission_id": self.mission_id, "instrument": self.instrument,
            "level": self.level, "title": self.title, "body_ids": list(self.body_ids),
            "archive": self.archive, "url": self.page_url, "citation": self.citation,
            "doi": self.doi, "needs_login": bool(self.login_url), "login_url": self.login_url,
            "portal_only": self.portal_only, "portal_help": self.portal_help,
            "live": bool(self.service), "service": self.service, "refs": list(self.refs),
            "auto_index": self.auto_index, "index_note": self.index_note,
            "has_profiles": any(kind == "profile" for _, _, kind in self.rules) or bool(self.profile_rows),
            "profile_rows": self.profile_rows, "coverage": list(self.coverage),
        }


AKATSUKI_CITATION = ("Imamura, T., et al. (2017). Initial performance of the radio occultation "
                     "experiment in the Venus orbiter mission Akatsuki. Earth, Planets and Space, 69, 137.")
AKATSUKI_PROFILE_COLUMNS = {
    # Geometric altitude = RADIUS - body radius (GEOPOTENTIAL_HEIGHT is not
    # geometric and would not line up with other missions).
    "radius": "RADIUS",
    "temperature": "TEMPERATURE",
    "temperature_sigma": "SIGMA TEMPERATURE",
    "pressure": "PRESSURE",
    "pressure_sigma": "SIGMA PRESSURE",
    "number_density": "NUMBER_DENSITY",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "sza": "SOLAR_ZENITH_ANGLE",
    "lst": "LOCAL_SOLAR_TIME",
    "et": "EPHEMERIS_SECONDS",
}

MEX_CITATION = ("Paetzold, M., et al. (2016). Mars Express 10 years at Mars: observations by the Mars "
                "Express Radio Science Experiment (MaRS). Planetary and Space Science, 127, 44-90.")
RS_PROFILE_COLUMNS = {  # ESA/JAXA radio-science L4 layout (MaRS, VeRa heritage)
    "radius": "RADIUS",
    "temperature": "TEMPERATURE",
    "temperature_sigma": "SIGMA TEMPERATURE",
    "pressure": "PRESSURE",
    "pressure_sigma": "SIGMA PRESSURE",
    "number_density": "NUMBER DENSITY",
    "number_density_sigma": "SIGMA NUMBER DENSITY",      # (MaRS, MGS and MRO TPS)
    "electron_density": ("ELECTRON NUMBER DENSITY", "ELECTRON DENSITY"),
    "electron_density_sigma": ("SIGMA ELECTRON NUMBER DENSITY", "NOISE LEVEL ELECTRON NUMBER DENSITY",
                               "SIGMA ELECTRON DENSITY"),
    "refractivity": "REFRACTIVITY",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "sza": "SOLAR ZENITH ANGLE",
    "lst": ("LOCAL SOLAR TIME", "LOCAL TRUE SOLAR TIME OF OCCULTATION"),   # the latter: MRO header
    "et": "EPHEMERIS SECONDS",
    # m^2/s^2 at each tangent point; read where the data set integrates in it (hydrostatic_in_geopotential)
    "geopotential": "GEOPOTENTIAL",
}

# Entry-accelerometer profiles (MER, Phoenix): RADIAL_DISTANCE in metres from the centre of Mars
EDL_PROFILE_COLUMNS = {"radius": "RADIAL_DISTANCE", "temperature": "TEMP", "temperature_sigma": "SIGMA_TEMP",
                       "pressure": "PRESS", "pressure_sigma": "SIGMA_PRESS", "latitude": "LATITUDE",
                       "longitude": "LONGITUDE"}

MGS_CITATION = ("Hinson, D. P., et al. (1999). Initial results from radio occultation measurements with "
                "Mars Global Surveyor. JGR, 104(E11), 26997-27012; Tyler, G. L., et al. (2001), JGR 106(E10).")

HASI_CITATION = ("Fulchignoni, M., et al. (2005). In situ measurements of the physical characteristics "
                 "of Titan's environment. Nature, 438, 785-791.")

GP_CITATION = ("Seiff, A., et al. (1998). Thermal structure of Jupiter's atmosphere near the edge of a "
               "5-um hot spot in the north equatorial belt. JGR, 103(E10), 22857-22889.")

MGN_CITATION = ("Jenkins, J. M., Steffes, P. G., Hinson, D. P., Twicken, J. D., & Tyler, G. L. (1994). "
                "Radio occultation studies of the Venus atmosphere with the Magellan spacecraft. "
                "2. Results from the October 1991 experiments. Icarus, 110, 79-94.")
MGN_UNITS = {   # from catalog/mgn_rtpd.cat and mgn_abs.cat (the labels give none)
    "ALTITUDE": "KM", "TEMPERATURE": "K", "TEMP_DEV": "K", "PRESSURE": "BAR", "PRESS_DEV": "BAR",
    "DENSITY": "KG/M**3", "DENS_DEV": "KG/M**3", "REFRACTIVITY": "N-UNITS", "REFRACT_DEV": "N-UNITS",
    "ABSORPTIVITY": "DB/KM", "ABSORP_DEV": "DB/KM", "H2SO4_VOLMIX": "PPM", "H2SO4_VM_DEV": "PPM",
}

CORSS_CITATION = ("Kliore, A. J., et al. (2008). First results from the Cassini radio occultations of the "
                  "Titan ionosphere. JGR, 113, A09317.")

ISSDC_HELP = ("ISRO's ISSDC distributes this data through PRADAN, which needs a free account. "
              "Sign in, search by date and payload, download the products (PDS4 .xml labels with their "
              ".csv/.tab tables), then load them with Load File: select each .xml together with its table.")

# Juno radio occultations of Jupiter: where and when the Juno-Earth line passed 1000 km above
# the 1-bar ellipsoid (71492 x 66854 km), before ingress (I) and after egress (E), computed by
# scripts/juno_occultation_points.py from the NAIF reconstructed Juno trajectory (spk_rec_*).
# Perijove 53 was on 2023-07-31; 55-59 had no Earth occultation.  Against the team's own
# geometry in Coffin et al.'s files (perijoves 53, 54, 62): within 1 s, 0.1 deg of latitude and
# 0.7 deg of longitude.  (UTC, planetocentric latitude, east longitude.)
JUNO_OCCULTATION_POINTS = {
    "53I": ("2023-07-31T09:07:57", 41.08, 254.14),
    "53E": ("2023-07-31T09:19:00", 12.61, 249.85),
    "54I": ("2023-09-07T12:00:02", 42.90, 191.30),
    "54E": ("2023-09-07T12:12:56", 10.02, 186.42),
    "60I": ("2024-04-09T08:50:42", 46.88, 344.21),
    "60E": ("2024-04-09T09:05:24", 10.35, 338.26),
    "61I": ("2024-05-12T03:38:58", 54.53, 251.41),
    "61E": ("2024-05-12T04:04:06", -6.74, 241.29),
    "62I": ("2024-06-13T19:53:17", 59.14, 251.99),
    "62E": ("2024-06-13T20:26:27", -20.95, 238.81),
    "63I": ("2024-07-16T14:32:17", 64.47, 164.07),
    "63E": ("2024-07-16T15:12:40", -34.57, 148.93),
    "64I": ("2024-08-18T06:55:02", 67.61, 157.50),
    "64E": ("2024-08-18T07:40:03", -44.42, 141.56),
    "65I": ("2024-09-20T02:26:39", 69.35, 34.84),
    "65E": ("2024-09-20T03:14:12", -50.08, 18.78),
    "66I": ("2024-10-22T18:09:03", 69.49, 48.19),
    "66E": ("2024-10-22T18:56:59", -49.67, 31.93),
    "67I": ("2024-11-24T13:04:04", 67.95, 302.55),
    "67E": ("2024-11-24T13:49:55", -42.88, 286.04),
    "68I": ("2024-12-27T05:21:52", 65.71, 290.97),
    "68E": ("2024-12-27T06:03:57", -33.14, 274.80),
    "69I": ("2025-01-28T23:05:10", 64.37, 229.29),
    "69E": ("2025-01-28T23:44:35", -26.79, 213.52),
    "70I": ("2025-03-02T16:04:37", 65.01, 197.00),
    "70E": ("2025-03-02T16:44:56", -27.69, 180.59),
    "71I": ("2025-04-04T09:30:41", 67.27, 151.15),
    "71E": ("2025-04-04T10:15:02", -35.04, 133.16),
    "72I": ("2025-05-07T03:00:52", 70.29, 104.46),
    "72E": ("2025-05-07T03:50:34", -46.45, 84.87),
    "73I": ("2025-06-08T20:29:41", 73.45, 59.41),
    "73E": ("2025-06-08T21:24:21", -59.89, 39.37),
    "74I": ("2025-07-11T13:39:14", 76.00, 26.45),
    "74E": ("2025-07-11T14:37:27", -73.54, 8.69),
    "75I": ("2025-08-13T07:04:22", 78.65, 343.38),
    "75E": ("2025-08-13T08:04:34", -86.32, 352.79),
    "76I": ("2025-09-14T23:51:57", 80.99, 321.65),
    "76E": ("2025-09-15T00:52:48", -81.60, 103.89),
    "77I": ("2025-10-17T16:05:07", 82.62, 318.87),
    "77E": ("2025-10-17T17:05:59", -74.34, 109.19),
    "78I": ("2025-11-19T08:38:57", 83.02, 302.00),
    "78E": ("2025-11-19T09:40:18", -72.92, 92.74),
    "79I": ("2025-12-22T01:16:19", 81.79, 281.56),
    "79E": ("2025-12-22T02:18:54", -78.35, 66.95),
    "80I": ("2026-01-23T17:20:32", 79.47, 279.50),
    "80E": ("2026-01-23T18:24:08", -87.48, 29.89),
}

DATASETS: List[Dataset] = [
    Dataset(
        id="issdc-mom", mission_id="mom", instrument="MOM payloads (MCC, MENCA, LAP, TIS, MSM)", level="ISSDC",
        title="Mars Orbiter Mission data at ISSDC (account required)",
        body_ids=("mars",), archive="ISRO ISSDC (PRADAN)",
        base_url="https://pradan.issdc.gov.in/", volume_pattern=r"^$",
        login_url="https://pradan.issdc.gov.in/", portal_only=True, portal_help=ISSDC_HELP,
    ),
    Dataset(
        id="issdc-ch2", mission_id="chandrayaan2", instrument="Chandrayaan-2 orbiter payloads (incl. DFRS, CHACE-2)",
        level="ISSDC", title="Chandrayaan-2 data at ISSDC (account required)",
        body_ids=("moon",), archive="ISRO ISSDC (PRADAN)",
        base_url="https://pradan.issdc.gov.in/ch2/", volume_pattern=r"^$",
        login_url="https://pradan.issdc.gov.in/ch2/", portal_only=True, portal_help=ISSDC_HELP,
    ),
    Dataset(
        id="corss_occul_el_dens", mission_id="cassini", instrument="RSS (Radio Science)", level="Derived (PDS4)",
        title="Cassini radio occultations of Titan: ionospheric electron density profiles",
        body_ids=("titan",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^corss_occul_el_dens$",
        pds4_product_dir="data/",
        rules=((r"_edp_", "Ionosphere electron density profile", "profile"),
               (r"summary", "Occultation summary table", "other")),
        profile_columns={"radius": "OCCPTRADIUS", "electron_density": "ELECDEN",
                         "electron_density_sigma": "ELECDENERR", "latitude": "OCCPTLAT",
                         "longitude": "OCCPTLON", "sza": "OCCPTSZA", "lst": "OCCPTLST", "et": "ETRX"},
        extra_variables={"tec_m2": ("TEC", None)},
        citation=CORSS_CITATION,
        times_from_labels=True,
    ),
    Dataset(
        id="jno-x-mwr", mission_id="juno", instrument="MWR (Microwave Radiometer)", level="EDR + derived",
        title="Juno microwave radiometer: raw records, antenna and brightness temperatures, NH3/H2O distributions",
        body_ids=("jupiter",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^jnomwr_\d{4}$",
        rules=(
            (r"/atm-bright-temp/", "Atmospheric brightness temperature", "other"),
            (r"/antenna-temp/", "Antenna temperature", "other"),
            (r"/nh3-distribution/", "NH3 distribution (derived)", "other"),
            (r"/h2o-distribution/", "H2O distribution (derived)", "other"),
            (r"/synchrotron/", "Synchrotron emission", "other"),
            (r"/edr/", "Raw science record (EDR)", "other"),
            (r"/irdr/", "IRDR record", "other"),
            (r"/grdr/", "GRDR record", "other"),
        ),
        citation="Janssen, M. A., et al. (2017). MWR: Microwave Radiometer for the Juno mission to Jupiter. Space Sci. Rev., 213, 139-185.",
    ),
    Dataset(
        id="vex-v-rss-1-ent-v1.0", mission_id="vex", instrument="VeRa (Radio Science)", level="L1 + ancillary",
        title="Venus Express radio science (PDS copy): raw records, Earth ionosphere/troposphere calibrations, SPICE",
        body_ids=("venus",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^VXRS_\d{4}$",
        rules=(
            (r"(^|/)rsr/", "Radio science receiver (open-loop) record", "other"),
            (r"(^|/)odf/", "Orbit data file (closed loop)", "other"),
            (r"(^|/)tnf/", "Tracking and navigation file", "other"),
            (r"(^|/)ion/", "Earth ionosphere calibration", "other"),
            (r"(^|/)tro/", "Earth troposphere calibration", "other"),
            (r"(^|/)wea/", "DSN weather", "other"),
            (r"(^|/)(bsp|bck|brs|bro)/", "Ephemeris / attitude (SPICE)", "other"),
        ),
        citation="Hausler, B., et al. (2006). Radio science investigations by VeRa onboard the Venus Express spacecraft. PSS, 54, 1315-1335.",
    ),
    Dataset(
        id="vex-v-vra-1-2-3", mission_id="vex", instrument="VeRa (Radio Science)", level="L1A-L2",
        title="Venus Express VeRa (ESA PSA): open- and closed-loop Doppler and power, levels 1A to 2, per orbit",
        body_ids=("venus",), archive="ESA PSA",
        base_url="https://archives.esac.esa.int/psa/ftp/VENUS-EXPRESS/VRA/",
        volume_pattern=r"^VEX-[VX]-VRA-1-2-3-",
        rules=(
            (r"/level02/", "Level 2 (calibrated) record", "other"),
            (r"/level1b/", "Level 1B record", "other"),
            (r"/level1a/", "Level 1A record", "other"),
        ),
        # e.g. V32ICL2L1B_AG1_073610303_00.LBL -> 2007 day 361 03:03 (the index has no times)
        time_from_name=r"_(?P<yy>\d{2})(?P<doy>\d{3})(?P<hh>\d{2})(?P<mm>\d{2})_\d+\.",
        citation="Hausler, B., et al. (2006). Radio science investigations by VeRa onboard the Venus Express spacecraft. PSS, 54, 1315-1335.",
    ),
    Dataset(
        id="mgn-v-rss-5-occ-prof-rtpd-v1.0", times_earth_received=True, mission_id="magellan", instrument="RSS (Radio Science)", level="L5",
        title="Magellan radio occultation, October 1991: refractivity, temperature, pressure and density profiles",
        body_ids=("venus",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^mg_2401$",
        static_labels=("data/mgn_rtpd.lbl",),
        split_by=("ORBIT_NUMBER", "WAVELENGTH"),
        split_time="ert_rollover", fixed_time="1991-10-05T00:00:00",
        rules=((r"mgn_rtpd", "Temperature-pressure-density profile (per orbit and band)", "profile"),),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "temperature_sigma": "TEMP_DEV",
                         "pressure": "PRESSURE", "pressure_sigma": "PRESS_DEV", "refractivity": "REFRACTIVITY",
                         "latitude": "LATITUDE", "longitude": "LONGITUDE", "sza": "ZENITH_ANGLE", "lst": "LOCAL_TIME"},
        column_units=MGN_UNITS,
        extra_variables={"density_measured": ("DENSITY", "DENS_DEV")},
        altitude_reference_km=6052.0,          # label: "Altitude above 6052 km"
        citation=MGN_CITATION,
    ),
    Dataset(
        id="mgn-v-rss-5-occ-prof-abs-h2so4-v1.0", times_earth_received=True, mission_id="magellan", instrument="RSS (Radio Science)", level="L5",
        title="Magellan radio occultation, October 1991: microwave absorptivity and H2SO4 vapour profiles",
        body_ids=("venus",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^mg_2401$",
        static_labels=("data/mgn_abs.lbl",),
        split_by=("ORBIT_NUMBER", "WAVELENGTH"),
        split_time="ert_rollover", fixed_time="1991-10-05T00:00:00",
        rules=((r"mgn_abs", "Absorptivity and H2SO4 vapour profile (per orbit and band)", "profile"),),
        profile_columns={"altitude": "ALTITUDE", "latitude": "LATITUDE", "longitude": "LONGITUDE",
                         "sza": "ZENITH_ANGLE", "lst": "LOCAL_TIME"},
        column_units=MGN_UNITS,
        extra_variables={"h2so4_ppm": ("H2SO4_VOLMIX", "H2SO4_VM_DEV"),
                         "absorptivity_db_km": ("ABSORPTIVITY", "ABSORP_DEV")},
        citation=MGN_CITATION,
    ),
    Dataset(
        id="mgn-v-rss-1-rocc-v2.0", times_earth_received=True, mission_id="magellan", instrument="RSS (Radio Science)", level="L1",
        title="Magellan radio occultation raw data: open-loop (ODR) and tracking (TDF) records",
        body_ids=("venus",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^mg_22\d{2}$",
        rules=((r"(^|/)odr/", "Open-loop data record (ODR)", "other"),
               (r"(^|/)tdf/", "Tracking data file (TDF)", "other")),
        citation=MGN_CITATION,
    ),
    Dataset(
        id="gp-j-entry-v1.0", mission_id="galileo", instrument="Galileo Probe (ASI, NMS, NEP, NFR, ...)", level="L3",
        altitude_reference="the 1-bar pressure level",             # label: "Altitude above 1-bar level"
        title="Galileo probe at Jupiter: atmospheric structure descent profile and probe instrument data",
        body_ids=("jupiter",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^gp_0001$",
        rules=(
            (r"/asi/descent\.", "ASI descent profile (T, P, density vs altitude)", "profile"),
            (r"/asi/", "ASI entry / sensor data", "other"),
            (r"/nms/", "Neutral mass spectrometer data", "other"),
            (r"/nep/", "Nephelometer data", "other"),
            (r"/nfr/", "Net flux radiometer data", "other"),
            (r"/dwe/", "Doppler wind experiment data", "other"),
            (r"/epi/", "Energetic particle data", "other"),
            (r"/had/", "Helium abundance detector data", "other"),
            (r"/lrd/", "Lightning and radio emission data", "other"),
        ),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "pressure": "PRESSURE",
                         "gravity": "GRAVITY"},
        citation=GP_CITATION,
        label_from_data=True,
        fixed_time="1995-12-07T22:04:44",    # probe entry (Young et al. 1996, Science 272)
        # the navigation team's post-entry trajectory in the Doppler wind data (archives/trajectories.py)
        descent_trajectory=("gp-j-entry-v1.0", "PROBETRJ"),
    ),
    Dataset(
        id="hp-ssa-hasi-2-3-4-mission-v1.1", mission_id="cassini", instrument="Huygens HASI", level="L2-L4",
        altitude_reference="the surface at the Huygens landing site (Fulchignoni et al. 2005)",
        title="Huygens probe HASI: Titan entry and descent atmospheric profiles and sensor data",
        body_ids=("titan",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^hphasi_\d{4}$",
        rules=(
            (r"/profiles/hasi_l4_atmo_profile_entry", "L4 atmospheric profile, entry (in situ)", "profile"),
            (r"/profiles/hasi_l4_atmo_profile_descen", "L4 atmospheric profile, descent (in situ)", "profile"),
            (r"/profiles/", "L4 trajectory profile (altitude / velocity)", "other"),
            (r"/tem/", "Temperature sensor data", "other"),
            (r"/ppi/", "Pressure sensor data", "other"),
            (r"/acc/", "Accelerometer data", "other"),
            (r"/pwa/", "Permittivity and wave analyser data", "other"),
        ),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "pressure": "PRESSURE"},
        citation=HASI_CITATION,
        times_from_labels=True,
        descent_trajectory=("hp-ssa-dtwg-6-trajectory-v1.0", "HUY_DTWG_DESCENT_POS"),
    ),
    Dataset(
        id="hp-ssa-dtwg-6-trajectory-v1.0", mission_id="cassini", instrument="Huygens DTWG (descent trajectory)",
        level="L6 (reconstructed)",
        title="Huygens probe descent trajectory at Titan, 14 January 2005: reconstructed latitude, longitude, "
              "altitude and pressure every second",
        body_ids=("titan",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^hpdtwg_\d{4}$",
        rules=((r"descent_pos", "Descent trajectory: position and pressure", "profile"),
               (r"(^|/)data/", "Entry trajectory, velocity and aerodynamics", "other")),
        # REF_ALT: "with respect to the reference sphere of 2575 km from planet center";
        # WEST_LON is west longitude (the landing site 192.3 W = 167.7 E, 10.3 S)
        profile_columns={"altitude": "REF_ALT", "pressure": "ATMOSPHERIC PRESSURE",
                         "pressure_sigma": "ATMOSPHERIC_PRESSURE_ERROR", "latitude": "LAT",
                         "longitude": "WEST_LON", "et": "ET_EPOCH"},
        altitude_reference_km=2575.0, west_longitude=True, times_from_labels=True,
        citation=("Kazeminejad, B., et al. (2007). Huygens' entry and descent through Titan's atmosphere: "
                  "Methodology and results of the trajectory reconstruction. Planet. Space Sci., 55, 1845-1876."),
        doi="10.1016/j.pss.2007.04.013",
    ),
    Dataset(
        id="mgs-m-rss-5-sdp-v1.0", mission_id="mgs", instrument="RS (Radio Science)", level="L5 (SDP)",
        title="Mars Global Surveyor radio occultation: temperature-pressure and electron density profiles",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^mors_1\d{3}$",
        rules=(
            (r"(^|/)tps/", "Temperature-pressure profile", "profile"),
            (r"(^|/)eds/", "Ionosphere electron density profile", "profile"),
            (r"(^|/)ocs/", "Occultation summary", "other"),
            (r"(^|/)sha/", "Gravity field (spherical harmonics)", "other"),
            (r"(^|/)img/", "Gravity / topography map", "other"),
        ),
        profile_columns=RS_PROFILE_COLUMNS,
        hydrostatic_in_geopotential=True,
        citation=MGS_CITATION,
    ),
    Dataset(
        id="vex-vera-gramigna2023", mission_id="vex", instrument="VeRa (Radio Science)", level="Derived (research data)",
        title="Venus Express radio occultations of 2014 (NASA DSN): temperature, pressure and density profiles (Gramigna et al. 2023)",
        body_ids=("venus",), archive="Zenodo (CC-BY-4.0)",
        base_url="https://zenodo.org/records/20056665/",
        volume_pattern=r"^repository$",
        repository={"kind": "zenodo_zip", "record": "20056665", "zip": "RS_2014_VEX_singlefreq_X_Gramigna_et_al_2023.zip",
                    "members": r"VEX_RO_2014_DOY\d{3}_(INGRESS|EGRESS)\.txt\.txt", "delimiter": "\t", "time_column": 1,
                    "columns": [("SAMPLE_NUMBER", ""), ("UTC_TIME", "UTC"), ("EPHEMERIS_SECONDS", "s"), ("RADIUS", "km"),
                                ("LATITUDE", "deg"), ("LONGITUDE", "deg"), ("BENDING_ANGLE", "deg"), ("PRESSURE", "Pa"),
                                ("TEMPERATURE", "K"), ("NUMBER_DENSITY", "m-3"), ("SOLAR_ZENITH_ANGLE", "deg"),
                                ("LOCAL_SOLAR_TIME", "hh:mm:ss")]},
        rules=((r"^vex_ro_2014", "Neutral atmosphere profile (T, p, n), X-band single frequency", "profile"),),
        profile_columns={"radius": "RADIUS", "temperature": "TEMPERATURE", "pressure": "PRESSURE",
                         "number_density": "NUMBER_DENSITY", "latitude": "LATITUDE", "longitude": "LONGITUDE",
                         "sza": "SOLAR_ZENITH_ANGLE", "lst": "LOCAL_SOLAR_TIME"},
        column_units={"RADIUS": "KM", "PRESSURE": "PASCAL", "TEMPERATURE": "K", "NUMBER_DENSITY": "1/M**3"},
        citation=("Gramigna, E., et al. (2023). Analysis of NASA's DSN Venus Express radio occultation data for year 2014. "
                  "Advances in Space Research, 71(1), 1198-1215. Data: doi:10.5281/zenodo.20056665 (CC-BY-4.0)."),
        doi="10.5281/zenodo.20056665",
    ),
    Dataset(
        id="vex-vera-fsi-imamura", mission_id="vex", instrument="VeRa (Radio Science)", level="Derived (research data)",
        title="Venus Express radio occultations 2006-2014: temperature profiles by Full Spectrum Inversion (Imamura et al. 2018)",
        body_ids=("venus",), archive="Zenodo (CC-BY-4.0)",
        base_url="https://zenodo.org/records/4621070/",
        volume_pattern=r"^repository$",
        # Columns (from the values: p = n k T exactly): radius km, altitude km, T K, p Pa, n m^-3.
        # Below the lowest valid level the files hold n constant; those rows are masked, and so
        # are the levels just above where the density flattens as the signal fades (the
        # temperature falls faster than 15 K/km with height there; dry adiabatic is about 10).
        repository={"kind": "zenodo_files", "record": "4621070", "revision": 2,
                    "files": r"temperature_fsi_(?P<date>\d{6})[a-z]?-?\d*(_lin)?\.dat",
                    "columns": [("RADIUS", "km"), ("ALTITUDE", "km"), ("TEMPERATURE", "K"), ("PRESSURE", "Pa"),
                                ("NUMBER_DENSITY", "m-3")],
                    "mask_constant": ("NUMBER_DENSITY", ("TEMPERATURE", "PRESSURE")),
                    "max_lapse": ("TEMPERATURE", "ALTITUDE", 15.0, ("PRESSURE", "NUMBER_DENSITY")),
                    "meta_xlsx": "FSI_VeRa_profiles.xlsx",
                    "meta_columns": ["file", "year", "month", "day", "direction", "latitude", "local_time"]},
        rules=((r"^temperature_fsi_\d{6}", "Neutral atmosphere profile (T, p, n) by Full Spectrum Inversion", "profile"),),
        profile_columns={"radius": "RADIUS", "temperature": "TEMPERATURE", "pressure": "PRESSURE",
                         "number_density": "NUMBER_DENSITY", "latitude": "LATITUDE", "lst": "LST"},
        column_units={"RADIUS": "KM", "PRESSURE": "PASCAL", "TEMPERATURE": "K", "NUMBER_DENSITY": "1/M**3"},
        citation=("Imamura, T., et al. (2018). Fine vertical structures at the cloud heights of Venus revealed by radio "
                  "holographic analysis of Venus Express and Akatsuki radio occultation data. JGR Planets, 123, 2151-2161. "
                  "Data: doi:10.5281/zenodo.4621070 (CC-BY-4.0)."),
        doi="10.5281/zenodo.4621070",
    ),
    Dataset(
        id="vex-soir-co2-temperature", mission_id="vex", instrument="SPICAV-SOIR", level="Derived (research data)",
        title="Venus Express SOIR solar occultations 2006-2014: CO2 density, pressure and temperature at the terminator (BIRA-IASB, version w24)",
        body_ids=("venus",), archive="BIRA-IASB data repository (CC-BY-4.0)",
        base_url="https://data.aeronomie.be/dataset/venus-atmospheric-profiles-from-spicav-soir-vexv24/",
        volume_pattern=r"^repository$",
        # Version w24 (Mahieux et al. 2023), which replaces w23: one VOTable per occultation,
        # its time, the latitude and longitude at 120 km, local time and Ls in PARAMs.
        # Some profiles repeat one temperature over their top 10 km: the value the retrieval
        # starts its downward integration from, not a measurement (pressure there is n k T
        # with it); temperature and pressure are masked there, the density is kept.
        # The top level of every profile is that starting temperature too, written with an
        # uncertainty of 0 (1e-13 K): also masked.  (Both as in w23: 172 and 718 of the 718
        # profiles.)
        # The mean molar mass at each level (total_molar_mass, g/mol) is kept: it falls from
        # 43.4 below 120 km to about 20 at 175 km (CO2 giving way to O and CO), and the mass
        # density, scale height and the temperature retrieved from the total density use it.
        repository={"kind": "votable_files", "revision": 6,
                    "mask_constant": ("temperature", ("err_temperature", "pressure", "err_pressure")),
                    "mask_zero_sigma": ("err_temperature", ("temperature", "err_temperature", "pressure", "err_pressure")),
                    "url": "https://data.aeronomie.be/dataset/26265617-8175-4a73-b219-4d837b7a6adc/resource/d1e25354-0f3f-4cab-827f-b682910035bb/download/cox_h2o_hdo_hxcl_hf_soir_w24.zip",
                    "members": r"CO2_0/Orbit(?P<orbit>\d{4})\.(?P<case>\d)_CO2_0_w24\.\d+\.xml",
                    "product_id": "soir_co2_orbit{orbit:04d}_{case}", "time": "time_min_calendar",
                    "geometry": {"LATITUDE": ("latitude_120km",), "LONGITUDE": ("longitude_120km",),
                                 "LST": ("local_time_min", "local_time_max"),
                                 "LS": ("solar_longitude_min", "solar_longitude_max")},
                    "keep": ("altitude", "pressure", "err_pressure", "temperature", "err_temperature",
                             "total_density", "err_total_density", "total_molar_mass", "err_total_molar_mass",
                             "volume_mixing_ratio_SmoothingFactor=1.0")},
        rules=((r"^soir_co2", "Mesosphere and thermosphere profile at the terminator (T, p, n)", "profile"),),
        profile_columns={"altitude": "altitude", "temperature": "temperature", "temperature_sigma": "err_temperature",
                         "pressure": "pressure", "pressure_sigma": "err_pressure", "number_density": "total_density",
                         "number_density_sigma": "err_total_density",
                         "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"altitude": "KM", "pressure": "MBAR", "err_pressure": "MBAR", "temperature": "K",
                      "err_temperature": "K", "total_density": "1/CM**3", "total_molar_mass": "G/MOL",
                      "err_total_molar_mass": "G/MOL"},
        # and the CO2 volume mixing ratio at each level (the same for every smoothing factor:
        # the composition the team's total density and molar mass follow), for the frost point
        extra_variables={"molar_mass": ("total_molar_mass", "err_total_molar_mass"),
                         "co2_fraction": ("volume_mixing_ratio_SmoothingFactor=1.0", None)},
        altitude_reference="the Venus surface at the tangent point, as given by the SOIR team",
        citation=("Mahieux, A., et al. (2023). The SOIR/Venus Express species concentration and temperature "
                  "database: CO2, CO, H2O, HDO, H35Cl, H37Cl, HF individual and mean profiles. Icarus, 405, 115713. "
                  "Data: Vandaele, A. C., et al. (2024), BIRA-IASB, doi:10.18758/71021090 (CC-BY-4.0)."),
        doi="10.18758/71021090",
    ),
    Dataset(
        id="vega1-vega2-v-2-3-venus-v1.0", mission_id="vega", instrument="VEGA 2 lander METEO; VEGA 1/2 balloons",
        level="L2-L3",
        title="VEGA 2 lander descent profile (63 km to the surface) and VEGA 1/2 balloon records at Venus (June 1985)",
        body_ids=("venus",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^vega_5001$",
        rules=((r"vg2lr", "Lander descent profile (pressure, temperature)", "profile"),
               (r"vg[12]bl_rdr", "Balloon record, level 3 (p, T, winds, position; time series near 54 km)", "other"),
               (r"vg[12]bl_edr", "Balloon record, level 2", "other")),
        profile_columns={"altitude": "Altitude", "temperature": "Temperature", "pressure": "Pressure"},
        altitude_reference="the surface at the VEGA 2 landing site (reconstructed altitude, 0 m at touchdown)",
        citation=("Lorenz, R. D., Crisp, D., & Huber, L. (2018). Venus atmospheric structure and dynamics from the VEGA "
                  "lander and balloons: New results and PDS archive. Icarus, 305, 277-283. Data: VEGA1/VEGA2-V-2/3-VENUS-V1.0."),
        doi="10.1016/j.icarus.2017.12.044",
        times_from_labels=True,
    ),
    Dataset(
        id="mer-m-imu-5-edl-derived-v1.0", mission_id="mer", instrument="IMU (entry)", level="L5 (derived)",
        title="Spirit and Opportunity entry profiles: density, pressure and temperature (January 2004)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^merimu_2001$",
        rules=((r"mer\dprofiles", "Entry profile (density, pressure, temperature)", "profile"),),
        profile_columns=EDL_PROFILE_COLUMNS,
        extra_variables={"density_measured": ("RHO", "SIGMA_RHO")},
        citation=("Withers, P., & Smith, M. D. (2006). Atmospheric entry profiles from the Mars Exploration Rovers "
                  "Spirit and Opportunity. Icarus, 185, 133-142. Data: MER1/MER2-M-IMU-5-EDL-DERIVED-V1.0."),
        doi="10.1016/j.icarus.2006.06.013",
        label_from_data=True,
    ),
    Dataset(
        id="phx-m-ase-5-edl-rdr-v1.0", mission_id="phoenix", instrument="ASE (entry)", level="L5 (RDR)",
        title="Phoenix entry profile at 68 N: density, pressure and temperature (May 2008)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^phxase_0002$",
        rules=((r"phxprofiles", "Entry profile (density, pressure, temperature)", "profile"),
               (r"phxcompact", "Entry profile, compact version", "other")),
        profile_columns=EDL_PROFILE_COLUMNS,
        extra_variables={"density_measured": ("RHO", "SIGMA_RHO")},
        citation=("Withers, P., & Catling, D. C. (2010). Observations of atmospheric tides on Mars at the season and "
                  "latitude of the Phoenix atmospheric entry. GRL, 37(24). Data: PHX-M-ASE-5-EDL-RDR-V1.0."),
        doi="10.1029/2010gl045382",
        label_from_data=True,
    ),
    Dataset(
        id="mpf-m-asimet-4-ddr-edl-v1.0", mission_id="mpf", instrument="ASI/MET (entry)", level="DDR (derived)",
        title="Mars Pathfinder entry profile at 19 N: density, pressure and temperature (July 1997)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^mpam_0001$",
        index_path="index/ed_index.tab",
        rules=((r"edl_ddr", "Entry profile (density, pressure, temperature)", "profile"),),
        # Altitudes above the landing site, where the radius of Mars is 3389.72 km (label);
        # the uncertainties are 3-sigma envelopes, + and - (the + one is used, as 1-sigma).
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE",
                         "temperature_sigma": "POSITIVE_TEMP_UNCERTAINTY", "pressure": "PRESSURE",
                         "pressure_sigma": "POSITIVE_PRESSURE_UNCERTAINTY",
                         "latitude": "PLANETOCENTRIC_LATITUDE", "longitude": "EAST_LONGITUDE"},
        extra_variables={"density_measured": ("DENSITY", "POSITIVE_DENSITY_UNCERTAINTY")},
        sigma_factor={"temperature_k": 1 / 3, "temperature_c": 1 / 3, "pressure_hpa": 1 / 3, "density_measured": 1 / 3},
        altitude_reference_km=3389.72,
        citation=("Magalhaes, J. A., Schofield, J. T., & Seiff, A. (1999). Results of the Mars Pathfinder atmospheric "
                  "structure investigation. JGR, 104(E4), 8943-8955. Data: MPF-M-ASIMET-4-DDR-EDL-V1.0."),
        doi="10.1029/1998JE900041",
    ),
    Dataset(
        id="msl-edl-atmosphere", mission_id="msl", instrument="EDL reconstruction", level="Derived (PDS4)",
        title="Curiosity entry profile over Gale crater: density, pressure and temperature (August 2012)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^msledl_bundle$",
        pds4_product_dir="data/",
        rules=((r"bu_pds_edldata", "Entry profile (density, pressure, temperature)", "profile"),),
        # (the label gives units only in the field descriptions)
        profile_columns={"radius": "Radial distance [km]", "temperature": "Atmospheric temperature",
                         "temperature_sigma": "Temperature uncertainty", "pressure": "Atmospheric pressure",
                         "pressure_sigma": "Atmospheric pressure uncertainty", "latitude": "Latitude",
                         "longitude": "Longitude"},
        column_units={"Atmospheric temperature": "K", "Temperature uncertainty": "K", "Atmospheric pressure": "Pa",
                      "Atmospheric pressure uncertainty": "Pa", "Atmospheric Density": "kg/m^3",
                      "Radial distance [km]": "KILOMETER"},
        extra_variables={"density_measured": ("Atmospheric Density", "Density uncertainty")},
        citation=("Holstein-Rathlou, C., Maue, A., & Withers, P. (2016). PSS, 120, 15-23. "
                  "Data: Holstein-Rathlou & Withers (2015), https://doi.org/10.17189/1518944."),
        doi="10.17189/1518944",
        times_from_labels=True,
    ),
    Dataset(
        id="insight-edl-atmosphere", mission_id="insight", instrument="EDL reconstruction", level="Derived (PDS4)",
        title="InSight entry profile over Elysium Planitia: density, pressure and temperature (November 2018)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^insight_edl_bundle$",
        pds4_product_dir="data/",
        rules=((r"edl_atmosphere", "Entry profile (density, pressure, temperature)", "profile"),
               (r"edl_complete", "Entry reconstruction, all quantities", "other"),
               (r"edl_imu", "Entry IMU data", "other")),
        # Radial distance, not "Planetocentric Altitude" (which is above 3396.19 km), so the
        # profile shares VEDA's 3389.5 km Mars reference with the other missions.
        profile_columns={"radius": "Radial Distance", "temperature": "Atmospheric Temperature",
                         "temperature_sigma": "Std Dev Temperature", "pressure": "Atmospheric Pressure",
                         "pressure_sigma": "Std Dev Pressure", "latitude": "Planetocentric Latitude",
                         "longitude": "Planetocentric Longitude", "lst": "Local Solar Time (LST)"},
        extra_variables={"density_measured": ("Atmospheric Density", "Std Dev Density")},
        # p = rho R T with R = 188.95 J/(kg K) at every level (pure CO2; Mars' composition
        # gives 191.2): the archived temperatures are 1.2 % above VEDA's from the density
        citation="Karatekin, O. (2020). InSight EDL Bundle (urn:nasa:pds:insight_edl). NASA PDS.",
        doi="10.17189/1518935",
        times_from_labels=True,
    ),
    Dataset(
        id="ody-m-accel-5-derived-v1.0", mission_id="ody", instrument="ACC (aerobraking accelerometer)",
        level="L5 (derived)",
        title="Mars Odyssey aerobraking: thermospheric density profiles from the accelerometer (Oct 2001 - Jan 2002)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^odya_1001$",
        rules=((r"data/prof/accprof", "Density profile along the aerobraking pass", "profile"),
               (r"data/calt/", "Densities and scale heights at constant altitude", "other"),
               (r"data/anc/", "Pass ancillary data (periapsis)", "other"),
               (r"data/raw/", "Raw accelerations", "timeseries")),
        label_from_data=True,
        # RADIAL_DIST (km from the centre of Mars), not ALTITUDE (above the MOLA areoid),
        # so the profiles share VEDA's 3389.5 km sphere with the other Mars data sets.
        profile_columns={"radius": "RADIAL_DIST", "latitude": "LATITUDE", "longitude": "LONGITUDE",
                         "lst": "LOCAL_SOLAR_TIME", "sza": "SOLAR_ZENITH_ANGLE"},
        # 7-s running mean (RHO7): the unaveraged density is noisy, the 39-s mean spans
        # tens of km in altitude on the legs.  "Null values are 0" (data set catalogue).
        extra_variables={"density_measured": ("RHO7", "SRHO7")},
        fill_values={"RADIAL_DIST": (0.0,), "LATITUDE": (0.0,), "LONGITUDE": (0.0,)},
        # Labelled KILOGRAM PER CUBIC METER, but the values are kg/km^3 (66 at 85 km; the drag
        # equation with the file's own acceleration, speed and drag coefficient gives
        # Odyssey's mass-to-area ratio of 41 kg/m^2 only in kg/km^3)
        value_factor={"density_measured": 1e-9},
        pass_legs="TIME_AFTER_PERI",
        citation=("Withers, P., & Murphy, J. R. (2009). ODY-M-ACCEL-5-DERIVED-V1.0, NASA Planetary Data System; "
                  "Tolson, R. H., et al. (2005). Application of accelerometer data to Mars Odyssey aerobraking "
                  "and atmospheric modeling. J. Spacecraft Rockets, 42(3), 435-443."),
        doi="10.2514/1.15173",
    ),
    Dataset(
        id="mro-crism-smith2013-aerosol", mission_id="mro", instrument="CRISM (limb)", level="Derived (PDS4)",
        title="MRO CRISM limb observations: vertical profiles of dust and water-ice aerosol, 2009-2012 (Smith et al. 2013)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/mro-crism_atmos-db/data_derived/",
        volume_pattern=r"^repository$",
        # One table holds the 502 profiles; a profile is one Mars year, Ls, latitude and (west)
        # longitude.  The table gives no time: the date is found from the Mars year and Ls (the
        # label's start and stop dates are those of the first and last rows' Ls).
        repository={"kind": "csv_split",
                    "url": "https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/mro-crism_atmos-db/data_derived/"
                           "Smith2013_vertical_distribution_ice_dust.csv",
                    "header": False,
                    "columns": [("MARS_YEAR", ""), ("SOLAR_LONGITUDE", "deg"), ("LATITUDE", "deg"), ("LONGITUDE", "deg"),
                                ("HEIGHT_SCALE", "scale heights"), ("DUST_MIXING_RATIO", ""), ("ICE_MIXING_RATIO", ""),
                                ("HEIGHT_KM", "km")],
                    "split": ("MARS_YEAR", "SOLAR_LONGITUDE", "LATITUDE", "LONGITUDE"),
                    "product_id": "crism_smith2013_{key}", "mars_year": "MARS_YEAR", "ls": "SOLAR_LONGITUDE",
                    "latitude": "LATITUDE", "longitude": "LONGITUDE", "west_longitude": True,
                    "keep": ("HEIGHT_KM", "HEIGHT_SCALE", "DUST_MIXING_RATIO", "ICE_MIXING_RATIO")},
        rules=((r"^crism_smith2013", "Dust and water-ice aerosol vertical profile (CRISM limb)", "profile"),),
        profile_columns={"altitude": "HEIGHT_KM", "latitude": "LATITUDE", "longitude": "LONGITUDE"},
        # "Mixing ratio" (Smith et al. 2013, eq. 1): optical depth at 2.2 um per unit fraction of
        # the column mass; the column optical depth is the sum of mixing ratio x Qext x dp / p_surf
        extra_variables={"dust_mixing_ratio": ("DUST_MIXING_RATIO", None), "ice_mixing_ratio": ("ICE_MIXING_RATIO", None)},
        # retrieval levels 0.4 pressure scale heights apart from 0.2 above the surface (Smith et
        # al. 2013); the table also holds the levels halfway between, interpolated
        altitude_reference="the local surface (CRISM limb retrieval levels)",
        citation=("Smith, M. D., Wolff, M. J., Clancy, R. T., Kleinböhl, A., & Murchie, S. L. (2013). Vertical distribution "
                  "of dust and water ice aerosols from CRISM limb-geometry observations. JGR Planets, 118, 321-334. "
                  "Data: Khayat, A. S. J. (2024), Atmospheric Retrievals for Mars Integrated from MRO-CRISM Bundle, "
                  "NASA PDS, doi:10.17189/76ha-be75."),
        doi="10.17189/76ha-be75",
    ),
    Dataset(
        id="mro-crism-guzewich-aerosol", mission_id="mro", instrument="CRISM (limb)", level="Derived (PDS4)",
        title="MRO CRISM limb observations: dust and water-ice aerosol abundance and particle size profiles, 2010-2017 "
              "(Guzewich et al. 2014, 2019)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/mro-crism_atmos-db/data_derived/",
        volume_pattern=r"^repository$",
        # 916 profiles, one per CRISM limb observation (OBSERVATION_NAME), dated from the Mars
        # year and Ls as above; -999 is missing.
        repository={"kind": "csv_split",
                    "url": "https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/mro-crism_atmos-db/data_derived/"
                           "Guzewich2014_2019_vertical_distribution_ice_dust.csv",
                    "header": True,
                    "columns": [("MARS_YEAR", ""), ("SOLAR_LONGITUDE", "deg"), ("LATITUDE", "deg"), ("LONGITUDE", "deg"),
                                ("HEIGHT", "km"), ("ICE_MIXING_RATIO", "1/mbar"), ("ICE_EFFECTIVE_RADIUS", "um"),
                                ("ICE_EFFECTIVE_RADIUS_ERROR", "um"), ("DUST_MIXING_RATIO", "1/mbar"),
                                ("DUST_EFFECTIVE_RADIUS", "um"), ("DUST_EFFECTIVE_RADIUS_ERROR", "um"),
                                ("OBSERVATION_NAME", "text")],
                    "split": ("OBSERVATION_NAME",), "fill": -999.0,
                    "product_id": "crism_guzewich_{key}", "mars_year": "MARS_YEAR", "ls": "SOLAR_LONGITUDE",
                    "latitude": "LATITUDE", "longitude": "LONGITUDE", "west_longitude": True,
                    "text_meta": ("OBSERVATION_NAME",),
                    "keep": ("HEIGHT", "ICE_MIXING_RATIO", "ICE_EFFECTIVE_RADIUS", "ICE_EFFECTIVE_RADIUS_ERROR",
                             "DUST_MIXING_RATIO", "DUST_EFFECTIVE_RADIUS", "DUST_EFFECTIVE_RADIUS_ERROR")},
        rules=((r"^crism_guzewich", "Dust and water-ice aerosol and particle size profile (CRISM limb)", "profile"),),
        profile_columns={"altitude": "HEIGHT", "latitude": "LATITUDE", "longitude": "LONGITUDE"},
        # Here the "mixing ratio" is the optical depth at 2.2 um per mbar (the label's unit is
        # Delta(tau)/mb), not Smith et al.'s per unit column-mass fraction: separate variables
        extra_variables={"dust_opacity_per_mbar": ("DUST_MIXING_RATIO", None),
                         "ice_opacity_per_mbar": ("ICE_MIXING_RATIO", None),
                         "dust_effective_radius": ("DUST_EFFECTIVE_RADIUS", "DUST_EFFECTIVE_RADIUS_ERROR"),
                         "ice_effective_radius": ("ICE_EFFECTIVE_RADIUS", "ICE_EFFECTIVE_RADIUS_ERROR")},
        # levels 0.4 pressure scale heights apart, 0.2 to 6.6 above the surface (Guzewich et al. 2014)
        altitude_reference="the local surface (CRISM limb retrieval levels)",
        citation=("Guzewich, S. D., Smith, M. D., & Wolff, M. J. (2014). The vertical distribution of Martian aerosol "
                  "particle size. JGR Planets, 119, 2694-2708; Guzewich, S. D., & Smith, M. D. (2019). Seasonal "
                  "variation in Martian water ice cloud particle size. JGR Planets, 124, 636-643. Data: Khayat, A. S. J. "
                  "(2024), NASA PDS, doi:10.17189/76ha-be75."),
        doi="10.17189/76ha-be75",
    ),
    Dataset(
        id="mro-m-accel-5-profile-v1.0", mission_id="mro", instrument="ACC (aerobraking accelerometer)",
        level="L5 (derived)",
        title="MRO aerobraking: thermospheric density profiles from the accelerometer (Apr - Aug 2006)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^MROA_\d{4}$",
        rules=((r"data/profile_data/", "Density profile along the aerobraking pass", "profile"),
               (r"data/altitude_data/", "Densities and scale heights at constant altitude", "other"),
               (r"data/raw_data/", "Raw accelerations, attitude and thruster data", "timeseries"),
               (r"calib/", "Calibration and spacecraft data", "other")),
        # Labels are attached; the columns are in LABEL/PROFILE.FMT.  Altitudes are above
        # the areodetic spheroid (SIS_ACC.TXT: a = 3396.19 km, f = 5.88600756e-3) along
        # its normal at the areodetic latitude, put on the 3389.5 km sphere.
        profile_columns={"altitude": "1_SEC_ALTITUDE", "latitude": "AREODETIC LATITUDE",
                         "longitude": "LONGITUDE", "lst": "LOCAL_SOLAR_TIME", "sza": "SOLAR_ZENITH_ANGLE"},
        altitude_spheroid=(3396.19, 5.88600756e-3),
        # The 1-s density, the data set's own resolution (about 0.5 km in altitude on the
        # legs); the file's 39-s mean is there "for continuity with aerobraking data bases".
        extra_variables={"density_measured": ("1_SEC_AVG_DENSITY", "1_SEC_SIGMA")},
        # "A minus 1 (-1) anywhere in the data files indicates that data was not available"
        # (SIS); not applied to latitude and longitude, where -1.0 is a real value.
        fill_values={c: (-1.0,) for c in ("1_SEC_ALTITUDE", "1_SEC_AVG_DENSITY", "1_SEC_SIGMA",
                                          "LOCAL_SOLAR_TIME", "SOLAR_ZENITH_ANGLE")},
        value_factor={"density_measured": 1e-9},       # labelled KG/KM^3
        pass_legs="TIME_FROM_PERIAPSIS",
        folder_time=True,
        citation=("Tolson, R. H., Keating, G. M., Bougher, S. W., Brown, S. P., & Murphy, J. M. (2010). "
                  "MRO-M-ACCEL-5-PROFILE-V1.0, NASA Planetary Data System; Tolson, R. H., et al. (2008). "
                  "Atmospheric modeling using accelerometer data during Mars Reconnaissance Orbiter aerobraking "
                  "operations. J. Spacecraft Rockets, 45(3), 511-518."),
        doi="10.2514/1.34301",
    ),
    Dataset(
        id="maven-acc-profile", mission_id="maven", instrument="ACC (accelerometer)", level="L3 (derived, PDS4)",
        title="MAVEN accelerometer: thermospheric density profiles of the periapsis passes (deep dips, the 2019 "
              "aerobraking and science orbits, Oct 2014 - 2020)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/MAVEN/",
        volume_pattern=r"^acc_bundle$",
        pds4_product_dir="l3/", pds4_walk=2,                       # l3/<year>/<month>/
        time_from_name=r"_(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})_v\d+",
        label_time=True,
        rules=((r"pro-acc-p\d+", "Density profile along the periapsis pass", "profile"),),
        # Altitudes are above the spheroid a = 3396.19 km, f = 0.00588600756 (PROFDS.txt) at
        # areodetic latitudes, as for the MRO accelerometer data: put on the 3389.5 km sphere.
        profile_columns={"altitude": "AREODETIC ALTITUDE", "latitude": "Areodetic Latitude",
                         "longitude": "Longitude", "lst": "True Local Solar Time", "sza": "Solar Zenith Angle"},
        altitude_spheroid=(3396.19, 5.88600756e-3),
        # The 1-s density, the data set's own resolution, with its 1-sigma (inflated by the
        # scatter of the 1-s about the 99-s values, user advisory Eq. 2); the 99-s running
        # polynomial, which damps fuel slosh, spans tens of kilometres on the legs.
        extra_variables={"density_measured": ("1-SEC DENSITY", "SIGMA 1-SEC DENSITY")},
        value_factor={"density_measured": 1e-9},              # KG/KM**3
        pass_legs="Seconds from Periapsis",
        leg_min_snr=2.0,
        citation=("Tolson, R., & Lugo, R. (2016). MAVEN Accelerometer Data (urn:nasa:pds:maven_acc), NASA Planetary "
                  "Data System; Zurek, R. W., et al. (2015). Application of MAVEN accelerometer and attitude control "
                  "data to Mars atmospheric characterization. Space Sci. Rev., 195, 303-317."),
        doi="10.1007/s11214-014-0095-x",
    ),
    Dataset(
        id="maven-rose-edp", mission_id="maven", instrument="ROSE (Radio Occultation Science Experiment)",
        level="L3 (derived, PDS4)",
        title="MAVEN radio occultations (ROSE): ionospheric electron density profiles (2016 - 2025)",
        body_ids=("mars",), archive="NASA PDS PPI Node (PDS4)",
        base_url="https://pds-ppi.igpp.ucla.edu/data/",
        volume_pattern=r"^maven-rose-derived$",
        pds4_product_dir="data/edp/", pds4_walk=2,                 # data/edp/<year>/<month>/
        time_from_name=r"_(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})T(?P<hh>\d{2})(?P<mm>\d{2})(?P<ss>\d{2})_v\d+",
        representative={"time": "UTCTIME3550", "latitude": "AREOCENTRICLAT3550", "longitude": "AREOCENTRICLON3550",
                        "lst": "LTST3550", "sza": "SZA3550"},
        rules=((r"mvn_rse_l3_edp_", "Ionospheric electron density profile", "profile"),),
        # RADIUS (from the centre of Mars) rather than ALTITUDEMOLA, for the 3389.5 km sphere
        # of the other Mars data sets; the geometry is the ray's closest approach at each level.
        # One 1-sigma per profile: the rms of the density above 400 km (5e9 m^-3 if the
        # profile ends lower), SIS section 5.2.3.1.
        profile_columns={"radius": "RADIUS", "electron_density": "NELEC", "electron_density_sigma": "SNELEC",
                         "latitude": "OCCAREOCENTRICLAT", "longitude": "OCCAREOCENTRICLON",
                         "sza": "OCCSZA", "lst": "OCCLTST"},
        neutral_below_km=100.0,
        topside_min_snr=2.0,
        citation=("Withers, P. (2017). MAVEN ROSE Derived Data Bundle (urn:nasa:pds:maven.rose.derived), NASA Planetary "
                  "Data System, doi:10.17189/1517630; Withers, P., et al. (2020). The MAVEN Radio Occultation Science "
                  "Experiment (ROSE). Space Sci. Rev., 216, 61."),
        doi="10.17189/1517630",
    ),
    Dataset(
        id="maven-ngims-l2", mission_id="maven", instrument="NGIMS (Neutral Gas and Ion Mass Spectrometer)",
        level="L2 (PDS4)",
        title="MAVEN NGIMS: neutral gas and ion density profiles of the periapsis passes (Oct 2014 - present)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/MAVEN/",
        volume_pattern=r"^ngims_bundle$",
        pds4_product_dir="l2/", pds4_walk=2,                       # l2/<year>/<month>/
        time_from_name=r"_(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})T(?P<hh>\d{2})(?P<mm>\d{2})(?P<ss>\d{2})_v\d+",
        # the ion files are listed but not read as profiles: their densities would be taken for
        # the neutral number density (and its hydrostatic temperature)
        rules=((r"csn-abund", "Neutral gas density profile along the periapsis pass", "profile"),
               (r"ion-abund", "Ion abundances along the periapsis pass", "other")),
        profile_columns={"altitude": "ALT", "number_density": "ABUNDANCE", "number_density_sigma": "PRECISION",
                         "latitude": "LAT", "longitude": "LONG", "lst": "LST", "sza": "SZA"},
        # each species' density and 1-sigma on the CO2 times (profiles.py, _species_on_one_time_grid),
        # in m^-3; samples flagged UR (unreliable) are not used
        extra_variables={"n_co2_m3": ("ABUNDANCE_CO2", "PRECISION_CO2"),
                         "n_ar_m3": ("ABUNDANCE_AR", "PRECISION_AR"),
                         "n_n2_m3": ("ABUNDANCE_N2", "PRECISION_N2"),
                         "n_he_m3": ("ABUNDANCE_HE", "PRECISION_HE")},
        value_factor={"n_co2_m3": 1e6, "n_ar_m3": 1e6, "n_n2_m3": 1e6, "n_he_m3": 1e6},
        fill_values={"ABUNDANCE": (-999.0, 0.0), "PRECISION": (-999.0, 0.0),
                     "ABUNDANCE_CO2": (-999.0, 0.0), "ABUNDANCE_AR": (-999.0, 0.0),
                     "ABUNDANCE_N2": (-999.0, 0.0), "ABUNDANCE_HE": (-999.0, 0.0)},
        density_molar_mass=44.01,
        pass_legs="periapsis",
        citation=("Elrod, M., Benna, M., & Navas, T. (2014). MAVEN Neutral Gas and Ion Mass Spectrometer Data "
                  "(urn:nasa:pds:maven.ngims.calibrated), NASA Planetary Data System, doi:10.17189/1518931; Mahaffy, P. R., et al. (2015). The Neutral Gas and Ion Mass Spectrometer on "
                  "the Mars Atmosphere and Volatile Evolution Mission. Space Sci. Rev., 195, 49-73."),
        doi="10.17189/1518931",
    ),
    Dataset(
        id="maven-iuvs-occultation", mission_id="maven", instrument="IUVS (Imaging Ultraviolet Spectrograph)",
        level="L2 (derived, PDS4)",
        title="MAVEN IUVS stellar occultations: CO2, O2 and ozone density, temperature and pressure profiles (2015 - present)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/MAVEN/",
        volume_pattern=r"^iuvs_derived_bundle$",
        pds4_product_dir="l2/occultation/", pds4_walk=2,           # l2/occultation/<year>/<month>/
        time_from_name=r"_(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})T(?P<hh>\d{2})(?P<mm>\d{2})(?P<ss>\d{2})",
        rules=((r"iuv_l2_occultation", "Stellar occultation profile (CO2, O2, O3, temperature, pressure)", "profile"),),
        # FITS tables read by readers/iuvs_reader.py; densities in cm^-3, pressure in Pa,
        # longitudes east; the place is the half light point (HLP_geometry), as the team quotes it
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "temperature_sigma": "SIGMA_TEMPERATURE",
                         "pressure": "PRESSURE", "pressure_sigma": "SIGMA_PRESSURE",
                         "number_density": "N_CO2", "number_density_sigma": "SIGMA_N_CO2",
                         "latitude": "LATITUDE_PC", "longitude": "LONGITUDE_PC", "sza": "SZA", "lst": "LOCAL_TIME"},
        representative={"latitude": "HLP_LAT_PC", "longitude": "HLP_LON_PC", "sza": "HLP_SZA", "lst": "HLP_LT"},
        extra_variables={"n_co2_m3": ("N_CO2", "SIGMA_N_CO2"), "n_o2_m3": ("N_O2", "SIGMA_N_O2"),
                         "n_o3_m3": ("N_O3", "SIGMA_N_O3")},
        value_factor={"n_co2_m3": 1e6, "n_o2_m3": 1e6, "n_o3_m3": 1e6},
        density_molar_mass=44.01,
        citation=("Deighan, J. (2018). MAVEN IUVS Derived-level Data Product Bundle (urn:nasa:pds:maven.iuvs.derived), "
                  "NASA Planetary Data System, doi:10.17189/1518956; Gröller, H., et al. (2018). MAVEN/IUVS stellar "
                  "occultation measurements of Mars atmospheric structure and composition. JGR Planets, 123, 1449-1483."),
        doi="10.17189/1518956",
    ),
    Dataset(
        id="pvoro-nssdc", mission_id="pvo", instrument="ORO (Radio Occultation)", level="Derived (PDS4)",
        title="Pioneer Venus Orbiter radio occultations: temperature-pressure and electron density profiles "
              "(1978-1992, recovered from NSSDC by Withers et al. 2020)",
        body_ids=("venus",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^pvoro_bundle$",
        pds4_product_dir="data_derived/",
        rules=((r"nssdc_temp", "Temperature-pressure profile (200 K upper boundary)", "profile"),
               (r"nssdc_eden", "Ionosphere electron density profile", "profile"),
               (r"graph_temp_k82", "Temperature profile digitised from Kliore & Patel (1982)", "profile"),
               (r"graph_temp_k80", "Temperature vs pressure digitised from Kliore & Patel (1980), no altitude", "other"),
               (r"graph_eden", "Electron density digitised from published figures (observation time ambiguous)", "other"),
               (r"nssdc_freq", "Frequency residuals (NSSDC)", "other")),
        # Temperature products give three retrievals (upper boundary 150, 200, 250 K, on the
        # same radii); the 200 K one is used, as in Withers et al. (2020a), and half the
        # 150-250 K spread is its systematic uncertainty (the archive gives no random one).
        # Altitudes are R - 6051.8 km throughout.
        profile_columns={"radius": ("R20016", "R15"), "altitude": "Z", "temperature": ("T20016", "TEMP"),
                         "pressure": ("P20016", "PRESS"), "electron_density": "EDEN15",
                         "latitude": ("LAT16_SPICE", "LAT15_SPICE", "LAT_SPICE"),
                         "longitude": ("LON16_SPICE", "LON15_SPICE", "LON_SPICE"),
                         "sza": ("SZA16_SPICE", "SZA15_SPICE", "SZA_SPICE"),
                         "lst": ("LST16_SPICE", "LST15_SPICE", "LST_SPICE")},
        systematic_from_bracket={"temperature_k": ("T15016", "T25016"), "pressure_hpa": ("P15016", "P25016")},
        altitude_reference_km=6051.8,          # Z = R - 6051.8 km (user guide, Sections 2 and 5)
        fill_values={"R15": (1e9,), "EDEN15": (1e9,), "Z15": (1e9,), "Z": (-9.0,), "TEMP": (0.0,), "PRESS": (-9.0,)},
        citation=("Withers, P., Hensley, K., Vogt, M. F., & Hermann, J. (2020). Recovery and validation of Venus "
                  "neutral atmospheric (and ionospheric electron density) profiles from Pioneer Venus Orbiter radio "
                  "occultation observations. PSJ, 1, 79 and 78. Data: Withers & Huber (2020), doi:10.17189/tm55-bj87."),
        doi="10.17189/tm55-bj87",
        times_from_labels=True,
    ),
    Dataset(
        id="corss-titan-neutral-profiles", mission_id="cassini", instrument="RSS (Radio Science)", level="Derived (PDS4)",
        title="Cassini radio occultations of Titan: temperature, pressure and density profiles (2006-2016, Schinder et al.)",
        body_ids=("titan",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^titan_profiles_bundle$",
        pds4_product_dir="data/",
        rules=((r"^data/corsstpp[st]\d+[ie]", "Neutral atmosphere profile (T, p, n) with error bars", "profile"),),
        # RADIUS, not ALTITUDE_ABOVE_SURFACE (which is above 2575.0 km): the 2574.7 km Titan sphere
        profile_columns={"radius": "RADIUS", "temperature": "TEMPERATURE", "pressure": "PRESSURE",
                         "number_density": "NUMBER_DENSITY", "latitude": "LATITUDE", "longitude": "LONGITUDE",
                         "refractivity": "REFRACTIVITY"},
        extra_variables={"density_measured": ("MASS_DENSITY", None)},
        # 1-sigma errors from the spacecraft ephemeris (CE file) and from thermal noise
        # (WE file) are independent: total = sqrt(CE^2 + WE^2)
        sigma_from_siblings={
            "temperature_k": (("_CE_", "TEMPERATURE ERROR BAR"), ("_WE_", "TEMPERATURE ERROR BAR")),
            "pressure_hpa": (("_CE_", "PRESSURE ERROR BAR"), ("_WE_", "PRESSURE ERROR BAR")),
            "density_measured": (("_CE_", "DENSITY ERROR BAR"), ("_WE_", "DENSITY ERROR BAR")),
        },
        citation=("Schinder, P. J., et al. (2011, 2012). The structure of Titan's atmosphere from Cassini radio "
                  "occultations. Icarus, 215, 460-474; 221, 1020-1031. Data: CO-S-RS-4/5-RSDR-V1.0, PDS Atmospheres Node."),
        doi="10.1016/j.icarus.2011.07.030",
        times_from_labels=True,
    ),
    Dataset(
        id="corss-saturn-ionosphere", mission_id="cassini", instrument="RSS (Radio Science)", level="Derived (PDS4)",
        title="Cassini radio occultations of Saturn: ionospheric electron density profiles (2005-2013, Kliore et al.)",
        body_ids=("saturn",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^saturn_iono$",
        pds4_product_dir="data/",
        rules=((r"rss_s\d+_r\d+_ne_[ie]", "Ionosphere electron density profile", "profile"),),
        profile_columns={"altitude": "Altitude", "electron_density": "Electron Density",
                         "electron_density_sigma": "Electron Density Error Bar", "latitude": "Latitude"},
        # "Width of the error bar which is centered on the value"; 0 where none is given
        fill_values={"Electron Density Error Bar": (0.0,)},
        sigma_factor={"electron_density_cm3": 0.5},
        altitude_reference="the 1-bar NAIF reference ellipsoid of Saturn (60268 x 54364 km), at the profile latitude",
        citation=("Kliore, A. J., et al. (2009). Midlatitude and high-latitude electron density profiles in the "
                  "ionosphere of Saturn obtained by Cassini radio occultation observations. JGR, 114(A4). "
                  "Data: doi:10.17189/1518961."),
        doi="10.17189/1518961",
        times_from_labels=True,
    ),
    Dataset(
        id="cassini-uvis-saturn-thermosphere", mission_id="cassini", instrument="UVIS (EUV stellar occultations)",
        level="Derived (PDS4)",
        title="Cassini UVIS occultations of Saturn: thermospheric H2 density and temperature profiles (Koskinen et al.)",
        body_ids=("saturn",), archive="NASA PDS Atmospheres Node (PDS4)",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/",
        volume_pattern=r"^saturn_thermosphere$",
        pds4_product_dir="data/",
        rules=((r"euv\d{4}_\d{3}_.*_results", "Thermosphere H2 density and temperature profile", "profile"),
               (r"uvis_saturn_occfiles", "List of occultations", "other")),
        profile_columns={"altitude": "Altitude", "temperature": "Temperature", "temperature_sigma": "Temperature error",
                         "number_density": "Number density", "latitude": "Latitude", "longitude": "Longitude"},
        altitude_reference="the 1-bar level of Saturn along the surface normal (Koskinen et al. 2015)",
        # "Direct retrieval (inversion) molecular hydrogen number density" (the labels)
        density_molar_mass=2.01588,
        citation=("Koskinen, T. T., et al. (2015). Saturn's variable thermosphere from Cassini/UVIS occultations. "
                  "Icarus, 260, 174-189. Data: doi:10.17189/518e-p721."),
        doi="10.1016/j.icarus.2015.07.008",
        times_from_labels=True,
    ),
    Dataset(
        id="mro-m-rss-5-tps-v1.0", mission_id="mro", instrument="RSS (Radio Science)", level="L5 (derived)",
        title="Mars Reconnaissance Orbiter radio occultation: temperature-pressure profiles (2008-2012, D. Hinson)",
        body_ids=("mars",), archive="NASA PDS Atmospheres Node",
        base_url="https://pds-atmospheres.nmsu.edu/PDS/data/",
        volume_pattern=r"^mrors_2\d{3}$",
        rules=((r"(^|/)tps/", "Temperature-pressure profile", "profile"),),
        profile_columns=RS_PROFILE_COLUMNS,
        hydrostatic_in_geopotential=True,
        citation=("Hinson, D. P., et al. (2008). Radio occultation measurements and MGCM simulations of Kelvin "
                  "waves on Mars. Icarus, 193, 125-138. Data: MRO-M-RSS-5-TPS-V1.0, NASA PDS Atmospheres Node."),
        doi="10.1016/j.icarus.2007.09.009",
    ),
    Dataset(
        id="mex-m-mrs-5-occ", mission_id="mex", instrument="MaRS (Radio Science)", level="L4",
        title="Mars Express radio occultation: neutral atmosphere and ionosphere profiles (L4)",
        body_ids=("mars",), archive="ESA PSA",
        base_url="https://archives.esac.esa.int/psa/ftp/MARS-EXPRESS/MRS/",
        # The V1.0 and V2.0 copies of 9101 overlap; the catalogue keys products by id, so
        # the later volume's rows replace the earlier ones.
        volume_pattern=r"^MEX-M-MRS-5-OCC-\d{4}-V\d\.\d$",
        mirrors=(("https://pds-geosciences.wustl.edu/mex/mex-m-mrs-5-occ-v1/",
                  r"^MEX-M-MRS-5-OCC-(\d{4})-V\d\.\d$", r"mexmrs_\1"),),
        rules=(
            # AIO / IIO: text files with the occultation point's position and illumination,
            # one per profile; not tables (they used to be offered as profiles and fail)
            (r"l04_[ai]\wo_", "L4 occultation geometry (text)", "other"),
            (r"l04_a(\w{2})_", "L4 neutral atmosphere profile", "profile"),
            (r"l04_i(\w{2})_", "L4 ionosphere electron density profile", "profile"),
        ),
        profile_columns=RS_PROFILE_COLUMNS,
        # The ionosphere profiles run from the surface to 1000-5800 km: below the team's lowest
        # valid radius (else the highest level under 100 km at -3 sigma) the X-band densities
        # are the neutral atmosphere's, and above the peak they end in noise
        ne_lowest_valid_info=("ION_INFO", "Lowest valid altitude of ionospheric profile"),
        neutral_below_km=100.0,
        topside_min_snr=2.0,
        # Each profile is integrated down from three temperatures at the top (the labels'
        # LOWER / MEDIUM / UPPER BOUNDARY CONDITION columns, e.g. 130, 165 and 200 K); VEDA
        # uses MEDIUM and keeps half the LOWER-UPPER difference as the systematic uncertainty
        systematic_from_bracket={
            "temperature_k": ("TEMPERATURE (LOWER BOUNDARY CONDITION)", "TEMPERATURE (UPPER BOUNDARY CONDITION)"),
            "pressure_hpa": ("PRESSURE (LOWER BOUNDARY CONDITION)", "PRESSURE (UPPER BOUNDARY CONDITION)")},
        times_earth_received=True,
        citation=MEX_CITATION,
        # e.g. M65RSR0L04_AIX_041601543_60.LBL -> 2004 day 160 15:43
        time_from_name=r"_(?P<yy>\d{2})(?P<doy>\d{3})(?P<hh>\d{2})(?P<mm>\d{2})_\d+\.",
    ),
    Dataset(
        id="mex-m-spi-4-uvddr-prof-v1.0", mission_id="mex", instrument="SPICAM (UV stellar occultation)",
        level="L4 (derived)",
        title="Mars Express SPICAM stellar occultations: CO2 density and temperature, 60-130 km (2004-2005, Forget et al. 2009)",
        body_ids=("mars",), archive="ESA PSA",
        base_url="https://archives.esac.esa.int/psa/ftp/MARS-EXPRESS/SPICAM/",
        volume_pattern=r"^MEX-M-SPI-4-UVDDR-PROF-V1\.0$",
        # no index: the labels in DATA/ are listed, with each one's START_TIME
        pds4_product_dir="DATA/", times_from_labels=True,
        rules=((r"roobs_", "CO2 density profile (stellar occultation)", "profile"),
               (r"tobs_", "Temperature profile (stellar occultation)", "profile")),
        # Each profile is given for three temperatures at the top (100, 175, 250 K), all
        # three columns under one name (read as NAME, NAME_2, NAME_3): VEDA uses 175 K and
        # keeps half the 100-250 K difference as the systematic uncertainty.  The labels
        # and catalogue say cm^-3, but the values (2e-4 at 35 km, 5e-10 at 130 km) are the
        # mass density in kg/m^3 that Forget et al. (2009) plot.
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE_2", "temperature_sigma": "TEMPERATURE_ERROR",
                         "latitude": "INTERCEPT_POINT_LATITUDE", "longitude": "INTERCEPT_POINT_LONGITUDE"},
        extra_variables={"density_measured": ("CO2_DENSITY_2", "CO2_DENSITY_ERROR")},
        systematic_from_bracket={"temperature_k": ("TEMPERATURE", "TEMPERATURE_3")},
        altitude_reference="the Mars zero datum (MOLA areoid), as given by the SPICAM team",
        citation=("Forget, F., et al. (2009). Density and temperatures of the upper Martian atmosphere measured by "
                  "stellar occultations with Mars Express SPICAM. J. Geophys. Res., 114, E01004. "
                  "Data: MEX-M-SPI-4-UVDDR-PROF-V1.0, ESA PSA."),
        doi="10.1029/2008JE003086",
    ),
    Dataset(
        id="mex-m-spi-4-irddr-prof-v1.0", mission_id="mex", instrument="SPICAM (IR solar occultation)",
        level="L4 (derived)",
        title="Mars Express SPICAM solar occultations: water vapour profiles (2004-2018, Fedorova et al. 2021)",
        body_ids=("mars",), archive="ESA PSA",
        base_url="https://archives.esac.esa.int/psa/ftp/MARS-EXPRESS/SPICAM/",
        volume_pattern=r"^MEX-M-SPI-4-IRDDR-PROF-V1\.0$",
        # its index gives no observation times: the labels are listed and read, as above
        pds4_product_dir="DATA/", times_from_labels=True,
        rules=((r"_h2o_density", "Water vapour number density profile", "profile"),
               (r"_h2o_vmr", "Water vapour volume mixing ratio profile", "profile")),
        profile_columns={"altitude": "ALTITUDE",
                         "latitude": "INTERCEPT_POINT_LATITUDE", "longitude": "INTERCEPT_POINT_LONGITUDE"},
        extra_variables={"h2o_cm3": ("H2O_CONCENTRATION", "H2O_CONCENTRATION_ERROR"),
                         "h2o_ppm": ("H2O VOLUME MIXING RATIO", "H2O VOLUME MIXING RATIO ERROR")},
        altitude_reference="the Mars ellipsoid along the line of sight, as given by the SPICAM team",
        citation=("Fedorova, A., et al. (2021). Multi-annual monitoring of the water vapor vertical distribution on "
                  "Mars by SPICAM on Mars Express. J. Geophys. Res. Planets, 126, e2020JE006616. "
                  "Data: MEX-M-SPI-4-IRDDR-PROF-V1.0, ESA PSA."),
        doi="10.1029/2020JE006616",
    ),
    Dataset(
        id="juno-ro-coffin2025", mission_id="juno", instrument="Radio science (radio occultation)",
        level="Derived (research data)",
        title="Juno radio occultations: Jupiter ionosphere electron density profiles, perijoves 53-62 (Coffin et al. 2025)",
        body_ids=("jupiter",), archive="Zenodo (CC-BY-4.0)",
        base_url="https://zenodo.org/records/15305795/",
        volume_pattern=r"^repository$",
        # The files' ELECDEN is in m^-3, not the cm^-3 of the readme: the peaks (1.3-3.3 x 10^11)
        # equal those of the same occultations in Caruso et al.'s files in cm^-3 (1.3-3.4 x 10^5)
        repository={"kind": "zenodo_files", "record": "15305795", "delimiter": ",",
                    "files": r"PJ(?P<pj>\d{3})(?P<dir>[NX])_EDP_V01\.CSV",
                    "points": JUNO_OCCULTATION_POINTS, "directions": {"N": "I", "X": "E"},
                    "columns": [("ETTX", "s"), ("ETOCC", "s"), ("ETRX", "s"), ("UTCTX", "UTC"), ("UTCOCC", "UTC"),
                                ("UTCRX", "UTC"), ("OCCPTRADIUS", "km"), ("OCCPTALT", "km"), ("OCCPTLAT", "deg"),
                                ("OCCPTLON", "deg"), ("OCCPTSZA", "deg"), ("OCCPTLST", "h"), ("OCCPTSEP", "deg"),
                                ("OCCPTEPS", "deg"), ("ELECDEN", "m-3"), ("ELECDENERR", "m-3")]},
        rules=((r"^pj\d{3}n_", "Ionosphere electron density profile, ingress", "profile"),
               (r"^pj\d{3}x_", "Ionosphere electron density profile, egress", "profile")),
        profile_columns={"altitude": "OCCPTALT", "electron_density": "ELECDEN", "electron_density_sigma": "ELECDENERR",
                         "latitude": "OCCPTLAT", "longitude": "OCCPTLON", "sza": "OCCPTSZA", "lst": "OCCPTLST",
                         "et": "ETOCC"},
        column_units={"OCCPTALT": "KM", "ELECDEN": "1/M**3", "ELECDENERR": "1/M**3"},
        # the point 1000 km up (JUNO_OCCULTATION_POINTS), as for the Caruso et al. profiles
        representative={"latitude": "LATITUDE", "longitude": "LONGITUDE"},
        altitude_reference="Jupiter's 1-bar ellipsoid (71492 x 66854 km), at the occultation point",
        # the profiles run to 9000-29000 km, far into the noise; Jupiter's peaks are at 450-1900 km
        topside_min_snr=2.0, peak_below_km=3000.0,
        citation=("Coffin, D. A., et al. (2025). Juno-derived electron density profiles of the high-latitude Jovian "
                  "ionosphere. J. Geophys. Res. Space Physics, 130, e2025JA033754. Data: doi:10.5281/zenodo.15305795 "
                  "(CC-BY-4.0)."),
        doi="10.5281/zenodo.15305795",
    ),
    Dataset(
        id="juno-ro-caruso2026", mission_id="juno", instrument="Radio science (radio occultation)",
        level="Derived (research data)",
        title="Juno radio occultations: Jupiter ionosphere electron density profiles, perijoves 53-80 (Caruso et al. 2026)",
        body_ids=("jupiter",), archive="Zenodo (CC-BY-4.0)",
        base_url="https://zenodo.org/records/22706200/",
        volume_pattern=r"^repository$",
        # two columns, no time or place: those come from JUNO_OCCULTATION_POINTS (1000 km up)
        repository={"kind": "zenodo_zip", "record": "22706200", "zip": "Juno_Ne_profiles_UniBo.zip",
                    "members": r"PJ(?P<pj>\d{2})(?P<dir>[IE])_Ne\.txt", "delimiter": None,
                    "points": JUNO_OCCULTATION_POINTS,
                    "columns": [("ELECTRON_DENSITY", "cm-3"), ("ALTITUDE", "km")]},
        rules=((r"^pj\d{2}i_", "Ionosphere electron density profile, ingress", "profile"),
               (r"^pj\d{2}e_", "Ionosphere electron density profile, egress", "profile")),
        profile_columns={"altitude": "ALTITUDE", "electron_density": "ELECTRON_DENSITY",
                         "latitude": "LATITUDE", "longitude": "LONGITUDE"},
        column_units={"ALTITUDE": "KM", "ELECTRON_DENSITY": "1/CM**3"},
        altitude_reference="Jupiter's 1-bar ellipsoid (71492 x 66854 km), as given by the team",
        citation=("Caruso, A. (2026). Electron density profiles of Jupiter's ionosphere from Juno radio occultations, "
                  "doi:10.5281/zenodo.22706200 (CC-BY-4.0), for Caruso et al. (2026); method: Caruso, A., et al. (2025). "
                  "Probing Jupiter's atmosphere through Juno radio occultations: methodology and initial observations. "
                  "Geophys. Res. Lett., 52, e2024GL113231."),
        doi="10.5281/zenodo.22706200",
    ),
    Dataset(
        id="tgo-nomad-so-lopezvalverde2023", mission_id="tgo", instrument="NOMAD SO (solar occultation)",
        level="Derived (research data)",
        title="ExoMars TGO NOMAD solar occultations: temperature and pressure profiles, Mars Year 34 (Lopez-Valverde et al. 2023)",
        body_ids=("mars",), archive="Zenodo (CC-BY-4.0)",
        base_url="https://zenodo.org/records/7086187/",
        volume_pattern=r"^repository$",
        # One text file per scan in a .tar.xz: a header with the ranges of latitude, longitude
        # (east), local time and Ls over the scan (their midpoints are used), then 2-km levels
        # from 0 to 200 km.  Levels where the averaging kernel's diagonal is below 0.01 are the
        # first guess (the retrieval keeps it where the spectra say nothing) and are masked.
        repository={"kind": "zenodo_zip", "record": "7086187", "zip": "Year1_3ndRun_allTPfiles.tar.xz",
                    "members": r"TPcorrected_(?P<date>\d{8})_(?P<time>\d{6})_1p0a_SO_A_(?P<dir>[IE])_149_\.dat",
                    "delimiter": None,
                    "header_ranges": {"LATITUDE": "lats", "LONGITUDE": "longit", "LST": "lct", "LS_FILE": "L_s"},
                    "min_kernel": ("AVK_DIAGONAL", 0.01),
                    "columns": [("ALTITUDE", "km"), ("TEMPERATURE", "K"), ("PRESSURE", "hPa"),
                                ("TEMPERATURE_FIRST_GUESS", "K"), ("PRESSURE_FIRST_GUESS", "hPa"),
                                ("TEMPERATURE_ERROR", "K"), ("AVK_DIAGONAL", "")]},
        rules=((r"_so_a_i_149", "Temperature-pressure profile, ingress", "profile"),
               (r"_so_a_e_149", "Temperature-pressure profile, egress", "profile")),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "pressure": "PRESSURE",
                         "temperature_sigma": "TEMPERATURE_ERROR", "latitude": "LATITUDE", "longitude": "LONGITUDE"},
        column_units={"ALTITUDE": "KM", "TEMPERATURE": "K", "PRESSURE": "HPA", "TEMPERATURE_ERROR": "K"},
        altitude_reference="the tangent heights given by the NOMAD team (the data set does not name the reference surface)",
        citation=("Lopez-Valverde, M. A., et al. (2023). Martian atmospheric temperature and density profiles during the "
                  "first year of NOMAD/TGO solar occultation measurements. J. Geophys. Res. Planets, 128, e2022JE007278. "
                  "Data: doi:10.5281/zenodo.7086187 (CC-BY-4.0)."),
        doi="10.5281/zenodo.7086187",
    ),
    Dataset(
        id="tgo-acs-mir-belyaev2022", mission_id="tgo", instrument="ACS MIR (solar occultation)",
        level="Derived (research data)",
        title="ExoMars TGO ACS MIR solar occultations: CO2 density, temperature and pressure, 20-180 km, 2018-2021 (Belyaev et al. 2022)",
        body_ids=("mars",), archive="Mendeley Data (CC-BY-4.0)",
        base_url="https://data.mendeley.com/datasets/g6j5t2z73z/2/",
        volume_pattern=r"^repository$",
        # One text file per occultation (DATA/<hemisphere>/<orbit>n<k>_MEANprofiles.txt); the
        # time (the date only), place, local time and Ls are in OBSERVATION_LIST_v02.txt, found
        # by orbit and hemisphere (two orbits with two northern occultations each cannot be
        # told apart there and are left out).  The CO2 density is read as the density of CO2
        # (44.01 g/mol) for VEDA's own hydrostatic temperatures.
        repository={"kind": "zenodo_zip", "url": "https://data.mendeley.com/public-api/zip/g6j5t2z73z/download/2",
                    "zip": "acs_mir_belyaev2022_v2.zip", "delimiter": None,
                    "members": r".*/(?P<hemi>NORTHERN|SOUTHERN) HEMISPHERE/(?P<orbit>\d{6})n(?P<occ>\d)_MEANprofiles\.txt",
                    "product_id": "acs_mir_{orbit}_{hemi}_{occ}",
                    "catalog": {"member": "OBSERVATION_LIST_v02.txt", "key": [(0, "int"), (5, "sign")],
                                "groups": ["orbit", "hemi"], "date": (1, 2, 3),
                                "meta": {"LS": 4, "LATITUDE": 5, "LONGITUDE": 6, "LST": 7,
                                         "MESOPAUSE_KM": 8, "HOMOPAUSE_KM": 9}},
                    "columns": [("ALTITUDE", "km"), ("TEMPERATURE", "K"), ("TEMPERATURE_ERROR", "K"),
                                ("CO2_DENSITY", "cm-3"), ("CO2_DENSITY_ERROR", "cm-3"), ("PRESSURE", "mbar")]},
        rules=((r"^acs_mir_", "CO2 density, temperature and pressure profile", "profile"),),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "temperature_sigma": "TEMPERATURE_ERROR",
                         "pressure": "PRESSURE", "number_density": "CO2_DENSITY", "number_density_sigma": "CO2_DENSITY_ERROR",
                         "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"ALTITUDE": "KM", "TEMPERATURE": "K", "TEMPERATURE_ERROR": "K", "PRESSURE": "MBAR",
                      "CO2_DENSITY": "1/CM**3", "CO2_DENSITY_ERROR": "1/CM**3"},
        density_molar_mass=44.01,
        altitude_reference="the tangent heights given by the ACS team",
        citation=("Belyaev, D. A., et al. (2022). Thermal structure of the middle and upper atmosphere of Mars from "
                  "ACS/TGO CO2 spectroscopy. J. Geophys. Res. Planets, 127, e2022JE007286. Data: Mendeley Data, "
                  "doi:10.17632/g6j5t2z73z.2 (CC-BY-4.0)."),
        doi="10.17632/g6j5t2z73z.2",
    ),
    Dataset(
        id="tgo-acs-nir-fedorova2022", mission_id="tgo", instrument="ACS NIR (solar occultation)",
        level="Derived (research data)",
        title="ExoMars TGO ACS NIR solar occultations: water vapour, saturation, temperature and aerosol extinction, MY34-36 (Fedorova et al. 2022)",
        body_ids=("mars",), archive="Mendeley Data (CC-BY-4.0)",
        base_url="https://data.mendeley.com/datasets/6xrn9v4dc5/1/",
        volume_pattern=r"^repository$",
        # Three files per occultation (water vapour and saturation ratio, temperature, aerosol
        # extinction at 1.4 um), each a profile; place, local time and Ls in
        # list_of_NIRorbits_forsaturation.txt, by orbit and occultation number.  The list gives
        # no date: it is the day Mars reached the Ls, the Mars year counted from 34 in orbit order.
        repository={"kind": "zenodo_zip", "url": "https://data.mendeley.com/public-api/zip/6xrn9v4dc5/download/1",
                    "zip": "acs_nir_fedorova2022_v1.zip", "delimiter": None,
                    "members": r"orb(?P<orbit>\d{6})_N(?P<occ>\d)_(?P<kind>H2O_S|Temperature|aerosol_extinction)_ACSNIR\.txt",
                    "product_id": "acs_nir_{orbit}_{occ}_{kind}",
                    "catalog": {"member": "list_of_NIRorbits_forsaturation.txt", "key": [(0, "int"), (1, "int")],
                                "groups": ["orbit", "occ"], "first_mars_year": 34,
                                "meta": {"LS": 2, "LATITUDE": 3, "LONGITUDE": 4, "LST": 5}},
                    "columns": {"H2O_S": [("ALTITUDE", "km"), ("H2O", "ppmv"), ("H2O_ERROR", "ppmv"),
                                          ("SATURATION_RATIO", ""), ("SATURATION_RATIO_ERROR", "")],
                                "Temperature": [("ALTITUDE", "km"), ("TEMPERATURE", "K"), ("TEMPERATURE_ERROR", "K")],
                                "aerosol_extinction": [("ALTITUDE", "km"), ("EXTINCTION", "km-1"),
                                                       ("EXTINCTION_ERROR", "km-1")]}},
        rules=((r"_h2o_s$", "Water vapour and saturation ratio profile", "profile"),
               (r"_temperature$", "Temperature profile", "profile"),
               (r"_aerosol_extinction$", "Aerosol extinction profile (1.4 um)", "profile")),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "temperature_sigma": "TEMPERATURE_ERROR",
                         "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"ALTITUDE": "KM", "TEMPERATURE": "K", "TEMPERATURE_ERROR": "K"},
        extra_variables={"h2o_ppm": ("H2O", "H2O_ERROR"), "saturation_ratio": ("SATURATION_RATIO", "SATURATION_RATIO_ERROR"),
                         "aerosol_extinction_km": ("EXTINCTION", "EXTINCTION_ERROR")},
        altitude_reference="the tangent heights given by the ACS team",
        citation=("Fedorova, A., et al. (2022). A two-Martian years survey of the water vapor saturation state on Mars "
                  "based on ACS NIR/TGO occultations. J. Geophys. Res. Planets, 128, e2022JE007348. Data: Mendeley Data, "
                  "doi:10.17632/6xrn9v4dc5.1 (CC-BY-4.0)."),
        doi="10.17632/6xrn9v4dc5.1",
    ),
    Dataset(
        id="tgo-nomad-so-trompet2023", mission_id="tgo", instrument="NOMAD SO (solar occultation)",
        level="Derived (research data)",
        title="ExoMars TGO NOMAD solar occultations: CO2 density and temperature, 60-100 km, MY35-36 (Trompet et al. 2023)",
        body_ids=("mars",), archive="BIRA-IASB data repository (CC-BY-4.0)",
        base_url="https://data.aeronomie.be/dataset/subset-of-co2-and-temperature-vertical-profiles-retrieved-from-nomad-so-tgo-presented-in-trompet-et/",
        volume_pattern=r"^repository$",
        # One text file per scan, its time in the name; latitude, longitude (east) and local time
        # at each level.  The temperatures are the team's hydrostatic ones from the CO2 density,
        # which VEDA reads as the density of CO2 (44.01 g/mol) for its own.
        repository={"kind": "zenodo_zip", "zip": "trompet_jgr2022.zip", "delimiter": None,
                    "url": "https://data.aeronomie.be/dataset/a0985fc6-5453-4d06-b464-7488a4b324ee/resource/3f94ace1-bb8b-408d-b196-da2c64a57f58/download/trompet_jgr2022.zip",
                    "members": r"(?P<date>\d{8})_(?P<time>\d{6})_1p0a_SO_[A-Z]_(?P<dir>[IE])_\d+\.dat",
                    "columns": [("CO2_DENSITY", "cm-3"), ("CO2_DENSITY_ERROR", "cm-3"), ("TEMPERATURE", "K"),
                                ("TEMPERATURE_ERROR", "K"), ("ALTITUDE", "km"), ("LS", "deg"), ("LATITUDE", "deg"),
                                ("LONGITUDE", "deg"), ("LST", "h")]},
        rules=((r"_so_[a-z]_i_", "CO2 density and temperature profile, ingress", "profile"),
               (r"_so_[a-z]_e_", "CO2 density and temperature profile, egress", "profile")),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "temperature_sigma": "TEMPERATURE_ERROR", "number_density": "CO2_DENSITY", "number_density_sigma": "CO2_DENSITY_ERROR", "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"ALTITUDE": "KM", "TEMPERATURE": "K", "TEMPERATURE_ERROR": "K", "CO2_DENSITY": "1/CM**3",
                      "CO2_DENSITY_ERROR": "1/CM**3"},
        density_molar_mass=44.01,
        altitude_reference="the tangent heights given by the NOMAD team",
        citation=("Trompet, L., et al. (2023). Carbon dioxide retrievals from NOMAD-SO on ESA's ExoMars Trace Gas Orbiter "
                  "and temperature profiles retrievals with the hydrostatic equilibrium equation: 1. Description of the "
                  "method; 2. Temperature variabilities in the mesosphere at Mars terminator. J. Geophys. Res. Planets, "
                  "128, e2022JE007277 and e2022JE007279. Data: BIRA-IASB, doi:10.18758/71021074 (CC-BY-4.0)."),
        doi="10.18758/71021074",
    ),
    Dataset(
        id="tgo-nomad-so165-trompet2026", mission_id="tgo", instrument="NOMAD SO (solar occultation)",
        level="Derived (research data)",
        title="ExoMars TGO NOMAD solar occultations, order 165: upper thermosphere CO2 density and temperature, 140-190 km, 2018-2025 (Trompet 2026)",
        body_ids=("mars",), archive="BIRA-IASB data repository (CC-BY-4.0)",
        base_url="https://data.aeronomie.be/dataset/mars-upper-thermosphere-co2-density-and-temperature-vertical-profiles-retrieved-from-nomad-so/",
        volume_pattern=r"^repository$",
        # as Trompet et al. (2023), with local time before latitude and longitude in the files
        repository={"kind": "zenodo_zip", "zip": "trompet_2026_nomadso165.tar.gz", "delimiter": None,
                    "url": "https://data.aeronomie.be/dataset/20e7f5ab-6a6a-4951-b253-ec359db3f858/resource/2e96043b-f6e7-42a7-9e89-9da3f1d569dc/download/trompet_2026_nomadso165.tar.gz",
                    "members": r"(?P<date>\d{8})_(?P<time>\d{6})_1p0a_SO_[A-Z]_(?P<dir>[IE])_165\.dat",
                    "columns": [("CO2_DENSITY", "cm-3"), ("CO2_DENSITY_ERROR", "cm-3"), ("TEMPERATURE", "K"),
                                ("TEMPERATURE_ERROR", "K"), ("ALTITUDE", "km"), ("LS", "deg"), ("LST", "h"),
                                ("LATITUDE", "deg"), ("LONGITUDE", "deg")]},
        rules=((r"_so_[a-z]_i_", "Upper thermosphere CO2 density and temperature profile, ingress", "profile"),
               (r"_so_[a-z]_e_", "Upper thermosphere CO2 density and temperature profile, egress", "profile")),
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "temperature_sigma": "TEMPERATURE_ERROR", "number_density": "CO2_DENSITY", "number_density_sigma": "CO2_DENSITY_ERROR", "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"ALTITUDE": "KM", "TEMPERATURE": "K", "TEMPERATURE_ERROR": "K", "CO2_DENSITY": "1/CM**3",
                      "CO2_DENSITY_ERROR": "1/CM**3"},
        density_molar_mass=44.01,
        altitude_reference="the tangent heights given by the NOMAD team",
        citation=("Trompet, L. (2026). Mars upper thermosphere CO2 density and temperature vertical profiles retrieved "
                  "from NOMAD-SO diffraction order 165. BIRA-IASB, doi:10.18758/kk9pzsjq (CC-BY-4.0)."),
        doi="10.18758/kk9pzsjq",
    ),
    Dataset(
        id="tgo-nomad-so-h2o-brines2026", mission_id="tgo", instrument="NOMAD SO (solar occultation)",
        level="Derived (research data)",
        title="ExoMars TGO NOMAD solar occultations: water vapour profiles, April 2018 - December 2023 (Brines et al. 2026)",
        body_ids=("mars",), archive="Zenodo (CC-BY-4.0)",
        base_url="https://zenodo.org/records/15146458/",
        volume_pattern=r"^repository$",
        # One text file per scan in profiles.tar, its time in the name, its place, local time
        # and Ls in "# Label: value" header lines.  The files' total density is the Mars-PCM
        # model's, not a measurement: kept in the file, not read as the profile's density.
        repository={"kind": "zenodo_zip", "record": "15146458", "zip": "profiles.tar", "delimiter": None,
                    "members": r"(?P<date>\d{8})_(?P<time>\d{6})_1p0a_SO_[A-Z]_(?P<dir>[IE])_\d+-\d+\.dat",
                    "header_values": {"LATITUDE": "Latitude", "LONGITUDE": "Longitude", "LST": "Local Solar Time",
                                      "LS": "Solar Longitude"},
                    "columns": [("ALTITUDE", "km"), ("H2O_VMR", "ppm"), ("H2O_VMR_ERROR", "ppm"),
                                ("H2O_DENSITY", "cm-3"), ("H2O_DENSITY_ERROR", "cm-3"), ("MODEL_TOTAL_DENSITY", "cm-3")]},
        rules=((r"_so_[a-z]_i_", "Water vapour profile, ingress", "profile"),
               (r"_so_[a-z]_e_", "Water vapour profile, egress", "profile")),
        profile_columns={"altitude": "ALTITUDE", "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"ALTITUDE": "KM"},
        extra_variables={"h2o_ppm": ("H2O_VMR", "H2O_VMR_ERROR"), "h2o_cm3": ("H2O_DENSITY", "H2O_DENSITY_ERROR")},
        altitude_reference="the tangent heights given by the NOMAD team",
        citation=("Brines, A., et al. (2026). Water vapor vertical distribution on Mars after six years of TGO/NOMAD "
                  "solar occultations: 1. Global climatology. J. Geophys. Res. Planets, 131, e2024JE008916. "
                  "Data: doi:10.5281/zenodo.15146458 (CC-BY-4.0)."),
        doi="10.5281/zenodo.15146458",
    ),
    Dataset(
        id="nh-pluto-rex-profiles", mission_id="new_horizons", instrument="REX (Radio Science Experiment)",
        level="Derived (PDS4)",
        title="New Horizons radio occultation of Pluto: number density, pressure and temperature at entry and exit (14 July 2015, Hinson et al. 2017)",
        body_ids=("pluto",), archive="NASA PDS Small Bodies Node (PDS4)",
        base_url="https://pdssbn.astro.umd.edu/holdings/",
        volume_pattern=r"^pds4-nh_derived:plutosystem_atmospherics-v1\.0$",
        pds4_product_dir="rexatmos/", times_from_labels=True,
        rules=((r"rex_profile_entry", "Neutral atmosphere profile, occultation entry (sunset)", "profile"),
               (r"rex_profile_exit", "Neutral atmosphere profile, occultation exit (sunrise)", "profile")),
        # the labels write the number densities in units of 1e19 m^-3 (scaling_factor)
        profile_columns={"radius": "Radius", "temperature": "Temperature", "temperature_sigma": "Sigma Temperature",
                         "pressure": "Pressure", "pressure_sigma": "Sigma Pressure", "number_density": "Number Density",
                         "number_density_sigma": "Sigma Number Density", "latitude": "Latitude", "longitude": "Longitude",
                         "lst": "Local True Solar Time", "sza": "Solar Zenith Angle"},
        citation=("Hinson, D. P., et al. (2017). Radio occultation measurements of Pluto's neutral atmosphere with "
                  "New Horizons. Icarus, 290, 96-111. Data: urn:nasa:pds:nh_derived:plutosystem_atmospherics, "
                  "NASA PDS Small Bodies Node."),
        doi="10.1016/j.icarus.2017.02.031",
    ),
    Dataset(
        id="vco-v-rs-5-occ-v1.0", times_earth_received=True, mission_id="akatsuki", instrument="RS (Radio Science)", level="L3/L4",
        title="Akatsuki radio occultation: refractivity (L3) and atmospheric profiles (L4)",
        body_ids=("venus",), archive="JAXA DARTS",
        base_url="https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-rs-5-occ-v1.0/",
        volume_pattern=r"^vcors_2\d{3}$",
        rules=(
            (r"_l4_ai_", "L4 atmosphere profile, ingress", "profile"),
            (r"_l4_ae_", "L4 atmosphere profile, egress", "profile"),
            (r"_l4_", "L4 profile", "profile"),
            (r"_l3_i_", "L3 bending angle / refractivity, ingress", "other"),
            (r"_l3_e_", "L3 bending angle / refractivity, egress", "other"),
        ),
        profile_columns=AKATSUKI_PROFILE_COLUMNS,
        # as for Mars Express: three temperatures at the top (140, 170 and 200 K); the
        # archive's own 1-sigma columns hold only the invalid value -9.99
        systematic_from_bracket={
            "temperature_k": ("TEMPERATURE (LOWER TEMPERATURE AT BOUNDARY)", "TEMPERATURE (HIGHER TEMPERATURE AT BOUNDARY)"),
            "pressure_hpa": ("PRESSURE (LOWER TEMPERATURE AT BOUNDARY)", "PRESSURE (HIGHER TEMPERATURE AT BOUNDARY)")},
        citation=AKATSUKI_CITATION,
    ),
    Dataset(
        id="vco-v-rs-3-occ-v1.0", times_earth_received=True, mission_id="akatsuki", instrument="RS (Radio Science)", level="L2",
        title="Akatsuki radio occultation: received frequency and power (L2)",
        body_ids=("venus",), archive="JAXA DARTS",
        base_url="https://data.darts.isas.jaxa.jp/pub/pds3/vco-v-rs-3-occ-v1.0/",
        volume_pattern=r"^vcors_1\d{3}$",
        rules=((r"_l2_", "L2 frequency and signal power time series", "timeseries"),),
        citation=AKATSUKI_CITATION,
    ),
]


# Further data sets: every Akatsuki camera, more NASA PDS3 volumes, and live search for all
# payloads served by the ESA PSA, the NASA PDS Registry and OPUS.
from .indexed_datasets import INDEXED_DATASETS  # noqa: E402
from .service_datasets import SERVICE_DATASETS  # noqa: E402

DATASETS.extend(INDEXED_DATASETS)
DATASETS.extend(SERVICE_DATASETS)

# Reference papers of the original data sets (keys in references.json)
_REFS = {
    "corss_occul_el_dens": ("kliore2008", "kliore2004", "matson2002"),
    "jno-x-mwr": ("janssen2017", "bolton2017"),
    "vex-v-rss-1-ent-v1.0": ("hausler2006", "svedhem2007"),
    "vex-v-vra-1-2-3": ("hausler2006", "svedhem2007"),
    "vex-vera-gramigna2023": ("gramigna2023", "gramigna2026data", "hausler2006", "svedhem2007"),
    "vex-vera-fsi-imamura": ("imamura2018", "imamura2021data", "hausler2006", "svedhem2007"),
    "vex-soir-co2-temperature": ("mahieux2023", "mahieux2015", "bira2024soir", "svedhem2007"),
    "mgn-v-rss-5-occ-prof-rtpd-v1.0": ("jenkins1994", "steffes1994", "saunders1992"),
    "mgn-v-rss-5-occ-prof-abs-h2so4-v1.0": ("jenkins1994", "steffes1994", "saunders1992"),
    "mgn-v-rss-1-rocc-v2.0": ("jenkins1994", "saunders1992"),
    "gp-j-entry-v1.0": ("seiff1998", "johnson1992", "atkinson1998"),
    "hp-ssa-hasi-2-3-4-mission-v1.1": ("fulchignoni2005", "fulchignoni2002", "matson2002"),
    "hp-ssa-dtwg-6-trajectory-v1.0": ("kazeminejad2007", "matson2002"),
    "mgs-m-rss-5-sdp-v1.0": ("tyler2001", "hinson1999", "albee2001"),
    "mro-m-rss-5-tps-v1.0": ("hinson2008", "hinson1999", "zurek2007"),
    "mer-m-imu-5-edl-derived-v1.0": ("withers2006",),
    "vega1-vega2-v-2-3-venus-v1.0": ("lorenz2018",),
    "phx-m-ase-5-edl-rdr-v1.0": ("withers2010",),
    "msl-edl-atmosphere": ("holsteinrathlou2016", "holsteinrathlou2015data"),
    "insight-edl-atmosphere": ("karatekin2020data",),
    "ody-m-accel-5-derived-v1.0": ("tolson2005",),
    "mro-m-accel-5-profile-v1.0": ("tolson2008",),
    "maven-acc-profile": ("zurek2015", "tolson2016data"),
    "nh-pluto-rex-profiles": ("hinson2017", "stern2008"),
    "tgo-nomad-so-trompet2023": ("trompet2023a", "trompet2023b", "vandaele2018"),
    "tgo-nomad-so165-trompet2026": ("trompet2026data", "vandaele2018"),
    "tgo-nomad-so-h2o-brines2026": ("brines2026", "vandaele2018"),
    "tgo-acs-mir-belyaev2022": ("belyaev2022", "korablev2017"),
    "tgo-acs-nir-fedorova2022": ("fedorova2022", "korablev2017"),
    "mpf-m-asimet-4-ddr-edl-v1.0": ("magalhaes1999", "schofield1997"),
    "tgo-nomad-so-lopezvalverde2023": ("lopezvalverde2023", "vandaele2018"),
    "juno-ro-coffin2025": ("coffin2025", "asmar2017", "bolton2017"),
    "juno-ro-caruso2026": ("caruso2025", "asmar2017", "bolton2017"),
    "mex-m-spi-4-uvddr-prof-v1.0": ("forget2009", "bertaux2006"),
    "mex-m-spi-4-irddr-prof-v1.0": ("fedorova2021", "bertaux2006"),
    "maven-rose-edp": ("withers2020rose", "withers2020radiosci", "withers2017rosedata"),
    "maven-ngims-l2": ("mahaffy2015", "elrod2014data"),
    "maven-iuvs-occultation": ("groller2018", "mcclintock2015", "deighan2018data"),
    "mro-crism-smith2013-aerosol": ("smith2013", "khayat2024data"),
    "mro-crism-guzewich-aerosol": ("guzewich2014", "guzewich2019", "khayat2024data"),
    "corss-titan-neutral-profiles": ("schinder2011", "schinder2012", "schinder2015"),
    "corss-saturn-ionosphere": ("kliore2009", "kliore2014data"),
    "cassini-uvis-saturn-thermosphere": ("koskinen2015", "koskinen2018data"),
    "pvoro-nssdc": ("withers2020a", "withers2020b", "withers2020data", "kliore1980", "colin1980"),
    "mex-m-mrs-5-occ": ("patzold2016", "patzold2004", "chicarro2004"),
    "vco-v-rs-5-occ-v1.0": ("imamura2017", "nakamura2016"),
    "vco-v-rs-3-occ-v1.0": ("imamura2017", "nakamura2016"),
    "issdc-mom": ("arunan2015",),
    "issdc-ch2": (),
}
# Entry and descent probes and landers: the Geometry tab draws the probe's own descent
# (its reconstructed positions, its trajectory data set or its SPK), not the orbiter's orbit
DESCENT_DATA_SETS = {"gp-j-entry-v1.0", "hp-ssa-hasi-2-3-4-mission-v1.1", "hp-ssa-dtwg-6-trajectory-v1.0",
                     "vega1-vega2-v-2-3-venus-v1.0", "mer-m-imu-5-edl-derived-v1.0", "phx-m-ase-5-edl-rdr-v1.0",
                     "msl-edl-atmosphere", "insight-edl-atmosphere", "pds-pvo-pioneervenusprobeslaslnm"}

# Published landing and impact sites, for probes whose files give no position
# (planetocentric latitude, east longitude, as published)
PUBLISHED_SITES = {
    "pds-pvo-pioneervenusprobeslaslnm": {
        "kind": "impact sites", "source": "NASA NSSDCA probe pages; Colin 1980, doi:10.1029/JA085iA13p07575",
        # "match": parts of the product's name or path that say which probe took it (the
        # Large probe's LIR, LGC, LNMS, ...; the small probes' files name the probe)
        "sites": [{"name": "Large (Sounder) probe", "lat": 4.4, "lon": 304.0,
                   "match": ["lir_", "lgc_", "lnms", "gas_samples", "las_", "lcps", "lsfr", "lnfr", "lp_"]},
                  {"name": "North probe", "lat": 59.3, "lon": 4.8, "match": ["north"]},
                  {"name": "Day probe", "lat": -31.3, "lon": 317.0, "match": ["_day", "sp-day", "day_"]},
                  {"name": "Night probe", "lat": -28.7, "lon": 56.7, "match": ["night"]}]},
    "vega1-vega2-v-2-3-venus-v1.0": {
        "kind": "landing sites",
        "source": "the data set's own catalogue, vega_host.cat; Lorenz et al. 2018, doi:10.1016/j.icarus.2017.12.044",
        "sites": [{"name": "VEGA 2 lander", "lat": -7.14, "lon": 177.67, "match": ["vg2lr"]},
                  {"name": "VEGA 1 lander", "lat": 8.10, "lon": 175.85, "match": ["vg1lr"]}]},
}

# First and last observation dates of the data sets read on a first search, from their
# archive indexes (October 2026); "" for data sets still growing.  The mission's own data:
# ancillary files dated decades earlier are left out
COVERAGE = {
    "cassini-uvis-saturn-thermosphere": ("2005-04-13", "2017-08-04"),
    "co-s-inms-3-l1a-u-v1.0": ("2004-01-01", "2017-09-15"),
    "corss-saturn-ionosphere": ("2005-05-03", "2013-05-31"),
    "corss-titan-neutral-profiles": ("2006-03-19", "2016-05-06"),
    "corss_occul_el_dens": ("2006-03-19", "2016-05-06"),
    "gp-j-entry-v1.0": ("1995-12-07", "1995-12-07"),
    "hp-ssa-hasi-2-3-4-mission-v1.1": ("2005-01-14", "2005-01-14"),
    "hp-ssa-dtwg-6-trajectory-v1.0": ("2005-01-14", "2005-01-14"),
    "insight-edl-atmosphere": ("2018-11-26", "2018-11-26"),
    "jno-fgm-3-cal-v1.0": ("2011-08-25", ""),
    "jno-j-jnc-2-3-edr-rdr-v1.0": ("2011-08-26", ""),
    "jno-x-mwr": ("2014-01-01", ""),
    "maven-acc-profile": ("2014-10-07", ""),
    "nh-pluto-rex-profiles": ("2015-07-14", "2015-07-14"),
    "tgo-acs-mir-belyaev2022": ("2018-05-24", "2021-01-29"),
    "tgo-acs-nir-fedorova2022": ("2018-04-22", "2022-01-29"),
    "tgo-nomad-so-trompet2023": ("2019-04-22", "2021-11-29"),
    "tgo-nomad-so165-trompet2026": ("2018-04-23", "2025-06-30"),
    "tgo-nomad-so-h2o-brines2026": ("2018-04-21", "2023-12-23"),
    "mpf-m-asimet-4-ddr-edl-v1.0": ("1997-07-04", "1997-07-04"),
    "tgo-nomad-so-lopezvalverde2023": ("2018-04-23", "2019-03-13"),
    "juno-ro-coffin2025": ("2023-07-31", "2024-06-13"),
    "juno-ro-caruso2026": ("2023-07-31", "2026-01-23"),
    "mex-m-spi-4-uvddr-prof-v1.0": ("2004-01-13", "2006-04-11"),
    "mex-m-spi-4-irddr-prof-v1.0": ("2005-01-19", "2018-09-12"),
    "maven-rose-edp": ("2016-07-05", ""),
    "maven-ngims-l2": ("2014-10-18", ""),
    "maven-iuvs-occultation": ("2015-03-24", ""),
    "mer-m-imu-5-edl-derived-v1.0": ("2004-01-04", "2004-01-25"),
    "mex-m-mrs-5-occ": ("2004-04-02", ""),
    "mgn-v-rss-1-rocc-v2.0": ("1991-10-05", "1994-10-12"),
    "mgn-v-rss-5-occ-prof-abs-h2so4-v1.0": ("1991-10-05", "1991-10-06"),
    "mgn-v-rss-5-occ-prof-rtpd-v1.0": ("1991-10-05", "1991-10-06"),
    "mgs-m-rss-5-sdp-v1.0": ("1997-09-12", "2006-09-19"),  # (gravity models dated from Mariner 9, 1971)
    "mro-crism-guzewich-aerosol": ("2010-12-06", "2017-02-14"),
    "mro-crism-smith2013-aerosol": ("2009-07-10", "2012-04-26"),
    "mro-m-accel-5-profile-v1.0": ("2006-04-02", "2006-08-30"),
    "mro-m-mcs-2-edr-v1.0": ("2006-09-15", ""),
    "mro-m-mcs-4-rdr-v1.0": ("2006-09-24", ""),
    "mro-m-mcs-5-ddr-v1.0": ("2006-09-24", ""),
    "mro-m-rss-5-tps-v1.0": ("2008-08-01", ""),
    "msl-edl-atmosphere": ("2012-08-06", "2012-08-06"),
    "ody-m-accel-5-derived-v1.0": ("2001-10-26", "2002-01-11"),
    "phx-m-ase-5-edl-rdr-v1.0": ("2008-05-25", "2008-05-25"),
    "pvo-v-onms": ("1978-12-05", "1980-03-15"),
    "pvoro-nssdc": ("1978-12-05", "1989-10-18"),
    "vco-uvi-pds4": ("2010-05-21", "2024-03-24"),
    "vco-v-ir1-2-edr-v1.0": ("2010-05-21", "2016-12-09"),
    "vco-v-ir1-3-cdr-v1.0": ("2010-05-21", "2016-12-09"),
    "vco-v-ir1-3-sedr-v1.0": ("2010-05-21", "2016-12-09"),
    "vco-v-ir2-2-edr-v1.0": ("2010-05-21", "2016-12-09"),
    "vco-v-ir2-3-cdr-v1.0": ("2010-05-21", "2016-12-09"),
    "vco-v-ir2-3-sedr-v1.0": ("2010-05-21", "2016-12-09"),
    "vco-v-lir-2-edr-v1.0": ("2010-05-21", "2021-12-02"),
    "vco-v-lir-3-cdr-v1.0": ("2010-05-21", "2021-12-02"),
    "vco-v-lir-3-sedr-v1.0": ("2010-05-21", "2021-12-02"),
    "vco-v-rs-3-occ-v1.0": ("2016-03-03", "2024-04-24"),
    "vco-v-rs-5-occ-v1.0": ("2016-03-03", "2024-04-24"),
    "vco-v-uvi-2-edr-v1.0": ("2010-05-21", "2021-12-02"),
    "vco-v-uvi-3-cdr-v1.0": ("2010-05-21", "2021-12-02"),
    "vco-v-uvi-3-sedr-v1.0": ("2010-05-21", "2021-12-02"),
    "vega1-vega2-v-2-3-venus-v1.0": ("1985-06-11", "1985-06-15"),
    "vex-soir-co2-temperature": ("2006-05-12", "2014-11-27"),
    "vex-v-vra-1-2-3": ("2006-07-11", "2012-08-27"),
    "vco-lir-pds4": ("2010-05-21", "2024-03-24"),   # (from the file names: DARTS refused its index listing)
    "vex-v-rss-1-ent-v1.0": ("2005-11-09", "2013-12-19"),  # (Earth orientation and kernel files from 1962)
    "vex-vera-fsi-imamura": ("2006-07-15", "2009-09-13"),
    "vex-vera-gramigna2023": ("2014-01-20", "2014-03-11"),
}
import dataclasses as _dc  # noqa: E402
for _i, _d in enumerate(DATASETS):
    if _d.id in _REFS and not _d.refs:
        _d = DATASETS[_i] = _dc.replace(_d, refs=_REFS[_d.id])
    if _d.id in COVERAGE:
        DATASETS[_i] = _dc.replace(_d, coverage=COVERAGE[_d.id])


def get_dataset(dataset_id: str) -> Optional[Dataset]:
    dataset_id = dataset_id.lower()
    return next((d for d in DATASETS if d.id == dataset_id), None)


def datasets_for(mission_id: Optional[str] = None, body_id: Optional[str] = None) -> List[Dataset]:
    return [d for d in DATASETS
            if (not mission_id or d.mission_id == mission_id.lower())
            and (not body_id or body_id.lower() in d.body_ids)]
