# Changelog

All notable changes to VEDA. Versions follow [semantic versioning](https://semver.org/): 0.x releases are public and in active development (feedback from users shapes them), 1.0.0 will mark a stable interface.

## 0.2.0 (2026-10-02)

From this version on, every tested change is published straight away as the latest release ("VEDA 0.2.0 build N"), so this log lists changes by version but the builds in between already contain them.

### Updates
- **Automatic builds**: each change to VEDA that passes the tests on Windows, macOS and Linux is built for all three and published as the latest release.
- VEDA tells you when a newer build has been published (a notice with a download link; About > *Check for updates*). About shows the build number, date and commit. Turn it off in Settings > Network.
- A build whose release was published no longer reports failure when removing an older build fails (a tag already deleted by a cancelled run).
- **Fix: flybys shown as orbiters.** In a body's mission list, Cassini and New Horizons at Jupiter (gravity-assist flybys) and Cassini at Titan (repeated flybys) were labelled *Orbiter*; they are now *Flyby*.
- The scale heights on the body quick-cards follow from each body's gas constant, gravity and the temperature now stated beside them: Pluto showed 50 km, the value in its warm upper atmosphere, against 17.7 km at its 37 K surface (both now shown); Titan 20.8 km (was 20.0), Mars 11.0 km (was 11.1).
- **Data & Licenses** lists every mission VEDA reads from each archive (the NASA PDS entry missed Mars Odyssey, Spirit and Opportunity, Phoenix, Curiosity, InSight and VEGA) and has an entry for the research data repositories (Zenodo, BIRA-IASB) with their CC-BY-4.0 terms, which the Venus Express VeRa and SOIR profiles come under.
- The body banner shows the molar mass and the heat capacity cp beside the gas constant (the user guide said it did; it showed neither). For bodies with temperature-dependent cp the value is marked as the reference.
- The test suite passes when `VEDA_HOME` points at a data folder already in use: two download tests found the files an earlier run had cached and fetched nothing.

### Performance
- **Multiprocessing.** Profiles for comparisons are read and derived in parallel worker processes; the number is set in **Settings > Performance** (default: all CPU cores but one; 1 turns it off). The workers start in the background when VEDA opens and are reused, and work is sent in chunks; reading 240 Venus Express profiles took 1.0 s with 4 workers against 5.5 s before.
- **Parallel downloads**: selected products, and the index pages of archive volumes, are fetched several at a time (Settings > Performance, default 4).
- **Downloaded products are found from the cache folder listing** instead of one disk check per catalogue row: the default comparison and *Downloaded only* searches took 30 s on a catalogue of 220,000 products, now about 1 s. Catalogue indexes for profile and product-type filters make those searches up to 7 times faster.
- **Faster start, no leftover temporary folders.** The app gave Matplotlib a new temporary folder on every start, so it rebuilt its font list each time and every closed or crashed process (including each worker) left a folder in the temp directory (8 per launch). It now keeps one in VEDA's cache.
- Profiles already read are kept in memory for the session, so re-plotting a comparison with another variable, grouping or unit is immediate.
- **Reading profiles about twice as fast.** PDS3 labels were parsed one character at a time (Mars radio science labels are 30 to 45 kB, each read twice), and the subsolar point was recomputed for every level of a profile although all levels share one time; together these were 60 % of the time to read a profile. A Mars comparison of 120 downloaded MEX, MGS and MRO profiles took 4.2 s in one process, now 2.2 s.
- **Hand-picked comparisons** read their archive profiles in the worker processes too (they were read one at a time), and a product that cannot be downloaded or read is left out instead of failing the whole comparison.

### Comparisons
- **Local time, solar zenith angle and Mars season for every profile.** Where the archive does not give them (Mars Express, Venus Express SOIR zenith angles), VEDA computes them from the time and position with the JPL planetary elements and IAU rotation models; they agree with the archives that publish them to 0.01 h and 0.05 deg. Mars Express profiles were left out of every local-time or zenith-angle filter and group before ("local time unknown").
- **Measurement times for Mars Express, MRO and MGS.** Their label times are ground-station or pass times, up to 21 minutes from the measurement; VEDA now uses the spacecraft (MRO) and occultation (MGS) times from the header tables, which were ignored along with their local time, zenith angle and Ls, and subtracts the light time from Mars Express sample times.
- **Mars season (Ls)**: filter by an Ls range (330 to 30 wraps through the equinox), group composites by Ls, and use Ls as the altitude-cut axis; Ls is also in both CSV exports.
- **Fix: Mars Express "AIO"/"IIO" files were offered as profiles.** They are short text files describing each occultation's geometry and failed to load, using up part of every comparison; existing catalogues are corrected the next time VEDA starts.
- **Fix: comparison CSV wrote small values as zero.** Values had four fixed decimals, so densities (1e-7 kg/m3 in the thermosphere) and pressures above about 60 km on Mars were exported as 0.0000; they now have six significant figures. The CSV also gains the group composites, the number of profiles at each level, and a header line per profile with mission, instrument, time, latitude, longitude, local time and solar zenith angle.
- **Fix: "downloaded only" missed repository data sets.** The Venus Express VeRa, FSI and SOIR profiles were never found by *Downloaded only* searches, by comparisons with *Download* unticked, or by the default comparison (they are kept as converted CSV files, not PDS labels), although the tables showed them as downloaded.
- **Export profiles, all variables**: the compared profiles at their own levels with every archived and derived quantity, uncertainties and per-level geometry, one row per profile and level, for analysis in Python, R or a spreadsheet.
- The publication figure follows the grouping: group means with their own spread over the faded profiles; loaded files are labelled with the mission they came from.
- **Group composites (climatologies)** by latitude band, local solar time, solar zenith angle, year, month, month of the year or mission, each with its own mean and spread.
- **Altitude cut**: the compared variable at one altitude against time, latitude, local time, zenith angle, longitude or day of year, one point per profile, coloured by mission, group, latitude or local time; click a point to open its profile.
- **Deviation view**: each profile minus its group (or composite) mean, in percent for pressure and densities.
- **Grid step**: the spacing of the common altitude grid can be chosen (*Grid step*, 0.01 to 100 km; empty keeps the default, 0.5 km on Venus, Mars and Pluto and 2 km elsewhere). The step is in the comparison CSV header.
- **Comparison choices are remembered**: the *Which profiles* fields, grouping, grid step, vertical coordinate and view are filled in again when VEDA opens (a remembered filter is used only after *Apply*, so nothing is downloaded unasked).
- **Fix: comparisons did not say that a data set was not indexed when its bundled sample was catalogued.** A date-range comparison of Mars Express (or Akatsuki, Cassini Titan ionosphere) on a new data folder found only the sample shipped with VEDA and reported "1 kept" without the usual "not indexed yet" note, as if the archive held nothing else; a data set now counts as indexed only once an archive volume has been indexed.
- **Fix: an older comparison could replace a newer one.** Changing the variable (or any option) while a comparison was still running drew whichever answer came back last: temperatures in degrees Celsius could appear under a pressure axis. Answers to superseded requests are now dropped, and the *Which profiles* report shows *Searching...* while a filtered search runs instead of the previous result.
- The comparison variable list offers H2SO4 vapour and microwave absorptivity (Magellan) only for Venus; on other bodies they always gave an empty comparison. The H2SO4 entry no longer shows its unit twice.
- **Fix: compared data missing from *Cite*.** Only products opened one by one or picked by hand were listed in the Cite panel; profiles that entered a comparison through the filter or the default selection (the usual way) were not, so the panel could say no archive product had been opened under a plotted comparison. Every archive data set in a comparison is now listed.
- **Pressure levels**: *Vertical* > *Pressure* compares on a grid uniform in log pressure (0.02 decades) instead of altitude, so profiles with different altitude references (1-bar level, ellipsoid, landing site, sphere) line up; profiles without pressure are left out. The CSV (first column `pressure_hpa`) and the publication figure (log pressure axis) follow.
- **Open comparison**: the Comparison CSV records the comparison (settings and the exact profiles used) on its second line, `# recipe: {...}`, and *Open comparison (from its CSV)* redoes it from the file; the same JSON can be posted to the comparison API.
- **Layer statistics and profile diagnostics in the altitude cut.** *Show* plots, one point per profile, the minimum, maximum or mean of the compared variable between two altitudes, the altitude of the minimum or maximum, or a quantity computed from each whole profile: cold-point tropopause, electron density peak, Chapman layer fit, electron content, gravity-wave potential energy and wavelength. These were computed for every profile but shown nowhere; they are now also in the comparison CSV.
- **Fix: tropopause searched at Earth altitudes on every body.** The cold point was looked for between 6 and 25 km, so Titan profiles gave the 25 km edge instead of the 44 km tropopause and Venus profiles (from 40 km) their coldest level. It is now searched where each body has one (Titan by altitude, Jupiter and Saturn by pressure) and only an interior minimum counts; Venus and Mars, which have no cold-point tropopause, report none.
- **Fix: gravity-wave perturbations upside down for profiles listed from the top.** T' and the wave potential energy were computed in altitude order but written back in the file's order, so occultation profiles stored top-down had them reversed in altitude.
- **Fix: no ionosphere diagnostics without temperature.** Electron content, peak and Chapman fit were skipped for electron density profiles without a temperature column, which is most ionospheric occultations.
- **Fix: log-space composites mixed logarithms and values.** If a later profile in a pressure, density or electron density comparison had a zero or negative value (noisy electron densities often do), the earlier profiles had already been interpolated as logarithms and the rest as values: two profiles of 10^4 cm^-3 averaged to 5005, the first was drawn at 9.2 (its logarithm), and the result depended on the order of the profiles. Log or linear averaging is now decided once for all profiles.
- **Fix: profiles crossing midnight or the 0/360 meridian.** A profile's local time and longitude were the plain median along the ray path, so a profile from 23.9 h to 0.1 h was placed at 12 h (in local-time filters, groups and the altitude cut) and one crossing longitude 0 at 180 (also in loaded files). They are now medians taken around the circle.
- **Fix: gravity-wave background and potential energy.** The background temperature came from an 8 km Savitzky-Golay window, which left only 58 % of a 6 km wave and 24 % of an 8 km wave in T' (and 120 % of a 4 km wave); it is now a zero-phase Butterworth low-pass with an 8 km cutoff (T' keeps 98 % of waves shorter than 5 km, half of an 8 km wave, under 4 % of waves longer than 12 km). E_p used the measured N^2, which contains the wave and was clipped to 1e-6 s^-2 where the wave made it negative, giving spikes of thousands of J/kg; it now uses the N^2 of the background and is left out where that is unstable. The dominant wavelength is searched only among the waves T' keeps. Mean wave energies and wavelengths change accordingly.
- **Gravity on Jupiter and Saturn depends on latitude**: profiles with a latitude use the effective gravity there (J2 of the Juno and Cassini gravity fields and rotation), from 23.1 m/s^2 at Jupiter's equator to 26.9 at its poles and 9.0 to 12.1 on Saturn, instead of 24.79 and 10.44 everywhere. Scale heights, dry adiabatic lapse rates, N^2 and wave energies on these planets change by up to 15 %.

### Data
- **Jupiter's composition from the Galileo probe.** Jupiter's molar mass (2.22 g/mol) and gas constant (3745 J/(kg K)) did not match its listed composition (89.8 % H2, 10.2 % He, 0.3 % CH4, which gives 2.26 g/mol). The composition is now the Galileo probe's: helium 0.1359 of the hydrogen-helium mixture (Helium Interferometer, von Zahn et al. 1998, JGR 103, 22815) and CH4/H2 = 2.38e-3 (mass spectrometer, Wong et al. 2004, Icarus 171, 153), i.e. 86.233 % H2, 13.562 % He and 0.205 % CH4: molar mass 2.3141 g/mol, R = 3593 J/(kg K), cp = 12,092 J/(kg K) (computed as for Saturn). Scale heights on Jupiter are 4.1 % smaller, densities computed from pressure and temperature 4.2 % larger, and the dry adiabatic lapse rate 2.2 % larger.
- **Titan's molar mass.** Titan was given 28.6 g/mol and R = 290.7 J/(kg K), heavier than pure nitrogen and impossible for its listed nitrogen-methane composition (27.4 g/mol). The composition is now the Huygens GCMS stratospheric one (Niemann et al. 2010, JGR 115, E12006): 1.48 % CH4 (constant above about 45 km; 5.65 % below 7 km), 0.101 % H2 and 98.419 % N2, giving 27.810 g/mol, R = 299.0 J/(kg K) and a reference cp of 1049 J/(kg K). Scale heights on Titan are 2.8 % larger, densities computed from pressure and temperature 2.8 % smaller, and cp(T), which is divided by the molar mass, 2.3 % larger (dry adiabatic lapse rate 2.3 % smaller).
- **Mars molar mass from its composition.** Mars had 43.34 g/mol and R = 191.8 J/(kg K), while its listed composition gave 43.50 g/mol. The composition is now the Curiosity SAM three-Mars-year mean (Trainer et al. 2019, JGR Planets 124, 3000): 95.1 % CO2, 2.59 % N2, 1.94 % Ar, 0.161 % O2, 0.058 % CO, giving 43.487 g/mol and R = 191.2 J/(kg K). Densities computed from pressure and temperature on Mars are 0.3 % larger, scale heights 0.3 % smaller and cp(T) 0.4 % smaller (737 J/(kg K) at 200 K).
- **Pluto's composition.** Pluto's listed composition (99 % N2, 0.5 % CH4, 0.1 % CO) added up to 99.6 % and gave 27.95 g/mol against the 28.01 g/mol used. It is now 0.30 % CH4 near the surface (New Horizons Alice, 0.28-0.35 %, Young et al. 2018, Icarus 300, 174), 515 ppm CO (ALMA, Lellouch et al. 2017, Icarus 286, 289) and N2 the rest: 27.977 g/mol, R = 297.2 J/(kg K), reference cp 1041 J/(kg K). Derived quantities on Pluto change by 0.1 %.
- **Saturn's helium from Cassini.** Saturn's atmosphere was given Voyager's 3.25 % helium by volume, with a molar mass (2.07 g/mol) and gas constant (4016 J/(kg K)) that did not even match that composition (2.14 g/mol). It is now 11 % helium (+-2 %, Cassini UVIS occultations and CIRS limb scans, Koskinen & Guerlet 2018, Icarus 307, 161), 0.45 % methane and 88.55 % hydrogen: molar mass 2.2975 g/mol, R = 3619 J/(kg K), cp = 12,276 J/(kg K) (7/2 R for hydrogen, 5/2 R for helium). Scale heights on Saturn are 9.9 % smaller, densities computed from pressure and temperature 11 % larger, and the dry adiabatic lapse rate 14 % larger. (A CIRS-only analysis, Achterberg & Flasar 2020, finds less helium, He/H2 = 0.04-0.075; the value is not settled.)
- **Mars Odyssey aerobraking density profiles** (ODY-M-ACCEL-5-DERIVED-V1.0, Withers & Murphy, PDS Atmospheres Node): thermospheric mass density from about 85 to 170 km for each aerobraking pass, October 2001 to January 2002 (329 passes), from the accelerometer, with 1-sigma uncertainties, latitude, longitude, local time and solar zenith angle per level (Tolson et al. 2005). Each pass is offered as two profiles, the inbound and the outbound leg, which are hundreds of kilometres and up to 35 degrees of latitude apart; both carry the periapsis time. The 7-s running-mean density is used. The labels give the densities in kg/m^3 but the values are kg/km^3 (checked with the drag equation and the file's own acceleration, speed and drag coefficient); VEDA converts them. Altitudes are from the radial distance, on the 3389.5 km sphere used for the other Mars data sets. 2001 Mars Odyssey added as a mission.
- **Venus Express temperature profiles**, which PSA and PDS do not hold, from the teams' research data repositories (all CC-BY-4.0):
  - VeRa radio occultations of 2014 (NASA DSN), 25 profiles with time, latitude, longitude, solar zenith angle and local time (Gramigna et al. 2023; Zenodo doi:10.5281/zenodo.20056665);
  - VeRa radio occultations 2006-2009 retrieved by Full Spectrum Inversion, 32 profiles with date, latitude and local time (Imamura et al. 2018; Zenodo doi:10.5281/zenodo.4621070). Below the lowest valid level these files hold the number density constant, which made the derived temperatures wrong (800 K at 39 km); those rows are masked;
  - SPICAV-SOIR solar occultations 2006-2014, 644 profiles of CO2 density, pressure and temperature from about 70 to 170 km at the terminator, with uncertainties (Mahieux et al. 2015; BIRA-IASB doi:10.18758/71021089).
- A new kind of source, research data repositories (Zenodo and institutional archives): profiles without PDS labels are described by the data set (columns and units) and rewritten as small normalised CSV files.
- Venus Express instruments SPICAV-SOIR, SPICAV, ASPERA-4 and MAG added to the mission.
- **Fix: bundled sample profiles missing on a first start.** The samples are copied into the catalogue on its first use, but the check for downloaded products ran before that, so a mission view or comparison opened first found none of them.
- **Fix: densities labelled KILOGRAM PER CUBIC METER multiplied by 1000.** The test for g/cm^3 (Cassini) looked for "GRAM" and "CM" in the unit with its spaces removed, which "KILOGRAM PER CUBIC METER" also passes. Units are now read word by word; data sets whose labels write KG/M**3 or g/cm^3 were not affected.
- **Fix: one file downloaded twice at the same time.** Products in one archive folder share format files, and selected products are downloaded several at a time (profiles in several worker processes): both downloads wrote the same temporary file, so one failed with a permission error (the product was left out) and the saved file could be cut short. Each download now writes its own temporary file, and a file left half-written by a full disk or a cancelled download is removed.

### Loading your own files
- **Load dialog**: before a table is read, VEDA shows its columns (unit in the file, first values, range) and asks what each column is and in which unit, and what the file is (body, mission, instrument, observation time). Headerless files can be read. The choices are saved with the file and offered for the next one; loaded profiles carry the mission and instrument in legends and colours and are included in filtered comparisons.
- **Fixes**: a pressure column in hPa was divided by 100 (the unit test for Pascal also matched "HPA"); loaded files were all given the time 2026-01-01T12:00, which then appeared as an observation time (now the label's time, the one you enter, or none); Celsius was guessed from the median value on some bodies only (now from the label unit, or values below zero).
- Header units written as `name [unit]` or `name (unit)` and `# KEY=value` metadata lines are read from text tables.
- **Fix: fill values in text tables.** CSV and ASCII files without a label kept -999, -9999 and 1e36 as values: a Kelvin temperature column with a -999 level was taken for degrees Celsius (273 K added to every level), and the fills went into the derived quantities. These values are now missing, as in PDS3 tables, and zero or negative temperatures and pressures are left out when the columns are guessed too.

### Plots
- **Fix: small values rounded away in the profile view.** Profiles were sent to the page with five decimals, so the buoyancy frequency N^2 (around 1e-4 s^-2) was drawn with one significant digit (5e-05) and thermospheric densities (Odyssey, 1e-8 kg/m^3) and high-altitude pressures as zero. They now keep seven significant figures. The comparison and the CSV exports were not affected.
- **Log axes** (pressure, densities) showed minor ticks as bare digits ("5 6 7 8 9 0.1 2 3", where 5 meant 0.05) and SI prefixes ("100μ" for 1e-4), which read as wrong values after a unit change. Axes spanning less than about three decades now have 1-2-5 ticks with full values (0.05, 0.1, 0.2, 0.5 ...), wider ones one tick per decade as powers of ten; every axis uses powers of ten instead of SI prefixes.
- The footprint map titles showed a literal "&bull;" ("MARS &bull; Spatial Distribution of Observations"), and image titles in the product viewer "&middot; band 2"; the characters are shown now.
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
