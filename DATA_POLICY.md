# Data Policy, Archives and Citations

## 1. Scope

VEDA is a tool for finding, downloading, reading and analysing planetary science data that are published by space agency archives. VEDA does not own, host, re-distribute or modify those data:

* Products are downloaded from the official archive, on your request, into a cache on your own computer.
* The downloaded files are kept exactly as the archive published them. Unit conversions, derived quantities and comparisons are computed in memory, and exports say which archive file they came from.
* The terms of the archive that published a product apply to it. VEDA's MIT License applies only to the VEDA software.

The sample products bundled with VEDA (`src/veda/sampledata`) are unmodified copies of public archive products, included so the demonstrations and tests work offline. Each is listed in section 3 with its source.

---

## 2. Archives VEDA reads

### NASA Planetary Data System (PDS), Atmospheres Node
* **Host**: New Mexico State University, for NASA's Science Mission Directorate. https://pds-atmospheres.nmsu.edu/
* **How VEDA reads it**: PDS3 volume indexes (`INDEX.TAB` and format files) and PDS4 bundles over HTTPS. No account is needed.
* **Terms**: PDS data are freely available without restriction on use. Cite the data set (and its DOI where the archive gives one), the instrument team's reference publication and the PDS node.

### ESA Planetary Science Archive (PSA)
* **Host**: European Space Astronomy Centre (ESAC), Madrid. https://archives.esac.esa.int/psa/
* **How VEDA reads it**: the PSA FTP mirror of the PDS3 volumes, over HTTPS. No account is needed.
* **Terms**: open access for scientific use once a data set's proprietary period has ended. Acknowledge ESA, the PSA and the instrument team, and cite the data set and the instrument reference publication. A suitable acknowledgement is: *"This work used data from the [mission] [instrument] experiment, obtained from the ESA Planetary Science Archive (https://archives.esac.esa.int/psa/)."*

### JAXA Data Archives and Transmission System (DARTS)
* **Host**: Institute of Space and Astronautical Science (ISAS), JAXA. https://darts.isas.jaxa.jp/
* **How VEDA reads it**: the DARTS PDS3 tree and the Akatsuki SPICE kernels, over HTTPS. No account is needed.
* **Terms**: free for research and education. Acknowledge JAXA/ISAS and DARTS and cite the mission team's reference publication. A suitable acknowledgement is: *"Akatsuki data were provided by JAXA/ISAS through DARTS."*

### ISRO Indian Space Science Data Centre (ISSDC / PRADAN)
* **Host**: Indian Space Science Data Centre, ISRO, Byalalu, Bengaluru. https://pradan.issdc.gov.in/
* **How VEDA reads it**: PRADAN requires a registered account and its own website for downloads. VEDA opens the PRADAN page for you to sign in; you download the products there and import them into VEDA. VEDA never receives your credentials.
* **Terms**: data are released to registered users under the ISRO science data policy and the terms you accept when you register. Acknowledge ISRO and ISSDC and the payload team as those terms require.

### NASA NAIF SPICE and mission SPICE archives
* **Hosts**: NAIF, Jet Propulsion Laboratory (https://naif.jpl.nasa.gov/); ESA SPICE Service (Mars Express); JAXA DARTS (Akatsuki).
* **How VEDA uses them**: when you ask for an observation's geometry, VEDA lists the kernels it needs (leap seconds, planetary constants, planetary ephemeris, spacecraft trajectory) with their size, and downloads them only after you agree.
* **Terms**: SPICE kernels and the CSPICE toolkit are free to use. Acknowledge NAIF and cite Acton, C. H. (1996), *Ancillary data services of NASA's Navigation and Ancillary Information Facility*, Planetary and Space Science 44, 65-70, together with the producer of any mission kernels used. See https://naif.jpl.nasa.gov/naif/rules.html.

---

## 3. Connected data sets and what to cite

The authoritative list is VEDA's own catalogue (`src/veda/archives/datasets.py`), shown in the app under **Data & Licenses** with the same citations. Where an archive assigns a DOI to a data set, cite it as well; the PDS and PSA landing pages for each volume give it.

| Data set id | Mission and data | Archive | Instrument reference |
|---|---|---|---|
| `vco-v-rs-5-occ-v1.0` | Akatsuki radio occultation L3 refractivity and L4 profiles (Venus) | JAXA DARTS | Imamura, T., et al. (2017). Initial performance of the radio occultation experiment in the Venus orbiter mission Akatsuki. *Earth, Planets and Space*, 69, 137. |
| `vco-v-rs-3-occ-v1.0` | Akatsuki radio occultation L2 frequency and power (Venus) | JAXA DARTS | as above |
| `vex-v-vra-1-2-3` | Venus Express VeRa L1A to L2, per orbit (Venus) | ESA PSA | Häusler, B., et al. (2006). Radio science investigations by VeRa onboard the Venus Express spacecraft. *Planetary and Space Science*, 54, 1315-1335. |
| `vex-v-rss-1-ent-v1.0` | Venus Express VeRa, PDS copy with calibration and SPICE (Venus) | NASA PDS | as above |
| `mgn-v-rss-5-occ-prof-rtpd-v1.0` | Magellan radio occultation, Oct 1991: refractivity, T, P, density (Venus) | NASA PDS | Jenkins, J. M., Steffes, P. G., Hinson, D. P., Twicken, J. D., & Tyler, G. L. (1994). Radio occultation studies of the Venus atmosphere with the Magellan spacecraft. 2. Results from the October 1991 experiments. *Icarus*, 110, 79-94. |
| `mgn-v-rss-5-occ-prof-abs-h2so4-v1.0` | Magellan 13 cm absorptivity and H2SO4 vapour (Venus) | NASA PDS | as above |
| `mgn-v-rss-1-rocc-v2.0` | Magellan raw open-loop and tracking records (Venus) | NASA PDS | as above |
| `mex-m-mrs-5-occ` | Mars Express MaRS L4 neutral atmosphere and ionosphere (Mars) | ESA PSA | Pätzold, M., et al. (2016). Mars Express 10 years at Mars: observations by the Mars Express Radio Science Experiment (MaRS). *Planetary and Space Science*, 127, 44-90. |
| `mgs-m-rss-5-sdp-v1.0` | Mars Global Surveyor radio science T-P and electron density (Mars) | NASA PDS | Hinson, D. P., et al. (1999). Initial results from radio occultation measurements with Mars Global Surveyor. *JGR*, 104(E11), 26997-27012; Tyler, G. L., et al. (2001), *JGR*, 106(E10). |
| `gp-j-entry-v1.0` | Galileo probe atmospheric structure and instruments (Jupiter) | NASA PDS | Seiff, A., et al. (1998). Thermal structure of Jupiter's atmosphere near the edge of a 5-µm hot spot in the north equatorial belt. *JGR*, 103(E10), 22857-22889. |
| `jno-x-mwr` | Juno MWR records, antenna and brightness temperatures, NH3/H2O (Jupiter) | NASA PDS | Janssen, M. A., et al. (2017). MWR: Microwave Radiometer for the Juno mission to Jupiter. *Space Science Reviews*, 213, 139-185. |
| `corss_occul_el_dens` | Cassini RSS Titan ionospheric electron density (PDS4) | NASA PDS | Kliore, A. J., et al. (2008). First results from the Cassini radio occultations of the Titan ionosphere. *JGR*, 113, A09317. |
| `hp-ssa-hasi-2-3-4-mission-v1.1` | Huygens HASI entry and descent (Titan) | NASA PDS | Fulchignoni, M., et al. (2005). In situ measurements of the physical characteristics of Titan's environment. *Nature*, 438, 785-791. |
| `issdc-mom` | Mars Orbiter Mission payloads (sign-in and import) | ISRO ISSDC | cite the payload team's reference publication |
| `issdc-ch2` | Chandrayaan-2 orbiter payloads incl. DFRS, CHACE-2 (sign-in and import) | ISRO ISSDC | cite the payload team's reference publication |

### Bundled sample products

| Folder | Product | Source |
|---|---|---|
| `sampledata/venus_akatsuki` | Akatsuki RS Level 4 profile and a UVI image | JAXA DARTS, `vco-v-rs-5-occ-v1.0` and the Akatsuki UVI archive |
| `sampledata/mars_express` | MaRS L4 neutral atmosphere and ionosphere profiles | ESA PSA, `mex-m-mrs-5-occ` |
| `sampledata/titan_cassini_rss` | Cassini RSS Titan electron density (PDS4) | NASA PDS Atmospheres, `corss_occul_el_dens` |
| `sampledata/earth_cosmic2` | COSMIC-2 radio occultation granule | UCAR COSMIC Data Analysis and Archive Center (CDAAC) |

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
  version      = {3.0.0},
  url          = {https://github.com/jovian-explorer/VEDA},
  address      = {Thiruvananthapuram, Kerala, India}
}
```

### Data availability statement (template)
Remove the archives you did not use and add the data set DOIs:

> The spacecraft observations analysed in this study are publicly available from the NASA Planetary Data System (PDS) Atmospheres Node (https://pds-atmospheres.nmsu.edu/), the ESA Planetary Science Archive (PSA) (https://archives.esac.esa.int/psa/) and the JAXA Data Archives and Transmission System (DARTS) (https://data.darts.isas.jaxa.jp/); ISRO mission data are available to registered users from the Indian Space Science Data Centre (ISSDC/PRADAN) (https://pradan.issdc.gov.in/). Spacecraft and planetary ephemerides were obtained from the NASA NAIF SPICE archive (https://naif.jpl.nasa.gov/) and the mission SPICE archives at ESA and JAXA. Archived values were read, unit-converted and compared with VEDA version 3.0.0 (https://github.com/jovian-explorer/VEDA).

---

## 5. Scientific responsibility

* VEDA's derived quantities use the equations documented in the app (**Help** and **Variables**) and in [USAGE.md](USAGE.md), with the body constants listed there. They are not a substitute for the instrument team's own retrievals.
* Check any value you intend to publish against the product label, the data set documentation (`DOCUMENT/` and `CATALOG/` in each volume) and the instrument team's publications.
* Report errors in VEDA's reading or processing at https://github.com/jovian-explorer/VEDA/issues. Report errors in the data themselves to the archive.

VEDA is not affiliated with, endorsed by or sponsored by NASA, ESA, JAXA or ISRO, and cannot guarantee that their servers are available.
