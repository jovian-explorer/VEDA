"""Planetary Body and Mission Registry for VEDA.

Maintains authoritative physical constants, atmospheric properties, and
spacecraft mission definitions across NASA, ESA, JAXA, and NOAA planetary programs.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from .models import BodyInfo, InstrumentInfo, MissionInfo


# ===========================================================================
# PLANETARY BODIES & CELESTIAL TARGETS
# ===========================================================================

BODIES: Dict[str, BodyInfo] = {
    "venus": BodyInfo(
        id="venus",
        name="Venus",
        category="terrestrial_planet",
        radius_km=6051.8,
        surface_gravity=8.87,
        mean_molecular_weight=43.45,  # 96.5% CO2, 3.5% N2
        gas_constant_r=191.4,         # J / (kg K)
        isobaric_heat_capacity_cp=850.0,
        reference_pressure_hpa=92000.0,  # ~92 bar surface pressure
        atmospheric_composition={"CO2": 96.5, "N2": 3.5, "SO2": 0.015},
        description="Terrestrial planet enveloped in an opaque, superrotating carbon dioxide atmosphere with dense global sulphuric acid cloud decks (48 to 70 km altitude), extreme surface pressure (~92 bar), and intense greenhouse heating (~737 K surface temperature). Venus exhibits complex atmospheric wave phenomena, including planetary-scale Kelvin and Rossby waves, and strong thermal tides.",
        supported_missions=["akatsuki", "vex", "magellan", "pvo", "bepicolombo"],
        mission_page_url="https://science.nasa.gov/venus/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Venus/venus.html",
    ),
    "mars": BodyInfo(
        id="mars",
        name="Mars",
        category="terrestrial_planet",
        radius_km=3389.5,
        surface_gravity=3.72,
        mean_molecular_weight=43.34,  # 95% CO2, 2.6% N2, 1.9% Ar
        gas_constant_r=191.8,
        isobaric_heat_capacity_cp=830.0,
        reference_pressure_hpa=6.1,  # ~6.1 hPa (610 Pa) surface pressure
        atmospheric_composition={"CO2": 95.32, "N2": 2.6, "Ar": 1.9, "O2": 0.13},
        description="Terrestrial planet with a rarefied, highly dynamic carbon dioxide atmosphere (~6.1 hPa surface pressure) characterized by planetary dust storm cycles, polar CO2 and water-ice caps, diurnal thermal tides, and photochemical atmospheric loss driven by solar wind interaction with localized crustal remnant magnetic fields.",
        supported_missions=["mex", "maven", "mro", "mom"],
        mission_page_url="https://science.nasa.gov/mars/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Mars/mars.html",
    ),
    "jupiter": BodyInfo(
        id="jupiter",
        name="Jupiter",
        category="gas_giant",
        radius_km=69911.0,
        surface_gravity=24.79,
        mean_molecular_weight=2.22,  # 89% H2, 10% He
        gas_constant_r=3745.0,
        isobaric_heat_capacity_cp=12360.0,
        reference_pressure_hpa=1000.0,  # 1 bar reference level
        atmospheric_composition={"H2": 89.8, "He": 10.2, "CH4": 0.3},
        description="Largest gas giant in the Solar System, possessing a deep hydrogen-helium atmosphere with ammonia ice clouds, energetic lightning discharges, alternating counter-rotating zonal jet streams, persistent anticyclonic storms including the Great Red Spot, and an intense planetary magnetosphere.",
        supported_missions=["juno", "galileo", "cassini", "new_horizons"],
        mission_page_url="https://science.nasa.gov/jupiter/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Jupiter/jupiter.html",
    ),
    "saturn": BodyInfo(
        id="saturn",
        name="Saturn",
        category="gas_giant",
        radius_km=58232.0,
        surface_gravity=10.44,
        mean_molecular_weight=2.07,  # 96% H2, 3% He
        gas_constant_r=4016.0,
        isobaric_heat_capacity_cp=14000.0,
        reference_pressure_hpa=1000.0,  # 1 bar reference level
        atmospheric_composition={"H2": 96.3, "He": 3.25, "CH4": 0.45},
        description="Ringed gas giant with a hydrogen-dominated atmosphere exhibiting powerful equatorial jet streams exceeding 400 m/s, an enduring hexagonal polar jet stream pattern at the north pole, seasonal great storms, and intricate electrodynamic interactions with its massive ring system.",
        supported_missions=["cassini"],
        mission_page_url="https://science.nasa.gov/saturn/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Saturn/saturn.html",
    ),
    "titan": BodyInfo(
        id="titan",
        name="Titan",
        category="moon",
        radius_km=2574.7,
        surface_gravity=1.352,
        mean_molecular_weight=28.6,  # 95% N2, 5% CH4
        gas_constant_r=290.7,
        isobaric_heat_capacity_cp=1040.0,
        reference_pressure_hpa=1467.0,  # 1.47 bar surface pressure
        atmospheric_composition={"N2": 95.0, "CH4": 4.9, "H2": 0.1},
        description="Largest moon of Saturn, the only natural satellite with a dense atmosphere (surface pressure ~1.47 bar). Dominated by nitrogen and methane, Titan features multi-layered organic photochemical tholin hazes, active methane-ethane meteorological precipitation, and liquid hydrocarbon lakes and seas across polar regions.",
        supported_missions=["cassini"],
        mission_page_url="https://science.nasa.gov/saturn/moons/titan/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Titan/titan.html",
    ),
    "pluto": BodyInfo(
        id="pluto",
        name="Pluto",
        category="dwarf_planet",
        radius_km=1188.3,
        surface_gravity=0.62,
        mean_molecular_weight=28.01,  # >99% N2
        gas_constant_r=296.8,
        isobaric_heat_capacity_cp=1039.0,
        reference_pressure_hpa=0.0115,  # ~1.15 Pa (11.5 microbar) surface pressure
        atmospheric_composition={"N2": 99.0, "CH4": 0.5, "CO": 0.1},
        description="Kuiper Belt dwarf planet possessing a tenuous nitrogen atmosphere with methane and carbon monoxide, organized blue photochemical haze layers, active convective nitrogen-ice glaciers (Sputnik Planitia), and significant seasonal atmospheric sublimation and condensation cycles.",
        supported_missions=["new_horizons"],
        mission_page_url="https://science.nasa.gov/dwarf-planets/pluto/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Horizons/rex.html",
    ),
    "mercury": BodyInfo(
        id="mercury",
        name="Mercury",
        category="terrestrial_planet",
        radius_km=2439.7,
        surface_gravity=3.7,
        mean_molecular_weight=20.0,
        gas_constant_r=415.7,
        isobaric_heat_capacity_cp=1000.0,
        reference_pressure_hpa=1e-12,
        atmospheric_composition={"O": 42.0, "Na": 29.0, "H": 22.0, "He": 6.0},
        description="Innermost terrestrial planet possessing a dynamic surface-boundary exosphere composed primarily of O, Na, H, and He generated through solar wind sputtering, photon-stimulated desorption, and micrometeoroid impact vaporization, coupled with an offset dipolar intrinsic magnetic field.",
        supported_missions=["messenger", "bepicolombo"],
        mission_page_url="https://science.nasa.gov/mercury/",
        data_page_url="https://pds-geosciences.wustl.edu/missions/messenger/",
    ),
    "moon": BodyInfo(
        id="moon",
        name="Moon",
        category="moon",
        radius_km=1737.4,
        surface_gravity=1.62,
        mean_molecular_weight=20.0,
        gas_constant_r=415.7,
        isobaric_heat_capacity_cp=1000.0,
        reference_pressure_hpa=1e-11,
        atmospheric_composition={"He": 40.0, "Ne": 40.0, "Ar": 20.0},
        description="Earth's natural planetary satellite hosting an ultra-tenuous surface-boundary exosphere and localized dayside photo-electron sheaths, with permanently shadowed polar craters harboring substantial volatile water ice deposits and heavily cratered highland crust.",
        supported_missions=["lro", "chandrayaan2"],
        mission_page_url="https://science.nasa.gov/moon/",
        data_page_url="https://pds-geosciences.wustl.edu/missions/lro/",
    ),
    "ceres": BodyInfo(
        id="ceres",
        name="Ceres",
        category="dwarf_planet",
        radius_km=469.7,
        surface_gravity=0.28,
        mean_molecular_weight=18.0,
        gas_constant_r=461.5,
        isobaric_heat_capacity_cp=1850.0,
        reference_pressure_hpa=1e-10,
        atmospheric_composition={"H2O": 99.0},
        description="Largest body in the main asteroid belt, a water-rich dwarf planet featuring a hydrated silicate core, ice-rich outer shell, sodium carbonate salt deposits (faculae in Occator Crater), and transient water vapor outgassing observed during solar proton events.",
        supported_missions=["dawn"],
        mission_page_url="https://science.nasa.gov/dwarf-planets/ceres/",
        data_page_url="https://pds-smallbodies.astro.umd.edu/data_sb/missions/dawn/index.shtml",
    ),
    "vesta": BodyInfo(
        id="vesta",
        name="Vesta",
        category="asteroid",
        radius_km=262.7,
        surface_gravity=0.25,
        mean_molecular_weight=20.0,
        gas_constant_r=415.7,
        isobaric_heat_capacity_cp=1000.0,
        reference_pressure_hpa=0.0,
        atmospheric_composition={},
        description="Second-most massive body in the asteroid belt, a differentiated basaltic protoplanet with an intact iron-nickel core, ultramafic mantle, and basaltic crust gouged by the gigantic south-polar Rheasilvia impact basin.",
        supported_missions=["dawn"],
        mission_page_url="https://science.nasa.gov/mission/dawn/",
        data_page_url="https://pds-smallbodies.astro.umd.edu/data_sb/missions/dawn/index.shtml",
    ),
    "comet_67p": BodyInfo(
        id="comet_67p",
        name="Comet 67P/C-G",
        category="comet",
        radius_km=2.0,
        surface_gravity=0.0001,
        mean_molecular_weight=18.0,
        gas_constant_r=461.5,
        isobaric_heat_capacity_cp=1850.0,
        reference_pressure_hpa=1e-8,
        atmospheric_composition={"H2O": 70.0, "CO": 15.0, "CO2": 10.0},
        description="Bi-lobed Jupiter-family comet characterized by active volatile sublimation jets (H2O, CO, CO2), macromolecular refractory organic solids, diurnal water-ice frost cycles, and complex coma plasma boundary interactions explored in-situ by the Rosetta orbiter.",
        supported_missions=["rosetta"],
        mission_page_url="https://www.esa.int/Enabling_Support/Operations/Rosetta",
        data_page_url="https://psa.esa.int/psa/#/pages/search?mission=Rosetta",
    ),
}


# ===========================================================================
# SPACECRAFT MISSIONS
# ===========================================================================

MISSIONS: Dict[str, MissionInfo] = {
    "akatsuki": MissionInfo(
        id="akatsuki",
        name="Akatsuki (VCO)",
        agency="JAXA / ISAS",
        launch_date="2010-05-20",
        mission_status="completed",
        primary_targets=["venus"],
        mission_type="orbiter",
        target_encounters={"venus": "orbiter"},
        instruments=[
            InstrumentInfo(id="RS", name="Radio Science Experiment", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere"],
                           description="X-band radio occultation sounding Venus vertical temperature, pressure, refractivity, and static stability."),
            InstrumentInfo(id="UVI", name="Ultraviolet Imager", instrument_type="camera",
                           measurement_targets=["cloud_tops", "SO2"],
                           description="283 nm and 365 nm imaging tracking cloud-top wind vectors and SO2 distributions."),
            InstrumentInfo(id="LIR", name="Longwave Infrared Camera", instrument_type="camera",
                           measurement_targets=["cloud_tops", "thermal"],
                           description="10 micron uncooled microbolometer camera imaging cloud-top temperatures on day and night sides."),
            InstrumentInfo(id="IR1", name="1-Micron Camera", instrument_type="camera",
                           measurement_targets=["surface", "lower_clouds"],
                           description="Near-infrared camera imaging surface thermal emission and lower cloud dynamics."),
            InstrumentInfo(id="IR2", name="2-Micron Camera", instrument_type="camera",
                           measurement_targets=["middle_lower_clouds", "CO"],
                           description="Multi-band camera probing middle and lower clouds and carbon monoxide abundance."),
        ],
        authoritative_archive="JAXA DARTS / NASA PDS Atmospheres Node",
        archive_url="https://data.darts.isas.jaxa.jp/pub/pds3/",
        mission_page_url="https://www.isas.jaxa.jp/en/missions/spacecraft/current/akatsuki.html",
        data_page_url="https://data.darts.isas.jaxa.jp/pub/pds3/",
        citation="Imamura, T., et al. (2017). Initial performance of the radio occultation experiment aboard Akatsuki. Earth, Planets and Space, 69(1), 137.",
        description="JAXA Venus Climate Orbiter (Planet-C) dedicated to investigating the meteorological dynamics and super-rotation of Venus' atmosphere using multi-band imaging cameras (UV, 1-micron, 2-micron, Longwave IR) and ultra-stable X-band radio science occultation soundings.",
    ),
    "new_horizons": MissionInfo(
        id="new_horizons",
        name="New Horizons",
        agency="NASA / SwRI / JHUAPL",
        launch_date="2006-01-19",
        mission_status="operational",
        primary_targets=["pluto", "jupiter"],
        mission_type="flyby",
        target_encounters={"jupiter": "gravity_assist_flyby", "pluto": "flyby", "arrokoth": "flyby"},
        instruments=[
            InstrumentInfo(id="REX", name="Radio Science Experiment", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "surface_pressure"],
                           description="Uplink radio occultation measuring Pluto's surface pressure, temperature profile, and ionosphere."),
            InstrumentInfo(id="LORRI", name="Long Range Reconnaissance Imager", instrument_type="camera",
                           measurement_targets=["surface", "haze"],
                           description="Panchromatic high-resolution visible telescope imaging Pluto, Charon, Arrokoth, and Kuiper belt objects."),
            InstrumentInfo(id="MVIC", name="Multispectral Visible Imaging Camera (Ralph)", instrument_type="camera",
                           measurement_targets=["surface", "color"],
                           description="4-color and panchromatic imaging camera mapping composition and color."),
            InstrumentInfo(id="SWAP", name="Solar Wind Around Pluto", instrument_type="plasma",
                           measurement_targets=["solar_wind", "plasma"],
                           description="Solar wind analyzer measuring interaction with Pluto's escaping atmosphere."),
            InstrumentInfo(id="PEPSSI", name="Pluto Energetic Particle Spectrometer Science Investigation", instrument_type="plasma",
                           measurement_targets=["energetic_particles"],
                           description="Measures energetic ions and electrons across the outer solar system."),
            InstrumentInfo(id="SDC", name="Venetia Burney Student Dust Counter", instrument_type="dust_counter",
                           measurement_targets=["interplanetary_dust"],
                           description="Measures mass and distribution of dust grains from 1 AU beyond 55 AU."),
        ],
        authoritative_archive="NASA PDS Atmospheres / Small Bodies / Ring-Moon Systems",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Horizons/rex.html",
        mission_page_url="https://science.nasa.gov/mission/new-horizons/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Horizons/rex.html",
        citation="Stern, S. A., et al. (2015). The Pluto system: Initial results from its exploration by New Horizons. Science, 350(6258).",
        description="NASA New Frontiers mission that conducted the historic first flyby exploration of the Pluto-Charon system in July 2015 and Kuiper Belt object 486958 Arrokoth in January 2019, providing uplink radio occultations (REX) of Pluto's atmosphere and high-resolution LORRI imaging.",
    ),
    "juno": MissionInfo(
        id="juno",
        name="Juno",
        agency="NASA / JPL",
        launch_date="2011-08-05",
        mission_status="operational",
        primary_targets=["jupiter"],
        mission_type="orbiter",
        target_encounters={"jupiter": "orbiter"},
        instruments=[
            InstrumentInfo(id="GRAVITY_RO", name="Gravity & Radio Science", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "gravity"],
                           description="Radio occultation and Doppler gravity sounding of Jupiter's deep atmosphere and core."),
            InstrumentInfo(id="MWR", name="Microwave Radiometer", instrument_type="spectrometer",
                           measurement_targets=["deep_atmosphere", "ammonia", "water"],
                           description="6-channel radiometer sounding from 1 bar down to >100 bars pressure."),
            InstrumentInfo(id="JIRAM", name="Jovian InfraRed Auroral Mapper", instrument_type="camera",
                           measurement_targets=["aurora", "hotspots"],
                           description="Infrared imager and spectrometer probing upper troposphere and auroral emissions."),
            InstrumentInfo(id="JunoCam", name="JunoCam Visible Imager", instrument_type="camera",
                           measurement_targets=["cloud_tops"],
                           description="Wide-angle color camera providing high-resolution views of polar cyclones and atmospheric bands."),
        ],
        authoritative_archive="NASA PDS Atmospheres Node",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/JUNO/juno.html",
        mission_page_url="https://science.nasa.gov/mission/juno/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/JUNO/juno.html",
        citation="Bolton, S. J., et al. (2017). Jupiter's interior and deep atmosphere: The initial results from the Juno mission. Science, 356(6340), 821-825.",
        description="NASA New Frontiers polar-orbiting spacecraft at Jupiter, investigating the planet's deep atmospheric composition, ammonia distribution down to 100 bars with Microwave Radiometer (MWR), internal gravitational harmonics, dynamos, and polar auroral structures.",
    ),
    "cassini": MissionInfo(
        id="cassini",
        name="Cassini-Huygens",
        agency="NASA / ESA / ASI",
        launch_date="1997-10-15",
        mission_status="completed",
        primary_targets=["saturn", "titan", "jupiter"],
        mission_type="orbiter",
        target_encounters={"jupiter": "gravity_assist_flyby", "saturn": "orbiter", "titan": "multiple_flybys"},
        instruments=[
            InstrumentInfo(id="RSS", name="Radio Science Subsystem", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "rings", "ionosphere"],
                           description="S-, X-, and Ka-band occultation soundings of Saturn's and Titan's vertical atmospheres and ring particle sizes."),
            InstrumentInfo(id="CIRS", name="Composite Infrared Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["thermal_structure", "composition"],
                           description="Thermal infrared spectrometer measuring vertical temperature profiles and trace gas abundances."),
            InstrumentInfo(id="ISS", name="Imaging Science Subsystem", instrument_type="camera",
                           measurement_targets=["surface", "clouds", "rings"],
                           description="Narrow and wide-angle cameras capturing multi-spectral images of Saturn, Titan, and icy moons."),
            InstrumentInfo(id="UVIS", name="Ultraviolet Imaging Spectrograph", instrument_type="spectrometer",
                           measurement_targets=["aurora", "haze"],
                           description="Probing atmospheric structure, auroras, and ring occultations in the far/extreme UV."),
        ],
        authoritative_archive="NASA PDS Atmospheres / Ring-Moon Systems",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Cassini/cassini.html",
        mission_page_url="https://science.nasa.gov/mission/cassini/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Cassini/cassini.html",
        citation="Matson, D. L., et al. (2002). Cassini/Huygens flyby of Jupiter. Science, 296(5571), 1281-1282.",
        description="Flagship NASA/ESA/ASI mission to the Saturnian system (1997 to 2017), completing 294 orbits and numerous targeted flybys of Titan. Obtained multi-frequency radio science occultations of Saturn and Titan, mapped Titan's surface with radar, and carried out CIRS thermal infrared atmospheric sounding.",
    ),
    "vex": MissionInfo(
        id="vex",
        name="Venus Express (VEX)",
        agency="ESA",
        launch_date="2005-11-09",
        mission_status="completed",
        primary_targets=["venus"],
        mission_type="orbiter",
        target_encounters={"venus": "orbiter"},
        instruments=[
            InstrumentInfo(id="VeRa", name="Venus Radio Science Experiment", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "ionosphere"],
                           description="Dual-frequency radio sounding of Venus vertical temperature from 40 to 90 km and day/night ionosphere."),
            InstrumentInfo(id="VMC", name="Venus Monitoring Camera", instrument_type="camera",
                           measurement_targets=["clouds", "airglow"],
                           description="Wide-angle camera imaging cloud dynamics in UV, visible, and near-IR."),
            InstrumentInfo(id="VIRTIS", name="Visible and Infrared Thermal Imaging Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["surface_thermal", "cloud_composition"],
                           description="Spectrometer sounding lower atmosphere temperature through infrared atmospheric windows."),
        ],
        authoritative_archive="ESA Planetary Science Archive (PSA) / NASA PDS",
        archive_url="https://archives.esac.esa.int/psa/#!TableView/VEX=mission",
        mission_page_url="https://www.esa.int/Science_Exploration/Space_Science/Venus_Express",
        data_page_url="https://archives.esac.esa.int/psa/#!TableView/VEX=mission",
        citation="Tellmann, S., et al. (2009). The structure of Venus' middle atmosphere: Results from the Venus Express Radio Science experiment. JGR, 114.",
        description="ESA's dedicated Venus orbiter operational from 2006 to 2014, obtaining hundreds of high-vertical-resolution VeRa radio occultation temperature and pressure profiles from 40 to 90 km altitude, while monitoring SO2 chemistry and polar vortex dynamics.",
    ),
    "mex": MissionInfo(
        id="mex",
        name="Mars Express (MEX)",
        agency="ESA",
        launch_date="2003-06-02",
        mission_status="operational",
        primary_targets=["mars"],
        mission_type="orbiter",
        target_encounters={"mars": "orbiter"},
        instruments=[
            InstrumentInfo(id="MaRS", name="Mars Radio Science Experiment", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "ionosphere"],
                           description="Radio occultations of the neutral atmosphere (temperature, pressure, number density) and the ionosphere (electron density)."),
            InstrumentInfo(id="SPICAM", name="Spectroscopy for the Investigation of the Characteristics of the Atmosphere of Mars", instrument_type="spectrometer",
                           measurement_targets=["neutral_atmosphere", "ozone", "aerosols"],
                           description="UV and IR spectrometer for stellar and solar occultations and nadir sounding."),
            InstrumentInfo(id="PFS", name="Planetary Fourier Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["neutral_atmosphere"],
                           description="Infrared spectrometer retrieving atmospheric temperature profiles and composition."),
        ],
        authoritative_archive="ESA Planetary Science Archive (PSA)",
        archive_url="https://archives.esac.esa.int/psa/ftp/MARS-EXPRESS/",
        mission_page_url="https://www.esa.int/Science_Exploration/Space_Science/Mars_Express",
        data_page_url="https://archives.esac.esa.int/psa/ftp/MARS-EXPRESS/MRS/",
        citation="Paetzold, M., et al. (2016). Mars Express 10 years at Mars: Observations by the Mars Express Radio Science Experiment (MaRS). PSS, 127, 44-90.",
        description="ESA's Mars orbiter, in operation since 2003. MaRS radio occultations sound the neutral atmosphere from the surface to about 50 km and the ionosphere up to several hundred kilometres.",
    ),
    "maven": MissionInfo(
        id="maven",
        name="MAVEN",
        agency="NASA / GSFC / LASP",
        launch_date="2013-11-18",
        mission_status="operational",
        primary_targets=["mars"],
        mission_type="orbiter",
        target_encounters={"mars": "orbiter"},
        instruments=[
            InstrumentInfo(id="IUVS", name="Imaging Ultraviolet Spectrograph", instrument_type="spectrometer",
                           measurement_targets=["upper_atmosphere", "corona", "aurora"],
                           description="Measures global vertical profiles of neutral gases (CO2, CO, O) and ions in Mars' thermosphere and corona."),
            InstrumentInfo(id="NGIMS", name="Neutral Gas and Ion Mass Spectrometer", instrument_type="mass_spectrometer",
                           measurement_targets=["upper_atmosphere_composition"],
                           description="In-situ mass spectrometry measuring vertical isotopic and composition profiles during deep dips down to 125 km."),
            InstrumentInfo(id="ROSE", name="Radio Occultation Science Experiment", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "ionosphere"],
                           description="Radio occultation soundings of Mars electron density profiles and neutral lower atmosphere."),
        ],
        authoritative_archive="NASA PDS Atmospheres Node",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/MAVEN/maven.html",
        mission_page_url="https://science.nasa.gov/mission/maven/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/MAVEN/maven.html",
        citation="Jakosky, B. M., et al. (2015). MAVEN observations of the response of Mars to an interplanetary coronal mass ejection. Science, 350(6261).",
        description="NASA Mars Atmosphere and Volatile EvolutioN spacecraft orbiting Mars since 2014, investigating the upper atmosphere, ionosphere, solar wind interactions, and mechanisms driving atmospheric volatile escape over geological history.",
    ),
    "bepicolombo": MissionInfo(
        id="bepicolombo",
        name="BepiColombo",
        agency="ESA / JAXA",
        launch_date="2018-10-20",
        mission_status="operational",
        primary_targets=["mercury", "venus"],
        mission_type="orbiter",
        target_encounters={"venus": "flyby", "mercury": "orbiter"},
        instruments=[
            InstrumentInfo(id="MORE", name="Mercury Orbiter Radio science Experiment", instrument_type="radio_science",
                           measurement_targets=["gravity", "occultation"],
                           description="High-precision radio science investigation during cruise flybys and Mercury orbit."),
            InstrumentInfo(id="MERTIS", name="Mercury Radiometer and Thermal Infrared Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["surface", "thermal"],
                           description="Thermal infrared imaging spectrometer active during Venus flybys and Mercury science operations."),
            InstrumentInfo(id="PHEBUS", name="Probing of Hermean Exosphere By Ultraviolet Spectroscopy", instrument_type="spectrometer",
                           measurement_targets=["exosphere"],
                           description="UV spectrometer observing exospheric composition and emissions."),
        ],
        authoritative_archive="ESA Planetary Science Archive (PSA)",
        archive_url="https://archives.esac.esa.int/psa/",
        mission_page_url="https://www.esa.int/Science_Exploration/Space_Science/BepiColombo",
        data_page_url="https://archives.esac.esa.int/psa/",
        citation="Benkhoff, J., et al. (2010). BepiColombo: Comprehensive exploration of Mercury: Mission overview and science goals. PSS, 58(1), 2-20.",
        description="Joint ESA and JAXA dual-spacecraft mission to Mercury, carrying the Mercury Planetary Orbiter (MPO) and Mercury Magnetospheric Orbiter (Mio). Conducted multiple gravity-assist flybys of Venus and Mercury with active radiometer (MERTIS) and radio science (MORE) observations.",
    ),
    "galileo": MissionInfo(
        id="galileo",
        name="Galileo",
        agency="NASA / JPL",
        launch_date="1989-10-18",
        mission_status="completed",
        primary_targets=["jupiter", "venus"],
        mission_type="orbiter",
        target_encounters={"venus": "flyby", "jupiter": "orbiter"},
        instruments=[
            InstrumentInfo(id="RSS", name="Radio Science", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "ionosphere"],
                           description="S/X-band radio occultation measurements of Jupiter and Galilean moon ionospheres and atmospheres."),
            InstrumentInfo(id="SSI", name="Solid State Imaging", instrument_type="camera",
                           measurement_targets=["clouds", "moons"],
                           description="First CCD camera to orbit an outer planet, capturing dynamic atmospheric features and volcanism on Io."),
        ],
        authoritative_archive="NASA PDS Atmospheres Node / Imaging Node",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/catalog.htm#Jupiter",
        mission_page_url="https://science.nasa.gov/mission/galileo/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/catalog.htm#Jupiter",
        citation="Kliore, A. J., et al. (1997). The ionosphere of Europa from Galileo radio occultations. Science, 277(5324), 355-358.",
        description="Historic NASA Jupiter orbiter (1989 to 2003) that deployed the Galileo atmospheric entry probe, measuring in-situ atmospheric composition down to 22 bars, and conducted extensive dual-frequency radio occultations of the Jovian atmosphere and Galilean satellites.",
    ),
    "messenger": MissionInfo(
        id="messenger",
        name="MESSENGER",
        agency="NASA / JHUAPL",
        launch_date="2004-08-03",
        mission_status="completed",
        primary_targets=["mercury", "venus"],
        mission_type="orbiter",
        target_encounters={"venus": "flyby", "mercury": "orbiter"},
        instruments=[
            InstrumentInfo(id="RS", name="Radio Science Investigation", instrument_type="radio_science",
                           measurement_targets=["gravity", "exosphere"],
                           description="Doppler tracking and radio occultations characterizing Mercury's mass distribution and neutral exosphere."),
            InstrumentInfo(id="MDIS", name="Mercury Dual Imaging System", instrument_type="camera",
                           measurement_targets=["surface", "geology"],
                           description="Wide-angle and narrow-angle multispectral cameras mapping 100% of Mercury's surface."),
            InstrumentInfo(id="MASCS", name="Mercury Atmospheric and Surface Composition Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["exosphere", "minerals"],
                           description="UV to near-IR spectrometer probing sodium, calcium, and magnesium exospheric emission tails."),
        ],
        authoritative_archive="NASA PDS Planetary Data System (Geosciences / PPI / Atmospheres)",
        archive_url="https://pds-geosciences.wustl.edu/missions/messenger/",
        mission_page_url="https://science.nasa.gov/mission/messenger/",
        data_page_url="https://pds-geosciences.wustl.edu/missions/messenger/",
        citation="Solomon, S. C., et al. (2007). Return to Mercury: A global perspective on MESSENGER's first flyby. Science, 321(5885), 59-62.",
        description="NASA Discovery mission (2004 to 2015) and first orbiter of Mercury, characterizing its surface geochemistry, offset magnetic field, dynamic exosphere, and polar water-ice deposits in permanently shadowed craters.",
    ),
    "magellan": MissionInfo(
        id="magellan",
        name="Magellan",
        agency="NASA / JPL",
        launch_date="1989-05-04",
        mission_status="completed",
        primary_targets=["venus"],
        mission_type="orbiter",
        target_encounters={"venus": "orbiter"},
        instruments=[
            InstrumentInfo(id="RADAR", name="Synthetic Aperture Radar & Altimeter", instrument_type="radar",
                           measurement_targets=["surface_topography"],
                           description="High-resolution S-band radar mapping 98% of Venus' cloud-shrouded surface at 100m resolution."),
            InstrumentInfo(id="GRS", name="Gravity & Radio Occultation Science", instrument_type="radio_science",
                           measurement_targets=["gravity_field", "neutral_atmosphere"],
                           description="X/S-band radio occultations of Venusian upper and middle atmospheric temperature and sulphuric acid vapor."),
        ],
        authoritative_archive="NASA PDS Magellan Node",
        archive_url="https://pds-geosciences.wustl.edu/missions/magellan/",
        mission_page_url="https://science.nasa.gov/mission/magellan/",
        data_page_url="https://pds-geosciences.wustl.edu/missions/magellan/",
        citation="Saunders, R. S., et al. (1992). Magellan: Mission summary. JGR: Planets, 97(E8), 13067-13090.",
        description="NASA Venus orbiter (1989 to 1994) that mapped 98% of the surface using Synthetic Aperture Radar (SAR) at 100-meter resolution, and performed high-precision dual-frequency radio occultation soundings of atmospheric temperature and sulphuric acid vapor abundance.",
    ),
    "pvo": MissionInfo(
        id="pvo",
        name="Pioneer Venus Orbiter (PVO)",
        agency="NASA / Ames",
        launch_date="1978-05-20",
        mission_status="completed",
        primary_targets=["venus"],
        mission_type="orbiter",
        target_encounters={"venus": "orbiter"},
        instruments=[
            InstrumentInfo(id="ORO", name="Orbiter Radio Occultation", instrument_type="radio_science",
                           measurement_targets=["neutral_atmosphere", "ionosphere"],
                           description="Seminal S/X-band radio occultations establishing the baseline thermal and ionospheric structure of Venus across solar cycles."),
            InstrumentInfo(id="ONMS", name="Orbiter Neutral Mass Spectrometer", instrument_type="mass_spectrometer",
                           measurement_targets=["thermosphere_composition"],
                           description="In-situ composition measurements in the Venusian upper atmosphere."),
        ],
        authoritative_archive="NASA PDS Atmospheres Node",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/PVO/pvo.html",
        mission_page_url="https://science.nasa.gov/mission/pioneer-venus-1/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/PVO/pvo.html",
        citation="Colin, L. (1980). Pioneer Venus program. JGR: Space Physics, 85(A13), 7575-7598.",
        description="NASA Pioneer Venus 1 orbiter that operated from 1978 to 1992 across a full 11-year solar cycle, compiling the foundational long-term dataset of Venusian upper atmosphere neutral density, ionospheric electron density, and radio occultation profiles.",
    ),
    "lro": MissionInfo(
        id="lro",
        name="Lunar Reconnaissance Orbiter (LRO)",
        agency="NASA / GSFC",
        launch_date="2009-06-18",
        mission_status="operational",
        primary_targets=["moon"],
        mission_type="orbiter",
        target_encounters={"moon": "orbiter"},
        instruments=[
            InstrumentInfo(id="LROC", name="Lunar Reconnaissance Orbiter Camera", instrument_type="camera",
                           measurement_targets=["surface", "craters"],
                           description="Narrow Angle (0.5m/pixel) and Wide Angle (100m/pixel) camera imaging lunar terrain and landing sites."),
            InstrumentInfo(id="Diviner", name="Diviner Lunar Radiometer Experiment", instrument_type="radiometer",
                           measurement_targets=["surface_thermal", "water_ice"],
                           description="9-channel infrared radiometer measuring day/night surface thermal emissions and mapping ultra-cold polar cold traps down to 20 K."),
            InstrumentInfo(id="LAMP", name="Lyman Alpha Mapping Project", instrument_type="spectrometer",
                           measurement_targets=["polar_ice", "exosphere"],
                           description="Far-UV imaging spectrograph mapping permanently shadowed regions using starlight and interplanetary Lyman-alpha."),
        ],
        authoritative_archive="NASA PDS Geosciences / Imaging Nodes",
        archive_url="https://pds-geosciences.wustl.edu/missions/lro/",
        mission_page_url="https://science.nasa.gov/mission/lro/",
        data_page_url="https://pds-geosciences.wustl.edu/missions/lro/",
        citation="Chin, G., et al. (2007). Lunar Reconnaissance Orbiter overview: The mission and its results. Space Sci Rev, 129(4), 391-419.",
        description="NASA Lunar Reconnaissance Orbiter mapping the Moon in polar orbit since 2009, measuring surface thermal temperatures with the Diviner radiometer down to 20 K in permanently shadowed regions, and acquiring sub-meter optical imaging with LROC.",
    ),
    "mro": MissionInfo(
        id="mro",
        name="Mars Reconnaissance Orbiter (MRO)",
        agency="NASA / JPL",
        launch_date="2005-08-12",
        mission_status="operational",
        primary_targets=["mars"],
        mission_type="orbiter",
        target_encounters={"mars": "orbiter"},
        instruments=[
            InstrumentInfo(id="MCS", name="Mars Climate Sounder", instrument_type="radiometer",
                           measurement_targets=["atmospheric_temperature", "dust", "water_ice"],
                           description="Limb-sounding infrared radiometer profiling Martian temperature, dust opacity, and ice clouds from 0 to 80 km."),
            InstrumentInfo(id="HiRISE", name="High Resolution Imaging Science Experiment", instrument_type="camera",
                           measurement_targets=["surface", "active_processes"],
                           description="0.3m/pixel visible camera observing recurring slope lineae, avalanches, and polar ice caps."),
            InstrumentInfo(id="CRISM", name="Compact Reconnaissance Imaging Spectrometer for Mars", instrument_type="spectrometer",
                           measurement_targets=["surface_mineralogy"],
                           description="Visible and infrared imaging spectrometer identifying hydrated clay minerals and sulfates."),
        ],
        authoritative_archive="NASA PDS Geosciences / Atmospheres Nodes",
        archive_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Mars/mro.html",
        mission_page_url="https://science.nasa.gov/mission/mars-reconnaissance-orbiter/",
        data_page_url="https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/Mars/mro.html",
        citation="Zurek, R. W., & Smrekar, S. E. (2007). An overview of the Mars Reconnaissance Orbiter (MRO) science investigation. JGR: Planets, 112(E5).",
        description="NASA Mars Reconnaissance Orbiter operating continuously in Mars orbit since 2006, acquiring daily global atmospheric temperature, dust, and water-ice soundings with the Mars Climate Sounder (MCS) alongside ultra-high-resolution HiRISE surface imaging.",
    ),
    "dawn": MissionInfo(
        id="dawn",
        name="Dawn",
        agency="NASA / JPL",
        launch_date="2007-09-27",
        mission_status="completed",
        primary_targets=["ceres", "vesta"],
        mission_type="orbiter",
        target_encounters={"mars": "gravity_assist_flyby", "vesta": "orbiter", "ceres": "orbiter"},
        instruments=[
            InstrumentInfo(id="FC", name="Framing Camera", instrument_type="camera",
                           measurement_targets=["surface_geology"],
                           description="Multispectral visible camera providing high-resolution stereoscopic terrain models of Vesta and Ceres."),
            InstrumentInfo(id="VIR", name="Visible and Infrared Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["mineralogy", "ice_salts"],
                           description="Mapping surface mineralogy, ammoniated phyllosilicates, and sodium carbonate salt deposits."),
            InstrumentInfo(id="GRaND", name="Gamma Ray and Neutron Detector", instrument_type="spectrometer",
                           measurement_targets=["subsurface_composition", "hydrogen"],
                           description="Measuring elemental abundances of H, Fe, and K in the top meter of regolith."),
        ],
        authoritative_archive="NASA PDS Small Bodies Node",
        archive_url="https://pds-smallbodies.astro.umd.edu/data_sb/missions/dawn/",
        mission_page_url="https://science.nasa.gov/mission/dawn/",
        data_page_url="https://pds-smallbodies.astro.umd.edu/data_sb/missions/dawn/",
        citation="Russell, C. T., & Raymond, C. A. (2011). The Dawn mission to Vesta and Ceres. Space Sci Rev, 163(1), 3-23.",
        description="NASA Discovery mission powered by solar electric ion propulsion, the first mission to orbit two extraterrestrial bodies: asteroid 4 Vesta (2011 to 2012) and dwarf planet 1 Ceres (2015 to 2018), mapping geology, mineralogy, and elemental composition.",
    ),
    "rosetta": MissionInfo(
        id="rosetta",
        name="Rosetta",
        agency="ESA",
        launch_date="2004-03-02",
        mission_status="completed",
        primary_targets=["comet_67p"],
        mission_type="orbiter",
        target_encounters={"mars": "flyby", "comet_67p": "orbiter"},
        instruments=[
            InstrumentInfo(id="OSIRIS", name="Optical, Spectroscopic, and Infrared Remote Imaging System", instrument_type="camera",
                           measurement_targets=["nucleus", "coma_jets"],
                           description="Narrow and wide-angle imaging system tracking comet 67P activity, jets, and surface evolution."),
            InstrumentInfo(id="MIRO", name="Microwave Instrument for the Rosetta Orbiter", instrument_type="spectrometer",
                           measurement_targets=["subsurface_temperature", "coma_volatiles"],
                           description="Microwave radiometer and spectrometer measuring water, CO, and methanol outgassing rates and subsurface temperatures."),
            InstrumentInfo(id="RSI", name="Radio Science Investigation", instrument_type="radio_science",
                           measurement_targets=["gravity", "nucleus_mass", "coma"],
                           description="Doppler tracking and radio occultations determining comet mass, porosity, and gas coma density."),
        ],
        authoritative_archive="ESA Planetary Science Archive (PSA)",
        archive_url="https://archives.esac.esa.int/psa/#!TableView/Rosetta=mission",
        mission_page_url="https://www.esa.int/Enabling_Support/Operations/Rosetta",
        data_page_url="https://archives.esac.esa.int/psa/#!TableView/Rosetta=mission",
        citation="Taylor, M. G., et al. (2017). The Rosetta mission orbital phase: Overview and science highlights. Phil. Trans. R. Soc. A, 375(2097).",
        description="ESA flagship mission to comet 67P/Churyumov-Gerasimenko (2004 to 2016), which rendezvoused with the comet, deployed the Philae lander, and escorted the comet through perihelion while measuring gas coma composition, sublimation rates, and plasma interactions.",
    ),
    "mom": MissionInfo(
        id="mom",
        name="Mars Orbiter Mission (MOM / Mangalyaan)",
        agency="ISRO",
        launch_date="2013-11-05",
        mission_status="completed",
        primary_targets=["mars"],
        mission_type="orbiter",
        target_encounters={"mars": "orbiter"},
        instruments=[
            InstrumentInfo(id="MENCA", name="Mars Exospheric Neutral Composition Analyser", instrument_type="mass_spectrometer",
                           measurement_targets=["neutral_exosphere", "noble_gases"],
                           description="Quadrupole mass spectrometer developed at Space Physics Laboratory (SPL), VSSC, measuring in-situ neutral composition, diurnal variations, and altitude distributions of Mars exosphere."),
            InstrumentInfo(id="MCC", name="Mars Colour Camera", instrument_type="camera",
                           measurement_targets=["surface", "dynamic_weather"],
                           description="Tri-colour visible camera imaging Mars surface morphology, dust storms, and atmospheric dynamic phenomena."),
            InstrumentInfo(id="LAP", name="Lyman Alpha Photometer", instrument_type="photometer",
                           measurement_targets=["deuterium_hydrogen_ratio", "water_escape"],
                           description="Measures atomic hydrogen and deuterium Lyman-alpha emissions to determine Mars atmospheric water loss."),
            InstrumentInfo(id="TIS", name="Thermal Infrared Imaging Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["surface_thermal", "temperature"],
                           description="Thermal IR sensor measuring surface temperature and thermal emission properties."),
            InstrumentInfo(id="MSM", name="Methane Sensor for Mars", instrument_type="sensor",
                           measurement_targets=["methane_column"],
                           description="Fabry-Perot etalon sensor measuring atmospheric methane column abundance in parts per billion."),
        ],
        authoritative_archive="ISRO ISSDC (Indian Space Science Data Centre)",
        archive_url="https://www.issdc.gov.in/",
        mission_page_url="https://www.isro.gov.in/MarsOrbiterMission.html",
        data_page_url="https://www.issdc.gov.in/",
        citation="Bhardwaj, A., et al. (2016). On the evening and morning exosphere of Mars: Results from MENCA on the Mars Orbiter Mission. Geophysical Research Letters, 43(6), 2388-2395.",
        description="India's first interplanetary mission by ISRO (2013 to 2022), entering Mars orbit on 24 September 2014. Carried five scientific payloads including the Space Physics Laboratory (SPL/VSSC) MENCA quadrupole mass spectrometer for in-situ exospheric neutral composition sounding.",
    ),
    "chandrayaan2": MissionInfo(
        id="chandrayaan2",
        name="Chandrayaan-2 Orbiter (CH2O)",
        agency="ISRO",
        launch_date="2019-07-22",
        mission_status="operational",
        primary_targets=["moon"],
        mission_type="orbiter",
        target_encounters={"moon": "orbiter"},
        instruments=[
            InstrumentInfo(id="CHACE-2", name="Chandra's Atmospheric Composition Explorer-2", instrument_type="mass_spectrometer",
                           measurement_targets=["lunar_exosphere", "argon_40"],
                           description="Quadrupole mass spectrometer developed at Space Physics Laboratory (SPL), VSSC, measuring lunar neutral exospheric composition and global argon-40 diurnal distribution."),
            InstrumentInfo(id="DFRS", name="Dual Frequency Radio Science Experiment", instrument_type="radio_science",
                           measurement_targets=["ionosphere", "electron_density"],
                           description="X- and S-band coherent radio science sounding lunar ionospheric electron density and neutral exospheric boundaries."),
            InstrumentInfo(id="OHRC", name="Orbiter High Resolution Camera", instrument_type="camera",
                           measurement_targets=["surface_morphology", "landing_hazards"],
                           description="Sub-meter resolution visible camera providing 0.25 m/pixel optical images of lunar craters and polar terrain."),
            InstrumentInfo(id="CLASS", name="Chandrayaan-2 Large Area Soft X-ray Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["surface_elemental_composition"],
                           description="X-ray fluorescence spectrometer mapping elemental abundances of Mg, Al, Si, Ca, and Fe."),
            InstrumentInfo(id="IIRS", name="Imaging Infrared Spectrometer", instrument_type="spectrometer",
                           measurement_targets=["mineralogy", "hydration_ice"],
                           description="Hyperspectral imaging spectrometer from 0.8 to 5.0 microns mapping lunar hydration and water-ice signatures."),
            InstrumentInfo(id="DFSAR", name="Dual Frequency Synthetic Aperture Radar", instrument_type="radar",
                           measurement_targets=["polar_ice", "subsurface_roughness"],
                           description="L- and S-band polarimetric radar sounding permanent polar shadow craters for subsurface water-ice."),
        ],
        authoritative_archive="ISRO ISSDC / PRADAN (Planetary Data Archive)",
        archive_url="https://pradan.issdc.gov.in/ch2/",
        mission_page_url="https://www.isro.gov.in/Chandrayaan2.html",
        data_page_url="https://pradan.issdc.gov.in/ch2/",
        citation="Bhardwaj, A., et al. (2022). Observation of argon-40 in the lunar exosphere by CHACE-2 on Chandrayaan-2 orbiter. Geophysical Research Letters, 49(5), e2021GL097059.",
        description="ISRO advanced lunar exploration orbiter operational since 2019 in a 100 km polar orbit. Payload suite includes the Space Physics Laboratory (SPL/VSSC) CHACE-2 mass spectrometer and Dual Frequency Radio Science (DFRS) ionospheric electron density sounding.",
    ),
}


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def get_body(body_id: str) -> Optional[BodyInfo]:
    """Retrieve planetary body metadata."""
    return BODIES.get(body_id.lower())


def get_mission(mission_id: str) -> Optional[MissionInfo]:
    """Retrieve mission metadata."""
    return MISSIONS.get(mission_id.lower())


def list_bodies() -> List[dict]:
    """List all supported planetary bodies."""
    return [
        {
            "id": b.id,
            "name": b.name,
            "category": b.category,
            "radius_km": b.radius_km,
            "surface_gravity": b.surface_gravity,
            "mean_molecular_weight": b.mean_molecular_weight,
            "gas_constant_r": b.gas_constant_r,
            "isobaric_heat_capacity_cp": b.isobaric_heat_capacity_cp,
            "reference_pressure_hpa": b.reference_pressure_hpa,
            "atmospheric_composition": b.atmospheric_composition,
            "description": b.description,
            "supported_missions": b.supported_missions,
            "mission_page_url": b.mission_page_url,
            "data_page_url": b.data_page_url,
        }
        for b in BODIES.values()
    ]


def list_missions() -> List[dict]:
    """List all supported spacecraft missions with accurate classification."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "agency": m.agency,
            "launch_date": m.launch_date,
            "mission_status": m.mission_status,
            "mission_type": m.mission_type,
            "primary_targets": m.primary_targets,
            "target_encounters": m.target_encounters,
            "authoritative_archive": m.authoritative_archive,
            "archive_url": m.archive_url,
            "mission_page_url": m.mission_page_url or m.archive_url,
            "data_page_url": m.data_page_url or m.archive_url,
            "citation": m.citation,
            "description": m.description,
            "instruments": [
                {
                    "id": i.id,
                    "name": i.name,
                    "type": i.instrument_type,
                    "targets": i.measurement_targets,
                    "description": i.description,
                }
                for i in m.instruments
            ],
        }
        for m in MISSIONS.values()
    ]


def get_missions_for_body(body_id: str) -> List[dict]:
    """Return all missions that observed a specific body with encounter classification."""
    body = get_body(body_id)
    if not body:
        return []
    res = []
    for mid in body.supported_missions:
        m = get_mission(mid)
        if m:
            encounter = m.target_encounters.get(body_id.lower(), m.mission_type)
            res.append({
                "id": m.id,
                "name": m.name,
                "agency": m.agency,
                "mission_type": m.mission_type,
                "encounter_type": encounter,
                "instruments": [i.name for i in m.instruments],
                "archive": m.authoritative_archive,
                "archive_url": m.archive_url,
                "mission_page_url": m.mission_page_url or m.archive_url,
                "data_page_url": m.data_page_url or m.archive_url,
                "description": m.description,
            })
    return res


# ===========================================================================
# PLANETARY FIELD & SCIENTIFIC VARIABLE REGISTRY
# ===========================================================================

FIELD_REGISTRY: Dict[str, dict] = {
    "temperature_k": {
        "id": "temperature_k",
        "label": "Temperature (Kelvin)",
        "units": "K",
        "category": "thermodynamic",
        "formula": r"T",
        "reference": "Fjeldbo, G., Kliore, A. J., & Eshleman, V. R. (1971), Astron. J., 76, 123-140",
        "doi": "10.1086/111096",
        "archive": "NASA PDS / ESA PSA / JAXA DARTS",
        "description": "Planetary atmospheric temperature derived from radio occultation refractivity via hydrostatic integration."
    },
    "temperature_c": {
        "id": "temperature_c",
        "label": "Temperature (Celsius)",
        "units": "°C",
        "category": "thermodynamic",
        "formula": r"T_C = T - 273.15",
        "reference": "BIPM International Temperature Scale (ITS-90)",
        "doi": "10.1086/111096",
        "archive": "NASA PDS / ESA PSA / JAXA DARTS",
        "description": "Atmospheric temperature converted to degrees Celsius."
    },
    "pressure_hpa": {
        "id": "pressure_hpa",
        "label": "Atmospheric Pressure",
        "units": "hPa",
        "category": "thermodynamic",
        "formula": r"P(z) = \int_z^\infty \rho(z') g(z')\,dz'",
        "reference": "Tellmann, S., et al. (2012), Icarus, 221(2), 471-480",
        "doi": "10.1016/j.icarus.2012.08.023",
        "archive": "ESA PSA / NASA PDS",
        "description": "Planetary atmospheric pressure profile obtained from hydrostatic equilibrium integration."
    },
    "refractivity": {
        "id": "refractivity",
        "label": "Radio Refractivity",
        "units": "N-units",
        "category": "radio_science",
        "formula": r"N(r) = (n(r) - 1) \times 10^6 = 10^6 \left( \exp\left[\frac{1}{\pi} \int_a^\infty \frac{\alpha(x)}{\sqrt{x^2 - a^2}} \, dx\right] - 1 \right)",
        "reference": "Fjeldbo, G., Kliore, A. J., & Eshleman, V. R. (1971), Astron. J., 76, 123-140",
        "doi": "10.1086/111096",
        "archive": "NASA PDS / ESA PSA / JAXA DARTS",
        "description": "Radio refractivity inverted from spacecraft Doppler bending angle via the Abel integral transform."
    },
    "electron_density_cm3": {
        "id": "electron_density_cm3",
        "label": "Electron Density",
        "units": "el/cm³",
        "category": "ionosphere",
        "formula": r"N_e(r) = -\frac{f^2}{40.3 \pi} \int_r^{r_{sc}} \frac{d\alpha_{iono}/da}{\sqrt{a^2 - r^2}}\,da",
        "reference": "Withers, P., et al. (2014), J. Geophys. Res. Space Physics, 119(9), 7720-7732",
        "doi": "10.1002/2014JA020182",
        "archive": "NASA PDS / ESA PSA / ISRO ISSDC",
        "description": "Planetary ionospheric electron density inverted from dual-frequency radio occultation excess phase."
    },
    "potential_temperature": {
        "id": "potential_temperature",
        "label": "Potential Temperature",
        "units": "K",
        "category": "derived_stability",
        "formula": r"\theta = T \left(\frac{P_{ref}}{P}\right)^\kappa, \quad \kappa = \frac{R_{spec}}{c_p}",
        "reference": "Holton, J. R., & Hakim, G. J. (2012), An Introduction to Dynamic Meteorology, Academic Press",
        "doi": "10.1016/C2009-0-63394-8",
        "archive": "Planetary Thermodynamic Formulation",
        "description": "Potential temperature evaluated with body-specific gas constant R and isobaric heat capacity Cp."
    },
    "lapse_rate": {
        "id": "lapse_rate",
        "label": "Environmental Lapse Rate",
        "units": "K/km",
        "category": "derived_stability",
        "formula": r"\Gamma = -\frac{dT}{dz}",
        "reference": "Salby, M. L. (1996), Fundamentals of Atmospheric Physics, Academic Press",
        "doi": "10.1016/S0074-6142(96)80005-7",
        "archive": "Planetary Thermodynamic Formulation",
        "description": "Negative vertical derivative of temperature with respect to geometric altitude."
    },
    "scale_height": {
        "id": "scale_height",
        "label": "Atmospheric Scale Height",
        "units": "km",
        "category": "derived_structure",
        "formula": r"H = \frac{R_{spec} T}{g(z)} = \frac{k_B T}{\mu m_u g(z)}",
        "reference": "Chamberlain, J. W., & Hunten, D. M. (1987), Theory of Planetary Atmospheres, Academic Press",
        "doi": "10.1016/B978-0-12-167252-2.50005-1",
        "archive": "Planetary Thermodynamic Formulation",
        "description": "Atmospheric pressure e-folding scale height incorporating altitude-dependent planetary gravity g(z)."
    },
    "density": {
        "id": "density",
        "label": "Atmospheric Mass Density",
        "units": "kg/m³",
        "category": "derived_structure",
        "formula": r"\rho = \frac{P}{R_{spec} T}",
        "reference": "Seiff, A., et al. (1980), J. Geophys. Res., 85(A13), 7903-7933",
        "doi": "10.1029/JA085iA13p07903",
        "archive": "Planetary Thermodynamic Formulation",
        "description": "Planetary atmospheric gas density evaluated using the ideal gas law with body-specific mean molecular weight."
    },
    "buoyancy_freq_sq": {
        "id": "buoyancy_freq_sq",
        "label": "Squared Buoyancy Frequency N²",
        "units": "s⁻²",
        "category": "derived_stability",
        "formula": r"N^2 = \frac{g(z)}{T} \left( \frac{dT}{dz} + \frac{g(z)}{c_p} \right) = \frac{g(z)}{\theta} \frac{d\theta}{dz}",
        "reference": "Tellmann, S., et al. (2012), Icarus, 221(2), 471-480",
        "doi": "10.1016/j.icarus.2012.08.023",
        "archive": "Planetary Thermodynamic Formulation",
        "description": "Brunt-Vaisala static stability frequency squared determining atmospheric convective stability on other worlds."
    },
    "t_prime": {
        "id": "t_prime",
        "label": "Temperature Perturbation T'",
        "units": "K",
        "category": "waves",
        "formula": r"T' = T - T_{background}",
        "reference": "Ando, H., et al. (2020), J. Geophys. Res. Planets, 125(6), e2019JE006208",
        "doi": "10.1029/2019JE006208",
        "archive": "Planetary Wave Analysis",
        "description": "Small-scale atmospheric gravity wave temperature perturbation extracted by high-pass polynomial filtering."
    },
    "wave_potential_energy": {
        "id": "wave_potential_energy",
        "label": "Gravity Wave Potential Energy Density",
        "units": "J/kg",
        "category": "waves",
        "formula": r"E_p = \frac{1}{2} \left(\frac{g}{N}\right)^2 \left(\frac{T'}{T_0}\right)^2",
        "reference": "Creasey, J. E., et al. (2006), Geophys. Res. Lett., 33(1), L01803",
        "doi": "10.1029/2005GL024037",
        "archive": "Planetary Wave Analysis",
        "description": "Specific gravity wave potential energy density quantifying wave activity in planetary atmospheres."
    },
    "speed_of_sound": {
        "id": "speed_of_sound",
        "label": "Acoustic Speed of Sound",
        "units": "m/s",
        "category": "acoustics",
        "formula": r"c_s = \sqrt{\gamma R_{spec} T}, \quad \gamma = \frac{c_p}{c_p - R_{spec}}",
        "reference": "Salby, M. L. (1996), Fundamentals of Atmospheric Physics, Academic Press",
        "doi": "10.1016/S0074-6142(96)80005-7",
        "archive": "Planetary Acoustic Formulation",
        "description": "Adiabatic speed of sound in planetary gas mixtures."
    },
    "buoyancy_period": {
        "id": "buoyancy_period",
        "label": "Brunt-Vaisala Buoyancy Period",
        "units": "min",
        "category": "derived_stability",
        "formula": r"\tau_B = \frac{2\pi}{N} \cdot \frac{1}{60}",
        "reference": "Gill, A. E. (1982), Atmosphere-Ocean Dynamics, Academic Press",
        "doi": "10.1016/S0074-6142(08)60029-9",
        "archive": "Planetary Stability Formulation",
        "description": "Natural oscillation period of vertically displaced air parcels in a stably stratified planetary atmosphere."
    },
}

# ===========================================================================
# AUTHORITATIVE DATA PORTALS & LICENSES
# ===========================================================================

LEAD_RESEARCHER = (
    "Keshav Aggarwal, Research Associate at Space Physics Laboratory (SPL), "
    "Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), "
    "Thiruvananthapuram, Kerala, India (Former PMRF Scholar at DAASE, IIT Indore)"
)

DATA_AVAILABILITY_STATEMENT = (
    "The planetary spacecraft observations and radio occultation profiles analyzed by VEDA "
    "are publicly available from international planetary data archives: NASA Planetary Data System "
    "(PDS) Atmospheres and Geosciences Nodes at https://pds-atmospheres.nmsu.edu/, European Space "
    "Agency (ESA) Planetary Science Archive (PSA) at https://archives.esac.esa.int/psa/, JAXA Data "
    "Archives and Transmission System (DARTS) at https://data.darts.isas.jaxa.jp/, and ISRO Indian "
    "Space Science Data Centre (ISSDC / PRADAN) at https://pradan.issdc.gov.in/. All calibration, "
    "retrieval, and cross-mission comparative modeling are performed locally using VEDA."
)

DATA_PORTALS = [
    {
        "id": "nasa_pds_atm",
        "name": "NASA Planetary Data System (PDS) Atmospheres Node",
        "agency": "NASA Science Mission Directorate",
        "url": "https://pds-atmospheres.nmsu.edu/",
        "description": "Authoritative repository for planetary atmospheric dynamics, radio occultation soundings, and entry probe profiles (Venus, Mars, Jupiter, Saturn, Titan, Pluto).",
        "missions": ["new_horizons", "galileo", "cassini", "maven", "mro", "pvo"],
    },
    {
        "id": "nasa_pds_geo",
        "name": "NASA PDS Geosciences Node",
        "agency": "NASA Science Mission Directorate",
        "url": "https://pds-geosciences.wustl.edu/",
        "description": "Orbital radar soundings, thermal emission spectrometry, and geodetic measurements across planetary surfaces and exospheres.",
        "missions": ["messenger", "magellan", "lro"],
    },
    {
        "id": "esa_psa",
        "name": "ESA Planetary Science Archive (PSA)",
        "agency": "European Space Agency (ESA)",
        "url": "https://archives.esac.esa.int/psa/",
        "description": "Primary archive for European planetary exploration missions including radio science experiments and spectral sounders.",
        "missions": ["vex", "bepicolombo", "rosetta", "mex"],
    },
    {
        "id": "jaxa_darts",
        "name": "JAXA Data Archives and Transmission System (DARTS)",
        "agency": "ISAS / JAXA (Japan Aerospace Exploration Agency)",
        "url": "https://data.darts.isas.jaxa.jp/pub/pds3/",
        "description": "Host for Akatsuki (VCO) Venus Climate Orbiter radio science Level 4 temperature/pressure profiles and multi-band camera imagery.",
        "missions": ["akatsuki", "bepicolombo_mio"],
    },
    {
        "id": "isro_issdc",
        "name": "ISRO Indian Space Science Data Centre (ISSDC / PRADAN)",
        "agency": "Indian Space Research Organisation (ISRO)",
        "url": "https://pradan.issdc.gov.in/",
        "description": "Repository for Indian planetary missions, including Space Physics Laboratory (SPL/VSSC) Chandrayaan-2 DFRS radio science and MOM MENCA mass spectrometer.",
        "missions": ["mom", "chandrayaan2"],
    },
]

DATA_LICENSES = {
    "nasa_pds": {
        "name": "NASA Open Data Policy",
        "type": "Public Domain / U.S. Federal Government Work",
        "url": "https://pds.nasa.gov/",
        "terms": "Planetary data products are in the public domain and freely accessible to researchers worldwide.",
    },
    "esa_psa": {
        "name": "ESA Open Access Policy",
        "type": "Open Scientific Access",
        "url": "https://archives.esac.esa.int/psa/",
        "terms": "Free access for scientific research following completion of the proprietary instrument validation period.",
    },
    "jaxa_darts": {
        "name": "JAXA DARTS Science Data Policy",
        "type": "Open Research Access",
        "url": "https://data.darts.isas.jaxa.jp/",
        "terms": "Freely accessible for research and educational purposes with mandatory citation of JAXA and instrument teams.",
    },
    "isro_issdc": {
        "name": "ISRO Planetary Science Data Policy",
        "type": "Open Science Access",
        "url": "https://pradan.issdc.gov.in/",
        "terms": "Planetary datasets released by ISSDC are accessible according to ISRO open data guidelines.",
    },
    "software": {
        "name": "MIT License",
        "type": "Open Source",
        "copyright": "Copyright (c) 2026 Keshav Aggarwal, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO",
        "url": "https://github.com/jovian-explorer/VEDA/blob/main/LICENSE",
        "terms": "Permission is hereby granted, free of charge, to any person obtaining a copy of this software.",
    },
}


def list_variables() -> List[dict]:
    """List all registered planetary analysis variables with scientific metadata."""
    return list(FIELD_REGISTRY.values())


def get_variable_info(var_id: str) -> Optional[dict]:
    """Retrieve metadata for a specific scientific variable."""
    return FIELD_REGISTRY.get(var_id.lower())


def list_data_portals() -> List[dict]:
    """List authoritative planetary science data portals."""
    return DATA_PORTALS

