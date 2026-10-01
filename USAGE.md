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
Download the archive for your OS from the [Releases page](https://github.com/jovian-explorer/VEDA/releases), unzip it and run `VEDA.exe` (Windows), `VEDA.app` (macOS) or `./VEDA` (Linux). No Python installation is needed.

### Python Installation
```bash
pip install "git+https://github.com/jovian-explorer/VEDA.git"

veda                          # desktop window (browser fallback)
veda --browser                # open in the default browser
veda --no-window --port 8765  # headless server, open http://127.0.0.1:8765/
```

See the README for the development setup and platform notes.

---

## 2. Finding and Opening Real Observations

Everything VEDA shows comes from the official mission archives. Nothing is simulated: if no mission observed a body in your date range, the search returns nothing.

The top-left switch has three modes: **By Celestial Body**, **By Planetary Mission** and the **Guide**.

### Search a body by date (all missions)
1. Choose a planet or moon in **By Celestial Body**. The banner shows its radius, gravity, mean molecular weight, gas constant and composition, which VEDA uses for derived quantities.
2. In **Find observations of ...**, set **From** and **To**. Leave both empty to list only the indexed data sets; live data sets need dates. **Show** narrows the list to everything, atmosphere/ionosphere profiles, images or time series.
3. Press **Search all missions**. The first time, VEDA reads the index of every indexed data set for that body (progress is shown), then asks the live archive services for your dates; afterwards the same searches use the local catalogue and work offline.
4. The table lists mission, UTC time, product id, product type, payload and level, and whether the product is downloaded. Press **Open** (profiles) or **View** (anything else) to download and plot it, tick rows and press **Compare selected** to overlay them, or **Download selected** to cache them.

Example: Mars, 2005-07-01 to 2005-07-31 returns several hundred profiles from Mars Express MaRS and Mars Global Surveyor.

### Browse one mission by payload
1. Choose a spacecraft in **By Planetary Mission**. **Archive data** shows one chip per payload and data set (instrument, level, archive, indexed coverage). Tick the ones to search.
2. Filter by **From** / **To** date, **Product type** (for example atmosphere or ionosphere profiles, raw records), free **Search** text (product id, orbit), **Profiles only**, **Downloaded only**, and **Order** oldest or newest first.
3. Open, download or compare products as above. The observation viewer below shows the opened product.

### Missions that need an account (ISRO ISSDC)
Mars Orbiter Mission and Chandrayaan-2 data are on ISRO's PRADAN portal, which requires a free registered account and its own download pages. Their mission views show **Sign in to ISRO ISSDC**, which opens PRADAN in your browser. Download the products there, then press **Import downloaded files** and select them (PDS3 `.lbl` + data, or PDS4 `.xml` + data). VEDA never sees your password.

### Connected data sets
All 19 missions are connected, with 141 data sets covering nearly all of their payloads: indexed data sets (Akatsuki RS and cameras, Mars Express MaRS, Venus Express VeRa, Magellan, MGS, MRO MCS, Juno MWR/JunoCam/MAG, Galileo probe, Huygens HASI, Cassini Titan ionosphere and INMS, Pioneer Venus ONMS) and live data sets for the rest (ESA PSA, NASA PDS Registry, OPUS). The README has an overview and [DATA_POLICY.md](DATA_POLICY.md) the complete list with references and the few payloads not available yet.

### What an opened profile shows
* Every quantity in the product (temperature, pressure, number density, electron density, refractivity, absorptivity, H2SO4 and others) in its own panel, with the archived 1-sigma uncertainty as a band or error bars where the product provides it.
* Time, latitude, longitude, solar zenith angle and local solar time from the product, as chips above the plot.
* Derived quantities (section 3) computed from the archived temperature and pressure.
* **Plot style**, **Export figure**, **Geometry**, **Export CSV** and **Structured JSON**.

Units are read from the label and converted to VEDA's display units: pressure from Pa, hPa, bar or mbar; temperature from K or degrees C; densities from m^-3 or cm^-3, including scaled units such as `10^6 PER CUBIC METER`; radius and altitude from metres. Times come from the archive index (start time), the label or the file name; product creation dates are never used as observation times.

### Comparing observations
Selected profiles, from one mission or many, are interpolated onto a common altitude grid (0.5 km by default; altitudes below the reference level, such as Mars below the MOLA datum, are kept). Interpolation never extrapolates beyond a profile and never bridges a data gap wider than five times the profile's typical spacing.

* Temperature and other quantities that vary smoothly: arithmetic mean $\mu(z) = \frac{1}{M}\sum_m X_m(z)$ and the sample standard deviation (ddof = 1) as the $\pm 1\sigma$ spread.
* Pressure, mass and number density, and electron density (they change by orders of magnitude with height): interpolation and averaging in log space, i.e. the geometric mean, with the spread as a multiplicative $1\sigma$ factor. If any value is zero or negative (noisy electron densities), VEDA falls back to the linear treatment.
* The spread is drawn only at levels covered by at least two profiles; a single profile gives no spread.

Choose the variable and units on the left, colour the curves by mission, date or latitude, and toggle the mean and spread. **Export Comparison CSV** writes the gridded table.

### Live data sets
Data sets marked **live search** are not copied as an index: when you give **From** and **To** dates, VEDA asks the archive server for that instrument and window (ESA PSA EPN-TAP for Mars Express, Venus Express, Rosetta, BepiColombo and Huygens; the NASA PDS Registry API for MAVEN, Juno, New Horizons, MESSENGER, LRO, Galileo, Magellan, MGS, MRO, Pioneer Venus and Dawn; OPUS for Cassini, Galileo and New Horizons imaging and spectra). Up to 5,000 products per data set and window are listed; if there are more, VEDA says so and you can narrow the dates. Windows already searched in the last week are answered from the local catalogue.

Very large indexes (MRO CTX and MARCI, about 95 MB each) are read only when you press **Index now** on their data set.

### Viewing any product
**View** opens the product viewer for anything that is not an atmosphere profile (and **All fields** opens it from a profile):

| Product | What you can do |
|---|---|
| Table or time series | Pick the X field (time, row, any number) and up to 8 Y fields; one plot or one panel per field; log Y. Millions of rows are drawn at a few thousand points, keeping each minimum and maximum. **CSV of shown fields** saves what is plotted. |
| Vector fields (spectra, energy channels per row) | Spectrogram (log colour optional) with the mean spectrum underneath. |
| Profiles per row (e.g. MRO MCS DDR) | **View: Profiles (one per row)**: plot one vector against another (temperature against pressure, dust against altitude ...), step through rows with the arrows, overlay up to 12. |
| Image or map | Stretch, colour map, band slider, value read-out at a click, transects (two clicks) and the histogram. Maps keep their longitude and latitude axes. |
| Spectral cube | Band slider; clicking a pixel plots its spectrum (3 x 3 pixel mean), keeping the last few for comparison. |

Products with several data objects (an image and its housekeeping table, several tables) show one tab per object. Products described only as raw bytes in their label can be downloaded but not plotted; the viewer says so.

### What to cite
**Cite** in the toolbar lists the references for what you have opened and used on this computer: each data set with the archive data set identifiers of the products you opened, the instrument and mission papers, the archive acknowledgements, SPICE and SpiceyPy if you used geometry, the libraries behind derived quantities and figures, and VEDA. Copy everything as BibTeX or text, or copy the data availability statement. **Start a new list** clears it (for a new paper).

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
where the dry adiabatic lapse rate is $\Gamma_d = g(z) / c_p(T)$. VEDA evaluates N^2 from temperature alone (no pressure column needed).
* $N^2(z) > 0$: Dynamically stable layer supporting internal gravity wave propagation.
* $N^2(z) = 0$: Neutral stability.
* $N^2(z) < 0$: Superadiabatic, convective overturning instability.

### Heat capacity
For Venus, Mars, Titan and Pluto, $c_p$ depends on temperature: it is the mole-fraction weighted ideal-gas heat capacity of the main constituents (CO2, N2, Ar, O2, CH4, CO; JANAF thermochemical tables) divided by the mean molar mass. CO2's $c_p$ rises steeply with temperature, so this matters: Mars at 200 K has $c_p \approx 740$ J kg$^{-1}$ K$^{-1}$ (a constant 830 would understate $\Gamma_d$ by 11 %), and in the deep Venus atmosphere $c_p$ grows from about 850 at 300 K to about 1140 at 735 K. $c_p(T)$ is used for $N^2$, $\Gamma_d$ and the speed of sound $c_s = \sqrt{\gamma R_{spec} T}$ with $\gamma = c_p/(c_p - R_{spec})$. Potential temperature uses the conventional constant $\kappa = R_{spec}/c_p$ at the body's reference $c_p$. Other bodies use their constant $c_p$ (shown with the body constants).

### Gravity Wave Potential Energy
Atmospheric gravity wave activity is quantified from temperature fluctuations $T'(z) = T(z) - \overline{T}(z)$:
$$E_p(z) = \frac{1}{2}\left(\frac{g(z)}{N(z)}\right)^2 \overline{\left(\frac{T'(z)}{\overline{T}(z)}\right)^2}$$
where $\overline{T}(z)$ is the background profile obtained through polynomial or low-pass vertical filtering.

### Ionospheric Vertical Total Electron Content (VTEC)
For ionospheric occultation retrievals, VEDA integrates vertical electron density $N_e(z)$:
$$\text{VTEC} = 10^{-7} \int_{z_{base}}^{z_{top}} N_e(z) dz \quad [\text{TECU}]$$
where $1 \text{ TECU} = 10^{16} \text{ electrons}/\text{m}^2$.

---

## 4. Plot Style and Figure Export

**Plot style** (on any profile or comparison plot) opens a panel whose choices apply immediately and are remembered on this computer:

| Group | Options |
|---|---|
| Lines and markers | lines, markers or both; line width; dash; marker size and symbol; colour palette |
| Uncertainty | none, error bars or shaded 1-sigma band |
| Axes | altitude or pressure as the vertical axis; swap axes; linear or log x; fixed ranges; grid; frame on all sides; ticks inside or outside |
| Text | sans or serif font, font size, legend position |
| Template | screen, or a journal template: AGU (JGR, GRL), Icarus/PSS (Elsevier), A&A, MNRAS |

**Export figure** saves the plot at the template's single-column (84 to 95 mm) or double-column (174 to 190 mm) width, as PNG at the DPI you choose or as vector SVG. In journal mode the fonts, sizes and black axes follow the journal's style.

---

## 5. Observation Geometry (SPICE)

Press **Geometry** on any opened product. VEDA computes it with NAIF SPICE for every mission with public kernels (all except the Mars Orbiter Mission and Chandrayaan-2).

**Kernels are downloaded for you.** Opening a mission fetches its generic and body kernels in the background; opening an observation fetches the spacecraft ephemeris covering its date. VEDA knows each mission's kernel archive (NAIF operational and PDS SPICE archives, the ESA SPICE service, the Akatsuki archive) and how its files map to dates: from the file names, from the PDS3 archive's coverage table, or from the archive's read-me. In **Settings > Observation geometry** you can turn this off or set the size above which VEDA asks first (400 MB by default). Kernels are kept in the cache and reused.

**Radio occultations** (profiles with per-sample ephemeris times):

| View | What it shows |
|---|---|
| Orbit (planet-fixed) | 3D spacecraft orbit for 90 minutes either side of the occultation in the body-fixed frame, the part flown during the profile, the tangent points, the lit side of the planet and the directions to the Sun and Earth |
| Orbit (inertial J2000) | the same in the inertial frame |
| View from Earth | the planet disk and the orbit in the sky plane as seen from Earth (north up, east right), split into visible and hidden behind the planet |
| Tangent-point map | the tangent-point track coloured by altitude with the terminator, subsolar and sub-Earth points, in cylindrical, north polar, south polar or orthographic projection |
| Angles along profile | solar zenith angle, local solar time and Sun-Earth-probe angle against tangent altitude |

Radio-science times are Earth-received times, so positions are corrected for light time. Where the product gives its own refracted tangent track, VEDA uses it and reports the straight-line minus refracted radius as ray bending. For Mars Express the computed tangent radii agree with the archived ones to about 1 km; for Akatsuki the SZA and local time agree with the published values to about 0.01 degrees.

**Every other observation** (in situ, images, spectra, cubes):

| View | What it shows |
|---|---|
| Orbit (planet-fixed) | the spacecraft orbit over the observation (at least the hour around it, at most a month), with the part during the observation highlighted and the Sun and Earth directions |
| Ground track | the sub-spacecraft track coloured by altitude, with the terminator and subsolar point, in the same projections as above |
| Altitude, angles and local time | altitude, solar zenith, emission and phase angles at the sub-spacecraft point, local solar time and latitude against time |

---

## 6. Astronomical FITS Canvas and Transect Slicing

FITS and PNG/JPEG images (for example the bundled Akatsuki UVI image) open in the image viewer:

1. **Contrast stretches**: ZScale, percentile (0.5% to 99.5%), linear, log, sqrt, asinh and histogram equalisation.
2. **Colour maps**: Inferno, Viridis, Plasma, Magma, Grayscale and Twilight.
3. **Pixel inspector**: image coordinates and value under the cursor.
4. **Line transects**: drag across the image from $(x_0, y_0)$ to $(x_1, y_1)$ to get the profile along the line and a histogram of pixel values.

---

## 7. Downloads, Cache and Offline Use

* Archive indexes are stored in a local SQLite catalogue (`archive_catalog.sqlite` in the cache folder) the first time a data set is searched. Re-indexing a data set picks up new volumes.
* Products are downloaded one at a time on request, with retries when an archive is busy. Each file is written in full before it is used, so an interrupted download never leaves a broken product.
* Everything is cached under the VEDA data folder (see the README). Downloaded products, the catalogue and SPICE kernels are reused offline.
* With **Settings > Network > Allow downloads** off, VEDA makes no network requests at all and works from the cache and the bundled samples.

---

## 8. Loading Your Own Files

Click **Load File** in the toolbar, drop files anywhere on the window, or use the drop zone in the Workflow Guide. You can select several files at once.

| Format | Extensions | Notes |
|---|---|---|
| PDS3 table | `.lbl` + `.tab` | Select the label **and** its table together; the label defines the columns. |
| PDS4 table | `.xml` + `.csv` or `.tab` | Select the XML label and its table together (character and delimited tables). |
| Text table | `.csv`, `.txt`, `.dat`, `.asc` | Needs a header row with an altitude column (`ALTITUDE`, `ALT`, `HEIGHT`, `Z` or `RADIUS`). |
| FITS image | `.fit`, `.fits`, `.fts` | Opens in the image viewer with stretch, colour map, histogram and transects. |
| Picture | `.png`, `.jpg`, `.jpeg` | Opens in the image viewer. |

Column names are matched as whole words, preferring the column that *leads* with the quantity and skipping uncertainty (`SIGMA ...`) columns. When a product carries several retrieval variants (e.g. Akatsuki's lower / medium / higher upper-boundary temperatures) the nominal **MEDIUM** variant is used. Loaded files are kept (the 25 most recent) under the *user_imported* mission so you can reopen, compare and export them.

---

## 9. Publication Figures and Data Export

* **Publication Figure** (Celestial Body mode) renders a journal-style Matplotlib figure of the current comparison at the DPI set in Settings (72 to 1200, default 300).
* **Snapshot Plot (PNG)** saves the on-screen plot.
* **Export figure** (on any profile or comparison) saves PNG or SVG at a journal column width; see section 4.
* **Export Comparison CSV** saves the interpolated multi-mission table: altitude grid, each mission's curve, the composite mean and its 1-sigma spread.
* **Export CSV** and **Structured JSON** save the open observation with its derived quantities. The CSV header names the archive, the source URL and file, the citation and the VEDA version, and states which columns are archived and which are derived.

---

## 10. Settings

Open **Settings** in the toolbar. Changes apply as soon as you save; **Reset to defaults** restores everything.

| Group | Setting | Effect |
|---|---|---|
| Appearance | Theme | Dark, Light, or Follow system. Plots follow the theme. |
| | Base font size / Interface zoom | Text size (11 to 20 px) and whole-interface zoom (A- / A+). |
| Units | Temperature, Pressure | Default units for the comparison plot and the quick unit switcher. |
| Start-up | Open on body, Default mission | Where VEDA opens next time. |
| Figures | Publication figure DPI | Resolution of exported publication figures. |
| Network | Allow downloads, Timeout | Turn online archive downloads off (offline work) and set how long to wait for a slow archive. |
| Observation geometry | Automatic SPICE downloads, size limit | Download the kernels for opened missions and observations by themselves, and ask first above the limit. |
| Data folders | Open | Shows and opens the data, cache, export and log folders. |

Settings are stored in `settings.json` inside the VEDA data folder (see the README). A damaged or hand-edited file never stops VEDA from starting: invalid entries fall back to their defaults.

---

## 11. Troubleshooting

| Symptom | What to do |
|---|---|
| "... is a PDS3 label and its data table was not included" | Select the `.lbl` and `.tab` together (Ctrl/Cmd-click), or drop both at once. |
| "No altitude column found" | Rename the altitude column (e.g. `altitude`) or load the table together with its PDS3 label. |
| Comparison plot says none of the observations contain the variable | Choose another variable or tick missions that measured it. |
| Download fails or times out | Check your connection, allow downloads in Settings > Network, or raise the timeout. Archives are occasionally offline for maintenance. |
| Window stays blank / does not open | Run `veda --browser`, or `veda-server` and open the printed address. On Linux install GTK or Qt support for pywebview (see the README). |
| Something else | Open Settings > Data folders > Logs and attach `startup.log` (and `startup-error.log` if present) to an issue at https://github.com/jovian-explorer/VEDA/issues. |
