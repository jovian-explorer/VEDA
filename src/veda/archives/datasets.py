"""Archive datasets VEDA can search.

Each entry points at a real, publicly served PDS3 data set: a directory of
volumes, each with an index/index.tab.  Every URL here was checked against the
archive; add new entries the same way (open the URL, confirm the volumes and
the index exist) rather than guessing paths.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

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
    "lst": "LOCAL SOLAR TIME",
    "et": "EPHEMERIS SECONDS",
}

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

DATASETS: List[Dataset] = [
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
        id="mex-m-mrs-5-occ", mission_id="mex", instrument="MaRS (Radio Science)", level="L4",
        title="Mars Express radio occultation: neutral atmosphere and ionosphere profiles (L4)",
        body_ids=("mars",), archive="ESA PSA",
        base_url="https://archives.esac.esa.int/psa/ftp/MARS-EXPRESS/MRS/",
        # The V1.0 and V2.0 copies of 9101 overlap; the catalogue keys products by id, so
        # the later volume's rows replace the earlier ones.
        volume_pattern=r"^MEX-M-MRS-5-OCC-\d{4}-V\d\.\d$",
        rules=(
            (r"l04_a(\w{2})_", "L4 neutral atmosphere profile", "profile"),
            (r"l04_i(\w{2})_", "L4 ionosphere electron density profile", "profile"),
        ),
        profile_columns=RS_PROFILE_COLUMNS,
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


def get_dataset(dataset_id: str) -> Optional[Dataset]:
    dataset_id = dataset_id.lower()
    return next((d for d in DATASETS if d.id == dataset_id), None)


def datasets_for(mission_id: Optional[str] = None, body_id: Optional[str] = None) -> List[Dataset]:
    return [d for d in DATASETS
            if (not mission_id or d.mission_id == mission_id.lower())
            and (not body_id or body_id.lower() in d.body_ids)]
