#!/usr/bin/env python3
"""Merge the KeyLab bridge assignments into a GrandOrgue MIDI Settings export.

  python make_go_midi_import.py Friesach-midi-settings.yaml Friesach-midi-settings-KeyLab.yaml

The bridge handles the sustain pedal (CC 64, main port) conditionally, so it is removed from
GrandOrgue's direct Sequencer/Next and Sequencer/LoadFile assignments.

Your existing assignments are kept (GrandOrgue's import clears every object that is not in the
file), and the bridge's receive/send events are added.  Events have no device, i.e. "any device";
they use channels 14-16, which the KeyLab never sends on.
"""
import sys
import yaml
import keylab_go_bridge as kb
from keylab_bridge.organ_layout import STOP_CHANNELS


def cc_event(ch0, cc, low, high):
    return {"event_type": "ControlChange", "channel": ch0 + 1, "key": cc, "low_value": low, "high_value": high}


def main(src, dst):
    doc = yaml.safe_load(open(src, encoding="utf-8"))
    # Remove every earlier bridge assignment first. The bridge owns these channels (commands 16, stops 15 plus any
    # spill channels, feedback 14, volumes 12). Leftover events from an older layout would keep answering to the
    # old CC numbers, and show up as "ghost" stops (a CC switching an object that is not on the panel).
    owned = {kb.CMD_CH + 1, kb.FB_CH + 1, kb.VOL_CH + 1, *[c for c in STOP_CHANNELS], kb.STOP_CH + 1}
    removed = 0
    for entry in doc["objects"]:
        for direction in ("receive", "send"):
            events = entry.get(direction)
            if not events:
                continue
            kept = [e for e in events if not (e.get("event_type") == "ControlChange" and e.get("channel") in owned)]
            removed += len(events) - len(kept)
            if kept:
                entry[direction] = kept
            else:
                entry.pop(direction)
    doc["objects"] = [o for o in doc["objects"] if len(o) > 1 or "path" not in o or o.get("name")]
    print(f"removed {removed} earlier bridge CC assignments on channels {sorted(owned)}")
    objs = {o["path"]: o for o in doc["objects"]}

    def obj(path):
        if path not in objs:
            objs[path] = {"path": path}
        return objs[path]

    # commands: bridge -> GrandOrgue (push buttons: 127 = press, 0 = release)
    for name, cc in kb.CMD.items():
        obj(kb.CMD_PATHS[name]).setdefault("receive", []).append(cc_event(kb.CMD_CH, cc, 0, 1))
    # feedback: GrandOrgue -> bridge (button lit state)
    for name, cc in kb.FB.items():
        obj(kb.FB_PATHS[name]).setdefault("send", []).append(cc_event(kb.FB_CH, cc, 0, 127))
    # step number label -> bridge (16 byte string, key 2)
    obj(kb.POSITION_LABEL_PATH).setdefault("send", []).append(
        {"event_type": "HWString", "key": kb.POSITION_LABEL_KEY, "start": 0, "length": 16})
    # drawbars: every stop, coupler and tremulant is set by CC (127 on / 0 off) and reports its state back
    for it in kb.ITEMS:
        o = obj(it.path)
        o.setdefault("receive", []).append(cc_event(kb.STOP_CH, it.cc, 0, 127))
        o.setdefault("send", []).append(cc_event(kb.STOP_CH, it.cc, 0, 127))

    # volume levels: bridge -> GrandOrgue (master fader and encoders 1-4); no feedback, to avoid echoes
    for key, (cc, path, _name) in kb.VOLS.items():
        obj(path).setdefault("receive", []).append(cc_event(kb.VOL_CH, cc, 0, 127))
    # The bridge chooses whether the sustain pedal loads a cued file or advances a piece.
    for path in ("Sequencer/Next", "Sequencer/LoadFile"):
        target = obj(path)
        target["receive"] = [event for event in target.get("receive", [])
                             if not (event.get("key") == kb.CC_SUSTAIN and
                                     event.get("event_type") == "ControlChange")]

    # manuals for MIDI-file sessions: each manual also listens (any device) on its own channel, all keys, so a recorded
    # session written by the stave editor reaches Pedal / Hauptwerk / Schwellwerk / Solowerk (see midi_stave/sessionmeta.py)
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "midi_stave"))
    import sessionmeta
    channels = {ch for _n, _p, ch in sessionmeta.manual_channels()}
    for entry in objs.values():                                  # drop an earlier run's manual-channel events
        events = entry.get("receive")
        if events:
            entry["receive"] = [e for e in events if not (e.get("event_type") == "Note" and "device" not in e
                                                          and e.get("channel") in channels)]
            if not entry["receive"]:
                entry.pop("receive")
    for name, path, ch in sessionmeta.manual_channels():
        obj(path).setdefault("receive", []).append(
            {"event_type": "Note", "channel": ch, "transpose": 0, "low_key": 0, "high_key": 127,
             "low_value": 1, "high_value": 127})
        print(f"{name}: MIDI channel {ch}")
    doc["objects"] = list(objs.values())
    with open(dst, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    print(f"{len(doc['objects'])} objects written to {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
