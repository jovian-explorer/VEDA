# Contributing to VEDA

Thank you for your interest in contributing to **VEDA (Visualization, Exploration, and Data Analysis)**. VEDA is developed to provide a robust, open, multi-mission scientific computational laboratory for planetary science.

---

## 1. Scientific Scope and Core Directives

When contributing code, algorithms, or mission data models to VEDA, the following architectural principles must be maintained:

1. **Non-Earth Planetary Scope**:
   * VEDA is dedicated to non-Earth planetary bodies, dwarf planets, moons, asteroids, and comets.
   * Earth-centric GNSS or terrestrial weather data pipelines must not be integrated into VEDA.
2. **Offline-First Architecture**:
   * The application must operate seamlessly in offline research environments without active internet connectivity.
   * All vendor libraries (e.g. KaTeX, Plotly, Three.js) must be bundled locally within `src/veda/frontend/vendor/`. No external CDN links are permitted in application HTML or scripts.
3. **Typography and Style Constraint**:
   * **Do not use em-dashes or en-dashes anywhere in the repository.**
   * Use standard ASCII hyphens (`-`), colons (`:`), commas (`,`), or parentheses (`()`).
   * This rule applies strictly across all code files, docstrings, user interface text, and documentation.

---

## 2. Development Workflow

### A. Environment Setup
Clone the repository and install required dependencies in a virtual environment:
```bash
git clone https://github.com/jovian-explorer/VEDA.git
cd VEDA
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```
The package lives in `src/veda/`; the web UI is in `src/veda/frontend/` and is served by the backend, so edits show up after a browser refresh.

### B. Branching Strategy
* Create feature branches from `main`:
  ```powershell
  git checkout -b feature/planetary-mission-name
  ```
* Use concise, conventional commit messages:
  * `feat(...)`: New planetary mission, algorithm, or data reader
  * `fix(...)`: Algorithmic or UI bug fixes
  * `docs(...)`: Documentation and citations updates
  * `test(...)`: Test suite additions and verification

### C. Coding Standards
* **Python Backend**:
  * Follow PEP 8 guidelines.
  * Use strict type hints and Pydantic schemas for data validation.
  * Ensure mathematical functions include docstrings documenting units, assumptions, and reference equations.
* **Frontend JavaScript**:
  * Use modern vanilla ES modules (`import`/`export`).
  * Maintain responsive layout support for varying screen resolutions.
  * Ensure all dynamically injected equations trigger `renderMathInElement()` via KaTeX.

---

## 3. Testing and Verification

Before submitting a pull request, run the complete verification test suite:

```bash
pytest
```
CI runs the same suite on Windows, macOS and Linux. To exercise the frozen build locally, run `pip install -e ".[build]"` and `python scripts/build_exe.py`, then `pytest tests/test_explorer_launch.py` (Windows).

All tests must pass with a 100% success rate. If you add a new planetary body, spacecraft mission, or scientific reader, you must provide corresponding unit tests under `tests/`.

---

## 4. Verification of Dash Constraints

To verify that no em-dashes or en-dashes have been inadvertently introduced, run the following verification command:

```powershell
python -c "
import sys, pathlib
found = False
for p in pathlib.Path('.').rglob('*'):
    if any(part in p.parts for part in ['.git', 'venv', '__pycache__', '.pytest_cache', 'build', 'dist']):
        continue
    if p.suffix in ['.py', '.js', '.html', '.css', '.md', '.ps1', '.json']:
        try:
            content = p.read_text(encoding='utf-8')
            if '\u2014' in content or '\u2013' in content:
                print(f'Disallowed dash character in: {p}')
                found = True
        except Exception:
            pass
if found:
    sys.exit(1)
print('Verification passed: Zero em-dashes and zero en-dashes detected.')
"
```

---

## 5. Third-Party Data and License Compliance

* If integrating demonstration data from space agency archives, verify that the dataset is in the public domain or covered by an open-access research license.
* Document the dataset source, Principal Investigator, and archive DOI in `DATA_POLICY.md` and the appropriate registry entries.
* Never commit proprietary or embargoed science data to the repository.
