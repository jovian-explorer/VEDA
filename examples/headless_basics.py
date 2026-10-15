"""Using VEDA from Python, without the window.

Runs offline on the profiles bundled with VEDA (an Akatsuki radio occultation of Venus and a
Mars Express neutral-atmosphere and ionosphere pair):

    python examples/headless_basics.py            # offline
    python examples/headless_basics.py --online   # also index, search and download from the archive

Everything here is the code the app itself uses; there is no separate API layer.
"""
from __future__ import annotations

import sys

import numpy as np

from veda.analysis.atmospheric import compare_profiles_on_body, profile_diagnostics
from veda.archives import catalog
from veda.archives.profiles import load_profile
from veda.core.registry import get_body


def show(prof, keys=("temperature_k", "pressure_hpa")):
    z = prof.altitude_km
    i = int(np.nanargmin(np.abs(z - np.nanmedian(z))))
    print(f"  {prof.observation_id}  {prof.time_utc}  lat {prof.latitude:.1f}  lon {prof.longitude:.1f}  "
          f"{np.nanmin(z):.1f}-{np.nanmax(z):.1f} km")
    for k in keys:
        v = getattr(prof, k, None)
        if v is not None:
            print(f"    {k} at {z[i]:.1f} km: {v[i]:.4g}")
    for k in ("scale_height", "buoyancy_freq_sq", "potential_temperature"):
        if k in prof.derived:
            print(f"    {k} at {z[i]:.1f} km: {prof.derived[k][i]:.4g}")


def main(online: bool = False) -> None:
    # 1. Search the catalogue (the bundled samples are in it from the start)
    res = catalog.search(catalog.SearchQuery(body_id="venus", kind="profile", limit=5))
    print(f"Venus profiles in the local catalogue: {res['total']}")

    # 2. Read a profile: the reader applies the data set's units, fill values, timing and
    #    corrections and derives the quantities (scale height, N^2, potential temperature ...)
    venus = load_profile("vco-v-rs-5-occ-v1.0", "rs_20160303_223100_udsc64_l4_ae_v10")
    show(venus)
    ion = load_profile("mex-m-mrs-5-occ", "M32ICL2L04_IIX_040931105_60")
    d = profile_diagnostics(ion)
    print(f"  Mars ionosphere: peak {d['ne_peak_cm3']:.4g} cm^-3 at {d['ne_peak_alt_km']:.1f} km, "
          f"Chapman fit peak {d['chapman_hm_km']:.1f} km, electron content {d['tec_tecu']:.3g} TECU")

    # 3. Compare: put profiles on one altitude grid with their mean and spread
    mars = load_profile("mex-m-mrs-5-occ", "M32ICL2L04_AIX_040931105_60")
    cmp = compare_profiles_on_body([mars], get_body("mars"), variable_name="temperature_k", altitude_step_km=1.0)
    print(f"  comparison grid: {len(cmp['grid_km'])} levels, {len(cmp['profiles'])} profile(s)")

    if online:
        # 4. Index a data set from its archive, search it by date and download a product
        from veda.archives.datasets import get_dataset
        ds = get_dataset("mgn-v-rss-5-occ-prof-rtpd-v1.0")
        print(f"Indexing {ds.title} ...")
        catalog.refresh_dataset(ds)
        found = catalog.search(catalog.SearchQuery(dataset_ids=[ds.id], start="1991-10-05", end="1991-10-06",
                                                   kind="profile"))
        print(f"  {found['total']} Magellan profiles on 5-6 October 1991")
        show(load_profile(ds.id, found["products"][0]["product_id"]))


if __name__ == "__main__":
    main(online="--online" in sys.argv)
