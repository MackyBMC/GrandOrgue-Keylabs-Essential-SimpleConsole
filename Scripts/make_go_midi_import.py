#!/usr/bin/env python3
"""Merge the KeyLab bridge assignments into a GrandOrgue MIDI Settings export.

  python make_go_midi_import.py Friesach-midi-settings.yaml Friesach-midi-settings-KeyLab.yaml

Also moves the sustain pedal (CC 64, main port) from Sequencer/Next to Sequencer/LoadFile.

Your existing assignments are kept (GrandOrgue's import clears every object that is not in the
file), and the bridge's receive/send events are added.  Events have no device, i.e. "any device";
they use channels 14-16, which the KeyLab never sends on.
"""
import sys
import yaml
import keylab_go_bridge as kb


def cc_event(ch0, cc, low, high):
    return {"event_type": "ControlChange", "channel": ch0 + 1, "key": cc, "low_value": low, "high_value": high}


def main(src, dst):
    doc = yaml.safe_load(open(src, encoding="utf-8"))
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
        for path in [it.path] + it.extra_paths:
            o = obj(path)
            o.setdefault("receive", []).append(cc_event(kb.STOP_CH, it.cc, 0, 127))
            o.setdefault("send", []).append(cc_event(kb.STOP_CH, it.cc, 0, 127))

    # volume levels: bridge -> GrandOrgue (master fader and encoders 1-4); no feedback, to avoid echoes
    for key, (cc, path, _name) in kb.VOLS.items():
        obj(path).setdefault("receive", []).append(cc_event(kb.VOL_CH, cc, 0, 127))
    # sustain pedal (CC 64 on the KeyLab main port) loads the cued file instead of stepping
    nxt = obj("Sequencer/Next")
    pedal = [e for e in nxt.get("receive", []) if e.get("key") == 64 and e.get("event_type") == "ControlChange"]
    if pedal:
        nxt["receive"] = [e for e in nxt["receive"] if e not in pedal]
        obj("Sequencer/LoadFile").setdefault("receive", []).extend(pedal)

    doc["objects"] = list(objs.values())
    with open(dst, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    print(f"{len(doc['objects'])} objects written to {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
