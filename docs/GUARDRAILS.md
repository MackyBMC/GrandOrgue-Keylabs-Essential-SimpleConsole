# Guardrails

*Status: DECIDED unless marked otherwise. These are the rules that protect the project. Assistants read this before changing anything.*

## Invariants
| ID | Rule | Origin / evidence |
|----|------|-------------------|
| I-1 | In the default path, keyboard, pedal and wheel input go straight to the engine; playing never passes through the Python bridge. | README "How it works"; MAIN port is not opened by the bridge by default. |
| I-2 | A controller or engine plugin failure must never stop sound or playback already running. The controller can be disengaged and re-engaged at any time. | Controller toggle (Unreleased); README. |
| I-3 | Registrations and scores store **logical IDs** (organ, division, stop). Engine-specific identifiers are derived by the engine adapter. Existing GrandOrgue markers stay readable. | Vision; ADR 0003/0004. PROPOSED for v3. |
| I-4 | Every v2 user file (config.yaml, setter YAML, `.ss` projects, MIDI settings, takes) stays readable by v3. Migrations are explicit, one-way and back up the original. | ROADMAP compatibility promises. PROPOSED. |
| I-5 | The core layer imports only the Python standard library (no mido, rtmidi, PySide6, yaml, numpy). | ADR 0006. PROPOSED. |
| I-6 | No engine-specific or controller-specific constant, path, channel or name lives outside its plugin. No new Friesach constant anywhere. | INVENTORY-V2.md. PROPOSED. |
| I-7 | MIDI callbacks never touch UI state; they post events to the UI thread (existing `post_ui_event` / `process_ui_event` pattern). | HANDOFF.md. |
| I-8 | Nothing is described as working on a real organ unless it has been tried on one. Say VERIFIED or UNVERIFIED. | CLAUDE.md rule. |
| I-9 | It is not a DAW. | CLAUDE.md rule; SCOPE.md. |
| I-10 | Never touch the `v1.0.0` tag or the v1 installer AppId. | CLAUDE.md rule. |
| I-11 | Windows first. Linux/macOS stay experimental until validated on real systems. | README; CLAUDE.md. |
| I-12 | The organ-mapping policy is "map as much of a large organ as possible": add MIDI channels and banks rather than refuse. | Owner, Cracow decision. |

## Change rules
- Changes ship as `.patch` files against the current line, checked with `git apply --check`; stacked patches state their order. Name carries the version level (`v2.0.9-...`, `v3.0.0-...`).
- Change notes go in the CHANGELOG block at the top of each edited source file (newest first, dated) and in `CHANGELOG.md`.
- Code must be free of Pylance/pyright errors, worked out from first principles (type optional libraries properly). Never re-send a patch already delivered and applied.
- No commit or push unless the owner asks.
- Architectural changes need an ADR (docs/adr/) with a status; do not silently change a DECIDED item.
- Behaviour-preserving refactors must prove equivalence (golden outputs, VERIFICATION.md) before behaviour changes ride along.

## Session constraints (owner working pattern)
Session time is limited: minimise back-and-forth, deliver files, put questions in `docs/claude.chat/<patch-name>.txt`, send each patch as soon as it is ready, keep replies short.
