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
    # Factor turning the archive's error column into 1 sigma (0.5 for a full error-bar width)
    sigma_factor: Dict[str, float] = field(default_factory=dict)
    # Vertical correlation length (km) of the archived 1-sigma errors, where the archive
    # documents one; 0: independent between levels (analysis/uncertainty.py)
    uncertainty_correlation_km: float = 0.0
    # Factor for an extra variable (and its uncertainty) whose label unit is wrong: the
    # Odyssey accelerometer densities are labelled kg/m^3 but are in kg/km^3 (1e-9)
    value_factor: Dict[str, float] = field(default_factory=dict)
    # Aerobraking passes: column of the time from periapsis (s).  Each pass is listed as
    # two profiles, the inbound leg (before periapsis) and the outbound leg, which are at
    # different places and local times and would zigzag if compared as one profile.
    pass_legs: Optional[str] = None
    # The per-sample times ("et" column) are when the signal reached the ground station,
    # not when it crossed the atmosphere (Mars Express MaRS: EPHEMERIS_SECONDS is the
    # ground received time); VEDA subtracts the one-way light time for the geometry.
    times_earth_received: bool = False
    # Profiles published in a research data repository (Zenodo, BIRA-IASB) without PDS
    # labels: how to list and read them (see archives/repositories.py)
    repository: Dict[str, Any] = field(default_factory=dict)
    # PDS4 bundle: folder (inside the bundle) holding the product XML labels; a tuple
    # gives several folders (Akatsuki LIR: calibrated levels, maps, geometry).
    pds4_product_dir: Optional[Union[str, Tuple[str, ...]]] = None
    # Products sit one level further down, in subfolders listed by the server
    # (Akatsuki: one folder per orbit, r0001 ...): list those too.
    pds4_walk: bool = False
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

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id, "mission_id": self.mission_id, "instrument": self.instrument,
            "level": self.level, "title": self.title, "body_ids": list(self.body_ids),
            "archive": self.archive, "url": self.base_url, "citation": self.citation,
            "doi": self.doi, "needs_login": bool(self.login_url), "login_url": self.login_url,
            "portal_only": self.portal_only, "portal_help": self.portal_help,
            "live": bool(self.service), "service": self.service, "refs": list(self.refs),
            "auto_index": self.auto_index, "index_note": self.index_note,
            "has_profiles": any(kind == "profile" for _, _, kind in self.rules),
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
    "electron_density": ("ELECTRON NUMBER DENSITY", "ELECTRON DENSITY"),
    "electron_density_sigma": ("SIGMA ELECTRON NUMBER DENSITY", "NOISE LEVEL ELECTRON NUMBER DENSITY",
                               "SIGMA ELECTRON DENSITY"),
    "refractivity": "REFRACTIVITY",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "sza": "SOLAR ZENITH ANGLE",
    "lst": ("LOCAL SOLAR TIME", "LOCAL TRUE SOLAR TIME OF OCCULTATION"),   # the latter: MRO header
    "et": "EPHEMERIS SECONDS",
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
        id="mgn-v-rss-5-occ-prof-rtpd-v1.0", mission_id="magellan", instrument="RSS (Radio Science)", level="L5",
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
        id="mgn-v-rss-5-occ-prof-abs-h2so4-v1.0", mission_id="magellan", instrument="RSS (Radio Science)", level="L5",
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
        id="mgn-v-rss-1-rocc-v2.0", mission_id="magellan", instrument="RSS (Radio Science)", level="L1",
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
        profile_columns={"altitude": "ALTITUDE", "temperature": "TEMPERATURE", "pressure": "PRESSURE"},
        citation=GP_CITATION,
        label_from_data=True,
        fixed_time="1995-12-07T22:04:44",    # probe entry (Young et al. 1996, Science 272)
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
        title="Venus Express SOIR solar occultations 2006-2014: CO2 density, pressure and temperature at the terminator, 70-170 km (BIRA-IASB)",
        body_ids=("venus",), archive="BIRA-IASB data repository (CC-BY-4.0)",
        base_url="https://data.aeronomie.be/dataset/venus-atmospheric-profiles-from-spicav-soir-vexv23/",
        volume_pattern=r"^repository$",
        # Some profiles repeat one temperature over their top 10 km: the value the retrieval
        # starts its downward integration from, not a measurement (pressure there is n k T
        # with it); temperature and pressure are masked there, the density is kept.
        # The top level of every profile is that starting temperature too, written with an
        # uncertainty of 0 (1e-13 K): also masked.
        repository={"kind": "votable_split", "revision": 3,
                    "mask_constant": ("temperature", ("err_temperature", "pressure", "err_pressure")),
                    "mask_zero_sigma": ("err_temperature", ("temperature", "err_temperature", "pressure", "err_pressure")),
                    "url": "https://data.aeronomie.be/dataset/bc9068b4-00c0-41fd-a1fa-54a3afaa14a4/resource/0d385c08-73bc-4106-89da-47e9282d2cad/download/co2_soir_w23.zip",
                    "member": "SOIRProfiles_CO2_0.xml", "split": ("orbit", "case"),
                    "product_id": "soir_co2_orbit{0:04.0f}_{1:.0f}", "time": "time_JDUTC_min",
                    "geometry": {"LATITUDE": ("latitude_min", "latitude_max"), "LONGITUDE": ("longitude_min", "longitude_max"),
                                 "LST": ("local_time_min", "local_time_max"), "LS": ("solar_longitude_min", "solar_longitude_max")},
                    "keep": ("altitude", "pressure", "err_pressure", "temperature", "err_temperature",
                             "total_density", "err_total_density")},
        rules=((r"^soir_co2", "Mesosphere and thermosphere profile at the terminator (T, p, n)", "profile"),),
        profile_columns={"altitude": "altitude", "temperature": "temperature", "temperature_sigma": "err_temperature",
                         "pressure": "pressure", "pressure_sigma": "err_pressure", "number_density": "total_density",
                         "number_density_sigma": "err_total_density",
                         "latitude": "LATITUDE", "longitude": "LONGITUDE", "lst": "LST"},
        column_units={"altitude": "KM", "pressure": "MBAR", "err_pressure": "MBAR", "temperature": "K",
                      "err_temperature": "K", "total_density": "1/CM**3"},
        altitude_reference="the Venus surface at the tangent point, as given by the SOIR team",
        citation=("Mahieux, A., et al. (2015). Update of the Venus density and temperature profiles at high altitude measured "
                  "by SOIR on board Venus Express. PSS, 113-114, 309-320. Data: BIRA-IASB, doi:10.18758/71021089 (CC-BY-4.0)."),
        doi="10.18758/71021089",
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
        citation="Karatekin, O., Banfield, D., & Ashley, J. (2020). InSight EDL atmospheric reconstruction. NASA PDS.",
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
        citation=("Tolson, R. H., Keating, G. M., Bougher, S. W., Brown, S. P., & Murphy, J. M. (2010). "
                  "MRO-M-ACCEL-5-PROFILE-V1.0, NASA Planetary Data System; Tolson, R. H., et al. (2008). "
                  "Atmospheric modeling using accelerometer data during Mars Reconnaissance Orbiter aerobraking "
                  "operations. J. Spacecraft Rockets, 45(3), 511-518."),
        doi="10.2514/1.34301",
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
        # Temperature products give three retrievals (upper boundary 150, 200, 250 K); the
        # 200 K one is used, as in Withers et al. (2020a), and half the 150-250 K spread is
        # its uncertainty.  Altitudes are R - 6051.8 km throughout.
        profile_columns={"radius": ("R20016", "R15"), "altitude": "Z", "temperature": ("T20016", "TEMP"),
                         "pressure": ("P20016", "PRESS"), "electron_density": "EDEN15",
                         "latitude": ("LAT16_SPICE", "LAT15_SPICE", "LAT_SPICE"),
                         "longitude": ("LON16_SPICE", "LON15_SPICE", "LON_SPICE"),
                         "sza": ("SZA16_SPICE", "SZA15_SPICE", "SZA_SPICE"),
                         "lst": ("LST16_SPICE", "LST15_SPICE", "LST_SPICE")},
        sigma_from_bracket={"temperature_k": ("T15016", "T25016"), "pressure_hpa": ("P15016", "P25016")},
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
        times_earth_received=True,
        citation=MEX_CITATION,
        # e.g. M65RSR0L04_AIX_041601543_60.LBL -> 2004 day 160 15:43
        time_from_name=r"_(?P<yy>\d{2})(?P<doy>\d{3})(?P<hh>\d{2})(?P<mm>\d{2})_\d+\.",
    ),
    Dataset(
        id="vco-v-rs-5-occ-v1.0", mission_id="akatsuki", instrument="RS (Radio Science)", level="L3/L4",
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
        citation=AKATSUKI_CITATION,
    ),
    Dataset(
        id="vco-v-rs-3-occ-v1.0", mission_id="akatsuki", instrument="RS (Radio Science)", level="L2",
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
    "vex-soir-co2-temperature": ("mahieux2015", "bira2020soir", "svedhem2007"),
    "mgn-v-rss-5-occ-prof-rtpd-v1.0": ("jenkins1994", "steffes1994", "saunders1992"),
    "mgn-v-rss-5-occ-prof-abs-h2so4-v1.0": ("jenkins1994", "steffes1994", "saunders1992"),
    "mgn-v-rss-1-rocc-v2.0": ("jenkins1994", "saunders1992"),
    "gp-j-entry-v1.0": ("seiff1998", "johnson1992"),
    "hp-ssa-hasi-2-3-4-mission-v1.1": ("fulchignoni2005", "fulchignoni2002", "matson2002"),
    "mgs-m-rss-5-sdp-v1.0": ("tyler2001", "hinson1999", "albee2001"),
    "mro-m-rss-5-tps-v1.0": ("hinson2008", "hinson1999", "zurek2007"),
    "mer-m-imu-5-edl-derived-v1.0": ("withers2006",),
    "vega1-vega2-v-2-3-venus-v1.0": ("lorenz2018",),
    "phx-m-ase-5-edl-rdr-v1.0": ("withers2010",),
    "msl-edl-atmosphere": ("holsteinrathlou2016", "holsteinrathlou2015data"),
    "insight-edl-atmosphere": ("karatekin2020data",),
    "ody-m-accel-5-derived-v1.0": ("tolson2005",),
    "mro-m-accel-5-profile-v1.0": ("tolson2008",),
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
for _i, _d in enumerate(DATASETS):
    if _d.id in _REFS and not _d.refs:
        import dataclasses as _dc
        DATASETS[_i] = _dc.replace(_d, refs=_REFS[_d.id])


def get_dataset(dataset_id: str) -> Optional[Dataset]:
    dataset_id = dataset_id.lower()
    return next((d for d in DATASETS if d.id == dataset_id), None)


def datasets_for(mission_id: Optional[str] = None, body_id: Optional[str] = None) -> List[Dataset]:
    return [d for d in DATASETS
            if (not mission_id or d.mission_id == mission_id.lower())
            and (not body_id or body_id.lower() in d.body_ids)]
