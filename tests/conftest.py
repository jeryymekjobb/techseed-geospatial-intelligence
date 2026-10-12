"""The tests check the Västmanland 2014 scenario: pin it before any app module is imported.

They also read display profiles from a file of their own that does not exist, so the
exhibition PC's saved profiles (data/display-profiles.json) cannot change their results."""

import os
import tempfile

os.environ["TECHSEED_SCENARIO"] = "vastmanland2014"
os.environ["TECHSEED_PROFILE_FILE"] = os.path.join(tempfile.mkdtemp(prefix="techseed-tests-"), "display-profiles.json")
