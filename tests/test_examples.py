"""The headless example in the README runs (offline part)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def test_headless_example_runs_offline(capsys):
    path = Path(__file__).resolve().parents[1] / "examples" / "headless_basics.py"
    spec = importlib.util.spec_from_file_location("headless_basics", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main(online=False)
    out = capsys.readouterr().out
    assert "Mars ionosphere: peak 6302 cm^-3 at 145.4 km" in out
    assert "rs_20160303_223100_udsc64_l4_ae_v10" in out and "comparison grid" in out
