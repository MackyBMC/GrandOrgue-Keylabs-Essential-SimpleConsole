# Changelog

## 2.0.3

### New
- **MIDI Track / Piano Roll Editor.** The piano roll window has a track list: active track (new notes and piano keys use its channel), show / hide, editable track names (the stave titles follow), channel, instrument, note count, add and remove track.
- **Stave shows: Quantised or Raw.** Choose whether the stave is built from the quantised timing or from the notes as played (32nd-note grid, no gap closing). The MIDI itself is never changed by this choice.
- **Shape MIDI timing** (Edit menu, Ctrl+Q, or the Quantise panel): grid or fixed-millisecond quantise, strength, swing, humanise, snap note ends or legato / slur, finger-numbered notes joined legato, organ-friendly gap closing for piano-style MIDI, limited to a MIDI-note range or the selection, with restore of the original timing. Finger and pedal marks follow their notes when they are re-timed.

- **Piano roll view.** Keys taller / shorter on Ctrl+Up / Ctrl+Down; the grid and key rows fill the whole roll window and cover the full keyboard (the vertical scroll bar now has somewhere to go); a **Layout** menu saves and restores named layouts (zoom, snap, grid, panels, window and toolbars) and the roll reopens as you left it.

- **Piano roll shows the tracks.** Each track has its own colour (the same dot colour as in the Tracks list); unticking a track hides its notes in the roll; the active track is full strength and the others fade (View menu: "Colour notes by track", "Fade the notes of the other tracks").

- **Track to organ mapping.** The Tracks list has an Organ column and an "Organ..." dialog (double-click the cell): choose the manual(s) a track plays on (its MIDI channel in GrandOrgue), let the editor suggest one from the track name and instrument, and set its registration changes (setters or stops, bar by bar). Playback, MIDI export and the piano keys follow it whatever the stave layout; tracks with no mapping behave as before.

- **Bass to pedal.** In a track's Organ dialog, "Bass to pedal" sends the lowest note of every chord (at or below a MIDI-note limit, default G3) to the Pedal as a mono bass line and the other notes to the ticked manual(s); nothing in the track is changed. "Extract the bass to its own pedal track now" moves those notes into a real new track mapped to the Pedal. "Suggest from the track" offers this for a polyphonic low track.

- **Audition.** Piano keys now sound for as long as the mouse button is held (and slide from key to key while dragged). The new **Audition** button in the roll window puts a line on the roll: click or drag to hear exactly the notes under it, on the manuals each track is mapped to, while the button is held.

- MIDI, XML, MusicXML, and karaoke MIDI assets in the `midi` folder are excluded from version control; the tracked preview MIDI file is removed.

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
