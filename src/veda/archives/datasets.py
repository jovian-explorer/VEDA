"""Archive datasets VEDA can search.

Each entry points at a real, publicly served PDS3 data set: a directory of
volumes, each with an index/index.tab.  Every URL here was checked against the
archive; add new entries the same way (open the URL, confirm the volumes and
the index exist) rather than guessing paths.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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
    index_path: str = "index/index.tab"
    rules: Tuple[Rule, ...] = ()
    # Column names in the product label for loadable profiles (match_column
    # handles variants such as "TEMPERATURE (MEDIUM ...)").
    profile_columns: Dict[str, str] = field(default_factory=dict)
    citation: str = ""
    doi: str = ""
    login_url: Optional[str] = None   # portal needing an account

    def classify(self, file_name: str) -> Tuple[str, str]:
        name = file_name.lower()
        for rx, label, kind in self.rules:
            if re.search(rx, name):
                return label, kind
        return "Product", "other"

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

DATASETS: List[Dataset] = [
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
