#!/usr/bin/env python3
"""
GrandOrgue -> Arturia KeyLab Essential mk2 LCD bridge.

GrandOrgue label (SYSEX Hauptwerk 32 Byte LCD Value, or 16 Byte String Value)
  --> virtual MIDI port (e.g. loopMIDI "GO2KeyLab")
  --> this script
  --> KeyLab display (2 lines x 16 characters)

Requires:  pip install mido python-rtmidi
Usage:
  python keylab_lcd_bridge.py --list
  python keylab_lcd_bridge.py --test "Nimrod (Elgar)" --out "KeyLab"     # no GrandOrgue needed
  python keylab_lcd_bridge.py --in "GO2KeyLab" --out "KeyLab"            # normal use

Frame formats (from the GrandOrgue and rjuang FL Studio script sources):
  GrandOrgue LCD    : F0 7D 01 <key hi> <key lo> <colour> <32 ASCII chars> F7
  GrandOrgue String : F0 7D 19 <key> <16 ASCII chars> F7
  KeyLab display    : F0 00 20 6B 7F 42 04 00 60 01 <16 chars> 00 02 <16 chars> 00 7F F7
"""
import argparse
import time

KEYLAB_HEADER = [0x00, 0x20, 0x6B, 0x7F, 0x42]
LINE_WIDTH = 16
MIN_INTERVAL_S = 0.05  # the KeyLab display can lock up if it is flooded


def ascii_clean(text):
    """Keep printable 7-bit ASCII only; fold common accented letters."""
    fold: dict[str, str] = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "é": "e", "è": "e", "ê": "e",
            "à": "a", "â": "a", "ç": "c", "î": "i", "ô": "o", "û": "u",
            "Ä": "A", "Ö": "O", "Ü": "U", "É": "E"}
    out = "".join(fold[c] if c in fold else c for c in text)
    return "".join(c if 32 <= ord(c) < 127 else " " for c in out)


def parse_go_sysex(data):
    """data = sysex bytes WITHOUT F0/F7 (as mido gives them). Returns text or None."""
    d = list(data)
    if len(d) >= 6 and d[0] == 0x7D and d[1] == 0x01:      # 32 byte LCD
        raw = d[5:37]
    elif len(d) >= 3 and d[0] == 0x7D and d[1] == 0x19:    # 16 byte string
        raw = d[3:19]
    else:
        return None
    return "".join(chr(b & 0x7F) for b in raw).strip()


def split_lines(text, width=LINE_WIDTH):
    """Split a title over two 16-char lines, breaking at a space where possible."""
    text = " ".join(ascii_clean(text).split())
    if len(text) <= width:
        return text, ""
    cut = text.rfind(" ", 0, width + 1)
    if cut <= 0:
        cut = width
    return text[:cut].strip(), text[cut:].strip()[:width]


def keylab_data(line1, line2, center=True):
    fit = (lambda s: s.center(LINE_WIDTH)) if center else (lambda s: s.ljust(LINE_WIDTH))
    body = [0x04, 0x00, 0x60, 0x01]
    body += [ord(c) for c in fit(line1)[:LINE_WIDTH]] + [0x00, 0x02]
    body += [ord(c) for c in fit(line2)[:LINE_WIDTH]] + [0x00, 0x7F]
    return KEYLAB_HEADER + body  # mido adds F0 / F7


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
    ap.add_argument("--in", dest="inp", help="part of the virtual port name GrandOrgue sends to")
    ap.add_argument("--out", help="part of the KeyLab output port name")
    ap.add_argument("--test", help="send this text to the KeyLab display and exit")
    ap.add_argument("--left", action="store_true", help="left-align instead of centering")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    import mido
    backend = mido.Backend("mido.backends.rtmidi")

    if a.list:
        print("INPUT ports :", *backend.get_input_names(), sep="\n  ")
        print("OUTPUT ports:", *backend.get_output_names(), sep="\n  ")
        return

    out_name = find_port(backend.get_output_names(), a.out)
    if out_name is None:
        raise SystemExit("Give --out with part of the KeyLab output port name (see --list).")

    with backend.open_output(out_name) as out:
        def show(text):
            l1, l2 = split_lines(text)
            out.send(mido.Message("sysex", data=keylab_data(l1, l2, center=not a.left)))
            print(f"KeyLab <- [{l1}] [{l2}]")

        if a.test is not None:
            show(a.test)
            return

        in_name = find_port(backend.get_input_names(), a.inp)
        if in_name is None:
            raise SystemExit("Give --in with part of the loopMIDI port name (see --list).")
        print(f"Listening on '{in_name}', writing to '{out_name}'. Ctrl+C to stop.")
        last, last_t = None, 0.0
        with backend.open_input(in_name) as inp:
            for msg in inp:
                if msg.type != "sysex":
                    continue
                text = parse_go_sysex(msg.data)
                if a.verbose:
                    print("GO sysex:", list(msg.data)[:8], "->", repr(text))
                if not text or text == last:
                    continue
                wait = MIN_INTERVAL_S - (time.time() - last_t)
                if wait > 0:
                    time.sleep(wait)
                show(text)
                last, last_t = text, time.time()


if __name__ == "__main__":
    main()
