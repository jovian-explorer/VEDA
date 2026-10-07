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

The switch beside the VEDA name has three modes: **By Celestial Body**, **By Planetary Mission** and the **Workflow Guide**.

### Search a body by date (all missions)
1. Choose a planet or moon in **By Celestial Body**. The banner shows its radius, gravity, molar mass, gas constant, heat capacity $c_p$ and composition, which VEDA uses for derived quantities (for Venus, Mars, Titan and Pluto the $c_p$ shown is the reference value; derived quantities use $c_p(T)$).
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
All 25 missions are connected, with 161 data sets covering nearly all of their payloads. 55 are indexed: the radio occultation profiles of Akatsuki, Mars Express, Venus Express (PSA, PDS and the research repositories), Magellan, Pioneer Venus, MGS, MRO and Cassini (Titan, Saturn ionosphere); Venus Express SOIR; Cassini UVIS Saturn occultations; the Mars entry profiles (Spirit, Opportunity, Phoenix, Curiosity, InSight); the MRO and Mars Odyssey aerobraking densities; MRO CRISM aerosol profiles; the Galileo probe, Huygens HASI and VEGA 2 descents; the Akatsuki cameras, MRO MCS, CTX and MARCI, Juno MWR, JunoCam and MAG, Cassini INMS and Pioneer Venus ONMS; and the ISRO portal entries. The other 106 are searched live (ESA PSA, NASA PDS Registry, OPUS). The README has an overview and [DATA_POLICY.md](DATA_POLICY.md) the complete list with references and the few payloads not available yet.

### What an opened profile shows
* Every quantity in the product (temperature, pressure, number density, electron density, refractivity, absorptivity, H2SO4 and others) in its own panel, with the archived 1-sigma uncertainty as a band or error bars where the product provides it.
* Time, latitude, longitude, solar zenith angle and local solar time from the product, as chips above the plot.
* Derived quantities (section 3) computed from the archived temperature and pressure.
* **Plot style**, **Export figure**, **Geometry**, **Export CSV** and **Structured JSON**.

Units are read from the label and converted to VEDA's display units: pressure from Pa, hPa, bar or mbar; temperature from K or degrees C; densities from m^-3 or cm^-3, including scaled units such as `10^6 PER CUBIC METER`; radius and altitude from metres. Times come from the archive index (start time), the label or the file name; product creation dates are never used as observation times.

### Comparing observations
**Which profiles.** Tick the missions, then under *Which profiles* set any of: a date range, a latitude band, a local solar time range (22 to 2 h wraps through midnight), a solar zenith angle range, a Mars season (Ls) range, and the number of profiles per mission; press **Apply**. VEDA searches the whole archive catalogue of each mission's profile data sets on that body, takes candidates spread evenly over the dates, downloads and reads them (untick *Download* to use only what is already on disk), and keeps those inside the ranges. Latitude, local time and zenith angle are known only once a profile is read, so each mission tries up to four times as many profiles as it keeps. Under the form, a line per mission reports how many profiles were in the date range, how many were read and kept, and why the others were left out (for example "6 latitude outside the range", "local time unknown"). Without filters the comparison uses up to three downloaded profiles per mission. Profiles picked in an archive table (**Compare selected**) are used as they are. The CSV export and the publication figure always contain exactly the profiles on screen. VEDA remembers what you entered under *Which profiles* and the grouping, grid step, vertical coordinate and view, and fills them in the next time it opens; a remembered filter is used only after you press **Apply**.

Selected profiles, from one mission or many, are interpolated onto a common altitude grid (set under *Grid step*; by default 0.5 km on Venus, Mars and Pluto and 2 km on other bodies, from 0.01 to 100 km; altitudes below the reference level, such as the Hellas basin below the Mars reference sphere, are kept). Interpolation never extrapolates beyond a profile and never bridges a data gap wider than five times the profile's typical spacing.

**Coverage, resolution, uncertainty, data sets.** *Which profiles* can also require that the compared variable covers an altitude range (*Must cover from ... to*), that the profile's levels are at most so far apart (median spacing, *Level spacing at most*), and that its 1-sigma, median over the profile, archived or propagated, is at most a value in the variable's unit or a percentage of the value (*1σ at most*; profiles without an uncertainty are then left out); and *Data sets* and *Instruments* restrict the archive data sets drawn from (none selected: all; your loaded files are then not included). Like latitude and local time these are known only once a profile is read, so each mission tries up to four times as many profiles as it keeps. The report under the form names the filters in force and how many profiles each left out ("altitude range not covered", "levels too far apart", "uncertainty above the limit", "no uncertainty"), and the Comparison CSV's recipe line records the filter beside the profiles it chose. None of the data sets VEDA reads publishes per-profile quality flags, so there is no quality-flag filter.

**Outlier screen.** *Outlier screen* flags profiles far from the others: at each level with at least five profiles, the robust score $z = 0.6745\,(x - \tilde{x})/\mathrm{MAD}$ ($\tilde{x}$ the median of the profiles there, MAD the median absolute deviation from it; in log space for the log-averaged quantities), and a profile is flagged when $|z|$ exceeds the threshold (2.5, 3.5 or 5) on at least 10 % of its screened levels. When composites are grouped, each profile is judged within its own group (latitude bands or seasons that differ for real are not outliers of each other). Flagged profiles are drawn dashed, named in the status line and in the Comparison CSV, and stay in the composites unless *Leave flagged profiles out* is ticked; the recipe line records both choices. Example: 104 Venus Express and Akatsuki profiles grouped by 30° latitude bands at 3.5 flag 15, mostly SOIR profiles with very cold or warm layers near 110-130 km, among them orbit 1139 with 72 K at 116 km (archive 1-sigma 3490 K).

**Pressure levels.** Set *Vertical* to *Pressure* to compare on a grid uniform in log pressure (0.02 decades apart, about 1/20 of a scale height) instead of altitude. Profiles then line up whatever their altitude reference (the 1-bar level, an ellipsoid, a landing site, a sphere), so Galileo, Cassini UVIS and radio occultation profiles of the giant planets, or entry and orbiter profiles of Mars, compare directly; profiles without a pressure column are left out, and pressure itself cannot be the compared variable. The CSV and publication figure follow the grid (first column `pressure_hpa`, logarithmic pressure axis). The altitude cut needs altitude levels.

* Temperature and other quantities that vary smoothly: arithmetic mean $\mu(z) = \frac{1}{M}\sum_m X_m(z)$ and the sample standard deviation (ddof = 1) as the $\pm 1\sigma$ spread.
* Pressure, mass and number density, and electron density (they change by orders of magnitude with height): interpolation and averaging in log space, i.e. the geometric mean, with the spread as a multiplicative $1\sigma$ factor. If any value is zero or negative (noisy electron densities), VEDA falls back to the linear treatment.
* **Standard error of the mean and weighting.** The darker band around the mean is its standard error, $\mathrm{SEM} = s/\sqrt{n_{eff}}$, with $s$ the spread and $n_{eff}$ the effective number of profiles at that level (a factor in log space for the log-averaged quantities). With *Weighting: Inverse variance*, each value counts with $w_m = 1/\sigma_m^2$, its own 1-sigma at that level (archived or propagated; relative, $\sigma_m/X_m$, for the log-averaged quantities): $\mu = \sum w_m X_m / V_1$, $s^2 = \sum w_m (X_m - \mu)^2 / (V_1 - V_2/V_1)$ and $n_{eff} = V_1^2 / V_2$ (Kish), with $V_1 = \sum w_m$ and $V_2 = \sum w_m^2$. Values without an uncertainty, or with one under a millionth of the value (archives write 0 for assumed values), are left out at that level. With equal weights $n_{eff}$ is the number of profiles. The SEM contains the natural variability between profiles, not only their measurement errors. *Band around the mean* can show instead the 95 % interval of the mean from a percentile bootstrap: the profiles are resampled with replacement 1000 times (at least 200 for very large comparisons), the mean is recomputed with the same weights, and the 2.5 and 97.5 percentiles are taken. It needs no normal distribution of the profiles, so a few unusual profiles make it lopsided where mean $\pm 1.96$ SEM would not. The CSV has `composite_sem`, `plus_sem`, `minus_sem`, `ci95_low`, `ci95_high` and `n_effective` columns, also per group.
* The spread is drawn at levels covered by at least two profiles, and the mean where at least two profiles and at least half of all the compared profiles overlap: a single profile gives neither, and the mean of whichever few profiles reach a level would otherwise jump where that number changes.
* **One vertical reference.** Altitudes are measured from a sphere of the body's reference radius (Mars 3389.5 km, Venus 6051.8 km, Titan 2574.7 km), whether the archive gives a radius (MEX, VEX, MGS and MRO radio science) or an altitude above another sphere (Magellan gives altitudes above 6052 km; VEDA moves them up 0.2 km). The reference of each profile is shown on its **Altitude from** chip. Probes and a few data sets are the exception: Galileo altitudes are above the 1-bar level of Jupiter, Huygens and VEGA 2 altitudes above the landing site, Cassini Saturn profiles above the 1-bar ellipsoid or level and MRO CRISM aerosol profiles above the local surface; the altitude axis and the CSV exports name the reference, and the comparison says so when such profiles are mixed with others. Altitudes are not above the local surface or the Mars areoid, which differ from the sphere by several km.

Choose the variable and units on the left, colour the curves by mission, date or latitude, and toggle the mean and spread. **Export Comparison CSV** writes the gridded table: the composite and group means, spreads, standard errors and bootstrap intervals, the number and effective number of profiles at each level, and every profile on the common grid with its 1-sigma, with a header line per profile (mission, instrument, time, latitude, longitude, local time, solar zenith angle, Ls, altitude reference). **Export profiles, all variables** writes the same profiles at their own archived levels, nothing interpolated, one row per profile and level ("long" format, ready for `pandas.read_csv(..., comment="#")`, R or a pivot table): every archived and derived quantity, the 1-sigma uncertainties the archive gives and those VEDA propagates, and the latitude, longitude, local time and zenith angle of each level along the ray path where known. The units of each column are listed in the header.

**Redoing a comparison.** The second line of a Comparison CSV, `# recipe: {...}`, records the comparison: body, variable, grid, vertical coordinate, grouping and the exact profiles used (archive product ids). **Open comparison (from its CSV)** reads it back and redoes the comparison with those profiles, downloading any that are not in the cache; the same JSON can be posted to `/api/veda/compare/body/{body}` from a script. Files you loaded yourself are found only on the computer that holds them.

**Local time, solar zenith angle and Mars season.** Filters, groups and the altitude cut need each profile's local true solar time, solar zenith angle and, on Mars, the solar longitude Ls (0 northern spring equinox, 90 northern summer solstice, 180 autumn equinox, 270 winter solstice). VEDA uses the archive's values where it gives them (per level along the ray path, or in a header table as for MRO). Where it does not (Mars Express and Venus Express SOIR, for example), VEDA computes them from the time and the position: the body's position from the JPL approximate planetary elements (Standish, valid 1800-2050) and its rotation from the IAU WGCCRE models, for Venus, Mars, Jupiter, Saturn and Titan. Checked against the archives that publish both, the computed values agree to about 0.02 h in local time and 0.05 deg in Ls, and 0.3 deg or better in zenith angle (Mars Express AIO geometry files, MRO and MGS header tables, Venus Express VeRa 2014). The time used is that of the measurement at the planet: Mars Express and MRO label times are when the signal reached Earth, 4 to 21 minutes later, so VEDA uses the spacecraft time (MRO) or occultation time (MGS) from their header tables and subtracts the light time from Mars Express sample times (the profile time shown is then the measurement time at the lowest level; the label or file-name time is kept as LABEL_TIME and shown beside it). Profiles with a date but no clock time get no computed local time. In the profile viewer, computed values are marked with an asterisk.

**Climatologies (group composites).** *Group composites by* splits the compared profiles into bins and draws a mean and spread for each, with the individual profiles faded in their group's colour: latitude band, local solar time, solar zenith angle, Mars season Ls (bin width set under *Bin width*; by default 30°, 3 h, 30° and 30°), year, month, month of the year (all years together, a seasonal climatology) or mission. Each group follows the same rules as the overall composite (log-space averaging for pressure and densities; the mean where at least half of the group's profiles overlap). Profiles that lack the grouping quantity (for example no local time in the archive) are counted in the legend and left out of the group means.

**Altitude cut.** The *Altitude cut* tab plots the compared variable at one altitude, one point per profile, against time, latitude, local solar time, solar zenith angle, longitude, Mars season Ls or day of the year (all years together), coloured by mission, group, latitude or local time. It starts at the level reached by most profiles; type another altitude to move it. Hovering shows each profile's time and geometry, and clicking a point opens the profile. It uses the same profiles, grid and units as the comparison, so seasonal, latitudinal and local-time structure at a fixed height can be read directly.

*Show* changes what each point is:
- **Variable in a layer**: the minimum, maximum or mean of the compared variable between two altitudes (*From* and *to*), or the altitude of the minimum or maximum, for example the height of a temperature inversion or of the coldest level in any layer you choose. Only profiles covering the whole layer are used; means of pressure and densities are geometric. The status line counts the profiles whose extreme lies on an edge of the layer (they have none inside it).
- **From each whole profile**: quantities computed from each profile at its own resolution: the cold-point tropopause (altitude, temperature, pressure), the electron density peak and the fitted Chapman layer (peak density, altitude, scale height, R²), the electron content of the profile, the mean gravity-wave potential energy and dominant vertical wavelength, the departure from hydrostatic balance (largest and median, and the altitude of the largest) and the top temperature of the retrieval from density (section 3). Only those the compared profiles have are listed. They are also in the comparison CSV, on each profile's header line.

**Reference atmosphere.** On Venus and Mars, *Reference atmosphere* draws the body's reference profile. On Venus it is the global-average profile of the NASA Venus Global Reference Atmospheric Model (Venus-GRAM 2021; Justh et al. 2021, NASA/TM-20210022168), which below 100 km is the mean profile of the Venus International Reference Atmosphere (VIRA, Seiff et al. 1985), from 0 to 150 km, as a dotted line (temperature, pressure, density, and the scale height from its temperature with VEDA's constants; on pressure levels at the pressure of each level). *Show: Deviation from the reference atmosphere* plots each profile and the means minus it (in percent for pressure and density). It has no latitude, season or local-time dependence. The table comes from NASA's Aviary project (Apache License 2.0), which extracted it from Venus-GRAM; the Comparison CSV gets a `reference_*` column and a header line naming it. Example: 80 Akatsuki and Venus Express profiles average 226.6, 203.3 and 179.3 K at 70, 80 and 90 km against 229.8, 197.1 and 169.4 K in the reference.

On Mars it is the global-average profile of Mars-GRAM 2024 (GRAM Suite 2.1, NASA/TM-20240012934; dust optical depth 0.3; -8 to 80 km), from the same Aviary project. Its altitudes are above the MOLA areoid, which lies up to about 7 km above (equator) and 13 km below (poles) the 3389.5 km sphere VEDA's Mars profiles are referred to, so compare on pressure levels (*Vertical: Pressure*); the status line says so on altitude levels. (The table's own documentation calls its altitudes geopotential, but its pressures are hydrostatic for geometric heights: within 3 % up to 80 km with g falling as 1/r^2, 20 % off with a constant g.) Example on pressure levels: 10 Mars Express profiles within 45 degrees of the equator average 205.8, 188.7, 175.6 and 164.1 K at 3, 1, 0.3 and 0.1 hPa against 208.9, 189.2, 174.1 and 161.9 K in the reference; the 22 at higher latitudes, mostly in winter, are 20 to 40 K colder below 1 hPa. The Mars Climate Database is not offered: its terms do not allow commercial use without authorisation, which VEDA's MIT licence could not pass on.

**Cross section.** The *Cross section* tab shows the zonal mean of the compared profiles: in latitude bands (*Band width*, 10° by default) at every level of the comparison grid, the mean of the profiles in the band (with the comparison's weighting; geometric for densities and pressure, drawn as $\log_{10}$), its standard error $s/\sqrt{n_{eff}}$ (two or more profiles; in percent for the log-averaged quantities) or the number of profiles, as a latitude-altitude (or latitude-pressure) map. Profiles in a band are pooled whatever their time, local time or season, so the map is only as zonal as the sample; the profile count shows where it rests on one or two profiles. Profiles without a latitude are left out and counted. *Export cross section (CSV)* writes one row per band and level (latitude centre, level, mean, standard error, profiles) with the recipe line.

**Statistics of the points.** Under the cut, the mean of the points (geometric for densities and pressure) with its standard error $s/\sqrt{n}$, and 95 % percentile bootstrap intervals of the mean and of the median (the points resampled with replacement 1000 times), overall and per mission or group when coloured that way. Each point carries its own 1-sigma as an error bar where it has one: at one level the profile's 1-sigma there, for a layer mean $\sqrt{\sum_{ij} \sigma_i \sigma_j r_{ij}}/m$ over its $m$ grid levels, with $r_{ij} = \exp(-\Delta z^2/2L^2)$ and $L$ the correlation length of the profile's errors on the grid (that of its errors between levels, combined with that made by interpolating its levels onto the grid; relative errors for a geometric mean), for a layer minimum or maximum the 1-sigma at that level. Also as `POST /api/veda/analysis/point-statistics`.

**Binned means.** *Bins* takes a width in the units of the x axis (for example 30 for Ls or latitude, 2 for local time) and draws the mean of the points in each bin with its 95 % bootstrap interval, at the mean x of the bin's points (they may sit at one side of the bin), and lists each bin's range, mean, interval and number of profiles above the plot. Bins along local time, longitude and Ls start at 0 and wrap around (a point at 24.5 h is in the first bin); along other axes they start at a multiple of the width below the smallest value. Means are geometric on logarithmic axes. Example: 186 MRO radio occultation profiles at 20 km in 60-degree Ls bins: 150.9 K (95 %: 150.3 to 151.5, 90 profiles), 166.2 K (162.9 to 169.5, 59) and 179.7 K (177.9 to 181.4, 37). Also as `POST /api/veda/analysis/binned-statistics`.

**Correlation and regression.** *Against* also offers a second quantity of each profile: the compared variable at another altitude (*at (km)*) or any whole-profile quantity (tropopause, electron density peak, Chapman fit, wave energy, hydrostatic departure ...), so any two quantities can be plotted one against the other. With *Correlation and regression* ticked (any axis but time), VEDA gives Pearson's $r$ with a 95 % interval from Fisher's transform, $\tanh(\operatorname{atanh} r \pm 1.96/\sqrt{n-3})$, and its p-value; Spearman's rank correlation $\rho$ with a 95 % bootstrap interval; and the least-squares line $y = a + b\,x$ (drawn), with the standard errors of $a$ and $b$, a 95 % interval of $b$ from Student's $t$ ($n-2$ degrees of freedom) and one from 1000 bootstrap resamples of the profiles. Quantities on a logarithmic axis are correlated as $\log_{10}$. Also as `POST /api/veda/analysis/correlation`. Example: 51 Venus profiles give $r = 0.20$ (95 %: $-0.08$ to $0.45$) between the temperatures at 70 and 80 km, no significant correlation.

**Tides and waves (*Fit*).** Against local time, longitude or Ls, *Fit* draws the least-squares fit of a mean and one to four harmonics of the day (24 h), the circle (360 deg) or the Mars year through the points, $y(x) = a_0 + \sum_{n=1}^{N} [a_n \cos(n\omega x) + b_n \sin(n\omega x)]$ with $\omega = 2\pi/P$, and lists for each harmonic its amplitude $A_n = \sqrt{a_n^2 + b_n^2}$ and where it peaks, $x_n = \mathrm{atan2}(b_n, a_n)/(n\omega)$ (between 0 and $P/n$), each with a 1-sigma uncertainty from the covariance of the fit ($s^2 (X^T X)^{-1}$, $s^2$ the residual variance), the residual rms and $R^2$. Against local time these are the diurnal, semidiurnal ... components of the migrating tides; against longitude, at a near-fixed local time (aerobraking passes, sun-synchronous orbits), the wave-1, wave-2, wave-3 ... structure of non-migrating tides and stationary waves. Quantities on a logarithmic axis (densities, pressure) are fitted as $\ln y$ and their amplitudes are in percent of the (geometric) mean. The widest stretch without data is given: harmonic $n$ is marked not resolved when it exceeds $P/(2n)$, and a fit needs at least $2N + 2$ points at enough distinct positions. When every point has a 1-sigma (the compared variable at one altitude, from the archive or propagated), the fit is weighted, $w_i = 1/\sigma_i^2$ (relative errors for $\ln y$), and the covariance is $(X^T W X)^{-1}$, multiplied by the reduced $\chi^2$ when that exceeds 1 (then the points scatter more than their errors, and the scatter sets the uncertainty); the reduced $\chi^2$ is shown. In brackets beside each amplitude and position, a 95 % percentile bootstrap interval: the points are resampled with replacement 1000 times and refitted (positions taken around the circle, relative to the fitted one, so an interval near 0 h is not split at midnight); it does not assume Gaussian errors or a linear propagation, which fails for small amplitudes. Example: the inbound legs of MRO aerobraking passes 300-339 (Ls 94-96, about 41 deg S, 3.4 h local time) at 110 km give wave-2 and wave-3 density amplitudes of 24 and 20 % (1-sigma 8 %), with maxima at 166 and 32 deg E.

**Deviations.** *Show: Deviation from the mean* plots each profile minus its group's mean (or the composite mean when not grouped), and the group means minus the overall mean; for pressure and densities the deviation is in percent. This shows waves, tides and latitudinal structure that are invisible on a log axis spanning several decades.

Profiles read once are kept in memory for the session (the 512 most recent), so changing the variable, grouping or units does not read the files again.

### Live data sets
Data sets marked **live search** are not copied as an index: when you give **From** and **To** dates, VEDA asks the archive server for that instrument and window (ESA PSA EPN-TAP for Mars Express, Venus Express, Rosetta, BepiColombo and Huygens; the NASA PDS Registry API for MAVEN, Juno, New Horizons, MESSENGER, LRO, Galileo, Magellan, MGS, MRO, Pioneer Venus and Dawn; OPUS for Cassini and Galileo imaging and spectra). Up to 5,000 products per data set and window are listed; if there are more, VEDA says so and you can narrow the dates. Windows already searched in the last week are answered from the local catalogue.

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

### Temperature from a density profile
Accelerometer densities (MRO, Mars Odyssey), entry-probe densities (Phoenix, Spirit, Opportunity) and occultation number densities (SOIR, radio occultations) carry the temperature through hydrostatic balance. For every profile with a measured mass density, or a total number density $n$ (then $\rho = n k_B / R_{spec}$), VEDA integrates downwards from the top of the profile:
$$p(z) = p_{top} + \int_z^{z_{top}} \rho(z') g(z') \, dz', \qquad T(z) = \frac{p(z)}{\rho(z) R_{spec}}$$
Between two levels the density is taken as exponential, $\int \rho\,dz = (\rho_1 - \rho_2)\,\Delta z / \ln(\rho_1/\rho_2)$, which is exact for an isothermal layer. The upper boundary is $p_{top} = \rho_{top} R_{spec} T_{top}$, with $T_{top}$ the temperature of an isothermal layer fitted to the top 20 % of the profile's altitude range: $\ln \rho = c - \Phi / (R_{spec} T_{top})$, $\Phi = \int g\,dz$ the geopotential (weighted by the density uncertainties where the archive gives them). An error $\delta T_{top}$ decays downwards as $\delta T_{top}\,\rho_{top}/\rho(z)$, by a factor e per scale height, so the top one or two scale heights depend on the boundary and the rest does not; the fitted $T_{top}$ and the top altitude are listed with the profile. Noise in the density enters each level directly ($\delta T / T \approx \delta\rho/\rho$), so the 1-s MRO densities give noisy temperatures near their top.

The results are the variables *Temperature from density (hydrostatic)* and *Pressure from density (hydrostatic)*, in the profile view, comparisons and both CSV exports. The retrieval uses the body's mean molar mass, so it holds below the homopause, where the composition is that of the lower atmosphere (about 120 km on Mars, 125 km on Venus); above, where lighter atomic oxygen takes over, the temperatures come out too warm. Checked on archive profiles: the Phoenix entry temperatures (Withers & Catling 2010, retrieved the same way from the measured density) are reproduced to within 1 K from 10 to 100 km, and the Venus Express SOIR temperatures (Mahieux et al. 2015, with an altitude-dependent molar mass) to 1 K on average below 125 km (17 profiles), but by up to 150 K too warm at 150-165 km.

### Hydrostatic consistency
For every profile with temperature and pressure VEDA integrates the pressure with the profile's own temperature,
$$p_{hyd}(z) = p_0 \exp\left(-\int_{z_0}^{z} \frac{g}{R_{spec} T}\,dz'\right),$$
choosing $p_0$ so that the median of $\ln(p/p_{hyd})$ over the levels is zero (one bad level does not offset the rest), and reports the largest and the median $|p/p_{hyd} - 1|$ in percent, with the altitude of the largest, among the per-profile diagnostics (altitude cut *Show*, comparison CSV). Pressure, temperature and altitude that belong together give a few tenths of a percent (the Mars Express and Akatsuki radio occultation samples: 0.1 and 0.4 %); a larger value points to a wrong altitude scale, a level with a bad pressure or temperature, a different molar mass (SOIR: a median of 1.6 % for a profile ending at 121 km, a factor 3.5 at 166 km where the composition changes) or the top of a profile that depends on its upper boundary (Phoenix: 5.0 % at 119 km, median 0.8 %).

Where the profile has 1-sigma pressures or temperatures, VEDA also gives the departures its errors alone would cause: a perfectly hydrostatic pressure with the profile's own temperature is redrawn 200 times within the archived errors (correlated between levels as described under *Uncertainties of derived quantities*) and checked the same way; the median of its median departure and the 95th percentile of its largest are listed as *expected from the errors alone*. Departures well above these are not explained by the errors. Retrievals whose pressure and temperature come from one integration have errors correlated over the whole profile and depart much less than this level: the Mars Express sample gives 0.04 % (median) against 0.7 % expected; 32 Mars Express profiles 0.32 % against 0.52 %.

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

### Vertical wavenumber spectra
The *Spectra* tab takes the temperature profiles of the comparison (the same profiles and filters) in a layer (*Layer from ... to*; by default the 30 km covered by most profiles). In each profile covering at least 90 % of the layer with 16 or more levels, the temperature is put on an even grid (its median level spacing, at least 50 m), a quadratic fit is the background $T_0(z)$, and the normalised perturbation $x = (T - T_0)/T_0$ is multiplied by a Hann window $w$ and Fourier transformed. The one-sided power spectral density, in (cycles/km)$^{-1}$,
$$P(m) = \frac{2\,|X(m)|^2\,\Delta z}{\sum w^2}, \qquad m = \frac{k}{n\,\Delta z},$$
integrates over $m$ to the variance of the windowed perturbation. The spectra are put on one logarithmic wavenumber grid within the range every profile resolves and averaged; the mean is drawn with its 95 % bootstrap interval over the profiles (1000 resamples), over the faint individual spectra. The slope of $\log_{10} P$ against $\log_{10} m$ is fitted from three cycles per layer depth to a quarter of the coarsest Nyquist wavenumber, with its standard error and a bootstrap interval; a dashed $m^{-3}$ line (saturated gravity waves) is drawn for comparison. Example, 60 to 90 km on Venus: 32 FSI profiles give $-2.81 \pm 0.06$ (95 %: $-2.90$ to $-2.71$) for wavelengths of 0.2 to 10 km, 35 Akatsuki profiles $-3.26 \pm 0.07$ (1.1 to 9.6 km). *Export spectra (CSV)* writes the mean spectrum with its standard error and interval.

### Ionospheric Vertical Total Electron Content (VTEC)
For ionospheric occultation retrievals, VEDA integrates vertical electron density $N_e(z)$:
$$\text{VTEC} = 10^{-7} \int_{z_{base}}^{z_{top}} N_e(z) dz \quad [\text{TECU}]$$
where $1 \text{ TECU} = 10^{16} \text{ electrons}/\text{m}^2$.

### Tropopause
The cold-point tropopause is the coldest level of a profile inside a range where the body has one: 25 to 70 km on Titan (44 km and 70.4 K at the Huygens site, Fulchignoni et al. 2005) and 30 to 500 hPa on Jupiter and Saturn (near 100 hPa; Lindal et al. 1981, 1985), whose altitudes are relative to the 1 bar level. It counts only when the profile is warmer both below and above it in that range. Venus and Mars have no cold-point tropopause in VEDA: on Venus the tropopause near 60 km is a change in static stability while the temperature keeps falling into the mesosphere (use $N^2$ or a layer statistic of the lapse rate instead), and Mars has no persistent temperature minimum.

### Chapman layer
Electron density profiles are fitted with an alpha-Chapman layer, $N_e(z) = N_m \exp\left(\tfrac{1}{2}\left(1 - \zeta - e^{-\zeta}\right)\right)$ with $\zeta = (z - h_m)/H$, by nonlinear least squares; the peak density $N_m$, peak altitude $h_m$, neutral scale height $H$ and $R^2$ of the fit are given with the measured peak. These, and the electron content, are computed for every profile with electron density, with or without temperature (most ionospheric occultations have none).


### Uncertainties of derived quantities
Where the archive gives 1-sigma uncertainties of the measured quantities, VEDA carries them into what it derives, and shows them as bands (or error bars, *Plot style*) in the profile view, around each profile of a comparison of up to eight profiles, in the publication figure, and as `sigma_*` columns in every export.

Quantities that depend on one level are propagated to first order, the errors of $T$ and $p$ taken as independent:
$$\sigma_H = H\,\frac{\sigma_T}{T}, \qquad \sigma_\rho = \rho\sqrt{\left(\frac{\sigma_p}{p}\right)^2 + \left(\frac{\sigma_T}{T}\right)^2}, \qquad \sigma_\theta = \theta\sqrt{\left(\frac{\sigma_T}{T}\right)^2 + \left(\kappa\,\frac{\sigma_p}{p}\right)^2}, \qquad \sigma_c = c\,\frac{\sigma_T}{2T}.$$

Quantities that depend on several levels, the lapse rate, $N^2$ and $d\theta/dz$, and the temperature and pressure retrieved from a density profile (whose top boundary is fitted), are found by Monte Carlo: the profile is redrawn 200 times with Gaussian errors of the archived size (densities log-normally, with their relative error, so that they stay positive), everything is recomputed with the same derivatives and the same retrieval as the values, and the spread of the results is the uncertainty: half the width of their central 68 %, which is the standard deviation when they are normal but is not set by a few draws far out where a retrieval reacts strongly to its errors (SOIR temperatures from densities with 30-50 % errors had standard deviations up to 50 times larger, thousands of kelvin) (a fixed seed makes it repeatable; a level needs results from at least half the draws). For a central difference over $\pm\Delta z$ of independent errors this gives $\sigma_{dT/dz} = \sigma_T\sqrt{2}/(2\Delta z)$.

No archive VEDA reads says how its errors are correlated between levels, so VEDA finds out from each profile. Independent errors of the archived size would make the second differences of neighbouring values, $v_{i-1} - 2v_i + v_{i+1}$, scatter with the variance $\sigma_{i-1}^2 + 4\sigma_i^2 + \sigma_{i+1}^2$; errors with the correlation $r(\Delta z) = \exp(-\Delta z^2 / 2L^2)$ make it smaller, $\sigma^2(6 - 8r(D) + 2r(2D))$ for levels $D$ apart. The observed scatter (robust, from the median absolute deviation) gives the shortest $L$ that the profile allows, separately for temperature, pressure and density; the profile's own structure only adds scatter, so this $L$ is a lower bound. Real profiles scatter far less than their error bars: Mars Express temperatures 5 % of the independent variance (median of 32 profiles, $L$ = 0.26-1.36 km, median 0.52 km, close to the Fresnel radius of 0.3-0.65 km that the files give, the vertical resolution of the inversion), SOIR temperatures 0.1 % ($L$ = 3.8-10.6 km, about a scale height, over which the temperature is integrated from the density). The draws then have this correlation (a data set can instead declare $L$), and the result is listed with the profile's attributes (`error_correlation_temperature_km` and so on). Profiles with fewer than 12 levels with errors keep independent errors.

Correlation makes the uncertainty of a difference of levels smaller and that of a sum larger. On the real profiles above: lapse rate and $N^2$ 0.72 times (Mars Express, median) and 0.27 times (SOIR) their uncertainty with independent errors; the pressure integrated from SOIR densities 2.7 times larger; the temperature from density smaller in the middle of a profile and larger at its top, where the boundary temperature is fitted to levels whose errors no longer average out. The departures from hydrostatic balance expected from the errors hardly change (they depend on the error of each level against the whole profile): retrievals of pressure and temperature from one integration have errors correlated over the whole profile, longer than this lower bound.

**Systematic and random errors.** The archived 1-sigma is the random error. Mars Express, Akatsuki and Pioneer Venus Orbiter radio occultation profiles are integrated downward from a temperature assumed at the top of the profile, and their archives give three retrievals, from a low, a middle and a high boundary temperature (Mars Express 130, 165 and 200 K in the sample profile; Akatsuki 140, 170 and 200 K; Pioneer Venus 150, 200 and 250 K). VEDA uses the middle one and keeps half the difference between the low and the high one as a separate *systematic* uncertainty of temperature and pressure, and of every derived quantity, computed from both retrievals. It is largest at the top (Mars Express sample: 35 K at 48.8 km, 8.8 K at 35.8 km, 0.4 K near the ground; the random 1-sigma there: 10, 2.5 and 0.13 K) and is drawn as dotted lines beside the shaded random band, written as `systematic_*` columns in the profile exports and as `systematic_*` columns per profile in the comparison CSV. For Akatsuki, whose 1-sigma columns hold only the invalid value -9.99, it is the only uncertainty given. It is not used to weight composites or in the uncertainty filter, which use the random 1-sigma.

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

Press **Geometry** on any opened product. VEDA computes it with NAIF SPICE for 17 of the 25 missions: all except Mars Odyssey, the Mars landers and rovers (Spirit, Opportunity, Phoenix, Curiosity, InSight) and VEGA, which are not set up yet, and the Mars Orbiter Mission and Chandrayaan-2, which publish no kernels.

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
* Products are downloaded when you open, select or compare them, several at a time (Settings > Performance > Parallel downloads, default 4), with retries when an archive is busy. Each file is written in full before it is used, so an interrupted download never leaves a broken product.
* Everything is cached under the VEDA data folder (see the README). Downloaded products, the catalogue and SPICE kernels are reused offline.
* With **Settings > Network > Allow downloads** off, VEDA makes no network requests at all and works from the cache and the bundled samples.

---

## 8. Loading Your Own Files

Click **Load File** in the toolbar, drop files anywhere on the window, or use the drop zone in the Workflow Guide. You can select several files at once (up to 200 MB per file).

For a table, VEDA first shows what the file contains and asks what it is:

* **What it is**: the body, the mission (any VEDA mission, or *Other* with a name you type), the instrument, and the observation time in UTC. VEDA fills these from the label or header when it can (target, spacecraft, instrument, start time). The time places the profile in date searches and comparisons; leave it empty if you do not know it, nothing is invented.
* **Columns**: each column with its unit in the file, its first values and its range. For each, choose what it is (altitude, radius from the centre, temperature, pressure, electron, number or mass density, their 1σ uncertainties, latitude, longitude, local time, solar zenith angle) and its unit (km or m; K or °C; hPa, Pa, bar, mbar or kPa; cm⁻³ or m⁻³; kg/m³, g/cm³ or kg/km³). A mass density column is compared as *Mass density (archive)*, like the accelerometer and entry profiles in the archives; an uncertainty column without a unit in the file is taken to be in its quantity's unit. Files without a header (columns COL_1, COL_2, ...) can be read this way. VEDA suggests roles and units from the names and label units; check them. In text tables without a label, the values -999, -9999 and -99999, and values of 1e30 or more, are taken as missing.

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

* **Publication Figure** (Celestial Body mode) renders a journal-style Matplotlib figure of the current comparison at the DPI set in Settings (72 to 1200, default 300), following the grouping and the vertical coordinate.
* **Snapshot Plot (PNG)** saves the on-screen plot.
* **Export figure** (on any profile or comparison) saves PNG or SVG at a journal column width; see section 4.
* **Export Comparison CSV** saves the compared variable on the common grid: the composite and group means and spreads, the number of profiles at each level and every profile, with a header line per profile and a recipe line for **Open comparison (from its CSV)** (section 2, *Comparing observations*).
* **Export profiles, all variables (CSV)** saves the compared profiles at their own levels with every archived and derived quantity, one row per profile and level.
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
| Network | Allow downloads, Update notices, Automatic updates (*Check now*), Timeout, Large-file limit | Turn online archive downloads off (offline work), whether VEDA tells you when a newer build is published (one request to GitHub per session), whether a published build downloads the newest build once a week and installs it when it next starts (see below), how long to wait for a slow archive, and the size (default 250 MB) above which opening a product asks first, showing the file size and an estimated download time. |
| Performance | CPU worker processes, Parallel downloads | Worker processes read and derive many profiles at once (filtered comparisons, batch reading); the default is all cores but one, 1 runs everything in the main process. Profiles are read in batches across the workers, which is several times faster for comparisons of tens to hundreds of profiles. Parallel downloads (1 to 16, default 4) sets how many products are fetched at the same time. |
| Observation geometry | Automatic SPICE downloads, size limit | Download the kernels for opened missions and observations by themselves, and ask first above the limit. |
| Data folders | Open | Shows and opens the data, cache, export and log folders. |

Settings are stored in `settings.json` inside the VEDA data folder (see the README). A damaged or hand-edited file never stops VEDA from starting: invalid entries fall back to their defaults, and are kept in the file as they were until you have seen them (below).

### Automatic updates

A published build (not a copy run from source) looks for a newer build once a week, a minute after it starts, when *Automatic updates* and *Allow downloads* are on; *Check now* looks at once and shows the progress. A newer build for your system (`VEDA-<version>-windows-x86_64.zip`, `-macos-arm64`, `-linux-x86_64`) is downloaded into `updates/` in the data folder, checked against the size and SHA-256 digest that GitHub lists for the file, and unpacked beside the installation as `<folder>.update`. The next time VEDA starts it hands over to a small script (PowerShell on Windows, sh on macOS and Linux) that waits for it to exit, renames the installation to `<folder>.previous`, moves the new build into its place and starts it with the same command-line options; if a step fails, the old build is put back and started. The new build deletes `<folder>.previous` once it runs; `updates/install.log` records each step. Only the installation folder changes: the data folder, with your downloads and `settings.json`, is never touched, and VEDA does not update itself when the data folder lies inside the installation folder or the folder holding the installation cannot be written.

After an update, and whenever another version wrote `settings.json`, VEDA shows once what is new (the release notes) and the settings that were added (with their defaults), removed, renamed or changed (allowed values or default), with your stored value kept wherever this version accepts it and shown where it no longer does. *Use these settings* saves the values in the panel; closing it keeps everything as it is. What you saw is recorded in `settings_seen.json` beside `settings.json`.

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
