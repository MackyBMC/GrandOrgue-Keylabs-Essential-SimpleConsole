# Scope

*Status: PROPOSED (the three rings, the scope gate and the freeze rule await owner acceptance; the non-goals restate the existing rule "not a DAW").*

## Why this document exists
The project is largely built (roughly 70 % of the v2 feature set), and the v3 goal (controller- and engine-agnostic framework) can look like scope leap. It is not, **provided it is held to one rule: v3 re-seats what already exists behind contracts; it does not add new end-user capabilities until the migration milestones are done** (ROADMAP M0 to M5). The original intent is unchanged.

## The three rings
**Ring 1 - Product core (always in scope).** The reason the project exists.
- Live organ console: controller to engine, stops/couplers/tremulants, banks, volume, expression.
- Registrations: setters/combinations per organ, cue and activate while playing, steps within a piece.
- MIDI file performance and take recording through the organ.
- Stave Station: MIDI / MusicXML to score, track-to-manual mapping, registrations by bar, piano roll for organ-shaped edits.
- Organ management: import/scan an organ, generate its mapping.
- Installer, settings, languages, themes, accessibility of the GUI.

**Ring 2 - Framework (the v3 work).** Makes Ring 1 independent of one organ, one engine, one controller.
- Organ description as data (logical organ model).
- Engine adapter contract; GrandOrgue adapter extracted; later Aeolus.
- Controller plugin contract; KeyLab plugin extracted.
- Plugin discovery/loading, capability declaration, compatibility and migration of v2 data.

**Ring 3 - Deferred, gated by a real need.**
- Aeolus standalone adapter (first second engine, v3.1).
- A second controller plugin (v3.2).
- VST3/CLAP hosting as a separate native subsystem (v4.x, ADR 0008).
- Parameter "learn" mapping for generic plugins.
- macOS release; validated Linux release.
- Third-party (out-of-tree) plugin distribution (ADR 0007).

## Non-goals (will not be built)
- A general-purpose DAW (multitrack audio recording, mixing, editing, plugin chains, automation lanes).
- Sample-set authoring or organ definition (ODF) editing; GrandOrgue is the tool for that.
- A full professional engraver; Stave Station engraves what an organist needs for rehearsal and performance.
- Replacing GrandOrgue's audio engine, loading, or audio configuration.
- Cloud services, accounts, telemetry, licensing servers.
- Anything that puts Python in the real-time audio path.

## Borderline items already in the code (decision needed, see claude.chat)
| Item | Why borderline | Proposed disposition |
|------|----------------|----------------------|
| Mixer tab (per-program Windows volume, scenes) | Edges toward DAW mixing | Retain, but scope it to "match levels between the organ and one background player at a function"; no per-track audio features. |
| Audio spectrum / oscilloscope in floating LCD | Visual nicety, optional deps (NumPy, PyAudioWPatch) | Retain as optional, never required; no further audio visual work. |
| Textual (terminal) console | Neglected; third UI | Decide: maintain or retire. Not part of the v3 core either way. |
| Orchestral background player control | Depends on external program | Retain only as the mixer example above. |

## The scope gate (apply to every new feature, assistants included)
A change is in scope only if **all** answers are yes:
1. Does it serve a church musician's workflow in the Vision (prepare, rehearse, perform, register, notate, record)?
2. Is it in Ring 1 or Ring 2, or explicitly promoted from Ring 3 by the owner?
3. Can it be explained to a non-specialist in one sentence?
4. Does it keep engine- and controller-specific knowledge inside its plugin (GUARDRAILS I-6)?
5. Would a DAW user say "that's a normal DAW feature" and nobody in a church would miss it if removed? If yes, **reject**.

## Feature freeze during migration (PROPOSED)
From the start of v3 work until ROADMAP milestone M5 exits, v2.x receives **bug fixes only** on the `release-2.0` line, and the v3 line receives **no new end-user features**. This keeps the migration measurable (behaviour-identical to v2.0.8, see VERIFICATION.md).
