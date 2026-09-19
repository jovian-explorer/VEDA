# VEDA — Visualization, Exploration, and Data Analysis

**VEDA** is a multi-mission planetary-science data laboratory capable of discovering, downloading, processing, analyzing, visualizing, and comparing scientific observations across multiple robotic spacecraft missions and celestial bodies.

---

## Key Capabilities

### 1. Dual Exploration Paradigms

#### A. By Celestial Body
Explore any target planetary body or satellite:
* **Venus** (Akatsuki, Venus Express, Magellan, Pioneer Venus Orbiter, BepiColombo)
* **Earth** (COSMIC-2 constellation)
* **Mars** (MAVEN, Mars Reconnaissance Orbiter)
* **Jupiter** (Juno, Galileo, Cassini, New Horizons)
* **Saturn** (Cassini-Huygens)
* **Titan** (Cassini-Huygens)
* **Pluto & Arrokoth** (New Horizons)
* **Mercury** (MESSENGER, BepiColombo)
* **Moon** (Lunar Reconnaissance Orbiter)
* **Ceres** (Dawn)
* **Vesta** (Dawn)
* **Comet 67P/C-G** (Rosetta)

**Multi-Mission Simultaneous Selection**:
* Select multiple missions simultaneously (e.g. Venus: **Akatsuki** + **Venus Express** + **BepiColombo**).
* Aligns compatible atmospheric soundings onto a common body-specific vertical grid.
* Computes multi-spacecraft **composite mean $\mu(z)$** and **$\pm 1\sigma$ spread envelopes**.
* Interactive Plotly visualization showing individual spacecraft curves overlaid with the composite.
* One-click CSV export of cross-mission comparison tables.

#### B. By Mission
Dive into specific spacecraft architectures with accurate mission classification:
* **Orbiters**: Akatsuki, Juno, Cassini, Venus Express, MAVEN, BepiColombo, Galileo, MESSENGER, Magellan, PVO, LRO, MRO, Dawn, Rosetta.
* **Flybys & Encounters**: New Horizons (Pluto, Arrokoth, Jupiter gravity assist), BepiColombo Venus flybys, Galileo Venus/Earth flybys.
* **Constellations & Probes**: COSMIC-2 (six-satellite Earth RO constellation).
* **Multi-level Data Pipeline**: Raw $\to$ Calibrated $\to$ Derived $\to$ User Analysis $\to$ Visualization $\to$ Export.
* **Astronomical Imaging & Spectrometry**:
  - Full astronomical contrast stretching: **ZScale**, **Percentile (0.5%–99.5%)**, **Linear**, **Log**, **Sqrt**, **Asinh**, **Histogram Equalization**.
  - Scientific false-color palettes: Inferno, Viridis, Plasma, Magma, Grayscale, Twilight.
  - Interactive **1D Photometric Line Transect** tool: extracts pixel intensity cross-sections along arbitrary vectors $(x_0, y_0) \to (x_1, y_1)$.
  - **Pixel Intensity Histogram** and CDF distribution.

---

### 2. Multi-Planet Thermodynamic Engine

Applies target-specific physical constants ($R_{spec}, c_p, g_0, P_{ref}$) to compute:
* **Environmental Lapse Rate**: $\Gamma = -\frac{dT}{dz}$
* **Altitude-Dependent Gravity**: $g(z) = g_0 \left(\frac{R_p}{R_p + z}\right)^2$
* **Atmospheric Scale Height**: $H(z) = \frac{R_{spec} T(z)}{g(z)}$
* **Poisson Potential Temperature**: $\theta(z) = T(z) \left(\frac{P_0}{P(z)}\right)^\kappa$ where $\kappa = \frac{R_{spec}}{c_p}$
* **Static Stability / Brunt-Väisälä Buoyancy Frequency**:
  $$N^2(z) = \frac{g(z)}{\theta(z)} \frac{\partial \theta}{\partial z} = \frac{g(z)}{T(z)} \left(\frac{\partial T}{\partial z} + \frac{g(z)}{c_p}\right)$$
* **Ionospheric Vertical Total Electron Content (VTEC)**:
  $$\text{VTEC} = 10^{-7} \int N_e(z) dz \quad [\text{TECU}]$$
  with automatic $h_mF_2$ peak altitude and $N_mF_2$ maximum electron density identification.

---

### 3. Pure-Python Readers (Zero PVL / Heavy C Dependencies)

* **PDS3 Label & Table Reader** (`pds3_reader.py`):
  - Parses fixed-width and CSV `.TAB` / `.LBL` data without third-party PVL libraries.
  - Automatically handles column byte-offsets, units, sentinel values (`-999.0`, `-9999.0`), and missing constants.
  - Tested and verified on authentic JAXA Akatsuki Level 4 radio science data.
* **FITS Astronomical Image Reader** (`fits_reader.py`):
  - Reads multi-extension FITS files using `astropy.io.fits`.
  - Computes robust astronomical percentile intervals and renders high-fidelity PNG streams on the fly.
* **NetCDF-4 / HDF5 Reader** (`netcdf_reader.py`):
  - High-performance extraction of GNSS radio occultation profile granules.

---

## Quick Start

### Requirements
* Python 3.10+ (tested on Python 3.13)
* Dependencies: `fastapi`, `uvicorn`, `numpy`, `scipy`, `astropy`, `matplotlib`, `pillow`, `requests`

### Launching the Application

```powershell
# Method 1: Using the PowerShell launcher
.\launch.ps1

# Method 2: Direct Python launch
python app.py

# Method 3: Server-only mode (headless)
python app.py --no-window --port 8765
```

Once running, navigate to:
```
http://127.0.0.1:8765/
```
Interactive REST API Documentation is available at:
```
http://127.0.0.1:8765/api/docs
```

---

## Running Verification Tests

To execute the automated test suites:

```powershell
# Run all VEDA platform and advanced science tests
python -m pytest tests\test_veda.py tests\test_advanced_science.py -v
```

Output:
```
============================= 34 passed in 0.74s ==============================
```

---

## Authoritative Planetary Archives Integrated

* **NASA Planetary Data System (PDS)**: Atmospheres, Geosciences, Small Bodies, Ring-Moon Systems nodes.
* **ESA Planetary Science Archive (PSA)**: Venus Express, BepiColombo, Rosetta datasets.
* **JAXA Data Archives and Transmission System (DARTS)**: Akatsuki (VCO) Level 2–4 calibrated observations.
* **UCAR COSMIC Data Analysis and Archive Center (CDAAC)**: COSMIC-2 neutral atmospheric and ionospheric soundings.
