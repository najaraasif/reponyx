"""Root conftest.py — overrides pytest's default temp directory on Windows.

The default basetemp (pytest-of-<user>) can become locked on Windows,
causing PermissionError for all tests. This redirects to a writable location.
"""
import tempfile
import os


def pytest_configure(config):
    """Set a writable basetemp directory."""
    custom_basetemp = os.path.join(
        tempfile.gettempdir(), "reponyx-pytest-temp"
    )
    os.makedirs(custom_basetemp, exist_ok=True)
    config.option.basetemp = custom_basetemp
