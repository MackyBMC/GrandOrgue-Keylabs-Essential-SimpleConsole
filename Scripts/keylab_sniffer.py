#!/usr/bin/env python3
"""
KeyLab Essential sniffer: opens every KeyLab input port at once and prints each
message with the PORT it arrived on and, where known, the control's name.
Anything not yet mapped is flagged UNKNOWN, so press the DAW Command Center
buttons, pads, transport keys, Live/Bank etc. one at a time and paste the output.

Requires:  pip install mido python-rtmidi
Usage:
  python keylab_sniffer.py --list
  python keylab_sniffer.py                      # all ports containing "KeyLab"
  python keylab_sniffer.py --filter "Ess" --log capture.csv

Known controls come from captures of the KeyLab Essential 61 mk2 in DAW mode. The DAW port
speaks Mackie-Control-style messages; relative values: 0x01 = clockwise, 0x41 = counter-clockwise.
"""
import argparse
import time

# --- DAW port: Mackie Control style notes (channel 1) ------------------------------
DAW_NOTES = {
    0x50: "Save", 0x51: "Undo", 0x56: "Loop", 0x57: "Punch (in)", 0x58: "Punch (out)", 0x59: "Metro",
    0x5B: "<< Rewind", 0x5C: ">> Forward", 0x5D: "Stop", 0x5E: "Play/Pause", 0x5F: "Record",
    0x62: "Nav left (<-)", 0x63: "Nav right (->)", 0x64: "Preset", 0x65: "Cat/Char",
    0x2E: "Part 2 / Prev (bank mode?)", 0x2F: "Part 1 / Next (bank mode?)",
    0x30: "Part 2 / Prev", 0x31: "Part 1 / Next",
}
# --- MAIN port: Arturia sysex F0 00 20 6B 7F 42 02 00 00 <id> <val> F7 --------------
MAIN_BUTTONS = {
    0x10: "Oct -", 0x11: "Oct +", 0x12: "Chord", 0x13: "Trans", 0x14: "MIDI CH",
    0x15: "Map Select", 0x16: "Cat/Char", 0x17: "Preset", 0x18: "Nav left (<-)", 0x19: "Nav right (->)",
}
# --- MAIN port: pads send CC 0x24-0x2B (observed; pads 4 and 5 both gave 0x28 - retest) ---
PADS = {0x24: "Pad 1 (Analog Lab)", 0x26: "Pad 2 (DAW)?", 0x27: "Pad 3 (User 1)?", 0x28: "Pad 4/5 (User 2 / User 3)?",
        0x29: "Pad 6 (User 4)", 0x2A: "Pad 7 (User 5)", 0x2B: "Pad 8 (User 6)"}


def rel(v):
    """Mackie relative value: bit 6 = direction, low 6 bits = size."""
    return f"{'right' if v < 64 else 'left'} x{v & 0x3F}"


def describe(msg):
    """Return a human name for a message, or None if not known yet."""
    t = msg.type
    if t in ("note_on", "note_off"):
        name = DAW_NOTES.get(msg.note) if msg.channel == 0 else None
        if name:
            down = t == "note_on" and msg.velocity > 0
            return f"BUTTON {name} {'down' if down else 'up'}"
    elif t == "control_change":
        c, v = msg.control, msg.value
        if c == 0x3C:
            return f"JOG {rel(v)}"
        if 0x10 <= c <= 0x17:
            return f"ENCODER {c - 0x0F} {rel(v)}"
        if c == 0x01:
            return f"MOD WHEEL = {v}"
        if c == 0x40:
            return f"SUSTAIN PEDAL {'down' if v >= 64 else 'up'}"
        if c in PADS:
            return f"{PADS[c]} {'down' if v >= 64 else 'up'}"
    elif t == "pitchwheel":
        n = msg.channel + 1
        pos = (msg.pitch + 8192) >> 7  # this keyboard only uses the high 7 bits
        return ("MASTER FADER" if n == 9 else f"FADER {n}") + f" = {pos}"
    elif t == "sysex":
        d = list(msg.data)
        if d[:8] == [0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00, 0x00] and len(d) >= 10:
            name = MAIN_BUTTONS.get(d[8])
            if name:
                return f"PANEL BUTTON {name} {'down' if d[9] else 'up'}"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--filter", default="KeyLab", help="only ports whose name contains this")
    ap.add_argument("--log", help="also write a CSV of everything")
    ap.add_argument("--fader-gap", type=float, default=0.25, help="seconds between printed fader updates")
    a = ap.parse_args()

    import mido
    mido.set_backend("mido.backends.rtmidi")
    names = [n for n in mido.get_input_names()  # type: ignore[attr-defined]
             if a.filter.lower() in n.lower()]
    if a.list or not names:
        print("INPUT ports:", *mido.get_input_names(), sep="\n  ")  # type: ignore[attr-defined]
        return

    logf = open(a.log, "w", encoding="utf-8") if a.log else None
    if logf:
        logf.write("time,port,raw,meaning\n")
    t0 = time.time()
    last_fader = {}

    def make_cb(tag):
        def cb(msg):
            now = time.time() - t0
            meaning = describe(msg)
            raw = " ".join(f"{b:02X}" for b in msg.bytes())
            if logf:
                logf.write(f"{now:.3f},{tag},{raw},{meaning or 'UNKNOWN'}\n")
            if msg.type == "pitchwheel":                      # throttle the fader flood
                key = (tag, msg.channel)
                if now - last_fader.get(key, -9) < a.fader_gap:
                    return
                last_fader[key] = now
            print(f"[{tag:>4}] {raw:<12} {meaning or 'UNKNOWN  <-- new control?'}")
        return cb

    ports = []
    for n in names:
        tag = "DAW" if "DAW" in n.upper() else "MAIN"
        try:
            # open_input is provided dynamically by mido's selected backend.
            ports.append(mido.open_input(n, callback=make_cb(tag)))  # type: ignore[attr-defined]
            print(f"Opened [{tag}] {n}")
        except Exception as e:
            print(f"Could not open {n}: {e}  (another program has it?)")
    print("Listening. Press controls one at a time. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    for p in ports:
        p.close()
    if logf:
        logf.close()


if __name__ == "__main__":
    main()
