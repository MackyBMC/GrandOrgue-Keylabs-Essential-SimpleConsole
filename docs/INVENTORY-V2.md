# v2 assumption inventory and v3 destination map

*Status: FIRST PASS from file names, symbol names and grep counts on `release-2.0` @ `94fea73` (2026-11-13). Counts are VERIFIED (grep). Classification of any module not opened line by line is PROPOSED and marked "classify". Pass 2 (full read, symbol-level tagging) is ROADMAP M0.*

Tags: **L** logical/core, **E** engine-specific (GrandOrgue), **C** controller-specific (KeyLab), **A** app/UI, **S** stave, **I** infrastructure.

## 1. Hotspot counts (case-insensitive grep, `*.py`)
| Pattern | Top files (count) |
|---------|-------------------|
| `friesach` | application.py 6; preset_store.py 2; odf_scan.py 2; sessionmeta.py, go_settings.py, organ_layout.py, keylab_go_bridge.py, make_go_midi_import.py 1 each |
| `grandorgue` | application.py 43; qt_gui.py 30; keylab_go_bridge.py 20; translations.py 16; go_midi_setup.py 15; go_launcher.py 14; midi_protocol.py 8; go_settings.py 8 |
| `keylab` | keylab_go_bridge.py 30; qt_gui.py 26; application.py 12; midi_protocol.py 9; midi_ports.py 6 |
| manual names (`Hauptwerk\|Schwellwerk\|Solowerk\|Pedal`) | midi_stave.py 69; sessionmeta.py 37; core.py 25; application.py 23; qt_gui.py 22; track_panel.py 14; render.py 10; take_recorder.py 10 |
| `channel` | application.py 57; midi_stave.py 37; sessionmeta.py 35; take_recorder.py 34; core.py 31; midi_protocol.py 30; qt_gui.py 29; organ_layout.py 23 |
| `mido` | take_recorder.py 27; sessionmeta.py 12; midi_stave.py 10; keylab_go_bridge.py 9; core.py 7; stave_station.py 3; application.py 2 |
| `PySide6` | midi_stave.py 17; qt_gui.py 11; chrome.py 9; roll_window.py 5 |
Repo size: about 21k lines of Python (largest: midi_stave.py 3.9k, qt_gui.py 3.4k, application.py 2.4k, midi_protocol.py 0.85k, core.py 0.8k).

## 2. Symbol-level findings already confirmed
| Symbol / location | Tag | Problem | v3 destination |
|-------------------|-----|---------|----------------|
| `organ_layout.DIVISIONS`, `OTHERS` | L (data) | Friesach stops as Python constants | organ data file (`organ_id: friesach-parish`) |
| `organ_layout.SWITCH_OFFSET`, `TREMULANT_SWITCH`, `TREMULANT_DIVISION`, `PATH_OVERRIDES` | E | Friesach switch quirks | GrandOrgue wire map (generated) |
| `Item.path`, `Item.channel`, `Item.key`, `wire_for`, `STOP_CHANNELS`, `DEFAULT_SPILL_CHANNELS`, `CCS_PER_CHANNEL` | E | engine addressing inside the logical `Item` | GrandOrgue plugin; `Item` keeps only logical fields |
| `organ_layout.build_banks`, `BANK_SIZE`, `rebuild_layout` (mutates module globals) | L/C | single global layout; banks are a controller concern | core builds banks from model + controller `faders` |
| `midi_protocol.CMD_PATHS`, `FB_PATHS`, `VOL_CH`, `VOLS`, `POSITION_LABEL_PATH` | E | GrandOrgue object paths and channel plan | GrandOrgue plugin |
| `midi_protocol.KEYLAB_HEADER`, `LINE_WIDTH`, `TEXT_WIDTH`, `MIN_INTERVAL_S`, `LED_IDS`, `PAD_LED_*`, `DEFAULT_PAD_*`, `N_JOG_PRESS`, `MENU_PAGES`, `lcd_data`, `led_data`, `parse_go_sysex` | C (mostly) | KeyLab sysex, LCD and LED details; `parse_go_sysex` is E | KeyLab plugin / GO plugin respectively |
| `midi_protocol.Bridge` (line ~249) | classify | probably mixes C and E | split in M2/M4 |
| `sessionmeta.MANUALS` (Pedal ch2, Hauptwerk ch3, Schwellwerk ch4, Solowerk ch5) | L+E | four fixed manual slots, names used as keys in saved mappings | organ manuals + engine channel assignment; saved `track_map` keys migrate |
| `application.BridgeApp` (2,380 lines) | mixed | controller handling, engine feedback, organ import, setter logic, UI events in one class | split along core / controller / engine seams (M4) |
| `application._scan_organ_file`, `_generate_organ_map`, `_apply_organ_layout`, `import_organ`, `_commit_organ_import` | E (+L) | organ import is GrandOrgue-specific | GrandOrgue plugin `import_organ`; core consumes `Organ` |
| `application.handle_daw_message`, `handle_main_message`, `pad_lines`, `reload_pad_settings` | C | KeyLab message handling | KeyLab plugin |
| `application.process_ui_event`, `post_ui_event` | A/L | the event queue (keep) | core event bus |
| `application.activate_combination`, `cue_combination`, `navigate_combinations`, `request_navigate`, `save_combination_editor` | L | setter logic with GrandOrgue feedback mixed in | core registrations service |
| `config.yaml` (organ_path, combination_set 'Friesach', ports, faders, pads) | mixed | one file mixes app, engine, controller, organ | split per layer; `config.yaml` stays readable |
| `go_midi_setup.py`, `make_go_midi_import.py`, `go_settings.py`, `go_launcher.py`, `odf_scan.py`, `stop_grid.py` | E (stop_grid: classify) | GrandOrgue tooling | GrandOrgue plugin |
| `preset_store.py`, `combination_transfer.py` | L+E | setter YAML; contains GrandOrgue paths | core registrations + migration |
| `take_recorder.py`, `tempo.py`, `tempo_control.py` | L (+mido) | takes/tempo; mido at the core boundary | core session; MIDI event type at the edge |
| `midi_ports.py` | I | port discovery/open (rtmidi) | infrastructure used by plugins |
| `paths.py`, `lastdir.py`, `version.py` | I | locations | infrastructure |
| `qt_gui.py`, `console_ui.py` (Textual), `lcd_float.py`, `themes*.py`, `translations.py`, `polish.py` | A | UI; many GrandOrgue/KeyLab words in strings | app; strings keyed, not literal |
| `audio_tap.py`, `audio_mixer`, `mixer_panel` | A/I | optional audio visuals / mixer | app, optional |
| `midi_stave/*` | S | notation; manual names and channels assumed | stave layer on core model |
| `keylab_go_bridge.py` | A | entry point; wiring and CLI | app entry + plugin loader |

## 3. Pass 2 (to do, M0)
1. Open every module and tag each top-level symbol L/E/C/A/S/I in a table here (or `docs/inventory/*.csv`).
2. List every literal that encodes: a manual name, a channel number, a CC number, a GrandOrgue object path, a KeyLab sysex byte, a Friesach stop name.
3. Produce the import graph (who imports whom) and mark edges that would violate ARCHITECTURE section 3.
4. Output: the migration order per module and the golden-file list for regression (VERIFICATION.md).
