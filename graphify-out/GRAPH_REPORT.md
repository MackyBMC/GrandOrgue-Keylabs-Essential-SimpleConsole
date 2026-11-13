# Graph Report - GrandOrgue-Keylabs-Essential-SimpleConsole  (2026-11-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3888 nodes · 6386 edges · 193 communities (155 shown, 38 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 166 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `db23a1e2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
- Community 185
- Community 188
- Community 189

## God Nodes (most connected - your core abstractions)
1. `Stave` - 171 edges
2. `BridgeApp` - 110 edges
3. `BridgeWindow` - 85 edges
4. `LcdFloat` - 50 edges
5. `Bridge` - 43 edges
6. `SheetMusicWindow` - 38 edges
7. `MidiPorts` - 31 edges
8. `RollWindow` - 27 edges
9. `BarMap` - 26 edges
10. `TempoControl` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Stave` --uses--> `TempoSession`  [INFERRED]
  midi_stave/midi_stave.py → keylab_bridge/tempo.py
- `TempoControl` --uses--> `TempoSession`  [INFERRED]
  tempo_control.py → keylab_bridge/tempo.py
- `Stave` --uses--> `TempoControl`  [INFERRED]
  midi_stave/midi_stave.py → tempo_control.py
- `RollWindow` --uses--> `TempoControl`  [INFERRED]
  midi_stave/roll_window.py → tempo_control.py
- `main()` --calls--> `BridgeApp`  [EXTRACTED]
  keylab_go_bridge.py → keylab_bridge/application.py

## Import Cycles
- None detected.

## Communities (193 total, 38 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (6): AudioTap, callback(), optional(), fmt_clock(), LcdFloat, mix()

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (63): manuals, name, stops, switches, manuals, name, stops, switches (+55 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (31): ascii_clean(), lcd_data(), led_data(), pad_color_key(), pad_colors_for_spec(), pad_rgb(), pad_screen_color(), parse_go_sysex() (+23 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (12): app_name(), clean_name(), default_backend(), optional(), PycawBackend, Scenes, Strip, to_db() (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (5): Overview, RollWindow, Ruler, TempoControl, TempoTicks

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (55): manuals, name, stops, switches, couplers, manuals, name, stops (+47 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (53): manuals, name, stops, switches, manuals, name, stops, switches (+45 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (4): scope_trace(), spectrum_bands(), load_user_themes(), _anchor()

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (25): auto_channel_map(), channel_map(), channel_notes(), file_voices(), _foot_value(), format_marker(), format_reg(), format_stops() (+17 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (4): BarMap, load_musicxml(), main(), default_path()

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (11): ChatFile, linkify(), load_answers(), main(), MainWindow, parse_questions(), Question, QuestionCard (+3 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (48): manuals, name, stops, switches, manuals, name, stops, switches (+40 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (48): manuals, name, stops, switches, couplers, name, stops, switches (+40 more)

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (47): manuals, name, stops, switches, tremulants, name, stops, switches (+39 more)

### Community 17 - "Community 17"
Cohesion: 0.06
Nodes (47): manuals, name, stops, switches, manuals, name, stops, switches (+39 more)

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (46): manuals, name, stops, switches, name, stops, switches, name (+38 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (45): manuals, name, stops, switches, manuals, name, stops, switches (+37 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (45): manuals, name, stops, switches, name, stops, switches, name (+37 more)

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (22): build(), default_folder(), find_source(), fingerprint(), is_import_file(), _load(), output_for(), refresh_if_stale() (+14 more)

### Community 22 - "Community 22"
Cohesion: 0.05
Nodes (43): manuals, name, stops, switches, tremulants, name, stops, switches (+35 more)

### Community 23 - "Community 23"
Cohesion: 0.05
Nodes (43): manuals, name, stops, switches, tremulants, name, stops, switches (+35 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (42): manuals, name, stops, switches, tremulants, name, stops, switches (+34 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (42): manuals, name, stops, switches, name, stops, switches, name (+34 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (42): manuals, name, stops, switches, tremulants, name, stops, switches (+34 more)

### Community 27 - "Community 27"
Cohesion: 0.05
Nodes (42): manuals, name, stops, switches, name, stops, switches, name (+34 more)

### Community 28 - "Community 28"
Cohesion: 0.05
Nodes (42): continue-on-error, needs, runs-on, steps, strategy, jobs, build, prepare (+34 more)

### Community 29 - "Community 29"
Cohesion: 0.07
Nodes (4): stave_module(), TempoSession, main(), open_go_port()

### Community 30 - "Community 30"
Cohesion: 0.05
Nodes (41): manuals, name, stops, switches, name, stops, switches, name (+33 more)

### Community 32 - "Community 32"
Cohesion: 0.05
Nodes (40): manuals, name, stops, switches, name, stops, switches, name (+32 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (40): manuals, name, stops, switches, name, stops, switches, name (+32 more)

### Community 34 - "Community 34"
Cohesion: 0.05
Nodes (40): manuals, name, stops, switches, name, stops, switches, name (+32 more)

### Community 35 - "Community 35"
Cohesion: 0.06
Nodes (39): manuals, name, stops, switches, name, stops, switches, name (+31 more)

### Community 36 - "Community 36"
Cohesion: 0.07
Nodes (17): build_go_settings(), _cc(), compare_with_export(), _generic(), merge_settings_export(), windchest_count(), build_banks(), configure_layout() (+9 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (36): manuals, name, stops, switches, name, stops, switches, name (+28 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (36): manuals, name, stops, switches, name, stops, switches, name (+28 more)

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (18): escape(), melodic_line(), split_voices(), run(), warm_up(), _abbreviation(), _add_credits(), _add_multirests() (+10 more)

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (35): manuals, name, manuals, name, manuals, name, manuals, name (+27 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (17): _accepts(), assign(), estimate_bars(), estimate_bpm(), load_midi(), organ_staves(), pedal_leads(), QNote (+9 more)

### Community 44 - "Community 44"
Cohesion: 0.09
Nodes (34): manuals, name, stops, manuals, name, stops, couplers, manuals (+26 more)

### Community 47 - "Community 47"
Cohesion: 0.08
Nodes (3): make_staves(), stave_go_channels(), load_combos()

### Community 48 - "Community 48"
Cohesion: 0.10
Nodes (17): main(), modules_in(), needed_python(), plan(), resolve(), ascii_clean(), find_port(), keylab_data() (+9 more)

### Community 49 - "Community 49"
Cohesion: 0.12
Nodes (20): _alias_value(), _manual_alias(), _manual_key(), _match_name(), _name_key(), _object_key(), _record_unmatched(), _target_manual_items() (+12 more)

### Community 51 - "Community 51"
Cohesion: 0.15
Nodes (7): BridgeApp, _contains_combinations(), load_transfer_aliases(), transfer_combinations(), write_transfer_alias_template(), project_root(), set_config_key()

### Community 52 - "Community 52"
Cohesion: 0.08
Nodes (6): _realtime_boost(), _realtime_restore(), save_midi_at_tempo(), TakePlayer, threading_current(), write_stave_friendly()

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (4): LyricsDialog, SetterPicker, StopPicker, VoiceRegDialog

### Community 54 - "Community 54"
Cohesion: 0.09
Nodes (7): ConsoleUI, create_console_ui(), TextualConsoleUI, extra_css(), full_css(), _mix(), contrast_text()

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (29): switches, switches, switches, switches, switches, switches, switches, switches (+21 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (27): info, content-type, grandorgue-version, organ-name, saved_time, objects, name, path (+19 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (25): info, content-type, grandorgue-version, organ-name, saved_time, objects, name, path (+17 more)

### Community 60 - "Community 60"
Cohesion: 0.11
Nodes (7): make_seek_slider(), __init__(), mouseMoveEvent(), mousePressEvent(), _value_at(), clock(), TransportBar

### Community 61 - "Community 61"
Cohesion: 0.13
Nodes (6): find_grandorgue(), start_grandorgue(), acquire_lock(), grandorgue_running(), process_running(), main()

### Community 62 - "Community 62"
Cohesion: 0.13
Nodes (16): apply_theme(), build_chrome(), action(), _build_view_menu(), ensure_qtawesome(), _glyph_names(), icon(), _icon_credits() (+8 more)

### Community 63 - "Community 63"
Cohesion: 0.13
Nodes (3): core_is_poly(), OrganDialog, TrackPanel

### Community 64 - "Community 64"
Cohesion: 0.18
Nodes (6): save(), _settings(), AppearanceDialog, apply_toolbars(), _bars(), _key()

### Community 65 - "Community 65"
Cohesion: 0.17
Nodes (23): manuals, name, manuals, name, couplers, manuals, name, manuals (+15 more)

### Community 67 - "Community 67"
Cohesion: 0.14
Nodes (22): stops, stops, stops, stops, 001, 002, 003, 004 (+14 more)

### Community 68 - "Community 68"
Cohesion: 0.16
Nodes (22): switches, switches, switches, switches, switches, switches, 001, 002 (+14 more)

### Community 69 - "Community 69"
Cohesion: 0.12
Nodes (21): stops, stops, stops, stops, 001, 002, 004, 006 (+13 more)

### Community 70 - "Community 70"
Cohesion: 0.16
Nodes (7): add_step(), commit_current_row(), handle_cancel(), is_dirty(), load_row(), row_selected(), StopGridWidget

### Community 71 - "Community 71"
Cohesion: 0.12
Nodes (3): apply_theme(), on_mount(), refresh_dashboard()

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (8): ascii_clean(), Bridge, find_port(), keylab_data(), layout(), main(), parse_go_sysex(), split_lines()

### Community 73 - "Community 73"
Cohesion: 0.14
Nodes (19): switches, switches, switches, 001, 002, 003, 004, 005 (+11 more)

### Community 75 - "Community 75"
Cohesion: 0.13
Nodes (19): stops, stops, stops, stops, 001, 002, 004, 005 (+11 more)

### Community 76 - "Community 76"
Cohesion: 0.12
Nodes (19): stops, stops, stops, stops, 001, 002, 004, 006 (+11 more)

### Community 78 - "Community 78"
Cohesion: 0.15
Nodes (17): stops, stops, stops, 001, 002, 003, 004, 006 (+9 more)

### Community 79 - "Community 79"
Cohesion: 0.13
Nodes (17): switches, switches, 001, 002, 003, 004, 006, 007 (+9 more)

### Community 80 - "Community 80"
Cohesion: 0.15
Nodes (4): ConfigEditor, leaves(), _MiniRoll, read_config_comments()

### Community 82 - "Community 82"
Cohesion: 0.15
Nodes (15): stops, stops, stops, 001, 002, 004, 006, 007 (+7 more)

### Community 83 - "Community 83"
Cohesion: 0.20
Nodes (5): get(), put(), choose(), create(), refresh()

### Community 85 - "Community 85"
Cohesion: 0.19
Nodes (15): manuals, name, manuals, name, couplers, manuals, name, name (+7 more)

### Community 86 - "Community 86"
Cohesion: 0.18
Nodes (14): couplers, manuals, couplers, name, couplers, name, name, switches (+6 more)

### Community 87 - "Community 87"
Cohesion: 0.24
Nodes (8): app_dir(), data_dir(), first_run_config(), go_folder(), is_portable(), user_data_dir(), _writable(), default_config_path()

### Community 91 - "Community 91"
Cohesion: 0.26
Nodes (8): apply(), _Bus, _mix(), on_accent(), palette(), state(), stylesheet(), tokens()

### Community 92 - "Community 92"
Cohesion: 0.18
Nodes (13): couplers, manuals, name, couplers, name, name, switches, 001 (+5 more)

### Community 93 - "Community 93"
Cohesion: 0.19
Nodes (13): switches, switches, switches, 001, 002, 003, 004, 006 (+5 more)

### Community 94 - "Community 94"
Cohesion: 0.15
Nodes (13): h1, h2, hw, other, p1, p2, pedal, s1 (+5 more)

### Community 96 - "Community 96"
Cohesion: 0.15
Nodes (13): stops, 024, 025, 030, 031, 036, 037, 066 (+5 more)

### Community 97 - "Community 97"
Cohesion: 0.18
Nodes (12): stops, stops, 001, 002, 003, 004, 008, 009 (+4 more)

### Community 98 - "Community 98"
Cohesion: 0.18
Nodes (12): stops, stops, stops, 001, 004, 006, 007, 010 (+4 more)

### Community 99 - "Community 99"
Cohesion: 0.18
Nodes (12): switches, switches, 001, 002, 003, 005, 007, 008 (+4 more)

### Community 100 - "Community 100"
Cohesion: 0.17
Nodes (11): combination_set, faders, threshold, language, lcd_names, organ_layout_file, organ_path, preset_activation (+3 more)

### Community 101 - "Community 101"
Cohesion: 0.27
Nodes (6): _beat_text(), build_html(), _doh_near_middle(), _slot_text(), syllable(), _voice_line()

### Community 103 - "Community 103"
Cohesion: 0.17
Nodes (12): stops, stops, 001, 002, 004, 006, 007, 010 (+4 more)

### Community 104 - "Community 104"
Cohesion: 0.20
Nodes (10): name, switches, 000, sequencer, 000, 001, 006, 007 (+2 more)

### Community 105 - "Community 105"
Cohesion: 0.20
Nodes (10): manuals, name, tremulants, name, 000, 003, sequencer, 000 (+2 more)

### Community 106 - "Community 106"
Cohesion: 0.20
Nodes (10): name, switches, 000, sequencer, 000, 001, 005, 007 (+2 more)

### Community 107 - "Community 107"
Cohesion: 0.20
Nodes (11): stops, stops, stops, 002, 004, 006, 007, 010 (+3 more)

### Community 108 - "Community 108"
Cohesion: 0.18
Nodes (10): tremulants, info, content-type, grandorgue-version, organ-name, saved_time, sequencer, 000 (+2 more)

### Community 109 - "Community 109"
Cohesion: 0.20
Nodes (11): stops, stops, 001, 002, 012, 013, 014, 015 (+3 more)

### Community 110 - "Community 110"
Cohesion: 0.20
Nodes (11): couplers, manuals, name, name, switches, 001, 003, 000 (+3 more)

### Community 111 - "Community 111"
Cohesion: 0.18
Nodes (11): controls, encoder_step, encoders, jog_max_steps, loop_restart, volume_start, 1, 2 (+3 more)

### Community 112 - "Community 112"
Cohesion: 0.18
Nodes (5): _bounds(), _cut_point(), fill_rests(), meter_info(), split_for_meter()

### Community 113 - "Community 113"
Cohesion: 0.25
Nodes (11): tremulants, tremulants, tremulants, tremulants, tremulants, manuals, name, tremulants (+3 more)

### Community 114 - "Community 114"
Cohesion: 0.22
Nodes (10): switches, switches, 002, 003, 004, 008, 010, 011 (+2 more)

### Community 119 - "Community 119"
Cohesion: 0.20
Nodes (10): name, switches, manuals, manuals, 000, 002, 006, 005 (+2 more)

### Community 120 - "Community 120"
Cohesion: 0.27
Nodes (10): switches, switches, 001, 004, 005, 007, 009, 047 (+2 more)

### Community 121 - "Community 121"
Cohesion: 0.20
Nodes (10): switches, 002, 003, 008, 011, 013, 014, 016 (+2 more)

### Community 122 - "Community 122"
Cohesion: 0.22
Nodes (9): manuals, name, name, stops, switches, 001, 002, 018 (+1 more)

### Community 123 - "Community 123"
Cohesion: 0.22
Nodes (9): manuals, name, name, switches, name, 000, 001, 003 (+1 more)

### Community 124 - "Community 124"
Cohesion: 0.22
Nodes (9): switches, 002, 003, 008, 011, 013, 014, 016 (+1 more)

### Community 125 - "Community 125"
Cohesion: 0.25
Nodes (9): stops, stops, 003, 004, 006, 007, 009, 010 (+1 more)

### Community 126 - "Community 126"
Cohesion: 0.22
Nodes (9): name, stops, 001, 001, 002, 012, 013, 014 (+1 more)

### Community 127 - "Community 127"
Cohesion: 0.22
Nodes (8): name, info, content-type, grandorgue-version, organ-name, saved_time, sequencer, 000

### Community 128 - "Community 128"
Cohesion: 0.22
Nodes (3): _build_panels_bar(), toggle(), SectionPopup

### Community 129 - "Community 129"
Cohesion: 0.22
Nodes (8): full, manuals, manuals, manuals, sequencer, 000, 003, 007

### Community 130 - "Community 130"
Cohesion: 0.22
Nodes (9): couplers, name, switches, manuals, 001, 002, 005, 004 (+1 more)

### Community 131 - "Community 131"
Cohesion: 0.25
Nodes (8): switches, 003, 004, 008, 010, 011, 012, 013

### Community 132 - "Community 132"
Cohesion: 0.25
Nodes (8): name, stops, switches, 001, 002, 014, 015, 004

### Community 133 - "Community 133"
Cohesion: 0.25
Nodes (8): switches, 001, 005, 007, 009, 047, 053, 054

### Community 134 - "Community 134"
Cohesion: 0.25
Nodes (8): pads, ccs, dim, enabled, off_grey, refresh, shared_window, verbosity

### Community 135 - "Community 135"
Cohesion: 0.25
Nodes (8): ports, go, go_out, keylab_in, keylab_main_in, keylab_out, relay_main_in, relay_main_out

### Community 136 - "Community 136"
Cohesion: 0.25
Nodes (8): manuals, name, switches, manuals, 001, 001, 004, 014

### Community 137 - "Community 137"
Cohesion: 0.43
Nodes (8): tremulants, tremulants, tremulants, tremulants, tremulants, tremulants, 001, 002

### Community 138 - "Community 138"
Cohesion: 0.25
Nodes (7): CombinationSetterRouting, HardwareSettings, info, content-type, grandorgue-version, organ-name, saved_time

### Community 139 - "Community 139"
Cohesion: 0.29
Nodes (6): info, content-type, grandorgue-version, organ-name, saved_time, sequencer

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): switches, 005, 007, 009, 047, 053, 054

### Community 141 - "Community 141"
Cohesion: 0.29
Nodes (7): switches, 001, 002, 003, 008, 011, 014

### Community 142 - "Community 142"
Cohesion: 0.29
Nodes (7): stops, 001, 008, 009, 013, 014, 015

### Community 143 - "Community 143"
Cohesion: 0.29
Nodes (7): stops, stops, 004, 006, 007, 010, 011

### Community 144 - "Community 144"
Cohesion: 0.29
Nodes (6): info, content-type, grandorgue-version, organ-name, saved_time, sequencer

### Community 145 - "Community 145"
Cohesion: 0.29
Nodes (6): info, content-type, grandorgue-version, organ-name, saved_time, sequencer

### Community 146 - "Community 146"
Cohesion: 0.29
Nodes (7): testing, accept_ch1_aftertouch_pads, accept_note_pads, daw_trace, note_pad_channel, note_pad_first, pad_trace

### Community 148 - "Community 148"
Cohesion: 0.29
Nodes (6): info, content-type, grandorgue-version, organ-name, saved_time, sequencer

### Community 149 - "Community 149"
Cohesion: 0.33
Nodes (6): name, stops, switches, 003, 006, 007

### Community 150 - "Community 150"
Cohesion: 0.33
Nodes (6): name, stops, switches, 002, 018, 019

### Community 151 - "Community 151"
Cohesion: 0.33
Nodes (6): manuals, name, name, switches, 002, 003

### Community 152 - "Community 152"
Cohesion: 0.40
Nodes (6): couplers, couplers, 001, 002, 003, 000

### Community 153 - "Community 153"
Cohesion: 0.33
Nodes (6): name, stops, switches, 002, 018, 019

### Community 154 - "Community 154"
Cohesion: 0.33
Nodes (6): name, stops, switches, 002, 018, 019

### Community 156 - "Community 156"
Cohesion: 0.33
Nodes (3): flatten_svg(), _flatten_tspans(), walk()

### Community 157 - "Community 157"
Cohesion: 0.33
Nodes (5): info, content-type, grandorgue-version, organ-name, saved_time

### Community 158 - "Community 158"
Cohesion: 0.33
Nodes (5): info, content-type, grandorgue-version, organ-name, saved_time

### Community 159 - "Community 159"
Cohesion: 0.33
Nodes (6): HauptwerkDivision, AudioSliders, ControlNumber, DeviceIndex, EventType, MIDIChannel

### Community 160 - "Community 160"
Cohesion: 0.33
Nodes (6): DigitButton0, ControlNumber, DeviceIndex, EventType, MIDIChannel, TriggerValue

### Community 161 - "Community 161"
Cohesion: 0.33
Nodes (6): DigitButton1, ControlNumber, DeviceIndex, EventType, MIDIChannel, TriggerValue

### Community 162 - "Community 162"
Cohesion: 0.33
Nodes (6): DigitButton4, ControlNumber, DeviceIndex, EventType, MIDIChannel, TriggerValue

### Community 163 - "Community 163"
Cohesion: 0.33
Nodes (6): NextButton, ControlNumber, DeviceIndex, EventType, MIDIChannel, TriggerValue

### Community 164 - "Community 164"
Cohesion: 0.33
Nodes (6): PreviousButton, ControlNumber, DeviceIndex, EventType, MIDIChannel, TriggerValue

### Community 165 - "Community 165"
Cohesion: 0.47
Nodes (6): tremulants, tremulants, tremulants, 000, 001, 002

### Community 166 - "Community 166"
Cohesion: 0.40
Nodes (5): info, content-type, grandorgue-version, organ-name, saved_time

### Community 167 - "Community 167"
Cohesion: 0.40
Nodes (5): info, content-type, grandorgue-version, organ-name, saved_time

### Community 168 - "Community 168"
Cohesion: 0.40
Nodes (5): info, content-type, grandorgue-version, organ-name, saved_time

### Community 169 - "Community 169"
Cohesion: 0.40
Nodes (5): manuals, name, name, 003, 000

### Community 170 - "Community 170"
Cohesion: 0.40
Nodes (3): _format_yaml_value(), set_config_value(), _split_value_comment()

### Community 172 - "Community 172"
Cohesion: 0.50
Nodes (5): couplers, couplers, couplers, 001, 002

### Community 173 - "Community 173"
Cohesion: 0.40
Nodes (5): info, content-type, grandorgue-version, organ-name, saved_time

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (5): PedalDivision, ControlNumber, DeviceIndex, EventType, MIDIChannel

### Community 175 - "Community 175"
Cohesion: 0.40
Nodes (5): SchwellwerkDivision, ControlNumber, DeviceIndex, EventType, MIDIChannel

### Community 176 - "Community 176"
Cohesion: 0.40
Nodes (5): SolowerkDivision, ControlNumber, DeviceIndex, EventType, MIDIChannel

### Community 177 - "Community 177"
Cohesion: 0.40
Nodes (5): ControlNumber, DeviceIndex, EventType, MIDIChannel, Enclosure001

### Community 178 - "Community 178"
Cohesion: 0.50
Nodes (4): couplers, name, 001, 002

### Community 179 - "Community 179"
Cohesion: 0.50
Nodes (4): couplers, name, 002, 001

### Community 180 - "Community 180"
Cohesion: 0.50
Nodes (4): couplers, name, 001, 002

### Community 181 - "Community 181"
Cohesion: 0.50
Nodes (4): couplers, name, 002, 001

### Community 182 - "Community 182"
Cohesion: 0.50
Nodes (4): display, hold, live, refresh

## Knowledge Gaps
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Stave` connect `Community 8` to `Community 5`, `Community 9`, `Community 10`, `Community 11`, `Community 21`, `Community 155`, `Community 29`, `Community 37`, `Community 40`, `Community 171`, `Community 47`, `Community 53`, `Community 185`, `Community 186`, `Community 187`, `Community 57`, `Community 62`, `Community 77`, `Community 81`, `Community 102`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Stave` (e.g. with `TempoSession` and `TempoControl`) actually correct?**
  _`Stave` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.054987212276214836 - nodes in this community are weakly interconnected._
- **Why does `BridgeWindow` connect `Community 15` to `Community 0`, `Community 64`, `Community 66`, `Community 2`, `Community 4`, `Community 5`, `Community 70`, `Community 9`, `Community 80`, `Community 50`, `Community 83`, `Community 84`, `Community 54`, `Community 90`, `Community 60`, `Community 31`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `BridgeApp` (e.g. with `ConsoleUI` and `MidiPorts`) actually correct?**
  _`BridgeApp` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.05952380952380952 - nodes in this community are weakly interconnected._
- **Why does `TempoControl` connect `Community 5` to `Community 8`, `Community 9`, `Community 11`, `Community 15`, `Community 50`, `Community 29`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._