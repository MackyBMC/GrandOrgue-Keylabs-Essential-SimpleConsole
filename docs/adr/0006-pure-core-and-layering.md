# ADR 0006: Pure stdlib core and enforced layering
**Status:** PROPOSED.
**Context:** `mido` and Qt imports are spread widely; the long-term host may be a native subsystem or a different process model.
**Decision:** `core` imports only the standard library; layer rule per ARCHITECTURE section 3; MIDI crosses the core boundary as a small project-owned event type; an AST import check in the build enforces it.
**Consequences:** Some wrapper code at the edges; testability without hardware; a future non-Python host is possible without redesign.
