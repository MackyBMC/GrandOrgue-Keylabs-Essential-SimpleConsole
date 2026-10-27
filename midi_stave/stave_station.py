"""Stave editor without the bridge and without the KeyLab: edit MIDI / MusicXML and hear it on GrandOrgue.

Only GrandOrgue's virtual MIDI input (the bridge's output port, e.g. Bridge2GO from config.yaml) is opened. No controller,
no bridge, no setter list needed. Notes, manual channels, tempo-independent step play and the playhead all work; setter /
registration markers in a file are NOT applied here (that needs the bridge) - the status bar says so when a file has any.

CHANGELOG
2026-10-23  New: stave editor + playback to GrandOrgue without the bridge or a MIDI controller.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.dirname(HERE))


def open_go_port():
    """Open GrandOrgue's input (the cable the bridge normally writes to). Returns (port or None, message)."""
    try:
        import mido
        import yaml
        with open(os.path.join(os.path.dirname(HERE), "config.yaml"), encoding="utf-8") as handle:
            ports = (yaml.safe_load(handle) or {}).get("ports") or {}
        wanted = str(ports.get("go_out") or ports.get("go") or "")
        names = mido.get_output_names()
        match = next((n for n in names if wanted and wanted.casefold() in n.casefold()), None)
        if match is None:
            return None, f"No MIDI output matching '{wanted}'. Available: {', '.join(names) or 'none'}. Editing works; playback is off."
        return mido.open_output(match), f"Playing to {match}"
    except Exception as exc:
        return None, f"MIDI playback is off ({exc}). Editing works."


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWidgets import QStyleFactory
    app = QApplication(sys.argv)
    import render
    render.init_verovio()
    import midi_stave
    from keylab_bridge.take_recorder import TakePlayer
    window = midi_stave.Stave()
    port, message = open_go_port()
    if port is not None:
        player = TakePlayer(port.send)
        window.play_hook = lambda path, offset=0.0: player.start(path, offset=offset)
        window.seek_hook = player.seek
        window.stop_hook = player.stop
        window.pos_hook = player.position
        window.chord_hook = player.chord
        window.gate_hook = player.gate
        app.aboutToQuit.connect(lambda: (player.stop(), port.close()))
    try:                                        # global theme shared with the console (Appearance settings)
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import themes
        themes.apply(None, app)
        window.apply_theme(themes.tokens(), "")
        themes.bus.changed.connect(lambda: window.apply_theme(themes.tokens(), ""))
    except Exception:
        pass
    window.show()
    window.statusBar().showMessage(message)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.load(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
