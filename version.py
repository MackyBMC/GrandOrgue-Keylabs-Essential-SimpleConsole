"""Single source of truth for the version. Bump here, tag `v<version>`, push: the release workflow does the rest.

CHANGELOG
2026-11-21  Prepare release v2.0.9-32.
2026-11-21  Version may be X.Y.Z or X.Y.Z-N[letters] (2.0.9, 2.0.9-1, 2.0.9-1a); APP_VERSION_NUMERIC gives the four-number form Windows executables need.
2026-11-20  Prepare release v2.0.9.
2026-11-10  Prepare release v2.0.8.
"""
APP_NAME = "KeyLab GrandOrgue Bridge"
APP_VERSION = "2.0.9-32"              # X.Y.Z, or X.Y.Z-N with optional letters: 2.0.9-1, 2.0.9-1a, 2.0.9-2b

import re as _re

_PARTS = _re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-(\d+)([a-z]*))?", APP_VERSION)
if _PARTS is None:
    raise ValueError(f"APP_VERSION {APP_VERSION!r} must look like 2.0.9, 2.0.9-1 or 2.0.9-1a")
_BUILD = int(_PARTS.group(4) or 0) * 100 + sum((ord(c) - 96) * 26 ** i for i, c in enumerate(reversed(_PARTS.group(5) or "")))
APP_VERSION_NUMERIC = f"{_PARTS.group(1)}.{_PARTS.group(2)}.{_PARTS.group(3)}.{min(_BUILD, 65535)}"   # Windows file version: 2.0.9-1a -> 2.0.9.101
APP_ID = "KeyLabGrandOrgue"
REPO_URL = "https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole"
