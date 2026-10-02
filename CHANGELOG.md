# Changelog

All notable changes to VEDA. VEDA is pre-release software at version **0.0.1** until the repository is published; the public release will be **1.0.0**. The version number does not change before then. Work done during development is recorded below as milestones (the first two were briefly tagged v2.0.0 and v2.1.0; those tags are withdrawn).

## 0.0.1 (pre-release, in development)

### Milestone 5 (2026-10-02): reconciliation and scientific corrections

#### Science
- **Temperature-dependent heat capacity** for Venus, Mars, Titan and Pluto: cp(T) from the JANAF ideal-gas tables of the main constituents, weighted by composition (Mars 740 J/(kg K) at 200 K instead of a fixed 830; Venus 850 at 300 K rising to 1140 at 735 K). Used for N^2, the new dry adiabatic lapse rate g/cp(T) and the speed of sound; potential temperature keeps the conventional constant kappa at the reference cp.
- N^2, buoyancy period and dry adiabatic lapse rate are computed from temperature alone (they were skipped for profiles without a pressure column).
- Removed a second, Earth-constant implementation of potential temperature and N^2 (dry-air R and cp, 1000 hPa) that was not used by the app, so every derived value comes from one body-aware implementation.
- **Comparisons**: pressure, densities and electron density are interpolated and averaged in log space (geometric mean, multiplicative spread); the spread is the sample standard deviation and is shown only where at least two profiles overlap; data gaps are no longer bridged; altitudes below the reference level (Hellas and the northern lowlands lie below the 3389.5 km Mars reference sphere, the Galileo probe went below 1 bar) are kept instead of cut at 0 km, and gravity is computed correctly there.
- **One vertical reference for comparisons**: altitudes are measured from the body's reference sphere for every mission. Magellan RSS altitudes, given above 6052 km, are moved up 0.2 km onto the 6051.8 km Venus reference used for VEX radii. Each profile shows its altitude reference, and a comparison that mixes references (the Galileo probe's 1-bar level, the Huygens landing site) says so.
- New analytic tests: isothermal Mars (scale height, N^2 = g^2/(cp T), density, sound speed), a true dry adiabat through the deep Venus atmosphere (N^2 = 0 with cp(T)), potential temperature at the reference pressure, Chapman-layer TEC.

#### Data sources
- **MRO radio occultation profiles** (`mrors_2001`, MRO-M-RSS-5-TPS-V1.0, D. Hinson): 186 temperature-pressure-density profiles with uncertainties, 2008 to 2012, from the PDS Atmospheres Node; they compare directly with MGS and MEX profiles (same radius-based vertical reference). Cited as Hinson et al. (2008), Icarus 193, 125-138.
- **FTP fallback**: the PDS Atmospheres and Geosciences nodes and the ESA SPICE server also serve their trees over anonymous FTP; when HTTPS fails (server busy or down, not a missing file), VEDA retries the same path over FTP. The PDS Rings, PPI and NAIF nodes, ESA PSA and JAXA DARTS have no FTP that answers (checked 2026-10-02) and are read over HTTPS.
- **Mirror archives**: a data set can name other archives holding the same volumes. Mars Express MaRS occultation profiles come from ESA PSA and, when PSA fails, from the identical copy at the PDS Geosciences Node (same index and paths, volumes named mexmrs_9xxx), which also serves FTP.
- A 403 from a public archive (the PDS Rings Node sheds load this way) is retried with back-off instead of failing at once.

#### Reading products
- **Byte-order repair**: floats written in the opposite byte order to their label (Juno JIRAM RDR spectra are labelled MSB but written LSB) are detected from the values (about 70 orders of magnitude of spread and NaNs, against a few for the swapped bytes) and read correctly. Previously these spectra plotted as noise around 1e38.
- **Text products** (operations logs, PDS3 TEXT/DOCUMENT objects, PDS4 Stream_Text) open in the viewer as searchable text with a Save button, instead of the message "cannot be plotted". The data file of a live PDS4 product is now always downloaded, even when it is a .txt (it was skipped as an optional description).
- Opening a product shows download progress (MB received of the total).
- Signalling NaNs in data files no longer raise warnings.
- **Large files ask first**: opening a product whose data file is larger than the new *Large-file limit* setting (default 250 MB) shows its size and an estimated download time, with a button to download it, instead of starting a download of possibly over an hour (Juno UVS photon lists are about 1.2 GB).

#### Clean-up
- Version is 0.0.1 until the public 1.0.0 release; the v2.0.0 and v2.1.0 tags and releases are withdrawn. Release builds of 0.x tags are marked as pre-releases.
- Removed the unused COSMIC-2 (Earth) reader, adapter, samples and references (Earth is outside VEDA's scope), the COSMIC-era API client calls to endpoints VEDA never had, and unused client state.

### Milestone 4 (2026-10-01): every payload, geometry for all missions, citations

VEDA now covers nearly every payload of every mission, searchable by date, plottable, with geometry and tailored citations.

#### Every payload, searched by date
- Live search of whole instrument archives for the dates you give: ESA PSA EPN-TAP (Mars Express, Venus Express, Rosetta, BepiColombo, Huygens), the NASA PDS Registry API (MAVEN, Juno, New Horizons, MESSENGER, LRO, Galileo, Magellan, MGS, MRO, Pioneer Venus, Dawn) and OPUS (Cassini, Galileo and New Horizons imaging and spectra). 106 live data sets; answers are cached per window.
- New indexed data sets: all Akatsuki cameras (UVI, IR1, IR2, LIR: raw, calibrated, geometry), MRO MCS DDR/EDR/RDR from cumulative indexes, CTX and MARCI on request, JunoCam, Juno magnetometer, Cassini INMS, Pioneer Venus ONMS. 141 data sets in all.
- Index files are read four at a time; cumulative indexes are streamed from disk.

#### Plot any product
- New reader for PDS3 (ASCII and binary tables, containers, record arrays, multi-line records, images, qubes, arrays), PDS4 (binary, character and delimited tables, arrays), FITS and netCDF, memory-mapped.
- Product viewer: fields against fields and time, spectrograms, profiles per row (MCS), images and maps with stretch, transects and value read-out, cubes with per-pixel spectra. Peak-preserving decimation for large tables.
- Tolerant of common label errors (record lengths, integers labelled as floats, files shorter than their label) and clear messages when a product has no plottable layout.

#### Observation geometry for all missions
- SPICE kernel sources for 17 missions (file-name coverage, PDS3 coverage tables or archive read-me tables); Pluto, Ceres, Vesta and 67P body kernels and frames.
- Kernels download automatically when a mission or observation is opened (Settings: on/off and a size limit).
- Orbit geometry for any observation: 3D orbit, ground track, altitude, local time, solar zenith, emission and phase angles.

#### What to cite
- Cite panel: references for exactly the data sets and features you used (172 references with Crossref-verified DOIs), archive acknowledgements, BibTeX, text and a data availability statement.

#### Speed and stability
- Plots removed from the page are purged (they leaked resize handlers and memory); image-viewer listeners no longer accumulate; no backdrop blur on cards and the top bar.
- Thread-safe publication figures; SQLite WAL; Windows paths kept short for long archive URLs; folder builds instead of a onefile exe (start-up in seconds instead of a minute).

### Milestone 3 (2026-10-01): real archive data only

VEDA now works only with real archive data and can search it by body, mission, payload and date.

#### Breaking
- **All synthetic data removed.** The generated sample granules, the mission adapters that served them and `scripts/generate_sample_granules.py` are gone. Every mission now shows only products from its archive; the bundled samples are unmodified archive products (Akatsuki RS L4 and UVI, Mars Express MaRS L4, Cassini RSS Titan, COSMIC-2).

#### Archive engine
- Reads PDS3 volume indexes (`INDEX.TAB`, format files, DARTS and PSA layouts) and PDS4 bundles into a local SQLite catalogue; products are downloaded on request with retries and atomic writes.
- **Find observations of a body by date** searches every connected data set for that body at once.
- **Archive data** per mission: choose payloads and data sets, filter by date, product type, text, profiles only or downloaded only, sort, download, open and compare.
- Connected data sets: Akatsuki RS L2 to L4 (DARTS); Mars Express MaRS L4 and Venus Express VeRa (PSA); Magellan radio occultation profiles, H2SO4 and raw records, Venus Express VeRa (PDS copy), Mars Global Surveyor RS, Galileo probe, Huygens HASI, Cassini RSS Titan ionosphere (PDS4) and Juno MWR (PDS Atmospheres).
- ISRO ISSDC (Mars Orbiter Mission, Chandrayaan-2): sign in on PRADAN, download there, then import into VEDA.

#### Readers
- PDS3: stack-based label parser with quote-aware tokenising, `^STRUCTURE` format files, multiple tables per file, character columns, record repair, declared missing constants; PDS4 character and delimited tables.
- Unit-aware loading (pressure, temperature, number and electron density including scaled units, radius and altitude in metres); times from the index, label or file name, never from product creation dates.

#### Plotting and analysis
- Multi-panel profiles of every quantity in a product, with the archived 1-sigma uncertainty as bands or error bars, and the product's time, location, SZA and local time.
- **Plot style**: lines, markers, palettes, uncertainty, axes (log, swapped, pressure as vertical axis), fonts, legend, and AGU, Elsevier, A&A and MNRAS templates; **Export figure** at journal column width as PNG or SVG.
- Comparisons coloured by mission, date or latitude.

#### Observation geometry
- SPICE geometry for Akatsuki and Mars Express: orbit (planet-fixed and J2000), view from Earth, tangent-point map in four projections, SZA, local time and Sun-Earth-probe angle along the profile. Kernels are listed with their size and downloaded on confirmation; light time is corrected for Earth-received times.

#### Documentation and terms
- New **TERMS.md** (warranty, responsibility for results, fair use of the archives, privacy). **DATA_POLICY.md** rewritten around the connected data sets, each archive's terms and the reference publications to cite. README, USAGE, third-party licenses (SpiceyPy, NAIF CSPICE, Natural Earth added; Three.js removed, as it is not used), and the in-app Help, About and Data & Licenses panels updated. Data & Licenses lists the connected data sets from the catalogue and offers a copyable data availability statement.
- CSV exports name the source file and VEDA version and state which columns are archived and which are derived.

### Milestone 2 (2026-10-01, briefly tagged v2.1.0): science fixes, stability, security

#### Science fix
- **Akatsuki temperature profile.** Column lookup took the first name that merely
  *contained* the query, so `TEMPERATURE` matched
  `PRESSURE (LOWER TEMPERATURE AT BOUNDARY)` and the Akatsuki radio-science
  profile showed pressure in pascals as temperature (up to 47,300 K). Columns are
  now matched as whole words, preferring the column that leads with the quantity,
  skipping `SIGMA` columns and using the nominal `MEDIUM` retrieval. Akatsuki now
  reads 147-288 K over 54-95 km. No other bundled profile changes. The same fix
  applies to uploaded tables, where a bare `T` could previously match `LATITUDE`.

#### Stability
- The multi-mission comparison crashed on every body when no selected
  observation carried the chosen variable; it now explains what to do.
- Uploaded images opened in the profile viewer and failed; they open in the
  image viewer.
- **Load File** opened the file picker twice and parsed each file twice.
- Uploads are stored one folder per file, so a new upload never reuses a stale
  companion table from an earlier one, and deleting one never breaks another.
- The API returns clear 4xx messages instead of 500 errors for bad figure,
  image and histogram requests, and never includes server paths.
- Image sub-routes (render, histogram) were shadowed by the image route and
  returned 404.
- Three Workflow Guide buttons did nothing.

#### Security
- The local API no longer allows cross-origin requests from other websites and
  checks the `Host` header (DNS rebinding). Set `VEDA_ALLOWED_HOSTS` when serving
  on a network with `veda-server --host 0.0.0.0`.
- Settings are validated and saved atomically; a damaged `settings.json`
  falls back to defaults.

#### Features
- Select or drop several files at once; a PDS3 `.lbl` is sent with its `.tab`.
- Recently loaded files are kept under the *user_imported* mission.
- Settings now all take effect: theme (dark, light, follow system), font size,
  default temperature and pressure units, start-up body and mission,
  publication-figure DPI, online downloads on/off and download timeout,
  plus **Reset to defaults** and links to the data folders.
- The bar / Pa unit buttons now really convert the comparison plot.
- About shows the running version, repository links, a citation for the
  current version (with Copy) and install paths.
- Help is searchable and covers loading files, units, keyboard use and
  troubleshooting.
- Download failures explain the cause (offline, timeout, file removed).

#### Interface
- Plots follow the light/dark theme; the light theme is readable throughout.
- The comparison legend no longer covers the plot title.
- Header fits on one row at laptop widths; fixed the unreadable active tab and
  unit buttons, the squeezed mission list and the observation table.

#### Performance
- Text tables are parsed column-wise with NumPy instead of cell by cell.

### Milestone 1 (2026-09-30, briefly tagged v2.0.0): packaging and first builds

- Installable Python package (`pip install git+https://github.com/jovian-explorer/VEDA.git`)
  with `veda` and `veda-server` commands.
- Standalone builds for Windows, macOS and Linux attached to GitHub Releases.
- Per-user data folder on every OS (`VEDA_HOME` to override); free-port fallback.
- CI on Windows, macOS and Linux.
