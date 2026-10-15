# Model audit: where VEDA computes rather than reads

VEDA plots archive data. Where it computes something instead, from SPICE, a model, a formula or a
constant, this file lists it, ranked by how much a wrong result could mislead. It was made in
October 2026 from the code graph (graphify queries for positions, orbits, kernels, reference
atmospheres and derived quantities) and a read of every module named below. Line numbers are those
of commit `382295c`.

Each item gives: where, what it does, the basis (citations checked against Crossref with Argus;
all 11 resolved), what is wrong, how to verify it, and the minimal fix. **Status** says whether it is
fixed and in which commit.

Severity:
- **High**: a real-looking result that is not what it claims (wrong time, wrong vehicle, wrong
  point), with nothing in the interface to say so.
- **Medium**: a systematic offset of a few km, minutes or per cent, or a model value shown without
  saying it is a model.
- **Low**: small, documented, or affects bodies VEDA has no profiles for.

## What was checked against real ephemerides

- `analysis/solar_geometry.py` (approximate planet positions, Standish 1800-2050 Keplerian
  elements; IAU WGCCRE 2009 rotation, Archinal et al. 2011, doi:10.1007/s10569-010-9320-4) against
  SPICE with DE440 (Park et al. 2021, doi:10.3847/1538-3881/abd414) and PCK00011, at nine epochs
  1979-2024:
  - subsolar longitude within 0.010 deg (Venus), 0.069 deg (Mars), 0.20 deg (Jupiter, Saturn),
    0.16 deg (Titan): under 1 minute of local time;
  - subsolar latitude within 0.055 deg;
  - Mars Ls within 0.013 deg of SPICE `lspcn`;
  - Earth-body light time within 6 s.
- Body radii in `core/registry.py` against PCK00011: Venus, Pluto and Moon equal; Mars 3389.5 km is
  the volumetric mean of 3396.19/3376.20 km; Jupiter 69911 km and Saturn 58232 km are the IAU mean
  radii (Archinal et al. 2018, doi:10.1007/s10569-017-9805-5); Titan 2574.7 km matches PCK00011
  within 0.5 km.
- Every surface gravity against GM/R^2 (GM from the registry): all within 1 %, except Jupiter and
  Saturn (item M5).
- `et_to_utc` against SPICE `et2utc` with naif0012.tls: within 2 ms after the fix in L0 below.

No spacecraft position anywhere in VEDA is invented. Spacecraft positions come only from SPICE
(Acton 1996, doi:10.1016/0032-0633(95)00107-7). There is no schematic orbit, random placement or
fallback position, and a missing kernel is reported as an error. Observations without a position are
left off the maps and counted.

## High

### H1. Probe data sets drawn with the orbiter's orbit
- **Where:** `api/archive_routes.py` (geometry), `geometry/compute.py`. Data sets: Galileo probe
  `gp-j-entry-v1.0`, Huygens HASI `hp-ssa-hasi-2-3-4-mission-v1.1`, VEGA 2 lander, Pioneer Venus
  probes, and the Mars entry profiles (MER, Phoenix, MSL, InSight).
- **What:** the Geometry tab drew the mission's NAIF spacecraft, Galileo orbiter (-77) and Cassini
  (-82), not the probe, and labelled it as the observation.
- **Wrong:** this is the wrong vehicle. A first fix refused geometry for probes; the owner pointed
  out that descent probes have their own trajectories.
- **Fix:** each probe gets its own track, in this order:
  1. the profile's own reconstructed positions (MER, Phoenix, MSL, InSight);
  2. the probe's trajectory data set: Huygens, the reconstructed descent
     HP-SSA-DTWG-6-TRAJECTORY-V1.0 (Kazeminejad et al. 2007, doi:10.1016/j.pss.2007.04.013), added as
     a data set;
  3. the Galileo probe's post-entry trajectory from its Doppler wind data (`dwe/probetrj.tab`, EME50
     vectors turned into latitude and System III longitude with the file's pole and prime meridian;
     `archives/trajectories.py`). It leaves out the drift with the winds, about 0.4 deg
     (Atkinson et al. 1998, doi:10.1029/98JE00060), which the tab says.
  The VEGA balloons' records carry their VLBI-tracked positions (drawn as the flight track). Without
  any of these (VEGA landers, Pioneer Venus probes) the tab shows the published sites, labelled as
  published: PV impact sites from the NASA NSSDCA probe pages (Colin 1980,
  doi:10.1029/JA085iA13p07575), VEGA landing sites from the data set's catalogue vega_host.cat
  (Lorenz et al. 2018).
- **Verify:**
  - DTWG landing site 10.25 S, 167.68 E against Kazeminejad et al. (10.3 S, 167.7 E), tested on the
    archive file.
  - Galileo probe trajectory file at entry: 6.53 N, 4.88 W. The probe's own SPK (NAIF -344,
    s960730a.bsp, which ends at entry) gives 6.53 N, 4.94 W; tested with the kernel. The mission
    catalogue (gp_0001 MISSION.CAT) gives 6.54 N, 4.46 W. The descent ends near 6.41 N, as in the ASI
    file.
- **Status:** fixed.
- **Still open:**
  - The body map now draws the descent line of profiles that carry positions (2D map; the 3D globe
    still shows points).

### H2. Date-only times drawn as the observation (CRISM limb profiles)
- **Where:** `api/archive_routes.py:306-313`, `geometry/compute.py:184` (`orbit_geometry`). Data sets
  `mro-crism-smith2013-aerosol` (`datasets.py:695`) and `mro-crism-guzewich-aerosol` (`:729`).
- **What:** their catalogue time is a date, derived from Mars year and Ls (VEDA keeps only the
  date). `str2et` reads it as 00:00 UTC, so the tab draws MRO from 23:30 to 00:30 and marks
  midnight as "the observation".
- **Wrong:** this is a real MRO position at an invented time.
- **Fix:** refuse orbit geometry when the product's time has no clock time.
- **Status:** fixed with H1.

### H3. Earth-reception times treated as spacecraft times in orbit geometry
- **Where:** `geometry/compute.py:184-245` (`time_convention: "spacecraft"`), called for every
  product without per-sample ephemeris seconds.
- **What:** products whose catalogue times are ground-station times are drawn as if the
  spacecraft were there at that time:
  - Magellan radio occultations (`datasets.py:389, 407`, times from the ERT column);
  - Akatsuki (L2 and L4 labels: "the UTC receiver date and time");
  - Mars Express (`times_earth_received=True`, `:996`).
- **Wrong:** the "observation" arc is shifted along the orbit by the one-way light time: 4-22 min
  at Mars, 2-14 min at Venus.
- **Verify:** compare the arc with the occultation geometry (`observation_geometry`) of a product
  that has ephemeris seconds.
- **Fix:** for data sets whose times are Earth-received, subtract the light time before computing.
  The convention lives in one data set flag, used by both the profile reader and the geometry.
- **Status:** fixed (Magellan and Akatsuki flagged; the orbit arc uses the time at the planet).

### H4. Sub-Earth point evaluated two light times early
- **Where:** `geometry/compute.py:138`,
  `subpnt(..., mid - lt_mid, fixed, "CN", "399")`.
- **What:** `subpnt`'s epoch is the observer's (Earth's), and `CN` already moves the target back by
  the light time. Passing `mid - lt_mid` evaluates the planet at `mid - 2 lt`.
- **Wrong:** the sub-Earth point on the tangent-point map is off by the planet's rotation in one
  light time: 1-5 deg of longitude at Mars, about 1 deg at Titan, negligible at Venus.
- **Verify:** `subpnt` at `mid` against the planet-fixed direction to Earth already computed at
  line 96 (`earth_fixed`).
- **Fix:** call it at `mid`.
- **Status:** fixed; test against SPICE with real kernels.

## Medium

### M1. Tangent altitude on the equatorial radius
- **Where:** `geometry/compute.py:84, 172`.
- **What:** tangent altitudes are taken from PCK `RADII[0]`, the equatorial radius, while the
  profile's own altitudes, and the radius passed in at `archive_routes.py:323`, use VEDA's
  reference radius (`registry.radius_km`).
- **Wrong:** on Mars the Geometry tab's tangent altitude is 6.7 km lower than the profile's
  altitude.
- **Fix:** take altitudes above the body's reference radius, as the profile view does, and say so.
- **Status:** fixed.

### M2. Akatsuki times are ground-station times
- **Where:** `archives/datasets.py:1002, 1023` (no `times_earth_received`).
- **What:** the labels say UTC_TIME is "the UTC receiver date and time" (UDSC64), and
  EPHEMERIS_SECONDS corresponds to it.
- **Wrong:** profile times are 2-14 min after the measurement at Venus. Local time and zenith angle
  are not affected (they come from the files).
- **Fix:** set `times_earth_received`; the label time is kept as LABEL_TIME.
- **Status:** fixed with H3.

### M3. Computed Ls not marked as computed
- **Where:** `frontend/js/veda_app.js:3169`; `archives/profiles.py:638-639`.
- **What:** when the archive gives no Ls, VEDA computes it (checked against SPICE above). Local time
  and zenith angle carry the "computed*" mark; Ls does not.
- **Fix:** mark it the same way.
- **Status:** fixed.

### M4. Body quick-card values without sources
- **Where:** `frontend/js/veda_app.js:168-301` (`BODY_PHYSICAL_CONSTANTS`).
- **What:** these are hard-coded display strings: mean temperatures, scale heights at those
  temperatures, solar distances. The scale heights agree with R T / g0 from the registry, but the
  temperatures have no source and are shown as facts.
- **Fix:** compute what can be computed from the registry, and label the rest as typical values
  with a source, or remove them.
- **Status:** fixed: every value comes from the registry, the reference atmosphere or the
  orbital elements, or reads N/A.

### M5. Giant-planet gravity without a latitude
- **Where:** `core/registry.py:70-71, 98-99`; `analysis/atmospheric.py:58-107`.
- **What:** surface gravity 24.79 m/s^2 (Jupiter) and 10.44 m/s^2 (Saturn) are the effective
  equatorial 1-bar values. They are paired with the mean radius and used in g0 (R / (R + z))^2 when
  a profile has no latitude.
- **Wrong:** at mid-latitudes the gravity is up to 5 % too low (GM / R^2 at the mean radius is 25.9
  and 11.2). With a latitude, VEDA's J2-and-rotation model is used, which is right.
- **Fix:** say so: without the latitude the model text gives the equator-to-pole range of the
  effective gravity, and the profile view shows the gravity model.
- **Status:** fixed (labelled). No latitude is guessed.

### M6. Exosphere bodies carry made-up gas constants
- **Where:** `core/registry.py:165-244` (Mercury, Moon, Ceres, Vesta, comet 67P).
- **What:**
  - Mercury, the Moon and Vesta: molar mass 20 g/mol and cp 1000 J/(kg K), which are
    placeholders.
  - Ceres: molar mass 18.015 and cp 1850 (pure water vapour).
  - 67P: cp 1850.
  - All five: reference pressures of 1e-12 to 0 hPa, and compositions without sources.
- **Wrong:** these bodies have no collisional atmosphere, so scale height, potential temperature
  and N^2 have no meaning there. Vesta's reference pressure of 0 would make the potential
  temperature infinite.
- **Fix:** mark them as having no atmosphere for derived quantities (none are computed) and say so
  in the interface. VEDA has no profiles of these bodies.
- **Status:** fixed: flagged as exospheres; the placeholders are no longer shown, and the
  compositions are replaced by the NSSDCA fact-sheet descriptions.

## Low

### L0. Ephemeris seconds to UTC with today's leap seconds (fixed)
- **Where:** `analysis/solar_geometry.py:31`.
- **What:** TDB - UTC was fixed at 69.184 s, so 2004 times were 5 s early and 1991 times 11 s early.
- **Status:** fixed in `382295c`. It now uses each date's leap seconds and matches SPICE within
  2 ms.

### L1. CO2 triple-point pressure (fixed)
- **Where:** `analysis/condensation.py:33`.
- **What:** the frost point stops at the triple point. The value was 5185 hPa; Span & Wagner (1996,
  doi:10.1063/1.555991) give 5179.5 hPa.
- **Status:** fixed in `382295c`.

### L2. Planet positions for moons
- **Where:** `analysis/solar_geometry.py:12, 49`.
- **What:** Titan uses Saturn's position. The docstring says the Sun's direction changes by less
  than 0.01 deg; for Titan it is up to 0.05 deg.
- **Status:** measured against SPICE: 0.16 deg in all; docstring corrected.

### L3. Aberration on a planet-centred track
- **Where:** `geometry/compute.py:216`.
- **What:** `LT+S` with the planet as observer adds stellar aberration from the planet's own orbital
  motion: 1-10 km at 10^5 km.
- **Fix:** use `LT`.
- **Status:** fixed.

### L4. One molar mass for each atmosphere
- **Where:** `analysis/atmospheric.py:430-444` (`density_gas_constant`), `thermo.py:107`.
- **What:** the hydrostatic temperature from density, the heat capacity and the CO2 fraction use the
  bulk composition unless the archive gives a molar mass per level (SOIR does).
- **Wrong:** in the Mars thermosphere above about 130 km, where atomic O grows, the accelerometer
  temperatures are biased high by the molar-mass ratio (a few per cent at 150 km).
- **Fix:** documented here. A height-dependent composition would be a model choice, to be made with
  a cited model.

### L5. Heat capacity for potential temperature on Jupiter and Saturn
- **Where:** `thermo.py:135`.
- **What:** the constant-cp potential temperature uses the high-temperature 7/2 R reference cp,
  while N^2 and the adiabatic lapse rate use the intermediate cp(T) (Conrath & Gierasch 1984,
  doi:10.1016/0019-1035(84)90065-4).
- **Fix:** documented. These two are different conventions in the literature.

### L6. Labels on the body map
- **Where:** `frontend/js/veda_app.js:2492, 2548`.
- **What:** the status line says "Footprints & Ground Tracks", but one point per profile is drawn.
  The axis says "Longitude" without east. Longitudes are planetocentric east.
- **Fix:** say so.
- **Status:** fixed ("one point per profile"; axes "east, planetocentric").

### L7. Empirical thresholds
These are tuning choices, each explained in a comment, with no literature value behind them:
- `datasets.py:823, 848-849, 988-989`: the 2-sigma ends of noise and the -3-sigma neutral-region cut
  for MAVEN ROSE and Mars Express;
- `repositories.py:147-171`: the 15 K/km lapse limit for the VeRa FSI bottom;
- `wave_and_stability.py:87-88`: the 8 km gravity-wave cut-off;
- `coincidence.py:25`: the coincidence tolerances;
- `spectra.py:52`: the 3-spacing gap rule.

They are listed so a user can see them.

### L8. Predicted ephemerides
- **Where:** `geometry/kernels.py`.
- **What:** only the `dsindex` sources drop predicted kernels. Regex sources such as the BepiColombo
  and Mars Express monthly files could include predicted arcs.
- **Fix:** none needed for past observations, which are covered by reconstructed files. To check,
  compare the kernel's comment area.

### L9. Small inconsistencies found in the audit (fixed)
- `gravity_profile` said it applied to Jupiter and Saturn; Mars uses it too (GM, J2 and rotation;
  J2 only). The docstring and the interface text now say so.
- The gas constant was 8314.46 in two places and 8.314462618 in the heat-capacity code: one value
  now, the CODATA 2018 one (differences of 3e-7).
- **Status:** fixed.

### L11. CO2 frost point with the bulk CO2 fraction (fixed)
- **Where:** `analysis/atmospheric.py` (frost point), `archives/datasets.py` (SOIR).
- **What:** SOIR gives the CO2 volume mixing ratio at each level; the frost point used the bulk 0.965.
- **Status:** fixed: the per-level fraction is used where the archive gives one (0.5 K at 140 km on
  orbit 335).

### L10. Per-level gas constant with a bulk heat capacity (SOIR)
- **Where:** `analysis/atmospheric.py` (speed of sound, adiabatic lapse rate).
- **What:** where the archive gives a molar mass per level (SOIR, Venus thermosphere), R follows
  it, but cp(T) is the bulk CO2-N2 mixture's.
- **Wrong:** gamma and the adiabatic lapse rate are inconsistent above about 120 km, where atomic O
  matters.
- **Fix:** none without the composition per level; documented.

## Not models: conversions of archive values (for completeness)

The following convert or tidy archive values rather than model anything:
- unit conversions in `archives/profiles.py:58-96`;
- conversions of geodetic heights on the Mars spheroid to the reference sphere: `profiles.py:213-224`,
  constants from the archives' SIS documents;
- the kg/km^3 correction of the Odyssey and MRO accelerometer densities: `datasets.py:687, 792`,
  checked with the drag equation;
- the fill values named in labels.

Each is noted in the profile's altitude reference or in the CHANGELOG.
