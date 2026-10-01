# Changelog

All notable changes to VEDA. Versions follow [semantic versioning](https://semver.org/). VEDA stays at 0.x until its public release; 0.1.0 and 0.2.0 were first tagged as v2.0.0 and v2.1.0.

## 0.3.0 (unreleased)

VEDA now covers nearly every payload of every mission, searchable by date, plottable, with geometry and tailored citations.

### Every payload, searched by date
- Live search of whole instrument archives for the dates you give: ESA PSA EPN-TAP (Mars Express, Venus Express, Rosetta, BepiColombo, Huygens), the NASA PDS Registry API (MAVEN, Juno, New Horizons, MESSENGER, LRO, Galileo, Magellan, MGS, MRO, Pioneer Venus, Dawn) and OPUS (Cassini, Galileo and New Horizons imaging and spectra). 106 live data sets; answers are cached per window.
- New indexed data sets: all Akatsuki cameras (UVI, IR1, IR2, LIR: raw, calibrated, geometry), MRO MCS DDR/EDR/RDR from cumulative indexes, CTX and MARCI on request, JunoCam, Juno magnetometer, Cassini INMS, Pioneer Venus ONMS. 141 data sets in all.
- Index files are read four at a time; cumulative indexes are streamed from disk.

### Plot any product
- New reader for PDS3 (ASCII and binary tables, containers, record arrays, multi-line records, images, qubes, arrays), PDS4 (binary, character and delimited tables, arrays), FITS and netCDF, memory-mapped.
- Product viewer: fields against fields and time, spectrograms, profiles per row (MCS), images and maps with stretch, transects and value read-out, cubes with per-pixel spectra. Peak-preserving decimation for large tables.
- Tolerant of common label errors (record lengths, integers labelled as floats, files shorter than their label) and clear messages when a product has no plottable layout.

### Observation geometry for all missions
- SPICE kernel sources for 17 missions (file-name coverage, PDS3 coverage tables or archive read-me tables); Pluto, Ceres, Vesta and 67P body kernels and frames.
- Kernels download automatically when a mission or observation is opened (Settings: on/off and a size limit).
- Orbit geometry for any observation: 3D orbit, ground track, altitude, local time, solar zenith, emission and phase angles.

### What to cite
- Cite panel: references for exactly the data sets and features you used (174 Crossref-verified references), archive acknowledgements, BibTeX, text and a data availability statement.

### Speed and stability
- Plots removed from the page are purged (they leaked resize handlers and memory); image-viewer listeners no longer accumulate; no backdrop blur on cards and the top bar.
- Thread-safe publication figures; SQLite WAL; Windows paths kept short for long archive URLs; folder builds instead of a onefile exe (start-up in seconds instead of a minute).

### Earlier in 0.3.0

VEDA now works only with real archive data and can search it by body, mission, payload and date.

### Breaking
- **All synthetic data removed.** The generated sample granules, the mission adapters that served them and `scripts/generate_sample_granules.py` are gone. Every mission now shows only products from its archive; the bundled samples are unmodified archive products (Akatsuki RS L4 and UVI, Mars Express MaRS L4, Cassini RSS Titan, COSMIC-2).

### Archive engine
- Reads PDS3 volume indexes (`INDEX.TAB`, format files, DARTS and PSA layouts) and PDS4 bundles into a local SQLite catalogue; products are downloaded on request with retries and atomic writes.
- **Find observations of a body by date** searches every connected data set for that body at once.
- **Archive data** per mission: choose payloads and data sets, filter by date, product type, text, profiles only or downloaded only, sort, download, open and compare.
- Connected data sets: Akatsuki RS L2 to L4 (DARTS); Mars Express MaRS L4 and Venus Express VeRa (PSA); Magellan radio occultation profiles, H2SO4 and raw records, Venus Express VeRa (PDS copy), Mars Global Surveyor RS, Galileo probe, Huygens HASI, Cassini RSS Titan ionosphere (PDS4) and Juno MWR (PDS Atmospheres).
- ISRO ISSDC (Mars Orbiter Mission, Chandrayaan-2): sign in on PRADAN, download there, then import into VEDA.

### Readers
- PDS3: stack-based label parser with quote-aware tokenising, `^STRUCTURE` format files, multiple tables per file, character columns, record repair, declared missing constants; PDS4 character and delimited tables.
- Unit-aware loading (pressure, temperature, number and electron density including scaled units, radius and altitude in metres); times from the index, label or file name, never from product creation dates.

### Plotting and analysis
- Multi-panel profiles of every quantity in a product, with the archived 1-sigma uncertainty as bands or error bars, and the product's time, location, SZA and local time.
- **Plot style**: lines, markers, palettes, uncertainty, axes (log, swapped, pressure as vertical axis), fonts, legend, and AGU, Elsevier, A&A and MNRAS templates; **Export figure** at journal column width as PNG or SVG.
- Comparisons coloured by mission, date or latitude.

### Observation geometry
- SPICE geometry for Akatsuki and Mars Express: orbit (planet-fixed and J2000), view from Earth, tangent-point map in four projections, SZA, local time and Sun-Earth-probe angle along the profile. Kernels are listed with their size and downloaded on confirmation; light time is corrected for Earth-received times.

### Documentation and terms
- New **TERMS.md** (warranty, responsibility for results, fair use of the archives, privacy). **DATA_POLICY.md** rewritten around the connected data sets, each archive's terms and the reference publications to cite. README, USAGE, third-party licenses (SpiceyPy, NAIF CSPICE, Natural Earth added; Three.js removed, as it is not used), and the in-app Help, About and Data & Licenses panels updated. Data & Licenses lists the connected data sets from the catalogue and offers a copyable data availability statement.
- CSV exports name the source file and VEDA version and state which columns are archived and which are derived.

## 0.2.0

### Science fix
- **Akatsuki temperature profile.** Column lookup took the first name that merely
  *contained* the query, so `TEMPERATURE` matched
  `PRESSURE (LOWER TEMPERATURE AT BOUNDARY)` and the Akatsuki radio-science
  profile showed pressure in pascals as temperature (up to 47,300 K). Columns are
  now matched as whole words, preferring the column that leads with the quantity,
  skipping `SIGMA` columns and using the nominal `MEDIUM` retrieval. Akatsuki now
  reads 147-288 K over 54-95 km. No other bundled profile changes. The same fix
  applies to uploaded tables, where a bare `T` could previously match `LATITUDE`.

### Stability
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

### Security
- The local API no longer allows cross-origin requests from other websites and
  checks the `Host` header (DNS rebinding). Set `VEDA_ALLOWED_HOSTS` when serving
  on a network with `veda-server --host 0.0.0.0`.
- Settings are validated and saved atomically; a damaged `settings.json`
  falls back to defaults.

### Features
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

### Interface
- Plots follow the light/dark theme; the light theme is readable throughout.
- The comparison legend no longer covers the plot title.
- Header fits on one row at laptop widths; fixed the unreadable active tab and
  unit buttons, the squeezed mission list and the observation table.

### Performance
- Text tables are parsed column-wise with NumPy instead of cell by cell.

## 0.1.0

- Installable Python package (`pip install git+https://github.com/jovian-explorer/VEDA.git`)
  with `veda` and `veda-server` commands.
- Standalone builds for Windows, macOS and Linux attached to GitHub Releases.
- Per-user data folder on every OS (`VEDA_HOME` to override); free-port fallback.
- CI on Windows, macOS and Linux.
