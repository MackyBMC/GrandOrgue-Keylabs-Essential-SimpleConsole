# What's New in 2.0.8

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
