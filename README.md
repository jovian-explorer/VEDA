<p align="center">
  <img src="src/veda/frontend/img/veda_logo.png" width="140" alt="VEDA emblem" />
</p>

# VEDA: Visualization, Exploration, and Data Analysis

**VEDA** is a desktop laboratory for planetary atmosphere and ionosphere data. Pick a planet or moon and a date range, and VEDA finds every product the official archives hold for it across all connected missions. You can then download the products, plot them, derive physical parameters, compare observations and compute the observation geometry with SPICE.

All data shown in VEDA come straight from the mission archives (NASA PDS, ESA PSA, JAXA DARTS, ISRO ISSDC). Nothing is simulated.

---

## Documentation

* **[User guide](USAGE.md)**: searching, plotting, comparison, geometry, export, settings and troubleshooting.
* **[Data policy and citations](DATA_POLICY.md)**: the archives and data sets VEDA reads, their terms, and what to cite.
* **[Terms of use](TERMS.md)**: warranty, responsibility for results, archive etiquette and privacy.
* **[License (MIT)](LICENSE)** and **[third-party licenses](THIRD_PARTY_LICENSES.md)**.
* **[Contributing](CONTRIBUTING.md)** and **[changelog](CHANGELOG.md)**.

![Multi-mission comparison of Venus (dark theme)](docs/screenshots/body-comparison-dark.png)

| Comparison, light theme | Mission view | Settings |
|---|---|---|
| ![](docs/screenshots/comparison-light.png) | ![](docs/screenshots/mission-light.png) | ![](docs/screenshots/settings.png) |

---

## What you can do

### Find observations by body and date
In **By Celestial Body**, the *Find observations of ...* panel searches every connected data set for that body over the dates you give, for example all Mars occultations from Mars Express and Mars Global Surveyor in July 2005. Results show mission, UTC time, product, type, payload and level, and whether the product is already downloaded. Open one to plot it, tick several to compare them, or download them for offline work.

### Browse a mission by payload
In **By Planetary Mission**, *Archive data* lists the mission's payloads and data sets (instrument, processing level, archive). Choose the ones you want and filter by date, product type, free text (product id, orbit), profiles only or downloaded only, oldest or newest first.

VEDA reads each archive's own catalogue (PDS3 volume indexes, PDS4 bundles) into a local SQLite index the first time, so later searches are instant and work offline. Products are downloaded on demand into a cache, with retries, and each file is written in full before it is used.

### Connected data sets

| Body | Mission | Data | Archive |
|---|---|---|---|
| Venus | Akatsuki | Radio occultation L2 (frequency, power), L3 refractivity, L4 temperature, pressure, density | JAXA DARTS |
| Venus | Venus Express | VeRa radio science L1A to L2 (ESA PSA) and the PDS copy with calibration files | ESA PSA, NASA PDS |
| Venus | Magellan | Radio occultation (Oct 1991): T, P, density, refractivity; 13 cm absorptivity and H2SO4; raw ODR/TDF | NASA PDS |
| Mars | Mars Express | MaRS L4 neutral atmosphere and ionosphere profiles | ESA PSA |
| Mars | Mars Global Surveyor | Radio science T-P and electron density profiles | NASA PDS |
| Mars | Mars Orbiter Mission | All payloads, via sign-in and import | ISRO ISSDC |
| Moon | Chandrayaan-2 | Orbiter payloads incl. DFRS and CHACE-2, via sign-in and import | ISRO ISSDC |
| Jupiter | Galileo probe | Atmospheric structure descent profile and probe instrument data | NASA PDS |
| Jupiter | Juno | MWR raw records, antenna and brightness temperatures, NH3/H2O | NASA PDS |
| Titan | Cassini RSS | Ionospheric electron density profiles (PDS4) | NASA PDS |
| Titan | Huygens | HASI entry and descent profiles | NASA PDS |

ISRO's PRADAN portal requires a free account, so VEDA opens it for you to sign in; you download there and use **Import downloaded files**. VEDA never sees your password.

### Plot and derive
An opened profile shows every quantity in the product (temperature, pressure, number or electron density, refractivity, absorptivity, H2SO4 and so on) with the archived 1-sigma uncertainty where the product gives one, and the time, latitude, longitude, solar zenith angle and local time stored with it. Units are read from the label and converted (Pa, hPa, bar, mbar; K and degrees C; m^-3 and cm^-3, including scaled units).

From temperature and pressure VEDA derives, with the body's own constants ($R_{spec}, c_p, g_0, P_{ref}$):

* Lapse rate $\Gamma = -dT/dz$ and gravity $g(z) = g_0 (R_p/(R_p+z))^2$
* Scale height $H = R_{spec} T / g$ and speed of sound
* Potential temperature $\theta = T (P_0/P)^{R_{spec}/c_p}$ and mass density $\rho = P/(R_{spec} T)$
* Brunt-Vaisala frequency $N^2 = \frac{g}{T}\left(\frac{dT}{dz} + \frac{g}{c_p}\right)$ and buoyancy period
* Tropopause, gravity-wave temperature perturbations and potential energy
* For ionospheres, the peak height and density and $\text{VTEC} = 10^{-7}\int N_e\,dz$ (TECU)

### Compare observations
Selected profiles from any missions are interpolated onto a common altitude grid and drawn with their mean and 1-sigma spread. Colour the curves by mission, date or latitude, switch the variable and units, and export the comparison table as CSV.

### Style and export figures
**Plot style** controls lines, markers, palettes, uncertainty bands or error bars, linear or log axes, swapped axes, altitude or pressure as the vertical axis, grid, ticks, fonts and legend, with journal templates for AGU, Elsevier (Icarus/PSS), A&A and MNRAS. **Export figure** writes PNG at a chosen DPI or vector SVG at the journal's single- or double-column width. The body view also renders a Matplotlib publication figure.

### Observation geometry with SPICE
**Geometry** on an opened profile computes, with NAIF SPICE, the spacecraft orbit around the occultation (planet-fixed and inertial J2000), the view from Earth in the sky plane, the tangent-point track on a map (cylindrical, north or south polar, orthographic) and SZA, local solar time and Sun-Earth-probe angle along the profile. VEDA lists the kernels it needs and downloads them when you agree (generic kernels from NAIF, mission kernels from ESA and JAXA). Radio-science times are treated as Earth-received and corrected for light time; the result agrees with the archived tangent radii to about 1 km for Mars Express and with Akatsuki's published SZA and local time to about 0.01 degrees. Available for Akatsuki and Mars Express; other missions show the track stored in the product.

### Your own files
**Load File** or drag and drop: PDS3 (`.lbl` + `.tab`), PDS4 (`.xml` + table), CSV and text tables, FITS images and PNG/JPEG. FITS images open in a viewer with ZScale, percentile, linear, log, sqrt, asinh and histogram-equalised stretches, colour maps, a pixel inspector, line transects and histograms.

### Readers
Pure-Python PDS3 and PDS4 table readers: nested objects, `^STRUCTURE` format files, multiple tables per file, fixed-width and delimited records, character columns, declared missing constants, repaired broken records, and whole-word column matching that prefers the nominal retrieval and skips uncertainty columns.

---

## Installation

### Option A: download the app (no Python needed)
Open the [latest release](https://github.com/jovian-explorer/VEDA/releases/latest) and download the archive for your OS:

| OS | Asset | Run |
|---|---|---|
| Windows 10/11 (x64) | `VEDA-<version>-windows-x86_64.zip` | unzip, double-click `VEDA.exe` |
| macOS (Apple Silicon) | `VEDA-<version>-macos-arm64.zip` | unzip, right-click `VEDA.app` > Open the first time (the app is not notarized) |
| Linux (x86_64) | `VEDA-<version>-linux-x86_64.zip` | unzip, `chmod +x VEDA && ./VEDA` |

While the repository is private you need to be signed in to GitHub with access to it.

### Option B: install with pip (any OS, Python 3.10+)
```bash
pip install "git+https://github.com/jovian-explorer/VEDA.git"
veda                  # desktop window (falls back to the browser)
veda --browser        # always use the default browser
veda-server           # headless API + web UI, prints the URL
python -m veda        # same as `veda`
```
Add `[netcdf]` (`pip install "veda[netcdf] @ git+https://github.com/jovian-explorer/VEDA.git"`) to read HDF5-backed netCDF4 files; classic netCDF3 files work without it.

### Option C: development setup
```bash
git clone https://github.com/jovian-explorer/VEDA.git
cd VEDA
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Running

| Command | What it does |
|---|---|
| `veda` | Starts the backend on a free local port (8765 or the next free one) and opens the native window |
| `veda --browser` | Same, but opens your default browser |
| `veda --no-window --port 8765` | Server only; open `http://127.0.0.1:8765/` yourself |
| `veda-server --host 0.0.0.0` | Serve on your network (the API has no authentication, so only do this on a trusted network) |

The interactive REST API documentation is at `/api/docs` on the same address. The archive endpoints are under `/api/veda/archive` (data sets, index, search, fetch, profile) and `/api/veda/geometry`.

**Where VEDA keeps your files** (archive index, downloaded products, SPICE kernels, exports, settings, logs):

| OS | Location |
|---|---|
| Windows | `%LOCALAPPDATA%\VEDA` |
| macOS | `~/Library/Application Support/VEDA` |
| Linux | `$XDG_DATA_HOME/VEDA` (default `~/.local/share/VEDA`) |

Set `VEDA_HOME` to use a different folder. Deleting the cache folder is safe; VEDA downloads again what it needs.

An internet connection is needed to search an archive for the first time, to download products and to fetch SPICE kernels. The bundled sample products (Akatsuki, Mars Express, Cassini) work offline. Turn **Settings > Network > Allow downloads** off to work fully offline.

## Building the standalone app

```bash
pip install -e ".[build]"
python scripts/build_exe.py            # dist/VEDA.exe, dist/VEDA.app or dist/VEDA
python scripts/build_exe.py --archive  # also zips it for distribution
```
PyInstaller cannot cross-compile, so each OS builds its own binary. Pushing a `v*` tag runs `.github/workflows/release.yml`, which builds all three and attaches them to a GitHub Release.

## Platform notes

* **Windows**: uses the Microsoft Edge WebView2 runtime (preinstalled on Windows 10/11).
* **macOS**: uses the system WebKit, so nothing extra is needed. Unsigned builds need right-click > Open the first time.
* **Linux**: the native window needs GTK or Qt bindings for pywebview, for example `sudo apt install python3-gi gir1.2-webkit2-4.1` or `pip install "pywebview[qt]"`. Without them VEDA opens in your browser automatically.

---

## Data, citation and license

VEDA does not own or host any data. Each archive's terms apply to the data you download (see [DATA_POLICY.md](DATA_POLICY.md)); the MIT License applies to the VEDA software. When you publish results, cite the data set, the instrument team's reference publication and VEDA. **Data & Licenses** in the app lists every connected data set with its citation and gives a data availability statement you can copy.

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

* **License**: [MIT](LICENSE). Copyright (c) 2026 Keshav Aggarwal, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO.
* **Terms of use**: [TERMS.md](TERMS.md). VEDA is provided without warranty, has no accounts, analytics or telemetry, and contacts only the archives you search.
* **Third-party software**: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) (Plotly.js, KaTeX, FastAPI, Pydantic, SpiceyPy/CSPICE, NumPy, SciPy, Astropy, Matplotlib, Pillow, Requests, Uvicorn, PyWebView).
* VEDA is not affiliated with or endorsed by NASA, ESA, JAXA or ISRO.

---

## Project layout and tests

```
src/veda/archives/   archive data sets, catalogue index, downloads, profile loading
src/veda/geometry/   SPICE kernel planning/download and observation geometry
src/veda/readers/    PDS3, PDS4, FITS and text readers
src/veda/analysis/   derived atmospheric and ionospheric parameters
src/veda/api/        FastAPI backend
src/veda/frontend/   web UI (Plotly and KaTeX bundled for offline use)
src/veda/sampledata/ real archive products used by the demos and tests
packaging/           PyInstaller spec, entry script and icon
scripts/             build_exe.py
tests/               pytest suite
```

```bash
pytest                          # full suite
pytest tests/test_archives.py   # a single module
```
CI runs the suite on Windows, macOS and Linux for every push to `main`. The Windows exe launch tests in `tests/test_explorer_launch.py` run after `python scripts/build_exe.py` and skip otherwise.

---

## Author

**Keshav Aggarwal**, Research Associate, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), Thiruvananthapuram, Kerala, India. Formerly Prime Minister's Research Fellow, Department of Astronomy, Astrophysics and Space Engineering (DAASE), IIT Indore.

Research: planetary radio occultation, planetary atmospheres and ionospheres, solar wind velocity and turbulence, and coronal electron density.

Website: [https://jovian-explorer.github.io/](https://jovian-explorer.github.io/)
