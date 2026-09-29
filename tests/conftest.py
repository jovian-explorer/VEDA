"""pytest configuration for VEDA tests.

Tests import the installed ``veda`` package (``pip install -e ".[dev]"``).
All writes go to a throwaway data folder so a test run never touches the
user's real VEDA settings, cache or exports.
"""
import os
import tempfile

os.environ.setdefault("VEDA_HOME", tempfile.mkdtemp(prefix="veda-test-home-"))
