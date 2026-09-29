<p align="center">
  <img src="frontend/img/veda_logo.png" width="140" alt="VEDA Planetary Science Laboratory Emblem" />
</p>

# VEDA: Visualization, Exploration, and Data Analysis

**VEDA** is an open, multi-mission planetary-science computational laboratory capable of discovering, downloading, processing, analyzing, visualizing, and comparing scientific observations across multiple robotic spacecraft missions and celestial bodies.

---

## Documentation Quick Links

* 📖 **[User Guide and Scientific Manual](USAGE.md)**: Operational workflows, planetary thermodynamics, FITS imaging, and data export.
* 🛰️ **[Third-Party Data Policy and Citations](DATA_POLICY.md)**: Policies for NASA PDS, ESA PSA, JAXA DARTS, ISRO ISSDC, and mandatory academic attribution guidelines.
* ⚖️ **[Software License (MIT)](LICENSE)**: Open-source terms and conditions for VEDA.
* 📜 **[Third-Party Licenses and Attributions](THIRD_PARTY_LICENSES.md)**: Notices for bundled and linked open-source libraries (KaTeX, Plotly, Three.js, FastAPI, NumPy, SciPy, Astropy, Matplotlib, PyWebView).
* 🤝 **[Contributing Guidelines](CONTRIBUTING.md)**: Development workflow, coding conventions, testing protocols, and style rules.

---

## Key Capabilities

### 1. Runs Everywhere: Desktop App, Python Package, or Local Server
* **Standalone app** for Windows (`VEDA.exe`), macOS (`VEDA.app`) and Linux (`VEDA`), built automatically for every release.
* **Python package**: `pip install` straight from GitHub gives you the `veda` and `veda-server` commands.
* **Native window with a safe fallback**: opens in a native window (WebView2, WebKit or GTK/Qt) and falls back to your default browser if no webview runtime is available.
* **Self-contained**: frontend, math typesetting, plotting libraries and sample granules are all bundled, so the app works offline.

### 2. Dual Exploration Paradigms

#### A. By Celestial Body
Explore any non-Earth target planetary body or satellite:
* **Venus** (Akatsuki, Venus Express, Magellan, Pioneer Venus Orbiter, BepiColombo)
* **Mars** (MAVEN, Mars Reconnaissance Orbiter, Mars Orbiter Mission / MOM)
* **Jupiter** (Juno, Galileo, Cassini, New Horizons)
* **Saturn** (Cassini-Huygens)
* **Titan** (Cassini-Huygens)
* **Pluto and Arrokoth** (New Horizons)
* **Mercury** (MESSENGER, BepiColombo)
* **Moon** (Lunar Reconnaissance Orbiter, Chandrayaan-2)
* **Ceres** (Dawn)
* **Vesta** (Dawn)
* **Comet 67P/C-G** (Rosetta)

**Multi-Mission Simultaneous Selection**:
* Select multiple missions simultaneously (e.g. Venus: **Akatsuki** + **Venus Express** + **BepiColombo**).
* Aligns compatible atmospheric soundings onto a common body-specific vertical grid.
* Computes multi-spacecraft **composite mean $\mu(z)$** and **$\pm 1\sigma$ spread envelopes**.
* Interactive Plotly visualization showing individual spacecraft curves overlaid with the composite.
* One-click CSV export of cross-mission comparison tables.
* **Publication Figure Generator**: Generates 300-DPI publication-ready figures with LaTeX mathematical typography.

#### B. Planetary Spatial Coordinates Map and 3D Globe
* **2D Cylindrical Equirectangular Projection**: Visualizes observation locations, ray tangent points, and camera footprints with latitude and longitude guide bands.
* **3D Orthographic Rotating Globe**: Mathematical wireframe representation of the planetary body with latitude parallels and longitude meridians, plotting mission observation markers in true 3D coordinates.
* **Cross-Mission Synchronization**: Color-coded mission markers, observation tooltips, and click-to-highlight synchronization with the soundings table.

#### C. By Mission
Dive into specific spacecraft architectures with accurate mission classification:
* **Orbiters**: Akatsuki, Juno, Cassini, Venus Express, MAVEN, BepiColombo, Galileo, MESSENGER, Magellan, PVO, LRO, MRO, Dawn, Rosetta, Mars Orbiter Mission (MOM), Chandrayaan-2.
* **Flybys and Encounters**: New Horizons (Pluto, Arrokoth, Jupiter gravity assist), BepiColombo Venus flybys, Galileo Venus flyby.
* **Multi-level Data Pipeline**: Raw to Calibrated to Derived to User Analysis to Visualization to Export.
* **Astronomical Imaging and Interactive FITS Canvas**:
  * Full astronomical contrast stretching: **ZScale**, **Percentile (0.5% to 99.5%)**, **Linear**, **Log**, **Sqrt**, **Asinh**, **Histogram Equalization**.
  * Scientific palettes: Inferno, Viridis, Plasma, Magma, Grayscale, Twilight.
  * **Live Pixel Coordinate Inspector**: Real-time crosshair tracking displaying native image coordinates `(X, Y)` under the cursor.
  * **Click-and-Drag Custom Transect Slicing**: Scientists can drag a line slice directly across planetary cloud bands, surface features, or atmospheric limbs $(x_0, y_0) \to (x_1, y_1)$ to instantly extract 1D calibrated photometric flux cross-sections and 60-bin pixel value histograms/CDFs.

---

### 3. Remote Archive Discovery and Streaming Downloader

* **International Planetary Archives**: Direct queries to NASA Planetary Data System (PDS), ESA Planetary Science Archive (PSA), JAXA DARTS / ISAS, and ISRO ISSDC.
* **Live Progress and Cataloging**: Background streaming chunked downloader with byte tracking, SHA-256 verification, and SQLite cataloging via `/api/veda/archive/download` and `/api/veda/archive/tasks/{task_id}`.
* **In-App Search UI**: Query remote archives by agency and keyword directly within Mission Mode.

---

### 4. Multi-Planet Thermodynamic Engine

Applies target-specific physical constants ($R_{spec}, c_p, g_0, P_{ref}$) to compute:
* **Environmental Lapse Rate**: $\Gamma = -\frac{dT}{dz}$
* **Altitude-Dependent Gravity**: $g(z) = g_0 \left(\frac{R_p}{R_p + z}\right)^2$
* **Atmospheric Scale Height**: $H(z) = \frac{R_{spec} T(z)}{g(z)}$
* **Poisson Potential Temperature**: $\theta(z) = T(z) \left(\frac{P_0}{P(z)}\right)^\kappa$ where $\kappa = \frac{R_{spec}}{c_p}$
* **Static Stability / Brunt-Vaisala Buoyancy Frequency**:
  $$N^2(z) = \frac{g(z)}{\theta(z)} \frac{\partial \theta}{\partial z} = \frac{g(z)}{T(z)} \left(\frac{\partial T}{\partial z} + \frac{g(z)}{c_p}\right)$$
* **Gravity Wave Potential Energy**:
  $$E_p(z) = \frac{1}{2}\left(\frac{g(z)}{N(z)}\right)^2 \overline{\left(\frac{T'(z)}{\overline{T}(z)}\right)^2}$$
* **Ionospheric Vertical Total Electron Content (VTEC)**:
  $$\text{VTEC} = 10^{-7} \int N_e(z) dz \quad [\text{TECU}]$$

---

### 5. Pure-Python Readers (Zero PVL / Heavy C Dependencies)

* **PDS3 Label and Table Reader** (`pds3_reader.py`):
  * Parses fixed-width and CSV `.TAB` / `.LBL` data without third-party PVL libraries.
  * Automatically handles column byte-offsets, units, sentinel values (`-999.0`, `-9999.0`), and missing constants.
  * Tested and verified on authentic JAXA Akatsuki Level 4 radio science data.
* **FITS Astronomical Image Reader** (`fits_reader.py`):
  * Reads multi-extension FITS files using `astropy.io.fits`.
  * Computes robust astronomical percentile intervals and renders high-fidelity PNG streams on the fly.

---

## Installation

### Option A: download the app (no Python needed)
Open the [latest release](https://github.com/jovian-explorer/VEDA/releases/latest) and download the archive for your OS:

| OS | Asset | Run |
|---|---|---|
| Windows 10/11 (x64) | `VEDA-<version>-windows-x86_64.zip` | unzip, double-click `VEDA.exe` |
| macOS (Apple Silicon) | `VEDA-<version>-macos-arm64.zip` | unzip, right-click `VEDA.app` > Open the first time (the app is not notarized) |
| Linux (x86_64) | `VEDA-<version>-linux-x86_64.zip` | unzip, `chmod +x VEDA && ./VEDA` |

The repository is private, so you need to be signed in to GitHub with access to it.

### Option B: install with pip (any OS, Python 3.10+)
```bash
pip install "git+https://github.com/jovian-explorer/VEDA.git"
veda                  # desktop window (falls back to the browser)
veda --browser        # always use the default browser
veda-server           # headless API + web UI, prints the URL
python -m veda        # same as `veda`
```
Add `[netcdf]` (`pip install "veda[netcdf] @ git+https://github.com/jovian-explorer/VEDA.git"`) to read HDF5-backed COSMIC-2 netCDF4 files; classic netCDF3 granules work without it.

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

The interactive REST API documentation is at `/api/docs` on the same address.

**Where VEDA keeps your files** (cache, exports, settings, logs):

| OS | Location |
|---|---|
| Windows | `%LOCALAPPDATA%\VEDA` |
| macOS | `~/Library/Application Support/VEDA` |
| Linux | `$XDG_DATA_HOME/VEDA` (default `~/.local/share/VEDA`) |

Set `VEDA_HOME` to use a different folder.

## Building the Standalone App

```bash
pip install -e ".[build]"
python scripts/build_exe.py            # dist/VEDA.exe, dist/VEDA.app or dist/VEDA
python scripts/build_exe.py --archive  # also zips it for distribution
```
PyInstaller cannot cross-compile, so each OS builds its own binary. Pushing a `v*` tag runs `.github/workflows/release.yml`, which builds all three and attaches them to a GitHub Release.

## Platform Notes

* **Windows**: uses the Microsoft Edge WebView2 runtime (preinstalled on Windows 10/11).
* **macOS**: uses the system WebKit, so nothing extra is needed. Unsigned builds need right-click > Open the first time.
* **Linux**: the native window needs GTK or Qt bindings for pywebview, for example `sudo apt install python3-gi gir1.2-webkit2-4.1` or `pip install "pywebview[qt]"`. Without them VEDA opens in your browser automatically.

---

## Third-Party Data Policy and Attribution

VEDA processes public scientific data retrieved from international space agency archives:
* **NASA Planetary Data System (PDS)**: Public domain data governed by NASA Open Science guidelines.
* **ESA Planetary Science Archive (PSA)**: Open access research data provided under ESA planetary science policies.
* **JAXA Data Archives and Transmission System (DARTS)**: Open research data provided by JAXA / ISAS.
* **ISRO Indian Space Science Data Centre (ISSDC)**: Planetary data provided under ISRO science data terms.

### Mandatory Dual-Attribution for Academic Publications
When publishing scientific work that uses data, figures, or analyses produced with VEDA, researchers are required to cite both:
1. The original spacecraft instrument team and dataset DOI from the relevant archive.
2. The VEDA software platform.

See **[DATA_POLICY.md](DATA_POLICY.md)** for detailed citation instructions and dataset-specific BibTeX entries.

### BibTeX Citation for VEDA
```bibtex
@software{Aggarwal_VEDA_2026,
  author       = {Keshav Aggarwal},
  title        = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},
  year         = {2026},
  publisher    = {Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO},
  version      = {2.0.0},
  url          = {https://github.com/jovian-explorer/VEDA},
  address      = {Thiruvananthapuram, Kerala, India}
}
```

---

## Software License and Open-Source Attributions

* **Software License**: VEDA is distributed under the **[MIT License](LICENSE)**. Copyright (c) 2026 Keshav Aggarwal, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO.
* **Third-Party Open Source**: Bundles and interfaces with open-source libraries under permissive licenses (MIT, BSD-3-Clause, Apache-2.0, PSF). Full copyright statements and license texts are provided in **[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)**.
* **Offline KaTeX Typography**: KaTeX 0.16.9 is bundled locally in `src/veda/frontend/vendor/katex/` for self-contained, offline LaTeX mathematical equation rendering.

---

## Project Layout and Tests

```
src/veda/            Python package (FastAPI backend, readers, analysis, mission adapters)
src/veda/frontend/   Web UI served by the backend (bundled offline: KaTeX, Plotly, TopoJSON)
src/veda/sampledata/ Sample granules used by the demo workflows and the tests
packaging/           PyInstaller spec, entry script and icon
scripts/             build_exe.py, generate_sample_granules.py
tests/               pytest suite
```

```bash
pytest                          # full suite
pytest tests/test_veda.py -v    # a single module
```
CI runs the suite on Windows, macOS and Linux for every push to `main`. The Windows exe launch tests in `tests/test_explorer_launch.py` run after `python scripts/build_exe.py` and skip otherwise.

---

## Scientific Leadership and Affiliation

* **Lead Researcher and Developer**: Keshav Aggarwal
* **Current Affiliation**: Research Associate, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), Thiruvananthapuram, Kerala, India.
* **Former Affiliation**: Former Prime Minister's Research Fellow (PMRF Scholar), Department of Astronomy, Astrophysics and Space Engineering (DAASE), Indian Institute of Technology (IIT) Indore.
* **Research Focus**: Planetary Radio Occultation, Space Physics, Solar Wind Velocity and Turbulence, Coronal Electron Density, and Multi-Mission Planetary Science Data Systems.
* **Website**: [https://jovian-explorer.github.io/](https://jovian-explorer.github.io/)
