# What's New in 2.0.9

See [CHANGELOG.md](../CHANGELOG.md) for the itemized history. The sections below on 2.0.8 and earlier follow.

## For players

- **One tempo everywhere.** The session BPM starts at 80 (as in GrandOrgue) and ranges from 1 to 500. Changing it changes the GrandOrgue metronome in step, and the MIDI file player shows when GrandOrgue agrees. Recorded takes remember their BPM and play back at the speed you played them.
- **A setter tick you can trust.** A setter is ticked only when GrandOrgue itself confirms the file, the step and the stops. The setter list has a Status column ("F+ S5/7") and the setter GrandOrgue remembered is ticked as soon as the bridge starts.
- **Setter names that GrandOrgue understands.** Setter files get plain ASCII names of at most 32 characters; accents and other languages are kept as display names in `Settings/<organ>.names.yaml`. Existing folders are repaired silently, with a backup in `Combinations/_backup/`.
- **Setter files in GrandOrgue's own format.** Files saved by older versions that GrandOrgue could not use are rebuilt automatically. Setters jump to the right file after renames, and a newly saved setter shows up in GrandOrgue's list.

### One MIDI, one transport

- The file loaded in the main window is the same file in the stave editor and the piano roll; one shared transport (Play / Pause, Stop, Loop, Metronome, Save, position) drives it everywhere, and Pause resumes from where it stopped.
- Stave Station saves a project file (`.ss`) next to the MIDI with your settings, bar lines, track mapping, setters and edits; the MIDI itself is never changed.
- File > Export for GrandOrgue (native MIDI) writes the stops into the MIDI so GrandOrgue's own player switches them. View > Play stave edits chooses what Play uses; a "Quantised" toggle is on every transport.
- Recording on a MIDI with unsaved edits asks first. A small piano roll of the loaded MIDI shows in the player; double-click opens it in the Piano Roll tab.
- Stave engraving follows engraving practice: tied notes at the middle of the bar, correct rests, direction-aware spelling, shorter slurs.

### Layout and tools

- One merged menu bar and tabs Bridge / Stave Station / Piano Roll; the LCD can dock into the main window; the setter, stops and transport columns have draggable walls; lists and tables have fluid columns; text size scales the whole interface.
- Registration bank is a list that Cat/Char and the jog can step through; click an active registration to switch it off or on.
- A KeyLab toggle disengages the controller without stopping GrandOrgue; the bridge also runs without a KeyLab.
- Windows mixer (View > Mixer, Ctrl+M) with faders and scenes for GrandOrgue and the background player (needs `pycaw`).
- Piano roll snaps like FL Studio (Alt for free placement). Help > Licenses shows the full third-party notices.

## After updating

Re-import the Friesach MIDI settings (`Settings/Friesach-midi-settings-KeyLab.yaml`) in GrandOrgue: they now carry the metronome BPM label, the tremulant paths and the RefreshFiles route.

---

# What's New in 2.0.8 and earlier

This summarizes the changes since v2.0.3. See [CHANGELOG.md](../CHANGELOG.md) for the itemized history.

## For players

### Floating LCD

- The optional always-on-top LCD now shows transport, recording, metronome, clock, take progress, setter/cue, and drawn-stop information.
- Volume knobs and the swell fader follow live values and can be adjusted with the mouse or wheel.
- Choose a spectrum or oscilloscope view of the current output. This optional Windows audio capture uses NumPy and PyAudioWPatch; the rest of the app works without the audio display.
- The LCD indicates whether sheet-music jog navigation is browsing files or setters. Long LCD text scrolls instead of being silently cut off.

### Tempo and playback

- A single session tempo is shared by the bridge, Stave Station, and Piano Roll, with synchronized controls and shared undo/redo.
- MIDI playback scales the file's tempo map to the session tempo. Opening a file adopts its average tempo; the stave preview can retain the chosen session tempo. GrandOrgue metronome tempo feedback and step controls follow the same target.
- MIDI, karaoke MIDI, and MusicXML exports preserve the selected tempo.
- The playhead, timeline, and step-sequence length follow the playback tempo.
- Playback uses an absolute schedule to avoid slow timing drift. Long stalls are absorbed rather than followed by a catch-up burst, MIDI output workers wake on queued messages, and the completion log reports worst lateness and absorbed stalls.

### Sheet music and score follow

- During playback, the score follows the current bar and keeps it visible. Manual scrolling temporarily takes precedence; Stop followed by Play resumes following from the first bar.
- The sheet-music window can use the sustain pedal for page navigation: one tap advances and a double tap goes back. This option is separate from loading a setter; the jog press remains the setter-load action.
- Page scrolling and zoom behavior were improved, and the LCD cue preview identifies the current sheet-music navigation context.
- Organ manual names are shown consistently in organ, track, and stave views; changing manual settings refreshes the score and track list.
- Setters that share a name and step are resolved against the nearest known position, avoiding a jump to the wrong match.

## Maintenance and developer workflow

- Textual console output safely escapes Rich markup; typing fixes improve Pylance analysis without changing the existing shortcuts or footer behavior.
- ODF scan types and error/path handling were tightened; a development environment checker can inspect and repair the deployed venv.
- Personal take/directory state files are excluded from Git, and manual-count/name changes trigger a stave refresh.
- `tools/deploy_dev.ps1` preserves the deployed virtual environments. `-Pip` installs requirements into the target `.venv-build`, and `-Run` launches with that interpreter.
- VS Code task 10 can manually dispatch the GitHub release workflow to build artifacts. A branch dispatch does not publish a GitHub Release; pushing a `v*` tag triggers publication.
- The maintainer's deployed `start_keylab_bridge.ps1` was updated locally to prefer the deployed `.venv-build`; that live-folder edit is not a tracked repository file.

## Platform and verification status

- Windows is the supported release platform. The release workflow also builds an experimental Linux package; Linux MIDI routing and hardware remain unvalidated. macOS packaging is deferred.
- A successful GitHub build verifies compilation and packaging, not real-organ behavior. The new timing, pedal-navigation, and LCD behavior has not been verified on the real organ as part of these documentation changes.
