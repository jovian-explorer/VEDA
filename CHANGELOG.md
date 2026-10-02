# Changelog

All notable changes to VEDA. Versions follow [semantic versioning](https://semver.org/): 0.x releases are public and in active development (feedback from users shapes them), 1.0.0 will mark a stable interface.

## Unreleased

### Data
- **Venus Express temperature profiles**, which PSA and PDS do not hold, from the teams' research data repositories (all CC-BY-4.0):
  - VeRa radio occultations of 2014 (NASA DSN), 25 profiles with time, latitude, longitude, solar zenith angle and local time (Gramigna et al. 2023; Zenodo doi:10.5281/zenodo.20056665);
  - VeRa radio occultations 2006-2009 retrieved by Full Spectrum Inversion, 32 profiles with date, latitude and local time (Imamura et al. 2018; Zenodo doi:10.5281/zenodo.4621070). Below the lowest valid level these files hold the number density constant, which made the derived temperatures wrong (800 K at 39 km); those rows are masked;
  - SPICAV-SOIR solar occultations 2006-2014, 644 profiles of CO2 density, pressure and temperature from about 70 to 170 km at the terminator, with uncertainties (Mahieux et al. 2015; BIRA-IASB doi:10.18758/71021089).
- A new kind of source, research data repositories (Zenodo and institutional archives): profiles without PDS labels are described by the data set (columns and units) and rewritten as small normalised CSV files.
- Venus Express instruments SPICAV-SOIR, SPICAV, ASPERA-4 and MAG added to the mission.

### Loading your own files
- **Load dialog**: before a table is read, VEDA shows its columns (unit in the file, first values, range) and asks what each column is and in which unit, and what the file is (body, mission, instrument, observation time). Headerless files can be read. The choices are saved with the file and offered for the next one; loaded profiles carry the mission and instrument in legends and colours and are included in filtered comparisons.
- **Fixes**: a pressure column in hPa was divided by 100 (the unit test for Pascal also matched "HPA"); loaded files were all given the time 2026-01-01T12:00, which then appeared as an observation time (now the label's time, the one you enter, or none); Celsius was guessed from the median value on some bodies only (now from the label unit, or values below zero).
- Header units written as `name [unit]` or `name (unit)` and `# KEY=value` metadata lines are read from text tables.

### Plots
- **Log axes** (pressure, densities) showed minor ticks as bare digits ("5 6 7 8 9 0.1 2 3", where 5 meant 0.05) and SI prefixes ("100μ" for 1e-4), which read as wrong values after a unit change. Axes spanning less than about three decades now have 1-2-5 ticks with full values (0.05, 0.1, 0.2, 0.5 ...), wider ones one tick per decade as powers of ten; every axis uses powers of ten instead of SI prefixes.
- **Axis limits** set in Plot style applied to whatever was plotted next: limits typed for temperature in K stayed on the axis after switching to °C or to pressure. They now belong to the axis they were set for (variable and unit) and stop applying when that changes.

## 0.1.0 (2026-10-02): first public release

The first public release. It contains all the work below, done while the repository was private (version 0.0.1; the first two milestones were briefly tagged v2.0.0 and v2.1.0, tags since withdrawn).

### Release
- Repository public; downloads for Windows, macOS and Linux on the Releases page (no longer pre-releases).
- **Feedback** button in the toolbar and issue templates for problems and suggestions.
- Author affiliation: student visitor at the Space Physics Laboratory (SPL), VSSC, ISRO. Copyright is held by the author; VEDA is not published by an institution.
- Exports work in the desktop window (pywebview blocked downloads, so CSV, figure and BibTeX exports did nothing there).
- Faster first use: opening a downloaded product no longer retries its missing optional description files (the first Mars comparison took 24 s, now 0.2 s); one TLS context for all archive connections (the CA bundle was loaded again for every new connection, 1.4 s each); heavy scientific modules are imported in the background at start-up.
- `CITATION.cff` for GitHub's "Cite this repository".
- **Composite mean** is shown only where at least two profiles and at least half of the compared profiles overlap: where only one profile reached a level, the "mean" jumped to that profile's values (seen at the bottom and top of Mars comparisons).

### Milestone 5 (2026-10-02): reconciliation and scientific corrections

#### Science
- **Temperature-dependent heat capacity** for Venus, Mars, Titan and Pluto: cp(T) from the JANAF ideal-gas tables of the main constituents, weighted by composition (Mars 740 J/(kg K) at 200 K instead of a fixed 830; Venus 850 at 300 K rising to 1140 at 735 K). Used for N^2, the new dry adiabatic lapse rate g/cp(T) and the speed of sound; potential temperature keeps the conventional constant kappa at the reference cp.
- N^2, buoyancy period and dry adiabatic lapse rate are computed from temperature alone (they were skipped for profiles without a pressure column).
- Removed a second, Earth-constant implementation of potential temperature and N^2 (dry-air R and cp, 1000 hPa) that was not used by the app, so every derived value comes from one body-aware implementation.
- **Comparisons**: pressure, densities and electron density are interpolated and averaged in log space (geometric mean, multiplicative spread); the spread is the sample standard deviation and is shown only where at least two profiles overlap; data gaps are no longer bridged; altitudes below the reference level (Hellas and the northern lowlands lie below the 3389.5 km Mars reference sphere, the Galileo probe went below 1 bar) are kept instead of cut at 0 km, and gravity is computed correctly there.
- **One vertical reference for comparisons**: altitudes are measured from the body's reference sphere for every mission. Magellan RSS altitudes, given above 6052 km, are moved up 0.2 km onto the 6051.8 km Venus reference used for VEX radii. Each profile shows its altitude reference, and a comparison that mixes references (the Galileo probe's 1-bar level, the Huygens landing site) says so.
- **Vertical derivatives** no longer blow up at repeated altitudes: the old guard moved duplicates 1e-6 km apart, which turned any difference into a gradient of order 1e6 K/km. Duplicates are now averaged, and every derivative is a central difference over the neighbouring levels but never over less than +-50 m, so lapse rate and N^2 of entry profiles, and of the VEGA 2 lander after touchdown (altitude jitter of a few metres at constant temperature), are not dominated by noise.
- Zero or negative temperatures, pressures and densities are treated as fill (MER and Phoenix mark missing levels with -1).
- New analytic tests: isothermal Mars (scale height, N^2 = g^2/(cp T), density, sound speed), a true dry adiabat through the deep Venus atmosphere (N^2 = 0 with cp(T)), potential temperature at the reference pressure, Chapman-layer TEC.

#### Data sources
- **MRO radio occultation profiles** (`mrors_2001`, MRO-M-RSS-5-TPS-V1.0, D. Hinson): 186 temperature-pressure-density profiles with uncertainties, 2008 to 2012, from the PDS Atmospheres Node; they compare directly with MGS and MEX profiles (same radius-based vertical reference). Cited as Hinson et al. (2008), Icarus 193, 125-138.
- **Mars entry profiles**: density, pressure and temperature from the entries of Spirit and Opportunity (2004), Phoenix (2008, 68 N), Curiosity (2012) and InSight (2018), each with uncertainties, from the PDS Atmospheres Node. InSight's altitudes are read from its radial distance, because its altitude column is above 3396.19 km rather than the 3389.5 km Mars reference used everywhere else.
- **Choosing profiles to compare**: the multi-mission comparison takes a date range, latitude band, local solar time range (wrapping midnight), solar zenith angle range and a number of profiles per mission. Profiles come from the whole archive catalogue, spread evenly over the dates, downloaded when needed, and filtered on their geometry once read; a per-mission report says how many were found, read, kept and why others were left out. It used to compare one arbitrary downloaded profile per mission.
- **Exports match the screen**: the comparison CSV and the publication figure used to be recomputed from default profiles, ignoring hand-picked ones; they now use exactly the comparison on screen. The publication figure plots pressure and densities on a log axis, has one legend entry per mission with the number of profiles, states the number and dates of the profiles, and notes mixed altitude references.
- **Comparison grid** levels fall on whole multiples of the step (20.0, 20.5 km), not offsets from the lowest sample.
- **Time ranges in the product viewer**: From/To limits a table to a time or X range before decimation, and zooming re-reads the zoomed range, so decimation never hides fine structure. "Row number" as the X axis now works for tables that have a time column (it used to fall back to time).
- **Fix**: the product viewer dropped the last rows of ASCII tables whose ROW_BYTES leaves out the line end (every Mars Express MaRS profile lost its last two rows, the lowest altitudes of an ingress occultation). Profile loading was not affected.
- **Mission catalogue**: counts per category, a target-body filter and a search box; landers, rovers and probes have their own badge instead of "Orbiter". The Mars and Venus mission lists now include every mission with data sets there (MER, Phoenix, MSL, InSight; VEGA, MESSENGER and Galileo at Venus).
- **Akatsuki to the end of the mission**: the PDS4 bundles at JAXA DARTS (data.darts.isas.jaxa.jp/pub/pds4) add UVI and LIR images from December 2021 to March 2024, which the PDS3 volumes do not have (40,490 UVI and about 400,000 LIR products, 2010-2024). LIR includes the L2d brightness temperatures with the 2023 in-orbit recalibration (updated scaling, offset, shutter and baffle tables and spectral response; Taguchi et al. 2023), the L3d longitude-latitude maps and geometry. Indexing walks the per-orbit folders in parallel (UVI in under a minute).
- **Maps from grid-cell tables**: tables of (longitude, latitude, values) on a regular grid, such as LIR L3d, open as maps with longitude and latitude axes, one per value column. The L3d label gives the mapped value as a radiance in W/(m^2 sr m), but the values are brightness temperatures; VEDA labels them in K and says so.
- The radio science PDS4 bundle at DARTS holds the same occultations (2016-2024) as the PDS3 volumes VEDA already reads, so it is not added twice.
- **VEGA 2 lander descent profile** (pressure and temperature from 63 km to the surface, June 1985; Lorenz et al. 2018), with the VEGA 1 and 2 balloon records (time series near 54 km) as tables. Altitudes are above the landing site. VEGA mission added.
- **Pioneer Venus Orbiter radio occultations** (PDS4 bundle pvoro, recovered by Withers et al. 2020): 22 temperature-pressure profiles and 93 electron density profiles from NSSDC tapes, 24 temperature profiles digitised from Kliore & Patel (1982), with SPICE-derived latitude, longitude, solar zenith angle and local time; 1978-1989. The temperature retrieval with a 200 K upper boundary is used (as in the source paper), and half the spread between the 150 K and 250 K retrievals is given as its uncertainty (0.02 K at 55 km, about 6 K at 85 km). Products without altitude (Kliore & Patel 1980) and the digitised electron densities, whose observation times the archive calls ambiguous, open as tables but are not offered as profiles.
- **Cassini radio occultations of Titan** (Schinder et al.): 20 temperature-pressure-density profiles from the surface to about 300 km, 2006-2016, each with 1-sigma errors combined in quadrature from the archive's two independent error files (spacecraft ephemeris and thermal noise). Checked: 92.9 K and 1452 hPa at the surface for the November 2008 egress, against Huygens' 93.7 K and 1467 hPa in situ.
- **Cassini Saturn ionosphere** (60 radio occultation electron density profiles, 2005-2013, Kliore et al. 2009, re-referenced by P. Schinder to the 1-bar NAIF ellipsoid) and **Saturn thermosphere** (73 UVIS stellar occultation profiles of H2 density and temperature, 2005-2017, Koskinen et al. 2015). Each keeps its archive's vertical reference (ellipsoid or 1-bar level) and says so. The electron density error bar, given as a full width, is halved to 1 sigma; zero means "not given".
- **Unit fix**: number densities given in cm^-3 (Cassini) were stored as if in m^-3, and mass densities in g/cm^3 as if in kg/m^3; both are now converted from the label units. Data sets in m^-3 and kg/m^3 (MGS, MRO, MEX, Magellan, the Mars landers) were not affected.
- PDS4 products with a one-row header table before the data (PVO) are read correctly: the largest table is the data, header values become metadata (location, angles).
- Data sets can declare fill values that a label states only in prose (PVO: -9, 0 and 1e9 for "undefined").
- Four lander missions added: MER, Phoenix, MSL and InSight.
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
- Version reset to 0.0.1 for private development; the v2.0.0 and v2.1.0 tags and releases were withdrawn and 0.0.x builds marked as pre-releases.
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
