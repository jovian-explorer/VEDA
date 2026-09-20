"""Comprehensive API smoke test : checks all endpoints the frontend calls."""
import json
import urllib.request
import sys

BASE = "http://127.0.0.1:8992"
PASS = []
FAIL = []


def get(path, label=None):
    label = label or path
    try:
        r = urllib.request.urlopen(BASE + path, timeout=10)
        d = json.loads(r.read())
        PASS.append(label)
        return d
    except Exception as e:
        FAIL.append((label, str(e)))
        return None


def post(path, body, label=None):
    label = label or path
    try:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        r = urllib.request.urlopen(req, timeout=30)
        d = json.loads(r.read())
        PASS.append(label)
        return d
    except Exception as e:
        FAIL.append((label, str(e)))
        return None


def check(cond, label):
    if cond:
        PASS.append(label)
    else:
        FAIL.append((label, "assertion failed"))


# --- health and meta ---
health = get("/api/health")
check(health and health.get("status") == "ok", "health.status==ok")

meta = get("/api/meta")
check(meta is not None, "meta returns data")
check(meta and "streams" in meta, "meta has streams")
check(meta and "vocabulary" in meta, "meta has vocabulary")
check(meta and "settings" in meta, "meta has settings")
check(meta and "group_by_options" in meta, "meta has group_by_options")
check(meta and "sample_data_available" in meta, "meta has sample_data_available")
check(meta and meta.get("app", {}).get("version"), "meta.app.version present")
check(meta and meta.get("citation"), "meta.citation present")
check(meta and "default_stream" in (meta.get("settings") or {}), "settings.default_stream")
check(meta and "warn_download_mb" in (meta.get("settings") or {}), "settings.warn_download_mb")
check(meta and "plot_dpi" in (meta.get("settings") or {}), "settings.plot_dpi")

# --- local ---
summary = get("/api/local/summary")
check(summary is not None, "local/summary returns data")
check(summary and "n_granules" in summary, "summary.n_granules")
check(summary and "cache_bytes_on_disk" in summary, "summary.cache_bytes_on_disk")
check(summary and "cache_quota_bytes" in summary, "summary.cache_quota_bytes")
check(summary and "by_product" in summary, "summary.by_product")

datasets = get("/api/local/datasets")
check(datasets and "datasets" in datasets, "local/datasets has datasets key")

facets = get("/api/local/facets")
check(facets and "products" in facets, "facets has products")
check(facets and "sats" in facets, "facets has sats")
check(facets and "date_min" in facets, "facets has date_min")
check(facets and "date_max" in facets, "facets has date_max")

# --- load samples ---
loaded = post("/api/local/load-samples", {})
check(loaded and "indexed" in loaded, "load-samples returns indexed count")
if loaded:
    print(f"  Indexed {loaded['indexed']} sample granules")

# --- search ---
search_res = post("/api/profiles/search", {"good_only": False, "limit": 8})
check(search_res and "granules" in search_res, "search returns granules")
check(search_res and "total" in search_res, "search returns total")
granules = search_res.get("granules", []) if search_res else []
check(len(granules) > 0, f"search returns at least one granule (got {len(granules)})")

if granules:
    gid = granules[0]["id"]
    g0 = granules[0]
    # Check all fields the frontend reads
    for field in ["id", "file_name", "product", "lat", "lon", "local_time",
                  "sat", "occ_prn", "n_levels", "alt_max", "good", "time_utc"]:
        check(field in g0, f"granule has field: {field}")

    # --- profile detail ---
    detail = get(f"/api/profiles/{gid}")
    check(detail and "meta" in detail, "profile detail has meta")
    check(detail and "diagnostics" in detail, "profile detail has diagnostics")
    check(detail and "product_info" in detail, "profile detail has product_info")
    check(detail and "attribute_notes" in detail, "profile detail has attribute_notes")
    if detail:
        meta_keys = detail.get("meta", {})
        for key in ["file_name", "lat", "lon", "local_time", "sat", "occ_prn",
                    "time_utc", "good", "bad_code", "error_text", "setting"]:
            check(key in meta_keys, f"profile.meta has {key}")

    # --- plot profiles ---
    ids = [g["id"] for g in granules[:3]]
    plot = post("/api/plot/profiles", {
        "granule_ids": ids,
        "field": "Temp",
        "vertical": "MSL_alt",
    })
    check(plot and "series" in plot, "plot/profiles returns series")
    check(plot and "field_label" in plot, "plot/profiles returns field_label")
    check(plot and "vertical_label" in plot, "plot/profiles returns vertical_label")
    check(plot and "skipped" in plot, "plot/profiles returns skipped")
    if plot and plot.get("series"):
        s0 = plot["series"][0]
        for key in ["x", "y", "label", "granule_id", "lat", "local_time", "good"]:
            check(key in s0, f"profile series has {key}")
        check(isinstance(s0["x"], list), "series.x is list")
        check(isinstance(s0["y"], list), "series.y is list")
        nones_x = sum(1 for v in s0["x"] if v is None)
        check(nones_x < len(s0["x"]) * 0.5, f"series.x has <50% nulls (has {nones_x}/{len(s0['x'])})")

# --- composite ---
composite = post("/api/composite", {
    "search": {"good_only": False, "limit": 8},
    "field": "Temp",
    "vertical": "MSL_alt",
    "group_by": "lat_band",
    "convert_kelvin": False,
})
check(composite and "groups" in composite, "composite returns groups")
check(composite and "grid" in composite, "composite returns grid")
check(composite and "field_label" in composite, "composite returns field_label")
check(composite and "vertical_label" in composite, "composite returns vertical_label")
check(composite and "min_count" in composite, "composite returns min_count")
check(composite and "dropped_groups" in composite, "composite returns dropped_groups")
if composite and composite.get("groups"):
    g = list(composite["groups"].values())[0]
    for key in ["mean", "std", "p10", "p90", "n"]:
        check(key in g, f"composite group has {key}")

# --- diagnostics table ---
diag_table = post("/api/diagnostics/table", {
    "search": {"good_only": False, "limit": 8}
})
check(diag_table and "rows" in diag_table, "diagnostics/table returns rows")
check(diag_table and "columns" in diag_table, "diagnostics/table returns columns")
check(diag_table and "n" in diag_table, "diagnostics/table returns n")
check(diag_table and "unreadable" in diag_table, "diagnostics/table returns unreadable")

# --- exports ---
exports = get("/api/exports")
check(exports and "exports" in exports, "exports returns exports key")

# --- reveal folder ---
reveal = get("/api/reveal-folder?which=cache")
check(reveal and "opened" in reveal, "reveal-folder returns opened path")

# --- jobs ---
jobs = get("/api/jobs")
check(jobs and "jobs" in jobs, "jobs returns jobs list")

# --- static files ---
for path in ["/", "/js/main.js", "/js/api.js", "/css/app.css", "/vendor/plotly.min.js"]:
    try:
        r = urllib.request.urlopen(BASE + path, timeout=5)
        content = r.read()
        PASS.append(f"static:{path}")
        if path == "/vendor/plotly.min.js":
            check(len(content) > 1_000_000, "plotly.min.js is large enough (>1MB)")
    except Exception as e:
        FAIL.append((f"static:{path}", str(e)))

# --- summary ---
print(f"\n{'='*60}")
print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
if FAIL:
    print("\nFAILED:")
    for label, reason in FAIL:
        print(f"  FAIL: {label}: {reason}")
print("="*60)
sys.exit(0 if not FAIL else 1)
