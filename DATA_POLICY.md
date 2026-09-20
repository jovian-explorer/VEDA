# Third-Party Planetary Data Policy, Archive Guidelines, and Citations

## 1. Scope and Scientific Objective

VEDA (Visualization, Exploration, and Data Analysis) is an open scientific computational platform designed to ingest, calibrate, analyze, visualize, and compare observations from robotic planetary spacecraft across the Solar System.

VEDA does not claim ownership, copyright, or proprietary rights over original raw, calibrated, or derived telemetry data products obtained from international space agencies. All planetary observations accessible through or bundled as demonstration data with VEDA are public scientific datasets produced by the respective spacecraft instrument teams and hosted by international planetary data archives.

---

## 2. Authoritative Planetary Data Archives

VEDA directly queries, downloads, or processes datasets governed by international planetary science archives:

### A. NASA Planetary Data System (PDS)
* **Governing Body**: National Aeronautics and Space Administration (NASA), Science Mission Directorate.
* **Archival Discipline Nodes**:
  * **Atmospheres Node** (New Mexico State University): Radio occultation soundings, thermal profiles, and atmospheric dynamics.
  * **Planetary Plasma Interactions (PPI) Node** (University of California, Los Angeles): Magnetospheric and ionospheric measurements.
  * **Geosciences Node** (Washington University in St. Louis): Surface radar, topography, and geochemical observations.
  * **Small Bodies Node** (University of Maryland): Cometary and asteroid rendezvous and flyby data.
  * **Cartography and Imaging Sciences Node** (USGS / JPL): Multi-band orbital imaging and cartographic mosaics.
* **Terms of Use**: Data hosted by NASA PDS are in the public domain and freely available to the worldwide scientific community. Users are required by scientific etiquette and NASA policy to cite the corresponding PDS dataset Digital Object Identifier (DOI), the instrument Principal Investigator (PI) team, and the host PDS node in any resulting scientific publication.

### B. ESA Planetary Science Archive (PSA)
* **Governing Body**: European Space Agency (ESA), European Space Astronomy Centre (ESAC), Madrid, Spain.
* **Missions**: Venus Express (VEX), BepiColombo, Rosetta, Mars Express (MEX).
* **Terms of Use**: Data accessible through the ESA PSA are distributed under open-access policies for scientific research following completion of the mission-defined proprietary validation period.
* **Mandatory Acknowledgment**: Publications utilizing ESA planetary data must include the standard ESA acknowledgment statement:
  > "The scientific observations utilized in this study were retrieved from the European Space Agency (ESA) Planetary Science Archive (PSA), with scientific credit to the [Spacecraft Name] [Instrument Name] Principal Investigator and Science Team."

### C. JAXA Data Archives and Transmission System (DARTS)
* **Governing Body**: Institute of Space and Astronautical Science (ISAS) / Japan Aerospace Exploration Agency (JAXA).
* **Missions**: Akatsuki (Venus Climate Orbiter / VCO), Hayabusa2, BepiColombo (MMO / Mio).
* **Terms of Use**: Science data products released on DARTS are open to researchers worldwide.
* **Mandatory Acknowledgment**: Publications utilizing JAXA planetary observations must acknowledge JAXA and the corresponding mission team:
  > "Data from the Akatsuki (VCO) mission were provided by the Japan Aerospace Exploration Agency (JAXA) through the Data Archives and Transmission System (DARTS)."

### D. ISRO Indian Space Science Data Centre (ISSDC)
* **Governing Body**: Indian Space Research Organisation (ISRO), Bengaluru, India.
* **Missions**: Chandrayaan-2, Chandrayaan-3, Mars Orbiter Mission (MOM).
* **Terms of Use**: Planetary science datasets hosted by ISSDC are accessible according to the ISRO Science Data Policy. Authors must cite ISSDC and the relevant payload Principal Investigators.

---

## 3. Mandatory Dual-Attribution Policy for Publications

When publishing peer-reviewed journal papers, conference proceedings, technical reports, or theses that incorporate figures, tables, or analytical retrievals produced with VEDA, researchers are required to provide dual attribution:

1. **Primary Dataset Citation**: Cite the primary space agency dataset, the instrument Principal Investigator team, and the specific archive DOI or reference volume.
2. **Software Platform Citation**: Cite the VEDA computational platform to ensure computational reproducibility and scientific provenance.

### Standard Citation Text for Methodologies Sections:
> "Planetary atmospheric soundings and observational datasets were analyzed using VEDA (Visualization, Exploration, and Data Analysis), an open multi-mission planetary science platform developed at the Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO (Aggarwal, 2026). Primary mission datasets were retrieved from the [NASA PDS / ESA PSA / JAXA DARTS] archive."

---

## 4. BibTeX Citation Entries

### A. VEDA Software Platform
```bibtex
@software{Aggarwal_VEDA_2026,
  author       = {Keshav Aggarwal},
  title        = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},
  year         = {2026},
  publisher    = {Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO},
  version      = {1.0.0},
  url          = {https://jovian-explorer.github.io/},
  address      = {Thiruvananthapuram, Kerala, India}
}
```

### B. Akatsuki (VCO) Radio Science (JAXA DARTS)
```bibtex
@misc{Akatsuki_RS_Level4,
  author       = {Imamura, Takeshi and Ando, Hiroki and Tellmann, Silvia and P{\"a}tzold, Martin and H{\"a}usler, Bernd},
  title        = {{Akatsuki Radio Science Level 4 Vertical Atmospheric Profiles of Venus}},
  year         = {2017},
  publisher    = {JAXA Data Archives and Transmission System (DARTS)},
  howpublished = {\url{https://darts.isas.jaxa.jp/planet/project/akatsuki/}}
}
```

### C. Venus Express VeRa Radio Science (ESA PSA)
```bibtex
@article{Haeusler_VeRa_2006,
  author       = {H{\"a}usler, Bernd and P{\"a}tzold, Martin and Tyler, G. Leonard and Simpson, Richard A. and Bird, Michael K. and Dehant, V{\'e}ronique and Barriot, Jean-Pierre and Eidel, Walter and Mattei, R. and Remus, S. and Selle, J. and Tellmann, S. and Imamura, T.},
  title        = {{Radio science investigations on Venus Express: The VeRa instrument}},
  journal      = {Planetary and Space Science},
  volume       = {54},
  number       = {13},
  pages        = {1315-1335},
  year         = {2006},
  doi          = {10.1016/j.pss.2006.04.032}
}
```

### D. New Horizons REX Radio Science (NASA PDS Atmospheres)
```bibtex
@article{Gladstone_NewHorizons_2016,
  author       = {Gladstone, G. Randall and Stern, S. Alan and Ennico, Kimberly and Olkin, Catherine B. and Weaver, Harold A. and Young, Leslie A. and Summers, Michael E. and Strobel, Darrell F. and Hinson, David P. and Kammer, Joshua A. and others},
  title        = {{The atmosphere of Pluto as observed by New Horizons}},
  journal      = {Science},
  volume       = {351},
  number       = {6279},
  pages        = {aad8866},
  year         = {2016},
  doi          = {10.1126/science.aad8866}
}
```

### E. MAVEN Radio Science and NGIMS (NASA PDS PPI / Atmospheres)
```bibtex
@article{Jakosky_MAVEN_2015,
  author       = {Jakosky, Bruce M. and Lin, R. P. and Grebowsky, J. M. and Luhmann, J. G. and Mitchell, D. L. and Beutelschies, G. and Priser, T. and Acuna, M. and Andersson, L. and Baird, D. and others},
  title        = {{The Mars Atmosphere and Volatile Evolution (MAVEN) Mission}},
  journal      = {Space Science Reviews},
  volume       = {195},
  number       = {1},
  pages        = {3-48},
  year         = {2015},
  doi          = {10.1007/s11214-015-0139-x}
}
```

### F. Cassini Radio Science Subsystem (NASA PDS Atmospheres)
```bibtex
@article{Kliore_CassiniRSS_2004,
  author       = {Kliore, Arvydas J. and Anderson, John D. and Armstrong, J. W. and Asmar, Sami W. and Hamilton, Douglas P. and Rappaport, Nicole J. and Simpson, Richard A. and Flasar, F. Michael and Nagy, Andrew F. and French, Richard G. and others},
  title        = {{Cassini Radio Science Investigations at Saturn and Titan}},
  journal      = {Space Science Reviews},
  volume       = {115},
  number       = {1},
  pages        = {1-70},
  year         = {2004},
  doi          = {10.1007/s11214-004-1436-y}
}
```

### G. Mars Orbiter Mission MENCA Investigation (ISRO ISSDC)
```bibtex
@article{Bhardwaj_MENCA_2016,
  author       = {Bhardwaj, Anil and Thampi, Smitha V. and Das, Tirtha Pratim and Dhanya, M. B. and Naik, Neha and Pant, Tarun Kumar and Pradeepkumar, P. and Sreelatha, P. and Sundar, Abhishek and Vipin, K. K. and others},
  title        = {{On the evening and morning exosphere of Mars: Results from MENCA on the Mars Orbiter Mission}},
  journal      = {Geophysical Research Letters},
  volume       = {43},
  number       = {6},
  pages        = {2388-2395},
  year         = {2016},
  doi          = {10.1002/2016GL067707}
}
```

### H. Chandrayaan-2 Dual Frequency Radio Science (ISRO ISSDC / PRADAN)
```bibtex
@article{Choudhary_DFRS_2022,
  author       = {Choudhary, R. K. and Ambili, K. M. and Thampi, Smitha V. and Bhardwaj, Anil},
  title        = {{Dual Frequency Radio Science (DFRS) experiment onboard Chandrayaan-2: Detection of lunar ionosphere}},
  journal      = {Current Science},
  volume       = {122},
  number       = {2},
  pages        = {186-193},
  year         = {2022},
  doi          = {10.18520/cs/v122/i2/186-193}
}
```

---

## 5. Scientific Integrity and Algorithmic Provenance

1. **Deterministic Calculations**: VEDA implements verified equations for:
   * Hydrostatic equilibrium: $dP/dz = -\rho(z) g(z)$
   * Altitude-dependent gravity: $g(z) = g_0 (R_p / (R_p + z))^2$
   * Poisson potential temperature: $\theta(z) = T(z) (P_0 / P(z))^\kappa$
   * Brunt-Vaisala static stability: $N^2(z) = (g(z)/\theta(z)) (\partial \theta / \partial z)$
   * Gravity wave potential energy: $E_p(z) = \frac{1}{2}(g/N)^2 \overline{(T' / \overline{T})^2}$
   * Radio occultation Abel inversion: $\mu(r) - 1 = \frac{1}{\pi} \int_r^{r_{top}} \frac{\alpha(a)}{\sqrt{a^2 - r^2}} da$
2. **User Validation Responsibility**: VEDA is an analytical tool. Researchers retain full scientific responsibility for verifying that derived values align with peer-reviewed mission calibration documents and published literature before incorporating results into academic papers.
3. **Upstream Archive Independence**: VEDA is not affiliated with, endorsed by, or sponsored by NASA, ESA, JAXA, or ISRO. VEDA cannot guarantee continuous server availability, bandwidth, or uninterrupted access to remote third-party data repositories.
