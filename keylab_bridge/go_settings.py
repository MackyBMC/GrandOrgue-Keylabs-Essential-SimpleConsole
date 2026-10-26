"""Generate a GrandOrgue "MIDI Settings" yaml for the bridge, and compare one against a real export.

The format was taken from a real GrandOrgue v3.17.3-1 export of the Friesach organ: a list of objects, each with
a `path`, and `receive` / `send` lists of events. Only the channel-based entries the bridge itself uses are
generated. Device-specific bindings (e.g. a KeyLab wired straight to GrandOrgue) are the user's own and are
left alone, so the file is meant to be imported alongside them, never as a replacement for them.
"""
import datetime
import copy
import re

from .midi_protocol import CMD, CMD_CH, FB, FB_CH, VOL_CH
from .organ_layout import items_for_spec

GO_VERSION = "v3.17.3-1"

# (GrandOrgue object path, bridge command, feedback lamp the bridge reads back)
COMMAND_OBJECTS = (
    ("Sequencer/Prev", "prev_step", None), ("Sequencer/Next", "next_step", None),
    ("Sequencer/PrevFile", "prev_file", None), ("Sequencer/NextFile", "next_file", None),
    ("Sequencer/LoadFile", "load", "load_lit"), ("Sequencer/SaveFile", "save", None),
    ("Metronome/MetronomeOn", "metro", "metro_lit"),
    ("Metronome/MetronomeBpmP1", "tempo_up", None), ("Metronome/MetronomeBpmM1", "tempo_down", None),
    ("MidiPlayer/MidiPlayerPlay", "play", "play_lit"), ("MidiPlayer/MidiPlayerStop", "stop", None),
    ("MidiPlayer/MidiPlayerPause", "pause", "pause_lit"), ("Setter/PanicButton", "panic", None),
)


def _cc(channel0, key, high):
    return {"event_type": "ControlChange", "channel": channel0 + 1, "key": key, "low_value": 0, "high_value": high}


def build_go_settings(organ_name, spec, windchests=0, enclosures=0,
                     windchest_numbers=None, enclosure_numbers=None):
    objects = [{"path": "Sequencer/current file name",
                "send": [{"event_type": "HWLCD", "key": 1, "low_value": 0, "start": 0, "length": 32}]}]
    for path, command, lamp in COMMAND_OBJECTS:
        obj = {"path": path, "receive": [_cc(CMD_CH, CMD[command], 1)]}
        if lamp:
            obj["send"] = [_cc(FB_CH, FB[lamp], 127)]
        objects.append(obj)
    objects.append({"path": "volumes/Master", "receive": [_cc(VOL_CH, 1, 127)]})
    windchest_numbers = list(windchest_numbers or range(1, windchests + 1))
    enclosure_numbers = list(enclosure_numbers or range(1, enclosures + 1))
    volume_ccs = [index + 1 for index in range(len(windchest_numbers) + 1)] + [
        len(windchest_numbers) + int(number) + 1 for number in enclosure_numbers
    ]
    if any(channel_cc > 127 for channel_cc in volume_ccs):
        raise ValueError("the organ has more volume controls than GrandOrgue channel 12 can address")
    for index, number in enumerate(windchest_numbers, 1):
        objects.append({"path": f"volumes/Windchest{int(number):03d}", "receive": [_cc(VOL_CH, index + 1, 127)]})
    for number in enclosure_numbers:
        cc = len(windchest_numbers) + int(number) + 1
        objects.append({"path": f"enclosures/{int(number):03d}", "receive": [_cc(VOL_CH, cc, 127)]})
    for path, key in (("Sequencer/sequencer position", 2), ("Metronome/MetronomeBPM", 3)):
        objects.append({"path": path, "send": [{"event_type": "HWString", "key": key, "start": 0, "length": 16}]})
    for _kind, path, _number, _name, channel, key in items_for_spec(spec):
        if channel is None:                       # beyond the configured channels: never write an invented binding
            continue
        objects.append({"path": path, "receive": [_cc(channel, key, 127)], "send": [_cc(channel, key, 127)]})
    return {"info": {"content-type": "MIDI Settings", "organ-name": organ_name, "grandorgue-version": GO_VERSION,
                     "saved_time": datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")},
            "objects": objects}


def _generic(entries):
    """Entries without a `device` binding, as comparable tuples."""
    return sorted(tuple(sorted(e.items())) for e in (entries or []) if "device" not in e)


def compare_with_export(generated, export):
    """Compare a generated document with a real export. -> {"matched": n, "mismatches": [...], "export_only": [...]}.
    Only device-free entries count; `export_only` lists objects the export binds generically that we did not
    generate (they are yours, not the bridge's)."""
    theirs = {o["path"]: o for o in export.get("objects", [])}
    mismatches, matched = [], 0
    for obj in generated["objects"]:
        other = theirs.get(obj["path"])
        if other is None:
            mismatches.append(f"{obj['path']}: not in the export (organ has no such object, or a different path)")
            continue
        bad = [side for side in ("receive", "send") if _generic(obj.get(side)) != _generic(other.get(side))]
        if bad:
            mismatches.append(f"{obj['path']}: {'/'.join(bad)} differ")
        else:
            matched += 1
    ours = {o["path"] for o in generated["objects"]}
    export_only = [p for p, o in theirs.items()
                   if p not in ours and (_generic(o.get("receive")) or _generic(o.get("send")))]
    return {"matched": matched, "mismatches": mismatches, "export_only": export_only}


def merge_settings_export(export, generated):
    """Merge bridge routes into a GrandOrgue export without dropping user bindings."""
    if not isinstance(export.get("objects"), list):
        raise ValueError("GrandOrgue MIDI export must contain an objects list")
    merged = copy.deepcopy(export)
    objects = merged["objects"]
    objects_by_path = {item["path"]: item for item in objects if isinstance(item, dict) and item.get("path")}
    for generated_object in generated.get("objects", []):
        path = generated_object.get("path")
        if not path:
            continue
        target = objects_by_path.get(path)
        if target is None:
            target = {"path": path}
            objects.append(target)
            objects_by_path[path] = target
        for direction in ("receive", "send"):
            entries = target.setdefault(direction, [])
            for event in generated_object.get(direction, []) or []:
                if event not in entries:
                    entries.append(copy.deepcopy(event))
    generated_info = generated.get("info") or {}
    if isinstance(merged.get("info"), dict) and generated_info.get("organ-name"):
        merged["info"]["organ-name"] = generated_info["organ-name"]
    return merged


def windchest_count(export):
    return len([o for o in export.get("objects", []) if re.fullmatch(r"volumes/Windchest\d{3}", o["path"])])
