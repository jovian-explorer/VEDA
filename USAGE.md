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

Example: Mars, 2005-07-01 to 2005-07-31 returns several hundred profiles from Mars Express MaRS and Mars Global Surveyor (MRO radio occultations cover 2008 to 2012).

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
**Which profiles.** Tick the missions, then under *Which profiles* set any of: a date range, a latitude band, a local solar time range (22 to 2 h wraps through midnight), a solar zenith angle range, and the number of profiles per mission; press **Apply**. VEDA searches the whole archive catalogue of each mission's profile data sets on that body, takes candidates spread evenly over the dates, downloads and reads them (untick *Download* to use only what is already on disk), and keeps those inside the ranges. Latitude, local time and zenith angle are known only once a profile is read, so each mission tries up to four times as many profiles as it keeps. Under the form, a line per mission reports how many profiles were in the date range, how many were read and kept, and why the others were left out (for example "6 latitude outside the range", "local time unknown"). Without filters the comparison uses up to three downloaded profiles per mission. Profiles picked in an archive table (**Compare selected**) are used as they are. The CSV export and the publication figure always contain exactly the profiles on screen. VEDA remembers what you entered under *Which profiles* and the grouping, grid step, vertical coordinate and view, and fills them in the next time it opens; a remembered filter is used only after you press **Apply**.

Selected profiles, from one mission or many, are interpolated onto a common altitude grid (set under *Grid step*; by default 0.5 km on Venus, Mars and Pluto and 2 km on other bodies, from 0.01 to 100 km; altitudes below the reference level, such as the Hellas basin below the Mars reference sphere, are kept). Interpolation never extrapolates beyond a profile and never bridges a data gap wider than five times the profile's typical spacing.

**Pressure levels.** Set *Vertical* to *Pressure* to compare on a grid uniform in log pressure (0.02 decades apart, about 1/20 of a scale height) instead of altitude. Profiles then line up whatever their altitude reference (the 1-bar level, an ellipsoid, a landing site, a sphere), so Galileo, Cassini UVIS and radio occultation profiles of the giant planets, or entry and orbiter profiles of Mars, compare directly; profiles without a pressure column are left out, and pressure itself cannot be the compared variable. The CSV and publication figure follow the grid (first column `pressure_hpa`, logarithmic pressure axis). The altitude cut needs altitude levels.

* Temperature and other quantities that vary smoothly: arithmetic mean $\mu(z) = \frac{1}{M}\sum_m X_m(z)$ and the sample standard deviation (ddof = 1) as the $\pm 1\sigma$ spread.
* Pressure, mass and number density, and electron density (they change by orders of magnitude with height): interpolation and averaging in log space, i.e. the geometric mean, with the spread as a multiplicative $1\sigma$ factor. If any value is zero or negative (noisy electron densities), VEDA falls back to the linear treatment.
* The spread is drawn at levels covered by at least two profiles, and the mean where at least two profiles and at least half of all the compared profiles overlap: a single profile gives neither, and the mean of whichever few profiles reach a level would otherwise jump where that number changes.
* **One vertical reference.** Altitudes are measured from a sphere of the body's reference radius (Mars 3389.5 km, Venus 6051.8 km, Titan 2574.7 km), whether the archive gives a radius (MEX, VEX, MGS and MRO radio science) or an altitude above another sphere (Magellan gives altitudes above 6052 km; VEDA moves them up 0.2 km). The reference of each profile is shown on its **Altitude from** chip. Probes are the exception: Galileo altitudes are above the 1-bar level of Jupiter and Huygens altitudes above the landing site, and the comparison says so when such profiles are mixed with others. Altitudes are not above the local surface or the Mars areoid, which differ from the sphere by several km.

Choose the variable and units on the left, colour the curves by mission, date or latitude, and toggle the mean and spread. **Export Comparison CSV** writes the gridded table: the composite and group means and spreads, the number of profiles at each level, and every profile on the common grid, with a header line per profile (mission, instrument, time, latitude, longitude, local time, solar zenith angle). **Export profiles, all variables** writes the same profiles at their own archived levels, nothing interpolated, one row per profile and level ("long" format, ready for `pandas.read_csv(..., comment="#")`, R or a pivot table): every archived and derived quantity, the 1-sigma uncertainties the archive gives, and the latitude, longitude, local time and zenith angle of each level along the ray path where known. The units of each column are listed in the header.

**Redoing a comparison.** The second line of a Comparison CSV, `# recipe: {...}`, records the comparison: body, variable, grid, vertical coordinate, grouping and the exact profiles used (archive product ids). **Open comparison (from its CSV)** reads it back and redoes the comparison with those profiles, downloading any that are not in the cache; the same JSON can be posted to `/api/veda/compare/body/{body}` from a script. Files you loaded yourself are found only on the computer that holds them.

**Local time, solar zenith angle and Mars season.** Filters, groups and the altitude cut need each profile's local true solar time, solar zenith angle and, on Mars, the solar longitude Ls (0 northern spring equinox, 90 northern summer solstice, 180 autumn equinox, 270 winter solstice). VEDA uses the archive's values where it gives them (per level along the ray path, or in a header table as for MRO). Where it does not (Mars Express and Venus Express SOIR, for example), VEDA computes them from the time and the position: the body's position from the JPL approximate planetary elements (Standish, valid 1800-2050) and its rotation from the IAU WGCCRE models, for Venus, Mars, Jupiter, Saturn and Titan. Checked against the archives that publish both, the computed values agree to about 0.02 h in local time and 0.05 deg in Ls, and 0.3 deg or better in zenith angle (Mars Express AIO geometry files, MRO and MGS header tables, Venus Express VeRa 2014). The time used is that of the measurement at the planet: Mars Express and MRO label times are when the signal reached Earth, 4 to 21 minutes later, so VEDA uses the spacecraft time (MRO) or occultation time (MGS) from their header tables and subtracts the light time from Mars Express sample times (the profile time shown is then the measurement time at the lowest level; the label or file-name time is kept as LABEL_TIME and shown beside it). Profiles with a date but no clock time get no computed local time. In the profile viewer, computed values are marked with an asterisk.

**Climatologies (group composites).** *Group composites by* splits the compared profiles into bins and draws a mean and spread for each, with the individual profiles faded in their group's colour: latitude band, local solar time, solar zenith angle, Mars season Ls (bin width set under *Bin width*; by default 30°, 3 h, 30° and 30°), year, month, month of the year (all years together, a seasonal climatology) or mission. Each group follows the same rules as the overall composite (log-space averaging for pressure and densities; the mean where at least half of the group's profiles overlap). Profiles that lack the grouping quantity (for example no local time in the archive) are counted in the legend and left out of the group means.

**Altitude cut.** The *Altitude cut* tab plots the compared variable at one altitude, one point per profile, against time, latitude, local solar time, solar zenith angle, longitude or day of the year (all years together), coloured by mission, group, latitude or local time. It starts at the level reached by most profiles; type another altitude to move it. Hovering shows each profile's time and geometry, and clicking a point opens the profile. It uses the same profiles, grid and units as the comparison, so seasonal, latitudinal and local-time structure at a fixed height can be read directly.

*Show* changes what each point is:
- **Variable in a layer**: the minimum, maximum or mean of the compared variable between two altitudes (*From* and *to*), or the altitude of the minimum or maximum, for example the height of a temperature inversion or of the coldest level in any layer you choose. Only profiles covering the whole layer are used; means of pressure and densities are geometric. The status line counts the profiles whose extreme lies on an edge of the layer (they have none inside it).
- **From each whole profile**: quantities computed from each profile at its own resolution: the cold-point tropopause (altitude, temperature, pressure), the electron density peak and the fitted Chapman layer (peak density, altitude, scale height, R²), the electron content of the profile, and the mean gravity-wave potential energy and dominant vertical wavelength. Only those the compared profiles have are listed. They are also in the comparison CSV, on each profile's header line.

**Deviations.** *Show: Deviation from the mean* plots each profile minus its group's mean (or the composite mean when not grouped), and the group means minus the overall mean; for pressure and densities the deviation is in percent. This shows waves, tides and latitudinal structure that are invisible on a log axis spanning several decades.

Profiles read once are kept in memory for the session (the 512 most recent), so changing the variable, grouping or units does not read the files again.

### Live data sets
Data sets marked **live search** are not copied as an index: when you give **From** and **To** dates, VEDA asks the archive server for that instrument and window (ESA PSA EPN-TAP for Mars Express, Venus Express, Rosetta, BepiColombo and Huygens; the NASA PDS Registry API for MAVEN, Juno, New Horizons, MESSENGER, LRO, Galileo, Magellan, MGS, MRO, Pioneer Venus and Dawn; OPUS for Cassini, Galileo and New Horizons imaging and spectra). Up to 5,000 products per data set and window are listed; if there are more, VEDA says so and you can narrow the dates. Windows already searched in the last week are answered from the local catalogue.

Very large indexes (MRO CTX and MARCI, about 95 MB each) are read only when you press **Index now** on their data set.

### Viewing any product
**View** opens the product viewer for anything that is not an atmosphere profile (and **All fields** opens it from a profile):

| Product | What you can do |
|---|---|
| Table or time series | Pick the X field (time, row, any number) and up to 8 Y fields; one plot or one panel per field; log Y. **From / to** limits the rows to a time (or X) range; **Full range** resets it. Millions of rows are drawn at a few thousand points, keeping each minimum and maximum; zooming into the plot re-reads the zoomed range from the file, so every row is shown once the range is small enough. **CSV of shown fields** saves what is plotted. |
| Vector fields (spectra, energy channels per row) | Spectrogram (log colour optional) with the mean spectrum underneath. |
| Profiles per row (e.g. MRO MCS DDR) | **View: Profiles (one per row)**: plot one vector against another (temperature against pressure, dust against altitude ...), step through rows with the arrows, overlay up to 12. |
| Image or map | Stretch, colour map, band slider, value read-out at a click, transects (two clicks) and the histogram. Maps keep their longitude and latitude axes. |
| Spectral cube | Band slider; clicking a pixel plots its spectrum (3 x 3 pixel mean), keeping the last few for comparison. |
| Text (operations logs, notes, documents) | Read it in the viewer, find text (matches highlighted), save it as a .txt file. |

Products with several data objects (an image and its housekeeping table, several tables) show one tab per object. Products described only as raw bytes in their label can be downloaded but not plotted; the viewer says so.

Some archive labels contain errors, and VEDA repairs the common ones from the values themselves: floats written in the opposite byte order to the label (Juno JIRAM spectra), integers labelled as floats (VEX SPICAV), wrong record lengths and files shorter than their label.

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

On Jupiter and Saturn, which are flattened by rotation, gravity at the 1-bar level ranges from 23.1 m s$^{-2}$ at the equator to 26.9 at the poles (Jupiter) and from 9.0 to 12.1 (Saturn), so one value would put scale heights, $\Gamma_d$, $N^2$ and wave energies off by up to 15 %. For profiles with a latitude VEDA uses the effective gravity there: gravitation with the $J_2$ term of the Juno and Cassini gravity fields, minus the centrifugal acceleration, at $r$ = the 1-bar ellipsoid radius at the (planetocentric) latitude $\phi$ plus the altitude:
$$g_r = \frac{GM}{r^2}\left[1 - 3J_2\left(\frac{a}{r}\right)^2 P_2(\sin\phi)\right] - \omega^2 r\cos^2\phi, \quad g_\phi = \frac{3GMJ_2a^2}{r^4}\sin\phi\cos\phi + \omega^2 r \sin\phi\cos\phi, \quad g = \sqrt{g_r^2 + g_\phi^2}$$
Profiles without a latitude, and all other bodies, use the formula above; each profile states the gravity model used.

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

**Vertical derivatives** ($dT/dz$, $d\theta/dz$): samples at the same altitude are averaged first. Each derivative is a central difference between the neighbouring levels, but never over less than $\pm 50$ m (a 100 m vertical resolution): finely sampled profiles (entry accelerometers record every few metres) and altitude jitter (a lander after touchdown) would otherwise turn sample noise into huge gradients. On an even grid coarser than 50 m this is the ordinary central difference.

**Fill values**: temperatures, pressures and densities that are zero or negative are treated as missing (some archives, such as the MER and Phoenix entry profiles, mark missing levels with -1 without declaring it).

### Heat capacity
For Venus, Mars, Titan and Pluto, $c_p$ depends on temperature: it is the mole-fraction weighted ideal-gas heat capacity of the main constituents (CO2, N2, Ar, O2, CH4, CO; JANAF thermochemical tables) divided by the mean molar mass. CO2's $c_p$ rises steeply with temperature, so this matters: Mars at 200 K has $c_p \approx 740$ J kg$^{-1}$ K$^{-1}$ (a constant 830 would understate $\Gamma_d$ by 11 %), and in the deep Venus atmosphere $c_p$ grows from about 850 at 300 K to about 1140 at 735 K. $c_p(T)$ is used for $N^2$, $\Gamma_d$ and the speed of sound $c_s = \sqrt{\gamma R_{spec} T}$ with $\gamma = c_p/(c_p - R_{spec})$. Potential temperature uses the conventional constant $\kappa = R_{spec}/c_p$ at the body's reference $c_p$. Other bodies use their constant $c_p$ (shown with the body constants).

### Gravity Wave Potential Energy
Atmospheric gravity wave activity is quantified from temperature fluctuations $T'(z) = T(z) - \overline{T}(z)$:
$$E_p(z) = \frac{1}{2}\left(\frac{g(z)}{\overline{N}(z)}\right)^2 \left(\frac{T'(z)}{\overline{T}(z)}\right)^2, \qquad \overline{N}^2 = \frac{g}{\overline{T}}\left(\frac{d\overline{T}}{dz} + \frac{g}{c_p(\overline{T})}\right)$$
The background $\overline{T}(z)$ is a zero-phase (forward and backward) 4th-order Butterworth low-pass of the profile on a 100 m grid, with a cutoff wavelength of 8 km: $T'$ keeps at least 98 % of the amplitude of waves shorter than 5 km, 91 % at 6 km, half of an 8 km wave and at most 4 % of waves longer than 12 km. A cubic fit is removed before filtering, so a smoothly curved profile leaves no false perturbation at its top and bottom; sharp kinks (a tropopause, an inversion) still leave a small ringing of either sign around them. $\overline{N}$ is the stability of the background, not of the measured profile, whose $N^2$ contains the wave itself; where $\overline{N}^2 \le 0$, $E_p$ is not given. The dominant vertical wavelength is the peak of the $T'$ spectrum between 0.5 and 7 km; a peak closer to the 8 km cutoff is the edge of a longer wave that the filter removed, and none is reported.

### Ionospheric Vertical Total Electron Content (VTEC)
For ionospheric occultation retrievals, VEDA integrates vertical electron density $N_e(z)$:
$$\text{VTEC} = 10^{-7} \int_{z_{base}}^{z_{top}} N_e(z) dz \quad [\text{TECU}]$$
where $1 \text{ TECU} = 10^{16} \text{ electrons}/\text{m}^2$.

### Tropopause
The cold-point tropopause is the coldest level of a profile inside a range where the body has one: 25 to 70 km on Titan (44 km and 70.4 K at the Huygens site, Fulchignoni et al. 2005) and 30 to 500 hPa on Jupiter and Saturn (near 100 hPa; Lindal et al. 1981, 1985), whose altitudes are relative to the 1 bar level. It counts only when the profile is warmer both below and above it in that range. Venus and Mars have no cold-point tropopause in VEDA: on Venus the tropopause near 60 km is a change in static stability while the temperature keeps falling into the mesosphere (use $N^2$ or a layer statistic of the lapse rate instead), and Mars has no persistent temperature minimum.

### Chapman layer
Electron density profiles are fitted with an alpha-Chapman layer, $N_e(z) = N_m \exp\left(\tfrac{1}{2}\left(1 - \zeta - e^{-\zeta}\right)\right)$ with $\zeta = (z - h_m)/H$, by nonlinear least squares; the peak density $N_m$, peak altitude $h_m$, neutral scale height $H$ and $R^2$ of the fit are given with the measured peak. These, and the electron content, are computed for every profile with electron density, with or without temperature (most ionospheric occultations have none).

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

For a table, VEDA first shows what the file contains and asks what it is:

* **What it is**: the body, the mission (any VEDA mission, or *Other* with a name you type), the instrument, and the observation time in UTC. VEDA fills these from the label or header when it can (target, spacecraft, instrument, start time). The time places the profile in date searches and comparisons; leave it empty if you do not know it, nothing is invented.
* **Columns**: each column with its unit in the file, its first values and its range. For each, choose what it is (altitude, radius from the centre, temperature, pressure, electron or number density, their 1σ uncertainties, latitude, longitude, local time, solar zenith angle) and its unit (km or m; K or °C; hPa, Pa, bar, mbar or kPa; cm⁻³ or m⁻³). Files without a header (columns COL_1, COL_2, ...) can be read this way. VEDA suggests roles and units from the names and label units; check them. In text tables without a label, the values -999, -9999 and -99999, and values of 1e30 or more, are taken as missing.

The choices are saved with the file, so it reopens the same way, and kept for the next file you load. A loaded profile is labelled with the mission and instrument you gave ("VEX VeRa (your file)"), coloured like that mission in comparisons, and included in filtered comparisons of its body when its time and geometry match.

| Format | Extensions | Notes |
|---|---|---|
| PDS3 table | `.lbl` + `.tab` | Select the label **and** its table together; the label defines the columns. |
| PDS4 table | `.xml` + `.csv` or `.tab` | Select the XML label and its table together (character and delimited tables). |
| Text table | `.csv`, `.txt`, `.dat`, `.asc` | Comma, tab, semicolon or space separated, with or without a header row; units in the header as `name [unit]` or `name (unit)` are read. |
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
| Network | Allow downloads, Update notices, Timeout, Large-file limit | Turn online archive downloads off (offline work), whether VEDA tells you when a newer build is published (one request to GitHub per session), how long to wait for a slow archive, and the size (default 250 MB) above which opening a product asks first, showing the file size and an estimated download time. |
| Performance | CPU worker processes, Parallel downloads | Worker processes read and derive many profiles at once (filtered comparisons, batch reading); the default is all cores but one, 1 runs everything in the main process. Profiles are read in batches across the workers, which is several times faster for comparisons of tens to hundreds of profiles. Parallel downloads (1 to 16, default 4) sets how many products are fetched at the same time. |
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
