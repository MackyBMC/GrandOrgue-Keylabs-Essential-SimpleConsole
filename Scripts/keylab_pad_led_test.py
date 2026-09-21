#!/usr/bin/env python3
"""
Try colours on the 8 KeyLab Essential pads, so we know how to show stop states on them.

  python keylab_pad_led_test.py --out "KeyLab"               # mode "triple": 3 single LEDs per pad (R, G, B)
  python keylab_pad_led_test.py --out "KeyLab" --mode rgb    # the RGB command (rjuang notes it may not work)
  python keylab_pad_led_test.py --out "KeyLab" --mode mono   # one brightness value per pad

Each pad is shown red, green, blue, yellow, then off, one after another. Tell me which pads light and in what colours.
Try the other --out port ("DAW") if nothing lights.  Requires: pip install mido python-rtmidi
"""
import argparse
import time

HEADER = [0x00, 0x20, 0x6B, 0x7F, 0x42]
PADS = [32, 35, 38, 41, 44, 47, 50, 53]          # first LED id of each pad (from rjuang's script, Essential)
COLOURS = [("red", (127, 0, 0)), ("green", (0, 127, 0)), ("blue", (0, 0, 127)), ("yellow", (127, 100, 0)), ("off", (0, 0, 0))]


def frames(mode, base, rgb):
    r, g, b = rgb
    if mode == "rgb":
        return [HEADER + [0x02, 0x00, 0x16, base, r, g, b]]
    if mode == "mono":
        return [HEADER + [0x02, 0x00, 0x10, base, max(rgb)]]
    return [HEADER + [0x02, 0x00, 0x10, base + i, v] for i, v in enumerate((r, g, b))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="KeyLab")
    ap.add_argument("--mode", choices=["triple", "rgb", "mono"], default="triple")
    ap.add_argument("--pause", type=float, default=1.2)
    a = ap.parse_args()
    import mido
    mido.set_backend("mido.backends.rtmidi")
    output_names = mido.get_output_names()  # type: ignore[attr-defined]
    name = next((n for n in output_names if a.out.lower() in n.lower()), None)
    if not name:
        raise SystemExit("No output port matches; names: " + ", ".join(output_names))
    with mido.open_output(name) as port:  # type: ignore[attr-defined]
        print(f"Using '{name}', mode {a.mode}")
        for label, rgb in COLOURS:
            print(f"all pads: {label}")
            for base in PADS:
                for f in frames(a.mode, base, rgb):
                    port.send(mido.Message("sysex", data=f))
                    time.sleep(0.04)
            time.sleep(a.pause)


if __name__ == "__main__":
    main()
