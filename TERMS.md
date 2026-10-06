# Terms of Use

These terms describe how VEDA may be used and what it does on your computer. They add to, and do not replace, the [MIT License](LICENSE) under which the software is distributed, and the terms of the archives whose data you download ([DATA_POLICY.md](DATA_POLICY.md)).

## 1. The software

* VEDA is free and open-source software under the MIT License. You may use, copy, modify and redistribute it, including for commercial purposes, as long as the copyright and license notice are kept.
* VEDA is provided **as is, without warranty of any kind**. The author accepts no liability for any loss or damage arising from its use, including errors in data, derived values, figures or geometry.
* VEDA is a personal research tool developed by Keshav Aggarwal. It is not an official product or service of ISRO, and it is not affiliated with, endorsed by or sponsored by NASA, ESA, JAXA or ISRO.

## 2. The data

* The data you search and download belong to the mission teams and are published by their archives (NASA PDS, ESA PSA, JAXA DARTS, ISRO ISSDC, NASA NAIF and the mission SPICE archives) and by the instrument teams' research data repositories (Zenodo, BIRA-IASB). Each archive's terms apply to the data, and you are responsible for following them, including any registration terms you accept with ISSDC/PRADAN.
* VEDA does not redistribute data, apart from a few unmodified public sample products bundled for demonstrations and tests (listed in DATA_POLICY.md).
* Cite the data sets, the instrument teams and the archives in any publication, as described in DATA_POLICY.md.

## 3. Your results

* VEDA reads products, converts units, derives quantities and computes geometry with documented methods, but **you are responsible for checking results** against the product labels, the data set documentation and the instrument team's publications before relying on or publishing them.
* Derived quantities (for example potential temperature, static stability, scale height and VTEC) depend on the body constants and assumptions documented in the app and in USAGE.md. They are not the instrument team's official retrievals.

## 4. Fair use of the archives

The archives are shared public services. VEDA is built to treat them politely:

* it reads an archive's index once and keeps it in a local catalogue, so repeated searches do not contact the archive (a few index files are read at a time, as many as the *Parallel downloads* setting, 4 by default);
* live archive searches (ESA PSA, NASA PDS Registry, OPUS) ask once per data set and date window, list at most 5,000 products per answer, and are remembered for a week;
* it downloads only the products you open, select or compare (a filtered comparison downloads the candidate profiles it needs, up to four times the number per mission you set; untick *Download* to use only the cache), a few at a time (Settings > Performance, default 4), waits and retries when a server is busy, and keeps every downloaded file in a local cache;
* SPICE kernels are downloaded once per file and reused; automatic kernel downloads can be turned off, and above a size you choose VEDA asks first.

Please do not use VEDA, or modify it, to download whole archives in bulk without need, to bypass access controls, or to put unreasonable load on any server. For bulk transfers, use the bulk-download services the archives provide.

## 5. Privacy

* VEDA has no user accounts, no analytics, no advertising and no telemetry. It does not send anything about you or your work to the author or to anyone else.
* It connects to the internet only to contact the archive and SPICE servers you search or download from (including the SPICE kernels for missions and observations you open, if automatic kernel downloads are on), and once per session GitHub, to see whether a newer VEDA build has been published (turn this off in **Settings > Network**); nothing about you or your data is sent. With **Settings > Network > Allow downloads** off it makes no network requests at all. Those servers see an ordinary web request from your computer, with a User-Agent that names VEDA.
* Logins to ISRO ISSDC/PRADAN happen on the PRADAN website in your browser. VEDA never sees or stores your credentials.
* Everything VEDA stores (settings, archive catalogue, downloaded products, kernels, exports, logs) stays in its data folder on your computer (see the README). The list behind the **Cite** panel (which data sets and features you used) is kept only in this browser's local storage. Delete the data folder, or press *Start a new list* in Cite, to remove it.
* The local server binds to `127.0.0.1` by default. If you start it with `--host 0.0.0.0`, anyone on your network can use it, since it has no authentication.

## 6. Changes

These terms may be updated with new releases of VEDA; the version in the repository at the time of a release applies to that release.

Questions or problems: https://github.com/jovian-explorer/VEDA/issues
