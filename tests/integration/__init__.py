import os
import unittest

# These tests need Elite Dangerous to be running and send input to the game.
# They are skipped unless the environment variable EDAP_INTEGRATION is set to 1.
if os.environ.get("EDAP_INTEGRATION") != "1":
    raise unittest.SkipTest("Integration tests need the running game. Set EDAP_INTEGRATION=1 to enable.")
