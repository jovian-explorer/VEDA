"""pytest configuration for VEDA tests.

Tests import the installed ``veda`` package (``pip install -e ".[dev]"``).
All writes go to a throwaway data folder so a test run never touches the
user's real VEDA settings, cache or exports; the folder is deleted when the
run ends.
"""
import os
import shutil
import tempfile

if "VEDA_HOME" not in os.environ:
    _HOME = tempfile.mkdtemp(prefix="veda-test-home-")
    os.environ["VEDA_HOME"] = _HOME
else:
    _HOME = None


def pytest_unconfigure(config):
    if _HOME:
        from veda import parallel
        parallel.shutdown()          # worker processes may hold files in the folder
        shutil.rmtree(_HOME, ignore_errors=True)
