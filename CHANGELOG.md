# Changelog

All notable changes to VEDA. Versions follow [semantic versioning](https://semver.org/).

## 2.1.0

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

## 2.0.0

- Installable Python package (`pip install git+https://github.com/jovian-explorer/VEDA.git`)
  with `veda` and `veda-server` commands.
- Standalone builds for Windows, macOS and Linux attached to GitHub Releases.
- Per-user data folder on every OS (`VEDA_HOME` to override); free-port fallback.
- CI on Windows, macOS and Linux.
