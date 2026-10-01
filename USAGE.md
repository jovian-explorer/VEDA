# VEDA User Guide and Scientific Manual

This guide provides operational workflows, scientific methodologies, and usage instructions for **VEDA (Visualization, Exploration, and Data Analysis)**.

---

## 1. System Requirements and Installation

### Operating Environment
* **Platform**: Windows 10/11 (x64), macOS 12 or newer, or a desktop Linux distribution (x86_64).
* **System Memory**: 4 GB RAM minimum (8 GB or more recommended for multi-mission grids and large FITS images).
* **Display Resolution**: 1280 x 800 minimum (1920 x 1080 or higher recommended).
* **GUI Runtime**: WebView2 on Windows (preinstalled), WebKit on macOS (built in), GTK or Qt on Linux. Without a webview runtime VEDA opens in the default browser.

### Standalone App
Download the archive for your OS from the [latest release](https://github.com/jovian-explorer/VEDA/releases/latest), unzip it and run `VEDA.exe` (Windows), `VEDA.app` (macOS) or `./VEDA` (Linux). No Python installation is needed.

### Python Installation
```bash
pip install "git+https://github.com/jovian-explorer/VEDA.git"

veda                          # desktop window (browser fallback)
veda --browser                # open in the default browser
veda --no-window --port 8765  # headless server, open http://127.0.0.1:8765/
```

See the README for the development setup and platform notes.

---

## 2. Interface Navigation and Modes

VEDA provides two exploration paradigms accessible via the top-left navigation switch:

### Mode 1: Exploration by Celestial Body
1. **Target Selection**:
   * Click any planetary target in the body gallery: **Venus**, **Mars**, **Jupiter**, **Saturn**, **Titan**, **Pluto**, **Mercury**, **Moon**, **Ceres**, **Vesta**, or **Comet 67P**.
   * The target banner displays authoritative physical constants: equatorial radius $R_p$, surface gravity $g_0$, mean molecular weight $\mu$, specific gas constant $R_{spec}$, and primary atmospheric constituents.
   * Direct links are provided to the official exploration overview and the authoritative planetary data archive.
2. **Multi-Mission Comparative Analysis**:
   * In the Soundings panel, activate multiple missions simultaneously (e.g. for Venus: select **Akatsuki**, **Venus Express**, and **BepiColombo**).
   * VEDA aligns soundings onto a target-specific uniform vertical altitude grid ($z$).
   * The system computes:
     * Individual spacecraft vertical profiles
     * Multi-spacecraft composite mean: $\mu(z) = \frac{1}{M}\sum_{m=1}^M T_m(z)$
     * Observational spread envelope: $\mu(z) \pm 1\sigma(z)$
3. **Planetary Spatial Map and 3D Globe**:
   * **2D Cylindrical Equirectangular Projection**: Visualizes latitude and longitude coordinates of occultation tangent points and image centers.
   * **3D Orthographic Rotating Globe**: Wireframe mathematical sphere with latitude parallels and longitude meridians, plotting spacecraft observation footprints in 3D coordinate space.

### Mode 2: Exploration by Spacecraft Mission
1. **Mission Architecture**:
   * Browse 17 planetary missions filtered by mission class (**Orbiters** vs. **Flybys and Encounters**).
   * Inspect spacecraft trajectory parameters, orbital configurations, scientific payload suites, and target bodies.
   * Direct links are provided to the official mission portal and data archive.
2. **Observation Timeline and Soundings Catalog**:
   * Browse ingested observation soundings chronologically or filter by instrument.
   * View solar zenith angle (SZA), local solar time (LST), latitude, longitude, and measurement altitude ranges.

---

## 3. Scientific Inversion and Atmospheric Physics

VEDA incorporates a deterministic thermodynamic engine for planetary atmospheres:

### Hydrostatic Balance and State
The vertical structure is governed by hydrostatic balance and the Ideal Gas Law:
$$\frac{dP}{dz} = -\rho(z) g(z)$$
$$P(z) = \rho(z) R_{spec} T(z)$$
where altitude-dependent gravity is:
$$g(z) = g_0 \left(\frac{R_p}{R_p + z}\right)^2$$
and specific gas constant is $R_{spec} = R_{univ} / \mu$.

### Poisson Potential Temperature
To diagnose vertical stability and potential energy across varying pressure levels, VEDA calculates potential temperature referenced to $P_0$:
$$\theta(z) = T(z) \left(\frac{P_0}{P(z)}\right)^{\frac{R_{spec}}{C_p}}$$

### Brunt-Vaisala Static Stability Frequency
The buoyancy frequency squared quantifies resistance to vertical convective displacement:
$$N^2(z) = \frac{g(z)}{T(z)} \left(\frac{dT}{dz} + \Gamma_d\right) = \frac{g(z)}{\theta(z)} \frac{d\theta}{dz}$$
where the dry adiabatic lapse rate is $\Gamma_d = g(z) / C_p$.
* $N^2(z) > 0$: Dynamically stable layer supporting internal gravity wave propagation.
* $N^2(z) = 0$: Neutral stability.
* $N^2(z) < 0$: Superadiabatic, convective overturning instability.

### Gravity Wave Potential Energy
Atmospheric gravity wave activity is quantified from temperature fluctuations $T'(z) = T(z) - \overline{T}(z)$:
$$E_p(z) = \frac{1}{2}\left(\frac{g(z)}{N(z)}\right)^2 \overline{\left(\frac{T'(z)}{\overline{T}(z)}\right)^2}$$
where $\overline{T}(z)$ is the background profile obtained through polynomial or low-pass vertical filtering.

### Ionospheric Vertical Total Electron Content (VTEC)
For ionospheric occultation retrievals, VEDA integrates vertical electron density $N_e(z)$:
$$\text{VTEC} = 10^{-7} \int_{z_{base}}^{z_{top}} N_e(z) dz \quad [\text{TECU}]$$
where $1 \text{ TECU} = 10^{16} \text{ electrons}/\text{m}^2$.

---

## 4. Astronomical FITS Canvas and Transect Slicing

VEDA includes a high-performance scientific imaging pipeline for 2D FITS image granules:

1. **Contrast Stretching Algorithms**:
   * **ZScale**: IRAF-standard astronomical contrast stretch for optimal dynamic range.
   * **Percentile**: Min-max clipping using user-selectable intervals (0.5% to 99.5%).
   * **Linear / Log / Sqrt / Asinh**: Mathematical transfer functions for faint limb or high-contrast planetary disk analysis.
   * **Histogram Equalization**: Maximizes detail across complex planetary cloud decks.
2. **Scientific Color Palettes**:
   * Select from Inferno, Viridis, Plasma, Magma, Grayscale, or Twilight.
3. **Live Pixel Coordinate Inspector**:
   * Move the mouse across the canvas to view real-time image coordinates $(X, Y)$ and calibrated pixel intensity.
4. **Interactive 1D Transect Slicing**:
   * Click and drag across any cloud band, planetary limb, or ring feature $(x_0, y_0) \to (x_1, y_1)$.
   * Instantly renders a 1D photometric cross-section profile and 60-bin flux distribution histogram.

---

## 5. Remote Planetary Archive Query and Download

VEDA connects directly to international planetary science archives:

1. **Archive Search**:
   * In Mission Mode, open the Remote Archive Query interface.
   * Select target agency: **NASA PDS**, **ESA PSA**, **JAXA DARTS**, or **ISRO ISSDC**.
   * Enter search keywords, mission name, or target body.
2. **Chunked Streaming Acquisition**:
   * Click **Download** on any discovered file.
   * The backend initiates an asynchronous chunked transfer, calculating downloaded bytes, transfer speed, and SHA-256 cryptographic checksums.
   * Download progress is tracked in real time.
   * Upon completion, the file is indexed into the local SQLite catalog for immediate analysis.

---

## 6. Loading Your Own Files

Click **Load File** in the toolbar, drop files anywhere on the window, or use the drop zone in the Workflow Guide. You can select several files at once.

| Format | Extensions | Notes |
|---|---|---|
| PDS3 table | `.lbl` + `.tab` | Select the label **and** its table together; the label defines the columns. |
| Text table | `.csv`, `.txt`, `.dat`, `.asc` | Needs a header row with an altitude column (`ALTITUDE`, `ALT`, `HEIGHT`, `Z` or `RADIUS`). |
| FITS image | `.fit`, `.fits`, `.fts` | Opens in the image viewer with stretch, colour map, histogram and transects. |
| Picture | `.png`, `.jpg`, `.jpeg` | Opens in the image viewer. |

Column names are matched as whole words, preferring the column that *leads* with the quantity and skipping uncertainty (`SIGMA ...`) columns. When a product carries several retrieval variants (e.g. Akatsuki's lower / medium / higher upper-boundary temperatures) the nominal **MEDIUM** variant is used. Loaded files are kept (the 25 most recent) under the *user_imported* mission so you can reopen, compare and export them.

---

## 7. Publication Figures and Data Export

* **Publication Figure** (Celestial Body mode) renders a journal-style Matplotlib figure of the current comparison at the DPI set in Settings (72 to 1200, default 300).
* **Snapshot Plot (PNG)** saves the on-screen plot.
* **Export Comparison CSV** saves the interpolated multi-mission table: altitude grid, each mission's curve, the composite mean and its 1-sigma spread.
* In Mission mode, **Export CSV** and **Structured JSON** save the open observation with its derived diagnostics and provenance.

---

## 8. Settings

Open **Settings** in the toolbar. Changes apply as soon as you save; **Reset to defaults** restores everything.

| Group | Setting | Effect |
|---|---|---|
| Appearance | Theme | Dark, Light, or Follow system. Plots follow the theme. |
| | Base font size / Interface zoom | Text size (11 to 20 px) and whole-interface zoom (A- / A+). |
| Units | Temperature, Pressure | Default units for the comparison plot and the quick unit switcher. |
| Start-up | Open on body, Default mission | Where VEDA opens next time. |
| Figures | Publication figure DPI | Resolution of exported publication figures. |
| Network | Allow downloads, Timeout | Turn online archive downloads off (offline work) and set how long to wait for a slow archive. |
| Data folders | Open | Shows and opens the data, cache, export and log folders. |

Settings are stored in `settings.json` inside the VEDA data folder (see the README). A damaged or hand-edited file never stops VEDA from starting: invalid entries fall back to their defaults.

---

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| "... is a PDS3 label and its data table was not included" | Select the `.lbl` and `.tab` together (Ctrl/Cmd-click), or drop both at once. |
| "No altitude column found" | Rename the altitude column (e.g. `altitude`) or load the table together with its PDS3 label. |
| Comparison plot says none of the observations contain the variable | Choose another variable or tick missions that measured it. |
| Download fails or times out | Check your connection, allow downloads in Settings > Network, or raise the timeout. Archives are occasionally offline for maintenance. |
| Window stays blank / does not open | Run `veda --browser`, or `veda-server` and open the printed address. On Linux install GTK or Qt support for pywebview (see the README). |
| Something else | Open Settings > Data folders > Logs and attach `startup.log` (and `startup-error.log` if present) to an issue at https://github.com/jovian-explorer/VEDA/issues. |
