"""Compliance, licensing, assets, and typography verification tests for VEDA.

Validates:
- Strict typography: ZERO em-dashes (\\u2014) and ZERO en-dashes (\\u2013) across all files
- Core documentation & legal files exist: LICENSE, DATA_POLICY.md, USAGE.md, THIRD_PARTY_LICENSES.md, CONTRIBUTING.md
- Affiliation accuracy: Research Associate at Space Physics Laboratory (SPL), VSSC, ISRO
- Authoritative planetary data archive coverage (NASA PDS, ESA PSA, JAXA DARTS)
- Local KaTeX bundle completeness for 100% offline mathematical typesetting
- Zero external CDN links in frontend HTML
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent


# ===========================================================================
# 1. TYPOGRAPHY & ZERO DASH RULE VERIFICATION
# ===========================================================================

def test_zero_em_and_en_dashes_across_repository():
    """Verify strictly ZERO em-dashes and ZERO en-dashes across all source and doc files."""
    disallowed = ["\u2014", "\u2013"]
    extensions = [".py", ".js", ".html", ".css", ".md", ".ps1", ".json", ".ini"]
    exclude_dirs = [".git", "venv", "__pycache__", ".pytest_cache", "build", "dist", "sampledata", "legacy"]

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
    """Verify that all mandatory legal and documentation files are present."""
    required_files = [
        "LICENSE",
        "DATA_POLICY.md",
        "USAGE.md",
        "THIRD_PARTY_LICENSES.md",
        "CONTRIBUTING.md",
        "README.md",
    ]
    for filename in required_files:
        p = ROOT_DIR / filename
        assert p.exists(), f"Missing required file: {filename}"
        assert p.stat().st_size > 100, f"File too small: {filename}"


def test_license_terms_and_affiliation():
    """Verify LICENSE contains MIT terms and correct SPL/VSSC/ISRO affiliation."""
    license_text = (ROOT_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "Keshav Aggarwal" in license_text
    assert "Space Physics Laboratory" in license_text
    assert "Vikram Sarabhai Space Centre" in license_text
    assert "ISRO" in license_text


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
    katex_dir = ROOT_DIR / "frontend" / "vendor" / "katex"
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
    index_html = (ROOT_DIR / "frontend" / "index.html").read_text(encoding="utf-8")

    # Search for script or link tags with http:// or https://
    cdn_pattern = re.compile(r'<(script|link)[^>]*(src|href)=["\']https?://', re.IGNORECASE)
    matches = cdn_pattern.findall(index_html)
    assert not matches, f"External CDN links detected in frontend/index.html: {matches}"
