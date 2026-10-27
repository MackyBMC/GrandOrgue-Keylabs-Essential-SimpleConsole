# Handoff: KeyLab GrandOrgue Bridge (v2.0.x)

For any assistant (Claude, Copilot) or developer picking this up. Keep it short and current; update it when something here changes.

## What it is
Python / PySide6 tool for playing the GrandOrgue Friesach organ from an Arturia KeyLab Essential 61 mk2 (Windows, loopMIDI ports).
Parts:
- **Bridge** (`keylab_go_bridge.py`, `qt_gui.py`, `keylab_bridge/`): keyboard / pads / setters / stop grid / combinations, and MIDI file playback through GrandOrgue.
- **Stave Station** (`midi_stave/`): MIDI or MusicXML to engraved score (music21 + Verovio), plus the **MIDI Track / Piano Roll Editor**.
- Goal: a professional, simple tool for liturgical organ work in budget churches. Tracks map to organ manuals and registrations, like instruments in a DAW, but it is not a DAW.

## Run
`python -m pip install -r requirements.txt`, then `python keylab_go_bridge.py` (full app) or `python midi_stave\stave_station.py` (stave editor alone).
Dev organ folder: set `KEYLAB_GO_FOLDER` or `go_folder.txt` (data dir). The warning "Could not load organ layout" is harmless without it.
Release: bump `version.py`, tag `v<version>`, push; the GitHub Actions workflow builds (Nuitka) and the Inno Setup installer. See `docs/RELEASING.md`. New top-level modules must be added to the include list in `packaging/nuitka_build.py`.

## Layout
- `keylab_bridge/application.py`: BridgeApp, UI event queue (`post_ui_event` / `process_ui_event`), MIDI ports, setters.
- `keylab_bridge/take_recorder.py`: `TakePlayer` (file playback thread; events: chord, gate, seek), recorder, stave-friendly copy.
- `keylab_bridge/tempo.py` + `tempo_control.py` (from 2.0.4): one session-wide BPM (`TempoSession`, undo/redo, listeners); `TempoControl` fader+spin with ticks used in main, Stave and roll.
- `keylab_bridge/paths.py` (`go_folder()`), `preset_store.py`, `organ_layout.py`, `stop_grid.py`.
- `midi_stave/core.py`: notes, `BarMap`, bar detection, quantise/shape (`shape_notes`), `make_staves`/`organ_staves`/`NAME_SETS`, `stave_go_channels`, `export_fixed_midi`.
- `midi_stave/midi_stave.py`: `Stave` main window, `PianoRoll`, layouts, per-stave manual rows, registration dialogs, audition, playback hooks.
- `midi_stave/roll_window.py`, `track_panel.py` (track list, `OrganDialog`), `quant_tools.py`, `render.py` (MusicXML/Verovio), `sessionmeta.py` (manual slots, suggestions), `chrome.py`.
- `packaging/`: Nuitka, Inno Setup (Standard/Portable page + GrandOrgue folder page), Linux/mac experimental.

## Key design decisions
- **Manual slots are fixed, names are display only.** Slots: Pedal ch2, Hauptwerk ch3, Schwellwerk ch4, Solowerk ch5 (`sessionmeta.MANUALS`, override with `manual_channels` in config). `Stave.manual_label(slot)` gives the organ's own name (Great/Swell/Choir, German, French, custom). Saved mappings (`track_map`) always use the slot names. Future: read manual names from the `.organ` file.
- **Track to organ mapping**: `Stave.track_map[(track, channel)] = {manuals, reg, bass_split}`; feeds `core.TRACK_ROUTES / TRACK_SPLIT`; a track with no manual follows the stave layout.
- **Bass to pedal**: lowest note of each chord on the Pedal (mono lead) with a limit; can also be extracted into a real pedal track.
- **Time bases (easy to get wrong).** Stave preview file `_preview.mid` is written at the file's average tempo (`barmap.average_bpm()`). `TakePlayer.position()` returns file time at that tempo; beat = `t * average_bpm / 60`. Playback speed = session BPM / file average BPM (`TakePlayer.base_bpm`). Do not treat preview time as original-score seconds.
- **Tempo** is stored only when a MIDI / MusicXML file is saved or exported. Opening a file sets the session BPM to its average (no undo step); the stave preview keeps the chosen BPM.
- Opening a MIDI with 2+ tracks starts with "one stave per track, highest first".
- Quantise "Source": raw or quantised piano roll feeds the stave; shaping modes keep / snap / legato / fingered / organ (organ-friendly legato only lengthens).

## Gotchas
- Windows junctions cause Inno error 448: use the real path (e.g. `H:\...`).
- Ambiguous Qt shortcuts (Ctrl+Up/Down is key zoom, Ctrl+Shift+Up/Down is octave). Alt/Shift wheel swaps Qt axes: use `y or x`.
- First fill of organ widgets must not call `update_name_hint` before the rows exist.
- Changing organ names / manual count must call `changed()` (re-engrave), not only update the hint.
- Nuitka: bare-name imports need `--include-module`; matplotlib is excluded.

## Open items (not yet verified or built)
- Main-window "Tempo %" reportedly had no effect: cause not found (player proved fine in a test). Check the bridge log after moving the new fader.
- Real-organ test of gate events (audition) and track-level registration markers.
- Note-timing jitter on Windows after the `Condition.wait` change in `TakePlayer`.
- GrandOrgue tempo follows the session BPM by single step presses; may stall at GO's limits.
- Track-driven manual staves (each manual's stave fed by mapped tracks); 3+ manuals currently split by pitch.
- Read manual names from `.organ`; apply registration at the audition line; save `track_map` / `voice_reg` / `hidden_tracks` with the project.
- GUI field for the GrandOrgue folder; generic default `organ_path` with first-run prompt.
- Real Sponsors / Ko-fi handles in `.github/FUNDING.yml`; merge `release-2.0` to main via PR and tag.
- Linux / macOS packaging untested.
