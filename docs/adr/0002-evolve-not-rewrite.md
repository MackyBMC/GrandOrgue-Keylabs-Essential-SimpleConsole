# ADR 0002: Evolve the existing code, do not rewrite
**Status:** PROPOSED.
**Context:** About 21k lines exist and work on the real setup; the concern is mixing of layers, not a flawed foundation. Existing seams (`Item`, `odf_scan`, the UI event queue, controller toggle, separate Stave Station) are reusable.
**Decision:** Extract in place, behind contracts, in small behaviour-preserving steps with golden-output checks (ROADMAP M1 first). No big-bang rewrite, no new language for the app.
**Consequences:** Slower visible progress, much lower risk; temporary adapter shims will exist; every step must keep v2.0.8 behaviour identical.
