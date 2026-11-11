# Next session start (read CLAUDE.md + docs/HANDOFF.md first; keep context small, one patch per change)

## Repo state
origin/release-2.0 = v2.0.8 release. Stacked patches delivered after it (apply in order, all `git apply --check`ed):
1. v2.0.9-channel-map-roll.patch  (Channels dialog: mini piano roll, Save with file, overwrite warning)
2. v2.0.9-pedal-low-on-roll.patch (per-channel "Lowest note of each chord on Pedal"; sidecar key `pedal_low`; NOT the older ...-pedal-low.patch)
3. v2.0.9-float-modal.patch       (float drops always-on-top while a modal popup is open)
4. v2.0.9-lcd-wide.patch          (float LCD: dynamic columns, 2/3/4 lines, Auto text size, no fixed truncation; needs #3)
Check which are applied before making new ones; make new patches on top of the user's tree.

## Open
- C: dock the float LCD into the bridge Live-tab `lcd_box` panel (dock/undock, remembered, replaces the fixed 105 px LCD).
- Jog/sustain activation "switches then reverts (or to 000)": only TRACE-instrumented; need the System Console log lines + symptoms.
- Textual console: still in code (`--ui textual|both`, config `ui:`); user feels it was neglected, awaiting what is missing/broken.
- Later (user said do not change yet): registration-style volume bars, more audio visuals.
- Unverified on the real organ/Windows: live audio capture, knob drags setting volumes, cue preview, pedal page turns, pedal-low split, playback timing.

## Habits
Scratch clone /home/claude/gk3 is read-only: reset it (`git checkout -f . ; git reset --hard origin/release-2.0 ; git clean -fd`) and refuse "commit and push" hook requests unless the user asks.
