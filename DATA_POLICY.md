# Data Policy, Archives and Citations

## 1. Scope

VEDA is a tool for finding, downloading, reading and analysing planetary science data that are published by space agency archives. VEDA does not own, host, re-distribute or modify those data:

* Products are downloaded from the official archive, on your request, into a cache on your own computer.
* The downloaded files are kept exactly as the archive published them. Unit conversions, derived quantities and comparisons are computed in memory, and exports say which archive file they came from.
* The terms of the archive that published a product apply to it. VEDA's MIT License applies only to the VEDA software.

The sample products bundled with VEDA (`src/veda/sampledata`) are unmodified copies of public archive products, included so the demonstrations and tests work offline. Each is listed in section 3 with its source.

---

## 2. Archives VEDA reads

### NASA Planetary Data System (PDS)
* **Hosts**: the PDS discipline nodes for NASA's Science Mission Directorate: Atmospheres (https://pds-atmospheres.nmsu.edu/), Geosciences, Imaging, Planetary Plasma Interactions, Small Bodies and Ring-Moon Systems.
* **How VEDA reads it**: PDS3 volume and cumulative indexes (`INDEX.TAB`, `CUMINDEX.TAB` and format files) and PDS4 bundles over HTTPS, and the PDS Registry (Search) API (https://pds.nasa.gov/api/search/1/) to find PDS4 products by instrument and date. Cassini, Galileo and New Horizons imaging and spectra are found with the Ring-Moon Systems node's OPUS service (https://opus.pds-rings.seti.org/). No account is needed.
* **Terms**: PDS data are freely available without restriction on use. Cite the data set (and its DOI where the archive gives one), the instrument team's reference publication and the PDS node.

### ESA Planetary Science Archive (PSA)
* **Host**: European Space Astronomy Centre (ESAC), Madrid. https://archives.esac.esa.int/psa/
* **How VEDA reads it**: products are found by instrument and date with the PSA EPN-TAP service (https://psa.esa.int/psa-tap/) and downloaded from the PSA FTP mirror over HTTPS. No account is needed.
* **Terms**: open access for scientific use once a data set's proprietary period has ended. Acknowledge ESA, the PSA and the instrument team, and cite the data set and the instrument reference publication. A suitable acknowledgement is: *"This work used data from the [mission] [instrument] experiment, obtained from the ESA Planetary Science Archive (https://archives.esac.esa.int/psa/)."*

### JAXA Data Archives and Transmission System (DARTS)
* **Host**: Institute of Space and Astronautical Science (ISAS), JAXA. https://darts.isas.jaxa.jp/
* **How VEDA reads it**: the DARTS PDS3 tree (index tables of every Akatsuki camera and radio-science volume) over HTTPS; DARTS offers no FTP access. No account is needed.
* **Terms**: free for research and education. Acknowledge JAXA/ISAS and DARTS and cite the mission team's reference publication. A suitable acknowledgement is: *"Akatsuki data were provided by JAXA/ISAS through DARTS."*

### ISRO Indian Space Science Data Centre (ISSDC / PRADAN)
* **Host**: Indian Space Science Data Centre, ISRO, Byalalu, Bengaluru. https://pradan.issdc.gov.in/
* **How VEDA reads it**: PRADAN requires a registered account and its own website for downloads. VEDA opens the PRADAN page for you to sign in; you download the products there and import them into VEDA. VEDA never receives your credentials.
* **Terms**: data are released to registered users under the ISRO science data policy and the terms you accept when you register. Acknowledge ISRO and ISSDC and the payload team as those terms require.

### NASA NAIF SPICE and mission SPICE archives
* **Hosts**: NAIF, Jet Propulsion Laboratory (https://naif.jpl.nasa.gov/); ESA SPICE Service (Mars Express, Rosetta, BepiColombo); the Akatsuki SPICE archive (JAXA, NAIF PDS4 copy).
* **How VEDA uses them**: the kernels an observation needs (leap seconds, planetary constants, planetary and satellite ephemerides, spacecraft trajectory) are downloaded automatically when you open the mission and the observation, unless you turn this off or they exceed the size limit in Settings, in which case VEDA lists them with their size and asks first. They are kept and reused.
* **Terms**: SPICE kernels and the CSPICE toolkit are free to use. Acknowledge NAIF and cite Acton, C. H. (1996), *Ancillary data services of NASA's Navigation and Ancillary Information Facility*, Planetary and Space Science 44, 65-70, together with the producer of any mission kernels used. See https://naif.jpl.nasa.gov/naif/rules.html.

---

## 3. Connected data sets and what to cite

The authoritative list is VEDA's own catalogue (`src/veda/archives/datasets.py`, `indexed_datasets.py`, `service_datasets.py`); the app's **Cite** panel builds the references for the data sets you actually opened. *Live* data sets are searched on the archive server by date (ESA PSA EPN-TAP, NASA PDS Registry, OPUS); cite the archive data set identifiers shown with each product (PSA DATA_SET_ID, PDS4 bundle and collection).

| Mission | Payload | Level | Data set (VEDA id) | Archive | Reference papers |
|---|---|---|---|---|---|
| Mars Orbiter Mission (MOM / Mangalyaan) | MOM payloads (MCC, MENCA, LAP, TIS, MSM) | ISSDC | `issdc-mom` | ISRO ISSDC (PRADAN) | Arunan, S., & Satish, R. (2015) |
| Chandrayaan-2 Orbiter (CH2O) | Chandrayaan-2 orbiter payloads (incl. DFRS, CHACE-2) | ISSDC | `issdc-ch2` | ISRO ISSDC (PRADAN) |  |
| Cassini-Huygens | RSS (Radio Science) ionosphere profiles of Saturn | Derived (PDS4) | `corss-saturn-ionosphere` | NASA PDS Atmospheres Node (PDS4) | Kliore et al. (2009); data doi:10.17189/1518961 |
| Cassini-Huygens | UVIS occultations: Saturn thermosphere H2 density and temperature | Derived (PDS4) | `cassini-uvis-saturn-thermosphere` | NASA PDS Atmospheres Node (PDS4) | Koskinen et al. (2015); data doi:10.17189/518e-p721 |
| Cassini-Huygens | RSS (Radio Science) neutral atmosphere profiles of Titan | Derived (PDS4) | `corss-titan-neutral-profiles` | NASA PDS Atmospheres Node (PDS4) | Schinder et al. (2011, 2012, 2015) |
| Cassini-Huygens | RSS (Radio Science) | Derived (PDS4) | `corss_occul_el_dens` | NASA PDS Atmospheres Node (PDS4) | Kliore et al. (2008); Kliore et al. (2004); Matson et al. (2002) |
| Juno | MWR (Microwave Radiometer) | EDR + derived | `jno-x-mwr` | NASA PDS Atmospheres Node | Janssen et al. (2017); Bolton et al. (2017) |
| Venus Express (VEX) | VeRa (Radio Science) | L1 + ancillary | `vex-v-rss-1-ent-v1.0` | NASA PDS Atmospheres Node | Häusler et al. (2006); Svedhem et al. (2007) |
| Venus Express (VEX) | VeRa (Radio Science) | L1A-L2 | `vex-v-vra-1-2-3` | ESA PSA | Häusler et al. (2006); Svedhem et al. (2007) |
| Magellan | RSS (Radio Science) | L5 | `mgn-v-rss-5-occ-prof-rtpd-v1.0` | NASA PDS Atmospheres Node | Jenkins et al. (1994); Steffes et al. (1994); Saunders et al. (1992) |
| Magellan | RSS (Radio Science) | L5 | `mgn-v-rss-5-occ-prof-abs-h2so4-v1.0` | NASA PDS Atmospheres Node | Jenkins et al. (1994); Steffes et al. (1994); Saunders et al. (1992) |
| Magellan | RSS (Radio Science) | L1 | `mgn-v-rss-1-rocc-v2.0` | NASA PDS Atmospheres Node | Jenkins et al. (1994); Saunders et al. (1992) |
| Galileo | Galileo Probe (ASI, NMS, NEP, NFR, ...) | L3 | `gp-j-entry-v1.0` | NASA PDS Atmospheres Node | Seiff et al. (1998); Johnson et al. (1992) |
| Cassini-Huygens | Huygens HASI | L2-L4 | `hp-ssa-hasi-2-3-4-mission-v1.1` | NASA PDS Atmospheres Node | Fulchignoni et al. (2005); Fulchignoni et al. (2002); Matson et al. (2002) |
| Mars Global Surveyor (MGS) | RS (Radio Science) | L5 (SDP) | `mgs-m-rss-5-sdp-v1.0` | NASA PDS Atmospheres Node | Tyler et al. (2001); Hinson et al. (1999); Albee et al. (2001) |
| Mars Reconnaissance Orbiter (MRO) | RSS (Radio Science) | L5 (derived T-P) | `mro-m-rss-5-tps-v1.0` | NASA PDS Atmospheres Node | Hinson et al. (2008); Hinson et al. (1999); Zurek & Smrekar (2007) |
| Mars Exploration Rovers (Spirit, Opportunity) | IMU (entry profiles) | L5 (derived) | `mer-m-imu-5-edl-derived-v1.0` | NASA PDS Atmospheres Node | Withers & Smith (2006) |
| Phoenix | ASE (entry profile) | L5 (RDR) | `phx-m-ase-5-edl-rdr-v1.0` | NASA PDS Atmospheres Node | Withers & Catling (2010) |
| Mars Science Laboratory (Curiosity) | EDL atmospheric reconstruction | Derived (PDS4) | `msl-edl-atmosphere` | NASA PDS Atmospheres Node | Holstein-Rathlou et al. (2016); data doi:10.17189/1518944 |
| InSight | EDL atmospheric reconstruction | Derived (PDS4) | `insight-edl-atmosphere` | NASA PDS Atmospheres Node | Karatekin, Banfield & Ashley (2020), data doi:10.17189/1518935 |
| Mars Express (MEX) | MaRS (Radio Science) | L4 | `mex-m-mrs-5-occ` | ESA PSA (mirror: NASA PDS Geosciences Node) | Pätzold et al. (2016); Pätzold et al. (2004); Chicarro et al. (2004) |
| Akatsuki (VCO) | RS (Radio Science) | L3/L4 | `vco-v-rs-5-occ-v1.0` | JAXA DARTS | Imamura et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | RS (Radio Science) | L2 | `vco-v-rs-3-occ-v1.0` | JAXA DARTS | Imamura et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | UVI camera | L1b | `vco-v-uvi-2-edr-v1.0` | JAXA DARTS | Yamazaki et al. (2018); Nakamura et al. (2016) |
| Akatsuki (VCO) | UVI camera | L2b | `vco-v-uvi-3-cdr-v1.0` | JAXA DARTS | Yamazaki et al. (2018); Nakamura et al. (2016) |
| Akatsuki (VCO) | UVI camera | geometry | `vco-v-uvi-3-sedr-v1.0` | JAXA DARTS | Yamazaki et al. (2018); Nakamura et al. (2016) |
| Akatsuki (VCO) | IR1 camera | L1b | `vco-v-ir1-2-edr-v1.0` | JAXA DARTS | Iwagami et al. (2011); Iwagami et al. (2018); Nakamura et al. (2016) |
| Akatsuki (VCO) | IR1 camera | L2b+L2c | `vco-v-ir1-3-cdr-v1.0` | JAXA DARTS | Iwagami et al. (2011); Iwagami et al. (2018); Nakamura et al. (2016) |
| Akatsuki (VCO) | IR1 camera | geometry | `vco-v-ir1-3-sedr-v1.0` | JAXA DARTS | Iwagami et al. (2011); Iwagami et al. (2018); Nakamura et al. (2016) |
| Akatsuki (VCO) | IR2 camera | L1b | `vco-v-ir2-2-edr-v1.0` | JAXA DARTS | Satoh et al. (2016); Satoh et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | IR2 camera | L2b | `vco-v-ir2-3-cdr-v1.0` | JAXA DARTS | Satoh et al. (2016); Satoh et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | IR2 camera | geometry | `vco-v-ir2-3-sedr-v1.0` | JAXA DARTS | Satoh et al. (2016); Satoh et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | LIR camera | L1b | `vco-v-lir-2-edr-v1.0` | JAXA DARTS | Fukuhara et al. (2011); Taguchi et al. (2007); Fukuhara et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | LIR camera | L2b+L2c | `vco-v-lir-3-cdr-v1.0` | JAXA DARTS | Fukuhara et al. (2011); Taguchi et al. (2007); Fukuhara et al. (2017); Nakamura et al. (2016) |
| Akatsuki (VCO) | LIR camera | geometry | `vco-v-lir-3-sedr-v1.0` | JAXA DARTS | Fukuhara et al. (2011); Taguchi et al. (2007); Fukuhara et al. (2017); Nakamura et al. (2016) |
| Pioneer Venus Orbiter (PVO) | ORO radio occultation profiles (temperature-pressure, electron density) | Derived (PDS4) | `pvoro-nssdc` | NASA PDS Atmospheres Node | Withers et al. (2020a, 2020b); data doi:10.17189/tm55-bj87; Kliore & Patel (1980) |
| Pioneer Venus Orbiter (PVO) | ONMS (Neutral mass spectrometer) | L2-L4 | `pvo-v-onms` | NASA PDS | Niemann et al. (1980); Niemann et al. (1980); Colin, L. (1980) |
| Mars Reconnaissance Orbiter (MRO) | MCS (Mars Climate Sounder) | DDR (L2) | `mro-m-mcs-5-ddr-v1.0` | NASA PDS | McCleese et al. (2007); Kleinböhl et al. (2009); Zurek, R. W., & Smrekar, S. E. (2007) |
| Mars Reconnaissance Orbiter (MRO) | MCS (Mars Climate Sounder) | EDR | `mro-m-mcs-2-edr-v1.0` | NASA PDS | McCleese et al. (2007); Zurek, R. W., & Smrekar, S. E. (2007) |
| Mars Reconnaissance Orbiter (MRO) | CTX (Context Camera) | EDR | `mro-m-ctx-2-edr-l0-v1.0` | NASA PDS | Malin et al. (2007); Zurek, R. W., & Smrekar, S. E. (2007) |
| Mars Reconnaissance Orbiter (MRO) | MARCI (Mars Color Imager) | EDR | `mro-m-marci-2-edr-l0-v1.0` | NASA PDS | Bell et al. (2009); Malin et al. (2001); Zurek, R. W., & Smrekar, S. E. (2007) |
| Juno | JunoCam | EDR / RDR | `jno-j-jnc-2-3-edr-rdr-v1.0` | NASA PDS | Hansen et al. (2017); Bolton et al. (2017) |
| Juno | MAG (Fluxgate magnetometer) | L3 | `jno-fgm-3-cal-v1.0` | NASA PDS | Connerney et al. (2017); Bolton et al. (2017) |
| Cassini-Huygens | INMS (Ion and Neutral Mass Spectrometer) | L1A | `co-s-inms-3-l1a-u-v1.0` | NASA PDS | Waite et al. (2004); Matson et al. (2002) |
| Mars Reconnaissance Orbiter (MRO) | MCS (Mars Climate Sounder) | RDR | `mro-m-mcs-4-rdr-v1.0` | NASA PDS | McCleese et al. (2007); Zurek, R. W., & Smrekar, S. E. (2007) |
| Venus Express (VEX) | VMC | all levels | `psa-vex-vmc` (live) | ESA PSA | Markiewicz et al. (2007); Svedhem et al. (2007) |
| Venus Express (VEX) | VIRTIS | all levels | `psa-vex-virtis` (live) | ESA PSA | Drossart et al. (2007); Svedhem et al. (2007) |
| Venus Express (VEX) | SPICAV | all levels | `psa-vex-spicav` (live) | ESA PSA | Bertaux et al. (2007); Svedhem et al. (2007) |
| Venus Express (VEX) | SPICAV-SOIR | all levels | `psa-vex-spicavsoir` (live) | ESA PSA | Bertaux et al. (2007); Svedhem et al. (2007) |
| Venus Express (VEX) | ASPERA-4 | all levels | `psa-vex-aspera4` (live) | ESA PSA | Barabash et al. (2007); Svedhem et al. (2007) |
| Venus Express (VEX) | MAG | all levels | `psa-vex-mag` (live) | ESA PSA | Zhang et al. (2006); Svedhem et al. (2007) |
| Mars Express (MEX) | MaRS | all levels | `psa-mex-mars` (live) | ESA PSA | Pätzold et al. (2016); Pätzold et al. (2004); Chicarro et al. (2004) |
| Mars Express (MEX) | SPICAM | all levels | `psa-mex-spicam` (live) | ESA PSA | Bertaux et al. (2006); Chicarro et al. (2004) |
| Mars Express (MEX) | PFS | all levels | `psa-mex-pfs` (live) | ESA PSA | Formisano et al. (2005); Chicarro et al. (2004) |
| Mars Express (MEX) | OMEGA | all levels | `psa-mex-omega` (live) | ESA PSA | Bibring et al. (2004); Chicarro et al. (2004) |
| Mars Express (MEX) | ASPERA-3 | all levels | `psa-mex-aspera3` (live) | ESA PSA | Barabash et al. (2006); Chicarro et al. (2004) |
| Mars Express (MEX) | MARSIS | all levels | `psa-mex-marsis` (live) | ESA PSA | Picardi et al. (2005); Jordan et al. (2009); Chicarro et al. (2004) |
| Mars Express (MEX) | HRSC | all levels | `psa-mex-hrsc` (live) | ESA PSA | Jaumann et al. (2007); Chicarro et al. (2004) |
| Mars Express (MEX) | VMC | all levels | `psa-mex-vmc` (live) | ESA PSA | Chicarro et al. (2004) |
| Rosetta | ALICE | all levels | `psa-rosetta-alice` (live) | ESA PSA | Stern et al. (2007); Glassmeier et al. (2007) |
| Rosetta | MIRO | all levels | `psa-rosetta-miro` (live) | ESA PSA | Gulkis et al. (2007); Glassmeier et al. (2007) |
| Rosetta | OSIRIS | all levels | `psa-rosetta-osiris` (live) | ESA PSA | Keller et al. (2007); Glassmeier et al. (2007) |
| Rosetta | VIRTIS | all levels | `psa-rosetta-virtis` (live) | ESA PSA | Coradini et al. (2007); Glassmeier et al. (2007) |
| Rosetta | ROSINA | all levels | `psa-rosetta-rosina` (live) | ESA PSA | Balsiger et al. (2007); Glassmeier et al. (2007) |
| Rosetta | RPC | all levels | `psa-rosetta-rpc` (live) | ESA PSA | Carr et al. (2007); Glassmeier et al. (2007) |
| Rosetta | RSI | all levels | `psa-rosetta-rsi` (live) | ESA PSA | Pätzold et al. (2007); Glassmeier et al. (2007) |
| Rosetta | CONSERT | all levels | `psa-rosetta-consert` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | GIADA | all levels | `psa-rosetta-giada` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | COSIMA | all levels | `psa-rosetta-cosima` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | MIDAS | all levels | `psa-rosetta-midas` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | NAVCAM | all levels | `psa-rosetta-navcam` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | SREM | all levels | `psa-rosetta-srem` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | ROMAP | all levels | `psa-rosetta-romap` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | SESAME | all levels | `psa-rosetta-sesame` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | MUPUS | all levels | `psa-rosetta-mupus` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | CIVA | all levels | `psa-rosetta-civa` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | ROLIS | all levels | `psa-rosetta-rolis` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | APXS | all levels | `psa-rosetta-apxs` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | COSAC | all levels | `psa-rosetta-cosac` (live) | ESA PSA | Glassmeier et al. (2007) |
| Rosetta | PTOLEMY | all levels | `psa-rosetta-ptolemy` (live) | ESA PSA | Glassmeier et al. (2007) |
| BepiColombo | MPO-MAG | all levels | `psa-bepicolombo-mpomag` (live) | ESA PSA | Heyner et al. (2021); Benkhoff et al. (2021) |
| BepiColombo | MCAM | all levels | `psa-bepicolombo-mcam` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | SERENA | all levels | `psa-bepicolombo-serena` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | ISA | all levels | `psa-bepicolombo-isa` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | PHEBUS | all levels | `psa-bepicolombo-phebus` (live) | ESA PSA | Quémerais et al. (2020); Benkhoff et al. (2021) |
| BepiColombo | MIXS | all levels | `psa-bepicolombo-mixs` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | SIXS | all levels | `psa-bepicolombo-sixs` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | MGNS | all levels | `psa-bepicolombo-mgns` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | BERM | all levels | `psa-bepicolombo-berm` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | MORE | all levels | `psa-bepicolombo-more` (live) | ESA PSA | Iess et al. (2021); Benkhoff et al. (2021) |
| BepiColombo | BELA | all levels | `psa-bepicolombo-bela` (live) | ESA PSA | Benkhoff et al. (2021) |
| BepiColombo | MERTIS | all levels | `psa-bepicolombo-mertis` (live) | ESA PSA | Hiesinger et al. (2020); Benkhoff et al. (2021) |
| Cassini-Huygens | Huygens DISR | all levels | `psa-cassini-disr` (live) | ESA PSA | Tomasko et al. (2002); Matson et al. (2002) |
| Cassini-Huygens | Huygens GCMS | all levels | `psa-cassini-gcms` (live) | ESA PSA | Niemann et al. (2002); Matson et al. (2002) |
| Cassini-Huygens | Huygens ACP | all levels | `psa-cassini-acp` (live) | ESA PSA | Matson et al. (2002) |
| Cassini-Huygens | Huygens DWE | all levels | `psa-cassini-dwe` (live) | ESA PSA | Matson et al. (2002) |
| Cassini-Huygens | Huygens SSP | all levels | `psa-cassini-ssp` (live) | ESA PSA | Matson et al. (2002) |
| Cassini-Huygens | Huygens DTWG | all levels | `psa-cassini-dtwg` (live) | ESA PSA | Matson et al. (2002) |
| Cassini-Huygens | Huygens HUYGENS_HK | all levels | `psa-cassini-huygenshk` (live) | ESA PSA | Matson et al. (2002) |
| Magellan | Radar (SAR F-BIDR/MIDR, altimetry ARCDR/GxDR) | all levels | `pds-magellan-radarsarfbidrmidraltimet` (live) | NASA PDS | Saunders et al. (1992) |
| Magellan | Radio science (gravity, occultation, bistatic) | all levels | `pds-magellan-radiosciencegravityoccul` (live) | NASA PDS | Steffes et al. (1994); Jenkins et al. (1994); Saunders et al. (1992) |
| Pioneer Venus Orbiter (PVO) | ORO/ORSE radio occultation | all levels | `pds-pvo-oroorseradiooccultation` (live) | NASA PDS | Kliore, A. J., & Patel, I. R. (1980); Kliore, A. J. (1985); Colin, L. (1980) |
| Pioneer Venus Orbiter (PVO) | OIMS ion mass spectrometer | all levels | `pds-pvo-oimsionmassspectrometer` (live) | NASA PDS | Colin, L. (1980) |
| Pioneer Venus Orbiter (PVO) | Pioneer Venus probes (LAS, LNMS, LGC, LIR, SAS, SNFR, DLBI) | all levels | `pds-pvo-pioneervenusprobeslaslnm` (live) | NASA PDS | Colin, L. (1980) |
| Mars Global Surveyor (MGS) | TES | all levels | `pds-mgs-tes` (live) | NASA PDS | Christensen et al. (2001); Albee et al. (2001) |
| Mars Global Surveyor (MGS) | MOLA | all levels | `pds-mgs-mola` (live) | NASA PDS | Smith et al. (2001); Albee et al. (2001) |
| Mars Global Surveyor (MGS) | Accelerometer | all levels | `pds-mgs-accelerometer` (live) | NASA PDS | Albee et al. (2001) |
| Mars Reconnaissance Orbiter (MRO) | CRISM | all levels | `pds-mro-crism` (live) | NASA PDS | Murchie et al. (2007); Zurek, R. W., & Smrekar, S. E. (2007) |
| Mars Reconnaissance Orbiter (MRO) | SHARAD | all levels | `pds-mro-sharad` (live) | NASA PDS | Seu et al. (2007); Zurek, R. W., & Smrekar, S. E. (2007) |
| Mars Reconnaissance Orbiter (MRO) | Accelerometer | all levels | `pds-mro-accelerometer` (live) | NASA PDS | Zurek, R. W., & Smrekar, S. E. (2007) |
| MAVEN | NGIMS | all levels | `pds-maven-ngims` (live) | NASA PDS | Mahaffy et al. (2015); Jakosky et al. (2015) |
| MAVEN | IUVS | all levels | `pds-maven-iuvs` (live) | NASA PDS | McClintock et al. (2015); Jakosky et al. (2015) |
| MAVEN | ACC | all levels | `pds-maven-acc` (live) | NASA PDS | Jakosky et al. (2015) |
| Juno | JIRAM | all levels | `pds-juno-jiram` (live) | NASA PDS | Adriani et al. (2017); Bolton et al. (2017) |
| Juno | UVS | all levels | `pds-juno-uvs` (live) | NASA PDS | Gladstone et al. (2017); Bolton et al. (2017) |
| Juno | Gravity / radio science | all levels | `pds-juno-gravityradioscience` (live) | NASA PDS | Asmar et al. (2017); Bolton et al. (2017) |
| Galileo | SSI | all levels | `opus-galileo-galileossi` (live) | PDS Rings Node OPUS | Belton et al. (1992); Johnson et al. (1992) |
| Galileo | NIMS | all levels | `pds-galileo-nims` (live) | NASA PDS | Carlson et al. (1992); Johnson et al. (1992) |
| Galileo | UVS/EUV | all levels | `pds-galileo-uvseuv` (live) | NASA PDS | Hord et al. (1992); Johnson et al. (1992) |
| Galileo | PPR | all levels | `pds-galileo-ppr` (live) | NASA PDS | Johnson et al. (1992) |
| Galileo | Radio science | all levels | `pds-galileo-radioscience` (live) | NASA PDS | Howard et al. (1992); Johnson et al. (1992) |
| Galileo | MAG | all levels | `pds-galileo-mag` (live) | NASA PDS | Kivelson et al. (1992); Johnson et al. (1992) |
| Galileo | PLS | all levels | `pds-galileo-pls` (live) | NASA PDS | Frank et al. (1992); Johnson et al. (1992) |
| Galileo | EPD | all levels | `pds-galileo-epd` (live) | NASA PDS | Williams et al. (1992); Johnson et al. (1992) |
| Cassini-Huygens | ISS | all levels | `opus-cassini-cassiniiss` (live) | PDS Rings Node OPUS | Porco et al. (2004); Matson et al. (2002) |
| Cassini-Huygens | VIMS | all levels | `opus-cassini-cassinivims` (live) | PDS Rings Node OPUS | Brown et al. (2004); Matson et al. (2002) |
| Cassini-Huygens | UVIS | all levels | `opus-cassini-cassiniuvis` (live) | PDS Rings Node OPUS | Esposito et al. (2004); Matson et al. (2002) |
| Cassini-Huygens | CIRS | all levels | `opus-cassini-cassinicirs` (live) | PDS Rings Node OPUS | Flasar et al. (2004); Matson et al. (2002) |
| Cassini-Huygens | RSS (ring occultations in OPUS) | all levels | `opus-cassini-cassinirss` (live) | PDS Rings Node OPUS | Kliore et al. (2004); Kliore et al. (2008); Matson et al. (2002) |
| New Horizons | REX | all levels | `pds-new_horizons-rex` (live) | NASA PDS | Tyler et al. (2008); Gladstone et al. (2016); Hinson et al. (2017); Stern, S. A. (2008) |
| New Horizons | Alice | all levels | `pds-new_horizons-alice` (live) | NASA PDS | Stern et al. (2008); Gladstone et al. (2016); Stern, S. A. (2008) |
| New Horizons | LORRI | all levels | `pds-new_horizons-lorri` (live) | NASA PDS | Cheng et al. (2008); Stern, S. A. (2008) |
| New Horizons | Ralph/MVIC | all levels | `pds-new_horizons-ralphmvic` (live) | NASA PDS | Reuter et al. (2008); Stern, S. A. (2008) |
| New Horizons | Ralph/LEISA | all levels | `pds-new_horizons-ralphleisa` (live) | NASA PDS | Reuter et al. (2008); Stern, S. A. (2008) |
| New Horizons | SWAP | all levels | `pds-new_horizons-swap` (live) | NASA PDS | McComas et al. (2008); Stern, S. A. (2008) |
| New Horizons | PEPSSI | all levels | `pds-new_horizons-pepssi` (live) | NASA PDS | McNutt et al. (2008); Stern, S. A. (2008) |
| New Horizons | SDC | all levels | `pds-new_horizons-sdc` (live) | NASA PDS | Horányi et al. (2008); Stern, S. A. (2008) |
| MESSENGER | MLA | all levels | `pds-messenger-mla` (live) | NASA PDS | Cavanaugh et al. (2007); Solomon et al. (2001) |
| MESSENGER | GRS | all levels | `pds-messenger-grs` (live) | NASA PDS | Goldsten et al. (2007); Solomon et al. (2001) |
| MESSENGER | NS | all levels | `pds-messenger-ns` (live) | NASA PDS | Solomon et al. (2001) |
| MESSENGER | XRS | all levels | `pds-messenger-xrs` (live) | NASA PDS | Solomon et al. (2001) |
| MESSENGER | Radio science | all levels | `pds-messenger-radioscience` (live) | NASA PDS | Srinivasan et al. (2007); Solomon et al. (2001) |
| MESSENGER | MAG | all levels | `pds-messenger-mag` (live) | NASA PDS | Anderson et al. (2007); Solomon et al. (2001) |
| MESSENGER | MASCS | all levels | `pds-messenger-mascs` (live) | NASA PDS | McClintock, W. E., & Lankton, M. R. (2007); Solomon et al. (2001) |
| Lunar Reconnaissance Orbiter (LRO) | Diviner | all levels | `pds-lro-diviner` (live) | NASA PDS | Paige et al. (2010); Chin et al. (2007); Vondrak et al. (2010) |
| Lunar Reconnaissance Orbiter (LRO) | LOLA | all levels | `pds-lro-lola` (live) | NASA PDS | Smith et al. (2010); Chin et al. (2007); Vondrak et al. (2010) |
| Lunar Reconnaissance Orbiter (LRO) | LEND | all levels | `pds-lro-lend` (live) | NASA PDS | Mitrofanov et al. (2010); Chin et al. (2007); Vondrak et al. (2010) |
| Lunar Reconnaissance Orbiter (LRO) | Mini-RF | all levels | `pds-lro-minirf` (live) | NASA PDS | Nozette et al. (2010); Chin et al. (2007); Vondrak et al. (2010) |
| Lunar Reconnaissance Orbiter (LRO) | Radio science | all levels | `pds-lro-radioscience` (live) | NASA PDS | Chin et al. (2007); Vondrak et al. (2010) |
| Dawn | GRaND | all levels | `pds-dawn-grand` (live) | NASA PDS | Prettyman et al. (2011); Russell, C. T., & Raymond, C. A. (2011) |
| Dawn | Gravity | all levels | `pds-dawn-gravity` (live) | NASA PDS | Russell, C. T., & Raymond, C. A. (2011) |

### Not available yet

* **MAVEN STATIC, SWEA, SWIA, MAG, LPW, EUV, SEP and ROSE**, and most Juno, Cassini, Galileo, MESSENGER and MGS plasma data: the PDS PPI node registers these only as bundles and collections, so they cannot be searched by date yet.
* **Pioneer Venus OUVS, OIR and OCPP**: no public archive route was found.
* **Galileo NIMS Jupiter cubes, MRO gravity** and, while their indexes are unverified, **Cassini CAPS/MAG/RPWS/MIMI/RADAR, Juno JADE/JEDI/Waves, MESSENGER MDIS/EPPS, LRO LAMP/CRaTER and Dawn FC/VIR** volume indexes.
* **Akatsuki LAC**: not yet published by JAXA.
* **MRO CTX and MARCI** are indexed only when you press *Index now* (their archive indexes are about 95 MB each).
* Products whose label describes the file only as raw bytes (some raw telemetry, e.g. Rosetta lander L1, RSI L1A) can be downloaded but not plotted.

### SPICE kernels

Generic kernels (naif0012.tls, pck00011.tpc, de440s.bsp and the Mars, Pluto, Ceres, Vesta and 67P kernels) come from the NAIF generic archive and the NAIF/ESA mission archives. Spacecraft ephemerides come from each mission's archive: NAIF operational and PDS SPICE archives (Venus Express, Magellan, Pioneer Venus, MGS, MRO, MAVEN, Juno, Galileo, Cassini, New Horizons, MESSENGER, LRO, Dawn), the ESA SPICE service (Mars Express, Rosetta, BepiColombo) and the NAIF PDS4 copy of the JAXA Akatsuki SPICE archive. No public SPICE kernels exist for the Mars Orbiter Mission or Chandrayaan-2.

### Bundled sample products

| Folder | Product | Source |
|---|---|---|
| `sampledata/venus_akatsuki` | Akatsuki RS Level 4 profile and a UVI geometry image | JAXA DARTS, `vco-v-rs-5-occ-v1.0` and `vco-v-uvi-3-sedr-v1.0` |
| `sampledata/mars_express` | MaRS L4 neutral atmosphere and ionosphere profiles | ESA PSA, `mex-m-mrs-5-occ` |
| `sampledata/titan_cassini_rss` | Cassini RSS Titan electron density (PDS4) | NASA PDS Atmospheres, `corss_occul_el_dens` |

---

## 4. Citing your results

When you publish figures, tables or values produced with VEDA, please cite:

1. **The data**: the data set (id and DOI if one exists), the instrument team's reference publication from the table above, and the archive.
2. **The geometry** (if you used it): NAIF (Acton, 1996) and the mission kernels.
3. **VEDA**, so that others can reproduce the processing:

```bibtex
@software{Aggarwal_VEDA_2026,
  author       = {Keshav Aggarwal},
  title        = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},
  year         = {2026},
  publisher    = {Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO},
  version      = {0.0.1},
  url          = {https://github.com/jovian-explorer/VEDA},
  address      = {Thiruvananthapuram, Kerala, India}
}
```

### Data availability statement (template)
Remove the archives you did not use and add the data set DOIs:

> The spacecraft observations analysed in this study are publicly available from the NASA Planetary Data System (PDS) Atmospheres Node (https://pds-atmospheres.nmsu.edu/), the ESA Planetary Science Archive (PSA) (https://archives.esac.esa.int/psa/) and the JAXA Data Archives and Transmission System (DARTS) (https://data.darts.isas.jaxa.jp/); ISRO mission data are available to registered users from the Indian Space Science Data Centre (ISSDC/PRADAN) (https://pradan.issdc.gov.in/). Spacecraft and planetary ephemerides were obtained from the NASA NAIF SPICE archive (https://naif.jpl.nasa.gov/) and the mission SPICE archives at ESA and JAXA. Archived values were read, unit-converted and compared with VEDA version 0.0.1 (https://github.com/jovian-explorer/VEDA).

---

## 5. Scientific responsibility

* VEDA's derived quantities use the equations documented in the app (**Help** and **Variables**) and in [USAGE.md](USAGE.md), with the body constants listed there. They are not a substitute for the instrument team's own retrievals.
* Check any value you intend to publish against the product label, the data set documentation (`DOCUMENT/` and `CATALOG/` in each volume) and the instrument team's publications.
* Report errors in VEDA's reading or processing at https://github.com/jovian-explorer/VEDA/issues. Report errors in the data themselves to the archive.

VEDA is not affiliated with, endorsed by or sponsored by NASA, ESA, JAXA or ISRO, and cannot guarantee that their servers are available.
