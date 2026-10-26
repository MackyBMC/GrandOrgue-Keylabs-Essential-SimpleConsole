#!/usr/bin/env python3
"""
KeyLab Essential 61 mk2 (DAW mode)  <->  GrandOrgue bridge  (v3)

  KeyLab DAW port  --buttons/faders/jog-->  this script  --commands (CC on ch 16, stops on ch 15)-->  virtual cable --> GrandOrgue
  KeyLab LCD/LEDs  <--status/feedback----   this script  <--state feedback (ch 14, ch 15, label sysex)-- virtual cable <-- GrandOrgue

GrandOrgue keeps reading the KeyLab MAIN port directly (keys, pedal, wheels), so playing never
passes through Python.  Load Friesach-midi-settings-KeyLab.yaml in GrandOrgue (MIDI Objects > Import)
so it understands the messages below.

Controls (DAW mode)
    Rewind / Forward    previous / next step inside the loaded piece file (activates)
    Nav left / right    with Metro held, decrease / increase BPM; with Preset grid mode, move the 4x2 pad window horizontally
  Jog                 cue previous / next setter file (does NOT activate; Load file or your pedal does)
    Jog press           load the cued file
    Sustain pedal       load the cued file during MIDI playback; otherwise step the current piece when Play starts it
    Part 2/Prev, Part 1/Next   previous / next mapped stop bank
    Faders 1-8          drawbars for the stops of the current bank: a fader you move sets its stop on
                                            (above half travel) or off; faders you do not touch change nothing. Bank buttons
                                            continue to select fader banks while Preset grid mode remaps only the pads.
    Preset              open / close the Qt Stop Selection Grid; pads control the highlighted 4x2 window.
                      Bank overview (2.5 s after a bank change): # on/up  . off/down  ^ on but fader
                      down (raise it)  v off but fader up (lower it)  ? fader not seen yet
  Master fader        master volume;  Encoders 1-4: Pedal / Hauptwerk / Solowerk / Schwellwerk volume
  Encoder 5           Swell (Schwellwerk enclosure): turn right = more open, left = more closed
  Encoders 7, 8       Tremolo II / III: turn right = on, left = off (the tremolos are also in their division's bank)
    Play/Pause          GrandOrgue MIDI player, or start/pause a stepped piece when no MIDI is loaded
    Stop                stop/reset playback and panic (all sound off)
  Save                setter "Save file"
  Metro               GrandOrgue metronome on/off

LCD: first two characters of each line are status (top: bank e.g. H2, bottom: step, or "->" when a
file is cued), the rest is the current file name.  Moving a fader or encoder shows its readout (stop
name and state, or volume bar) on every update while it moves (at most every --live seconds),
then the normal display returns after --hold seconds.  Encoders 1-4 = Pedal, Hauptwerk, Solowerk,
Schwellwerk volume; encoder 5 = Swell (Schwellwerk enclosure); fader 9 = master volume.

Requires:  pip install mido python-rtmidi pyyaml textual
Run:
  python keylab_go_bridge.py --list
  python keylab_go_bridge.py --go "LoopBe" --kl-in "DAW" --kl-out "KeyLab" --verbose

Fallback for machines where GrandOrgue and this script cannot both open the KeyLab MAIN port
(some MIDI drivers refuse to share a device between two programs). --relay-main makes the
script the ONLY thing that opens the physical KeyLab MAIN port: every message (keys, pedal,
wheels, pads) is forwarded unchanged, the instant it arrives, to a virtual port that GrandOrgue
reads instead. This trades the "playing never touches Python" guarantee for a working pad
solution on awkward driver setups - use --kl-main (no relay) whenever direct sharing works.

  python keylab_go_bridge.py --go "LoopBe" --kl-in "DAW" --kl-out "KeyLab" ^
      --relay-main "KL2GO" --relay-main-in "Ess Midi In"
  (then point GrandOrgue's MIDI input at "KL2GO" instead of the KeyLab MAIN device)
"""

import argparse
import signal
import sys

from keylab_bridge import __version__
from keylab_bridge.application import BridgeApp
from keylab_bridge.console_ui import ConsoleUI, TextualConsoleUI, create_console_ui
from keylab_bridge.midi_ports import MidiPorts
from keylab_bridge.midi_protocol import (
    CC_JOG, CC_SUSTAIN, CMD, CMD_CH, CMD_PATHS, DEFAULT_PAD_CCS, DEFAULT_PAD_COLORS,
    ENCODER_VOLS, FB, FB_CH, FB_PATHS, FILENAME_LABEL_KEY, KEYLAB_HEADER, LED_IDS,
    LINE_WIDTH, MIN_INTERVAL_S, N_FORWARD, N_JOG_PRESS, N_LOOP, N_METRO, N_NAV_LEFT,
    N_NAV_RIGHT, N_NEXT_BANK, N_PLAY, N_PREV_BANK, N_REWIND, N_SAVE, N_STOP,
    PAD_LED_BASE, PAD_LED_GAP_S, PLAYER_START_CONFIRM_S, POSITION_LABEL_KEY,
    POSITION_LABEL_PATH, STOP_CH, TEXT_WIDTH, VOL_CH, VOLS, Bridge, ascii_clean,
    lcd_data, led_data, pad_color_key, pad_rgb, parse_go_sysex, screen_rgb, split_lines,
)
from keylab_bridge.organ_layout import (
    BANKS, BANK_SIZE, DIVISIONS, ITEMS, ITEM_BY_CC, OTHERS, SWITCH_OFFSET,
    TREMULANT_DIVISION, TREMULANT_SWITCH, Item, build_banks, rebuild_layout,
)
from keylab_bridge.preset_store import (
    _normalized_mapping_key, _replace_managed_switch, _write_managed_switches,
    apply_layout, apply_lcd_names, bridge_settings, default_config_path,
    describe_encoders, describe_tremolos, find_matching_port, find_port,
    learn_pads, load_combinations, load_config, load_language, load_preset_activation,
    load_theme,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="settings file (default: config.yaml next to this script)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--go", default="LoopBe", help="virtual cable used with GrandOrgue (in and out)")
    ap.add_argument("--go-out", help="if you use a second cable for bridge -> GrandOrgue")
    ap.add_argument("--kl-in", default="DAW", help="KeyLab DAW INPUT port (part of its name)")
    ap.add_argument("--kl-out", default="KeyLab", help="KeyLab OUTPUT port for LCD and LEDs")
    ap.add_argument("--kl-main", help="KeyLab MAIN input port (part of its name); needed for the pads, direct-share mode")
    ap.add_argument("--relay-main", help="fallback mode: name of a virtual output port. When set, this script becomes "
                     "the only reader of the KeyLab MAIN port and forwards every message to this port unchanged; "
                     "point GrandOrgue's MIDI input at this port instead of the KeyLab. Needs --relay-main-in too.")
    ap.add_argument("--relay-main-in", help="the physical KeyLab MAIN input port to relay from (with --relay-main); "
                     "defaults to the --kl-main value")
    ap.add_argument("--learn-pads", action="store_true", help="press pads 1-8 in turn and print the CC numbers for config.yaml")
    ap.add_argument("--threshold", type=int, default=64, help="fader value that switches a stop on")
    ap.add_argument("--hold", type=float, default=1.0, help="seconds a fader/knob readout stays before the normal display returns")
    ap.add_argument("--test-stop", type=int, help="send stop number N (1-52, see the bank table) on and exit")
    ap.add_argument("--test-off", action="store_true", help="with --test-stop: send off instead of on")
    ap.add_argument("--live", type=float, default=MIN_INTERVAL_S, help="minimum seconds between LCD writes while a fader moves (raise it if the LCD misbehaves)")
    ap.add_argument("--refresh", type=float, default=2.0, help="seconds between re-sending the normal display (0 = never)")
    ap.add_argument("--verbose", action="store_true", help="start with detailed MIDI debug messages enabled")
    ap.add_argument("--ui", choices=("textual", "simple", "none", "gui", "both"), default=None,
                    help="interface: textual, simple, gui, both, or none (default from config, otherwise textual)")
    ap.add_argument("--no-ui", action="store_true", help="disable the interactive console and print startup diagnostics only")
    ap.add_argument("--version", action="version", version=__version__)
    pre, _ = ap.parse_known_args()
    cfg_path = pre.config or default_config_path()
    cfg_defaults, raw = load_config(cfg_path)
    ap.set_defaults(**cfg_defaults)
    a = ap.parse_args()
    apply_layout(raw, cfg_path)
    apply_lcd_names(raw)
    br_settings = bridge_settings(raw)

    try:
        import mido
        mido.set_backend("mido.backends.rtmidi")
    except Exception as exc:
        print(f"MIDI backend could not start: {exc}", file=sys.stderr)
        print("Run Scripts\\install_requirements.bat and try again.", file=sys.stderr)
        return 1
    if a.list:
        print("INPUT ports :", *mido.get_input_names(), sep="\n  ")  # type: ignore[attr-defined]
        print("OUTPUT ports:", *mido.get_output_names(), sep="\n  ")  # type: ignore[attr-defined]
        return 0
    if a.learn_pads:
        learn_pads(mido, a.kl_main or "Ess Midi In")
        return 0
    if a.test_stop:
        it = ITEM_BY_CC[a.test_stop]
        with mido.open_output(find_port(mido.get_output_names(), a.go_out or a.go)) as port:  # type: ignore[attr-defined]
            port.send(mido.Message("control_change", channel=STOP_CH, control=it.cc, value=0 if a.test_off else 127))
        print(f"sent {'off' if a.test_off else 'on'} to {it.division} '{it.name}' ({it.path}), CC {it.cc} on channel {STOP_CH + 1}")
        return 0

    ui_mode = "none" if a.no_ui else (a.ui or "textual")
    ui = create_console_ui("textual" if ui_mode == "both" else "none" if ui_mode == "gui" else ui_mode)
    app = BridgeApp(mido, a, raw, br_settings, cfg_path, ui)
    try:
        import go_midi_setup
        note = go_midi_setup.refresh_if_stale()
        if note:
            print(note)
    except Exception as exc:
        print(f"GrandOrgue setup check skipped: {exc}")

    def stop_on_signal(_signum, _frame):
        raise KeyboardInterrupt

    for signal_name in ("SIGTERM", "SIGBREAK"):
        signal_number = getattr(signal, signal_name, None)
        if signal_number is not None:
            signal.signal(signal_number, stop_on_signal)
    try:
        if ui_mode in ("gui", "both"):
            try:
                from qt_gui import run_qt_ui
            except ImportError as exc:
                print(f"PySide6 GUI is unavailable: {exc}", file=sys.stderr)
                print("Install it with: python -m pip install PySide6", file=sys.stderr)
                return 1
            try:
                from keylab_bridge.go_launcher import start_grandorgue
                warning = start_grandorgue(app.active_organ_path)
                if warning:
                    print(f"GrandOrgue startup warning: {warning}", file=sys.stderr)
            except OSError as exc:
                print(f"GrandOrgue could not be started automatically: {exc}", file=sys.stderr)
            return run_qt_ui(app, ui)
        return app.run()
    finally:
        ui.close()
        if app.fatal:
            print("Console stopped with an error:\n" + app.fatal, file=sys.stderr)
        elif app.interrupted:
            print("Console stopped after Ctrl+C.")
        elif not ui.enabled:
            print("Console stopped cleanly.")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()          # the engraving worker is a spawned process: needed in the compiled program
    sys.exit(main())
