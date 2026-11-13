# ADR 0001: v2.x maintenance track, v3 framework track
**Status:** ACCEPTED (owner, 2026-11-13: "that is not a v2 target ... I need version 3 to have that capability").
**Context:** The controller-agnostic, engine-agnostic framework is the end-state vision, not an increment of v2. The hardcoded Friesach/GrandOrgue/KeyLab logic is not usable for GrandOrgue itself with multiple sample organs.
**Decision:** `release-2.0` stays the stable v2 line (bug fixes only). The framework is developed as v3. Patches carry their version level in the file name.
**Consequences:** Two lines to keep in step; forward-port fixes by patch; v2 users are not destabilised; v3 needs a compatibility promise for v2 data (ROADMAP).
