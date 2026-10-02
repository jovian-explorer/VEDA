"""Compliance, licensing, assets, and typography verification tests for VEDA.

Validates:
- Strict typography: ZERO em-dashes (\\u2014) and ZERO en-dashes (\\u2013) across all files
- Core documentation & legal files exist: LICENSE, DATA_POLICY.md, USAGE.md, THIRD_PARTY_LICENSES.md, CONTRIBUTING.md
- Affiliation accuracy: student visitor at the Space Physics Laboratory (SPL), VSSC, ISRO; copyright held by the author
- Authoritative planetary data archive coverage (NASA PDS, ESA PSA, JAXA DARTS)
- Local KaTeX bundle completeness for 100% offline mathematical typesetting
- Zero external CDN links in frontend HTML
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

from veda.config import frontend_dir

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND = frontend_dir()


# ===========================================================================
# 1. TYPOGRAPHY & ZERO DASH RULE VERIFICATION
# ===========================================================================

def test_zero_em_and_en_dashes_across_repository():
    """Verify strictly ZERO em-dashes and ZERO en-dashes across all source and doc files."""
    disallowed = ["\u2014", "\u2013"]
    extensions = [".py", ".js", ".html", ".css", ".md", ".ps1", ".json", ".ini", ".spec", ".txt"]
    exclude_dirs = [".git", "venv", ".venv", "__pycache__", ".pytest_cache", "build", "dist", "sampledata", "veda.egg-info"]

    violations = []
    for p in ROOT_DIR.rglob("*"):
        if any(part in p.parts for part in exclude_dirs):
            continue
        if p.suffix in extensions:
            try:
                text = p.read_text(encoding="utf-8")
                for char in disallowed:
                    if char in text:
                        codepoint = "EM-DASH" if char == "\u2014" else "EN-DASH"
                        violations.append(f"{p.relative_to(ROOT_DIR)}: contains {codepoint}")
            except Exception:
                pass

    assert not violations, f"Disallowed dash characters found:\n" + "\n".join(violations)


# ===========================================================================
# 2. DOCUMENTATION & LEGAL FILES VERIFICATION
# ===========================================================================

def test_mandatory_docs_exist():
    """Verify that all mandatory legal, configuration, and documentation files are present."""
    required_files = [
        "LICENSE",
        "DATA_POLICY.md",
        "USAGE.md",
        "THIRD_PARTY_LICENSES.md",
        "CONTRIBUTING.md",
        "README.md",
        "requirements.txt",
    ]
    for filename in required_files:
        p = ROOT_DIR / filename
        assert p.exists(), f"Missing required file: {filename}"
        assert p.stat().st_size > 100, f"File too small: {filename}"


def test_license_terms_and_affiliation():
    """LICENSE: MIT terms, copyright held by the author (not an institution)."""
    license_text = (ROOT_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "Keshav Aggarwal" in license_text
    assert "Copyright (c) 2026 Keshav Aggarwal" in license_text
    assert "ISRO" not in license_text


def test_data_policy_archives_and_bibtex():
    """Verify DATA_POLICY.md covers major archives and includes BibTeX entries."""
    policy_text = (ROOT_DIR / "DATA_POLICY.md").read_text(encoding="utf-8")
    assert "NASA Planetary Data System" in policy_text
    assert "ESA Planetary Science Archive" in policy_text
    assert "JAXA Data Archives and Transmission System" in policy_text
    assert "@software" in policy_text
    assert "Aggarwal_VEDA_2026" in policy_text


# ===========================================================================
# 3. OFFLINE ASSETS & ZERO-CDN VERIFICATION
# ===========================================================================

def test_katex_local_bundle_integrity():
    """Verify that KaTeX scripts, stylesheets, and font files exist locally for offline math typesetting."""
    katex_dir = FRONTEND / "vendor" / "katex"
    assert katex_dir.exists(), "KaTeX vendor directory does not exist"

    js_file = katex_dir / "katex.min.js"
    assert js_file.exists() and js_file.stat().st_size > 50000

    css_file = katex_dir / "katex.min.css"
    assert css_file.exists() and css_file.stat().st_size > 10000

    auto_render = katex_dir / "contrib" / "auto-render.min.js"
    assert auto_render.exists() and auto_render.stat().st_size > 1000

    fonts_dir = katex_dir / "fonts"
    assert fonts_dir.exists(), "KaTeX fonts directory missing"
    font_files = list(fonts_dir.glob("*.woff2"))
    assert len(font_files) >= 15, f"Expected at least 15 WOFF2 font files, found {len(font_files)}"


def test_frontend_zero_external_cdn():
    """Verify that frontend/index.html does not reference any external CDN links."""
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")

    # Search for script or link tags with http:// or https://
    cdn_pattern = re.compile(r'<(script|link)[^>]*(src|href)=["\']https?://', re.IGNORECASE)
    matches = cdn_pattern.findall(index_html)
    assert not matches, f"External CDN links detected in frontend/index.html: {matches}"


# ===========================================================================
# 4. QUALITY OF LIFE FEATURES VERIFICATION
# ===========================================================================

def test_every_guide_button_has_a_handler():
    """Regression: three Workflow Guide buttons did nothing (no handler case)."""
    import re as _re
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "js" / "veda_app.js").read_text(encoding="utf-8")
    actions = set(_re.findall(r'data-guide-action="([^"]+)"', index_html))
    handled = set(_re.findall(r"case '([^']+)':", app_js))
    assert actions, "no guide buttons found"
    assert not actions - handled, f"guide buttons without a handler: {sorted(actions - handled)}"


def test_demo_buttons_use_bundled_real_products():
    """Demo buttons may only open products that ship with VEDA."""
    app_js = (FRONTEND / "js" / "veda_app.js").read_text(encoding="utf-8")
    from veda.config import sampledata_dir
    shipped = {f.stem for f in sampledata_dir().rglob("*") if f.is_file()}
    import re as _re
    for oid in _re.findall(r"observation_id: (?:ion \? )?'([^']+)'(?: : '([^']+)')?", app_js):
        for o in filter(None, oid):
            assert o in shipped, f"demo opens {o}, which is not bundled"


def test_planetary_quick_card_and_constants_present():
    """Verify Planetary Body Physical Constants Quick-Card and constants coverage."""
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "js" / "veda_app.js").read_text(encoding="utf-8")

    assert 'id="veda-body-quick-card"' in index_html
    assert "BODY_PHYSICAL_CONSTANTS" in app_js
    assert "renderPlanetaryBodyQuickCard" in app_js

    # Check key celestial bodies covered in quick-card catalog
    for body_id in ["venus", "mars", "earth", "jupiter", "saturn", "titan", "pluto"]:
        assert f"{body_id}:" in app_js, f"Body {body_id} missing in BODY_PHYSICAL_CONSTANTS"

    # Check the 6 physical constants are displayed
    metrics = [
        "Surface gravity g",
        "Atmospheric scale height H",
        "Surface pressure P",
        "Dominant atmospheric composition",
        "Mean surface temperature T_surf",
        "Solar distance",
    ]
    for m in metrics:
        assert m in app_js, f"Missing physical metric tile in quick-card: {m}"


def test_quick_unit_switcher_elements_and_logic():
    """Verify Quick Unit Switcher buttons for Temperature and Pressure."""
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "js" / "veda_app.js").read_text(encoding="utf-8")

    # Unit switcher in comparative view
    assert "btn-comp-unit-k" in index_html
    assert "btn-comp-unit-c" in index_html
    assert "btn-comp-unit-bar" in index_html
    assert "btn-comp-unit-hpa" in index_html
    assert "btn-comp-unit-pa" in index_html

    # Unit switcher state and logic in JS
    assert "unitsTemperature" in app_js
    assert "unitsPressure" in app_js
    assert "unit-toggle-temp" in app_js
    assert "unit-toggle-pres" in app_js


def test_drag_and_drop_overlay_indicator():
    """Verify Drag-and-Drop fullscreen indicator and supported file formats."""
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "js" / "veda_app.js").read_text(encoding="utf-8")

    assert 'id="veda-drag-drop-overlay"' in index_html
    assert "setupGlobalDragAndDrop" in app_js

    # Check supported extensions indicated
    for ext in [".TAB", ".LBL", ".CSV", ".FIT", ".FITS"]:
        assert ext in index_html, f"Missing extension badge in index.html: {ext}"


def test_universal_font_scaling_controls():
    """Verify Universal UI Font Size Zoom Controller in index.html and app.css."""
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_css = (FRONTEND / "css" / "app.css").read_text(encoding="utf-8")
    main_js = (FRONTEND / "js" / "main.js").read_text(encoding="utf-8")

    # 1. HTML Controls exist
    assert 'class="font-zoom-ctrl"' in index_html, "Missing font-zoom-ctrl in index.html"
    assert 'id="btn-font-dec"' in index_html, "Missing btn-font-dec button in index.html"
    assert 'id="font-scale-display"' in index_html, "Missing font-scale-display in index.html"
    assert 'id="btn-font-inc"' in index_html, "Missing btn-font-inc button in index.html"

    # 2. CSS font scale variable and rules
    assert "--font-scale" in app_css, "Missing --font-scale in app.css"
    assert ".font-zoom-ctrl" in app_css, "Missing .font-zoom-ctrl in app.css"
    assert "calc(" in app_css, "CSS does not use calc() for scalable font sizing"

    # 3. JS handler implementation
    assert "applyFontScale" in main_js, "Missing applyFontScale in main.js"
    assert "wireFontScaling" in main_js, "Missing wireFontScaling in main.js"


def test_clean_plotly_math_and_katex_integration():
    """Verify cleanPlotlyMath helper and KaTeX equation formatting."""
    ui_js = (FRONTEND / "js" / "ui.js").read_text(encoding="utf-8")
    index_html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "js" / "veda_app.js").read_text(encoding="utf-8")

    # 1. cleanPlotlyMath export and usage
    assert "export function cleanPlotlyMath" in ui_js, "Missing cleanPlotlyMath in ui.js"
    assert "cleanPlotlyMath" in app_js, "veda_app.js should use cleanPlotlyMath"

    # 2. KaTeX rendering integration
    assert "export function renderMath" in ui_js, "Missing renderMath in ui.js"
    assert "renderMathInElement" in ui_js, "renderMath should delegate to renderMathInElement"

    # 3. No double-escaped backslashes in HTML formulas
    assert "\\\\left" not in index_html, "Double backslash \\left detected in index.html"
    assert "\\\\frac" not in index_html, "Double backslash \\frac detected in index.html"


