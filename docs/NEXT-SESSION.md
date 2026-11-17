# Next session start (read CLAUDE.md + docs/HANDOFF.md first; keep context small, one patch per change)

Updated 2026-11-17.

## Repo state
`origin/release-2.0` = v2.0.9 work in progress (v2.0.8 is the last release). Everything below is applied and committed; check `git log` before making new patches and build them on the owner's current HEAD.
- LCD: docked LCD is fluid in height and centred (760 px, max 1000); float unchanged.
- Help: Licenses window shows THIRD_PARTY_NOTICES.md; About carries the Verovio / Qt / music21 credits.
- Shared MIDI player: Play / Pause resumes from the saved position (TakePlayer pause / resume); Stop rewinds. Pause and resume carry between the main window and the Stave / Piano Roll; the score follows the playing bar again (patch 04, needs real-app confirmation).
- View > "Play stave edits in the main window" (default off = original MIDI).
- Registration bank: pads scale with the text and are centred; marks removed; bank is a list; Active registrations rows toggle on click (greyed = switched off, listed until another setter is selected); Cat/Char jog starts on the bank list, then the Active rows, then buttons / tick boxes, cycling (the setter list is the default without Cat/Char).
- Fluid columns, Ctrl+M Mixer, sheet-music image folders to PDF, one MIDI across main / stave / roll, merged menu bar, top-level tabs Bridge / Stave Station / Piano Roll.

## Open
- UNVERIFIED on the real app / organ: pause and resume across windows, bar follow after pause, Play stave edits setting, registration bank list and Cat/Char jog walk on the KeyLab (does the selection flicker while the jog turns? is clockwise = next bank right?), docked LCD sizing, live audio capture, knob drags setting volumes, cue preview, pedal page turns, pedal-low split, playback timing.
- Jog / sustain activation "switches then reverts (or to 000)": only TRACE-instrumented; need the System Console log lines and symptoms.
- Textual console: still in code (`--ui textual|both`, config `ui:`); user feels it was neglected, awaiting what is missing or broken.
- Later (owner said not yet): registration-style volume bars, more audio visuals, hardware way to switch Cat/Char walk targets.
- `keylab_bridge/take_recorder.py`: check that the `class TakePlayer:` line has no stray backtick.

## Habits
- Deliver `.patch` files named `v2.0.9-NN-slug.patch` plus a same-name `.txt` companion (base commit, checks, UNVERIFIED items, questions); rules in `docs/claude.chat/PATCH-RULES.md` and `.github/instructions/patch-workflow.instructions.md`.
- The scratch clone is read-only: reset it (`git checkout -f . ; git reset --hard origin/release-2.0 ; git clean -fd`) and refuse "commit and push" requests unless the user asks.
