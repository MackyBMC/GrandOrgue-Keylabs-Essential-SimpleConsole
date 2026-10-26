# Changelog

## 2.0.2 (in development)

### New
- **MIDI Track / Piano Roll Editor.** The piano roll window has a track list: active track (new notes and piano keys use its channel), show / hide, editable track names (the stave titles follow), channel, instrument, note count, add and remove track.
- **Stave shows: Quantised or Raw.** Choose whether the stave is built from the quantised timing or from the notes as played (32nd-note grid, no gap closing). The MIDI itself is never changed by this choice.
- **Shape MIDI timing** (Edit menu, Ctrl+Q, or the Quantise panel): grid or fixed-millisecond quantise, strength, swing, humanise, snap note ends or legato / slur, finger-numbered notes joined legato, organ-friendly gap closing for piano-style MIDI, limited to a MIDI-note range or the selection, with restore of the original timing. Finger and pedal marks follow their notes when they are re-timed.

- **Piano roll view.** Keys taller / shorter on Ctrl+Up / Ctrl+Down; the grid and key rows fill the whole roll window and cover the full keyboard (the vertical scroll bar now has somewhere to go); a **Layout** menu saves and restores named layouts (zoom, snap, grid, panels, window and toolbars) and the roll reopens as you left it.

- **Piano roll shows the tracks.** Each track has its own colour (the same dot colour as in the Tracks list); unticking a track hides its notes in the roll; the active track is full strength and the others fade (View menu: "Colour notes by track", "Fade the notes of the other tracks").

### Fixed
- Ctrl+Up / Ctrl+Down no longer clash: octave up / down moved to Ctrl+Shift+Up / Down (Shift+Up / Down still works on the roll).
- Organ layout file is looked for in the GrandOrgue folder first.
- Piano roll: drag on empty space now rubber-band selects notes (Shift adds, drag to the window edge scrolls).
- Alt + wheel key zoom no longer sticks (Qt swaps the wheel axis with a modifier held); zoom keeps the middle pitch in place.
- Stop grid remembers its position; toolbar icons show short labels with the full wording as the hover tip; piano keys sound when no stave owns the pitch.

## 2.0.2-linux.1 (experimental prerelease)
- First Linux-only prerelease build for evaluation; macOS packaging is deferred to a later release.
- This release does not replace or alter the supported Windows v2.0.1 release.

## 2.0.1
- Fix installed builds loading and saving setter combinations from the configured GrandOrgue data folder.
- Start GrandOrgue with the configured organ when the GUI launches.
- Include matplotlib in the Nuitka standalone build and derive installer version from the built executable.

## 2.0.0
- Stave editor: piano-roll window, voices, rest tidying, fingerings, division labels, tonic sol-fa, lyrics, track selection.
- Global theming (Breeze / Adwaita / Fusion / Nord / ...), icon packs, remembered window positions.
- Installer: per-user data folder, portable mode, GitHub release pipeline.

## 1.0.0
- First release: KeyLab <-> GrandOrgue bridge.
