#!/usr/bin/env python3
"""
GrandOrgue -> Arturia KeyLab Essential mk2 LCD bridge  (v2)

  GrandOrgue file-name label (SYSEX Hauptwerk 32 Byte LCD Value) --+
  GrandOrgue "Load file" button state (a CC, see --cue-cc) --------+--> LoopBe1
                                                                        |
                                                              this script
                                                                        |
                                                             KeyLab LCD (2 x 16)

Display:
  active registration :   " Nimrod (Elgar) "
  cued, not yet loaded:   ">Nimrod (Elgar)<"   (line 2 shows "-- cued --" if empty)

Revert: when a fader/knob overwrites the LCD, the registration name is put back
  * with --watch  : a few seconds after you stop touching the controls (--revert)
  * without it    : every --refresh seconds (simple fallback)

Requires:  pip install mido python-rtmidi

Examples
  python keylab_lcd_bridge.py --list
  python keylab_lcd_bridge.py --test "Nimrod (Elgar)" --out "KeyLab"
  python keylab_lcd_bridge.py --test "Nimrod (Elgar)" --cued --out "KeyLab"
  python keylab_lcd_bridge.py --in "LoopBe" --out "KeyLab" --cue-cc 20 --watch "KeyLab"

Frame formats (GrandOrgue source / rjuang FL Studio script):
  GrandOrgue LCD    : F0 7D 01 <key hi> <key lo> <colour> <32 ASCII> F7
  GrandOrgue String : F0 7D 19 <key> <16 ASCII> F7
  KeyLab display    : F0 00 20 6B 7F 42 04 00 60 01 <16> 00 02 <16> 00 7F F7
"""
import argparse
import time

KEYLAB_HEADER = [0x00, 0x20, 0x6B, 0x7F, 0x42]
LINE_WIDTH = 16
INNER = LINE_WIDTH - 2          # text width; one column each side is kept for the cue marks
MIN_INTERVAL_S = 0.05           # the KeyLab display can lock up if it is flooded
SUSTAIN_CC = 64


def ascii_clean(text):
    fold = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "é": "e", "è": "e", "ê": "e",
            "à": "a", "â": "a", "ç": "c", "î": "i", "ô": "o", "û": "u",
            "Ä": "A", "Ö": "O", "Ü": "U", "É": "E"}
    out = "".join(fold.get(c, c) for c in text)
    return "".join(c if 32 <= ord(c) < 127 else " " for c in out)


def parse_go_sysex(data):
    """data = sysex bytes without F0/F7. Returns the label text or None."""
    d = list(data)
    if len(d) >= 6 and d[0] == 0x7D and d[1] == 0x01:      # 32 byte LCD
        raw = d[5:37]
    elif len(d) >= 3 and d[0] == 0x7D and d[1] == 0x19:    # 16 byte string
        raw = d[3:19]
    else:
        return None
    return "".join(chr(b & 0x7F) for b in raw).strip()


def split_lines(text, width):
    text = " ".join(ascii_clean(text).split())
    if len(text) <= width:
        return text, ""
    cut = text.rfind(" ", 0, width + 1)
    if cut <= 0:
        cut = width
    return text[:cut].strip(), text[cut:].strip()[:width]


def layout(text, cued):
    """Return the two 16-character lines for the KeyLab."""
    l1, l2 = split_lines(text, INNER)
    if cued and not l2:
        l2 = "-- cued --"

    def deco(s):
        body = s.center(INNER)
        return (">" + body + "<") if (cued and s) else (" " + body + " ")

    return deco(l1), deco(l2)


def keylab_data(line1, line2):
    """SysEx body (without F0/F7) for the KeyLab display."""
    body = [0x04, 0x00, 0x60, 0x01]
    body += [ord(c) for c in line1.ljust(LINE_WIDTH)[:LINE_WIDTH]] + [0x00, 0x02]
    body += [ord(c) for c in line2.ljust(LINE_WIDTH)[:LINE_WIDTH]] + [0x00, 0x7F]
    return KEYLAB_HEADER + body


class Bridge:
    """All the logic, with no MIDI library needed (so it can be tested offline)."""

    def __init__(self, cue_cc=None, cue_note=None, cue_channel=None,
                 revert_s=3.0, refresh_s=5.0, watching=False):
        self.cue_cc, self.cue_note, self.cue_channel = cue_cc, cue_note, cue_channel
        self.revert_s, self.refresh_s, self.watching = revert_s, refresh_s, watching
        self.text, self.cued = "", False
        self.dirty = False
        self.last_send = 0.0
        self.last_activity = None       # time of the last fader/knob movement
        self.log = None

    # -- messages from GrandOrgue (via LoopBe) -------------------------------
    def from_go(self, msg):
        if msg.type == "sysex":
            t = parse_go_sysex(msg.data)
            if t is not None and t != "":
                self.text, self.dirty = t, True
            return
        if self.cue_channel is not None and getattr(msg, "channel", None) != self.cue_channel:
            return
        if msg.type == "control_change" and self.cue_cc is not None and msg.control == self.cue_cc:
            self.cued, self.dirty = msg.value >= 64, True
        elif self.cue_note is not None and msg.type in ("note_on", "note_off") and msg.note == self.cue_note:
            on = msg.type == "note_on" and msg.velocity > 0
            self.cued, self.dirty = on, True

    # -- messages from the keyboard itself (optional --watch) ----------------
    def from_keyboard(self, msg, now):
        if msg.type == "control_change":
            if msg.control == SUSTAIN_CC or msg.control == self.cue_cc:
                return
            self.last_activity = now
        elif msg.type in ("pitchwheel", "aftertouch"):
            self.last_activity = now

    # -- called about every 10 ms -----------------------------------------
    def tick(self, now):
        """Return SysEx body to send, or None."""
        if not self.text:
            return None
        if self.last_activity is not None:
            if now - self.last_activity >= self.revert_s:
                self.last_activity, self.dirty = None, True   # controls are quiet: put the name back
            else:
                return None                                   # still moving a fader: leave the LCD alone
        elif not self.watching and self.refresh_s and now - self.last_send >= self.refresh_s:
            self.dirty = True
        if self.dirty and now - self.last_send >= MIN_INTERVAL_S:
            self.dirty, self.last_send = False, now
            return keylab_data(*layout(self.text, self.cued))
        return None


def find_port(names, wanted):
    if wanted is None:
        return None
    for n in names:
        if wanted.lower() in n.lower():
            return n
    raise SystemExit(f"No MIDI port containing '{wanted}'. Use --list to see the names.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list MIDI ports and exit")
    ap.add_argument("--in", dest="inp", help="part of the LoopBe input port name")
    ap.add_argument("--out", help="part of the KeyLab OUTPUT port name")
    ap.add_argument("--test", help="send this text to the KeyLab display and exit")
    ap.add_argument("--cued", action="store_true", help="with --test: show the cued layout")
    ap.add_argument("--cue-cc", type=int, help="CC number the Load-file button sends (127 = cued, 0 = loaded)")
    ap.add_argument("--cue-note", type=int, help="or: note number the Load-file button sends")
    ap.add_argument("--cue-channel", type=int, help="MIDI channel 1-16 of the cue message (default: any)")
    ap.add_argument("--watch", help="part of the KeyLab INPUT port name, to see when faders move (optional)")
    ap.add_argument("--revert", type=float, default=3.0, help="seconds of quiet before the name is restored (with --watch)")
    ap.add_argument("--refresh", type=float, default=5.0, help="re-send interval without --watch (0 = off)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    import mido
    mido.set_backend("mido.backends.rtmidi")

    if a.list:
        print("INPUT ports :", *mido.get_input_names(), sep="\n  ")
        print("OUTPUT ports:", *mido.get_output_names(), sep="\n  ")
        return

    out_name = find_port(mido.get_output_names(), a.out)
    if out_name is None:
        raise SystemExit("Give --out with part of the KeyLab output port name (see --list).")

    with mido.open_output(out_name) as out:
        if a.test is not None:
            l1, l2 = layout(a.test, a.cued)
            out.send(mido.Message("sysex", data=keylab_data(l1, l2)))
            print(f"KeyLab <- [{l1}] [{l2}]")
            return

        in_name = find_port(mido.get_input_names(), a.inp)
        if in_name is None:
            raise SystemExit("Give --in with part of the LoopBe port name (see --list).")

        watch_port = None
        if a.watch:
            try:
                watch_port = mido.open_input(find_port(mido.get_input_names(), a.watch))
            except Exception as e:  # port busy (GrandOrgue has it) or not found
                print(f"Could not watch the keyboard ({e}); using periodic refresh every {a.refresh}s instead.")

        br = Bridge(cue_cc=a.cue_cc, cue_note=a.cue_note,
                    cue_channel=(a.cue_channel - 1) if a.cue_channel else None,
                    revert_s=a.revert, refresh_s=a.refresh, watching=watch_port is not None)
        print(f"Listening on '{in_name}', writing to '{out_name}'"
              + (", watching keyboard controls" if watch_port else "") + ". Ctrl+C to stop.")
        if a.cue_cc is None and a.cue_note is None:
            print("Note: no --cue-cc given, so the '>' cue marker is off.")

        with mido.open_input(in_name) as inp:
            try:
                while True:
                    now = time.time()
                    for m in inp.iter_pending():
                        if a.verbose:
                            print("from GO:", m)
                        br.from_go(m)
                    if watch_port:
                        for m in watch_port.iter_pending():
                            br.from_keyboard(m, now)
                    data = br.tick(now)
                    if data:
                        out.send(mido.Message("sysex", data=data))
                        l1, l2 = layout(br.text, br.cued)
                        print(f"KeyLab <- [{l1}] [{l2}]")
                    time.sleep(0.01)
            except KeyboardInterrupt:
                pass
        if watch_port:
            watch_port.close()


if __name__ == "__main__":
    main()
