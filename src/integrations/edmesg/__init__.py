"""EDMesg modules of EDAP. Makes the vendored EDMesg library in third_party/ importable."""

import sys

from core.paths import ROOT

_THIRD_PARTY = str(ROOT / "third_party")
if _THIRD_PARTY not in sys.path:
    sys.path.append(_THIRD_PARTY)
