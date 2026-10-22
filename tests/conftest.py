"""The tests check the Västmanland 2014 scenario: pin it before any app module is imported.

They also read display profiles from a file of their own that does not exist, so the
exhibition PC's saved profiles (data/display-profiles.json) cannot change their results."""

import os
import tempfile

os.environ["TECHSEED_SCENARIO"] = "vastmanland2014"
os.environ["TECHSEED_PROFILE_FILE"] = os.path.join(tempfile.mkdtemp(prefix="techseed-tests-"), "display-profiles.json")


import pytest


@pytest.fixture(autouse=True)
def _installed_demo_data(monkeypatch):
    """start_demo's main() checks each demo's data before starting it (missing_data); the tests that
    drive main() with stand-ins should not depend on which data this computer has. The check itself
    is tested through start_demo.MISSING_DATA in tests/test_start_demo.py."""
    from tools import start_demo

    monkeypatch.setattr(start_demo, "missing_data", lambda name: [])
