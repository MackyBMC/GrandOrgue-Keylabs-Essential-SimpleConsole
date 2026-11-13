# ADR 0003: The organ is data, not code
**Status:** PROPOSED.
**Context:** Friesach lives in `organ_layout.py` constants; Cracow needed a separate scan; the code mutates module globals to change layout.
**Decision:** An `Organ` is a data file (YAML) with manuals, stops, couplers, tremulants and stable logical ids. Engine importers (GrandOrgue ODF scan first) generate it and a separate wire map. Core loads `Organ` objects; no module-level layout state.
**Consequences:** Multiple organs can be loaded; setters/scores reference logical ids; a migration for v2 setter files and `track_map` keys is required; the data format becomes a compatibility surface (version it).
