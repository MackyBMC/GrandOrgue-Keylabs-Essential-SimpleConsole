"""Organ-session metadata stored INSIDE a MIDI file, shared by the bridge (records / plays) and the stave editor.

A setter change is a standard MIDI 'marker' meta event with the text   SETTER|<setter file>|<step id>|<name>
for example  SETTER|Friesach Advent.yaml|003|Tutti  : the stop combination (setter file + step 000-0xx) the organist
had active from that moment. Other MIDI software ignores markers, so the file stays a normal MIDI file.
Channels: each stave can be written on its own MIDI channel so GrandOrgue sends it to the intended manual.
Channel remap sidecar (bridge): <file>.chmap.json = {"source channel 1-16": target channel 1-16}.
"""
import json
import os

PREFIX = "SETTER"


def format_marker(filename, internal_id, name=""):
    return "|".join((PREFIX, str(filename), str(internal_id), str(name).replace("|", "/")))


def parse_marker(text):
    """-> (filename, internal_id, name) or None when the marker is not a setter change."""
    parts = str(text).split("|")
    if len(parts) >= 3 and parts[0] == PREFIX:
        return parts[1], parts[2], "|".join(parts[3:])
    return None


def format_reg(manual, filename, internal_id, name=""):
    """Voice registration: take the stops of this manual from that setter (file + step)."""
    return "|".join(("REG", manual, str(filename), str(internal_id), str(name).replace("|", "/")))


def parse_reg(text):
    parts = str(text).split("|")
    if len(parts) >= 4 and parts[0] == "REG":
        return parts[1], parts[2], parts[3], "|".join(parts[4:])
    return None


def format_stops(manual, paths, label=""):
    """Voice registration by individual stops: this manual's stops are exactly these GrandOrgue switch paths."""
    return "|".join(("STOPS", manual, ";".join(paths), str(label).replace("|", "/")))


def parse_stops(text):
    parts = str(text).split("|")
    if len(parts) >= 3 and parts[0] == "STOPS":
        return parts[1], [p for p in parts[2].split(";") if p], "|".join(parts[3:])
    return None


def load_stops():
    """Every stop of the organ as the bridge knows it: [{"manual": 0-3, "division", "name", "path"}]."""
    try:
        from keylab_bridge.organ_layout import ITEMS
        return [{"manual": it.manual, "division": getattr(it, "bank_code", ""), "name": it.name, "path": it.path}
                for it in ITEMS if it.kind == "stop"]
    except Exception:
        return []


def read_all_markers(path):
    """Every marker text of a file: [(seconds, text)]."""
    import mido
    found, now = [], 0.0
    try:
        for msg in mido.MidiFile(path):
            now += msg.time
            if msg.type == "marker":
                found.append((now, msg.text))
    except Exception:
        pass
    return found


def read_markers(path):
    """Setter markers of a MIDI file: [(seconds, filename, internal_id, name)] in time order."""
    import mido
    found, now = [], 0.0
    try:
        for msg in mido.MidiFile(path):
            now += msg.time
            if msg.type == "marker":
                parsed = parse_marker(msg.text)
                if parsed:
                    found.append((now, *parsed))
    except Exception:
        pass
    return found


def load_combos(scripts_dir=None):
    """Existing setter combinations as the bridge sees them: [{"name","filename","internal_id"}] (file + step 000-0xx)."""
    try:
        import yaml
        from keylab_bridge.preset_store import load_combinations
        scripts_dir = scripts_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config = os.path.join(scripts_dir, "config.yaml")
        with open(config, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        return [{"name": c["name"], "filename": c["filename"], "internal_id": c["internal_id"],
                 "switch_paths": sorted(c.get("switch_paths", ()))}
                for c in load_combinations(config, raw)]
    except Exception:
        return []


def channel_map(path):
    try:
        with open(path + ".chmap.json", encoding="utf-8") as handle:
            return {int(k) - 1: int(v) - 1 for k, v in json.load(handle).items()}
    except (OSError, ValueError):
        return {}


def save_channel_map(path, mapping):
    """mapping: {source 0-15: target 0-15}; identity entries are dropped."""
    data = {str(k + 1): v + 1 for k, v in mapping.items() if k != v}
    sidecar = path + ".chmap.json"
    if data:
        with open(sidecar, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    elif os.path.isfile(sidecar):
        os.remove(sidecar)


def channels_in(path):
    import mido
    try:
        return sorted({m.channel for m in mido.MidiFile(path) if m.type in ("note_on", "note_off")})
    except Exception:
        return []


# ---------------------------------------------------------------- manuals <-> MIDI channels
# Each GrandOrgue manual listens on its own MIDI channel for sessions played from a file (make_go_midi_import.py adds
# these Note receive events, any device). Override in config.yaml:  manual_channels: {Pedal: 2, Hauptwerk: 3, ...}
MANUALS = [("Pedal", "manuals/000", 2), ("Hauptwerk", "manuals/001", 3),
           ("Schwellwerk", "manuals/002", 4), ("Solowerk", "manuals/003", 5)]
MANUAL_SHORT = {"Pedal": "P", "Hauptwerk": "H", "Schwellwerk": "Sc", "Solowerk": "S"}


def manual_channels(scripts_dir=None):
    """[(name, GO object path, channel 1-16)] with any override from config.yaml."""
    result = list(MANUALS)
    try:
        import yaml
        scripts_dir = scripts_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(scripts_dir, "config.yaml"), encoding="utf-8") as handle:
            override = (yaml.safe_load(handle) or {}).get("manual_channels") or {}
        result = [(n, path, int(override.get(n, ch))) for n, path, ch in MANUALS]
    except Exception:
        pass
    return result


# ---------------------------------------------------------------- what a file says its tracks are -> manuals / stops
# Hauptwerk = the main voice (choir / melody / piano / organ), Schwellwerk = strings, ensemble, pads, Solowerk = brass,
# reeds, woodwind, leads, Pedal = bass instruments (and anything sitting low). Matches track names first, then GM program.
_NAME_RULES = [
    (("soprano", "alto", "tenor", "choir", "chor", "voice", "vocal", "sop.", "satb", "vox", "melody", "lead vocal"),
     ("Hauptwerk",), ("Principal", "Octave")),
    (("bass", "contrabass", "double bass", "tuba", "bassoon", "fagott", "cello", "basso", "continuo"), ("Pedal",), ("Subbass", "Bourdon", "Posaune")),
    (("trumpet", "trompete", "trombone", "horn", "brass", "cornet", "clarion"), ("Solowerk",), ("Trompete", "Trumpet", "Posaune", "Horn")),
    (("oboe", "clarinet", "sax", "reed", "krummhorn", "shawm"), ("Solowerk",), ("Oboe", "Krummhorn", "Schalmei")),
    (("flute", "flöte", "flote", "piccolo", "recorder", "pipe"), ("Solowerk",), ("Flöte", "Flote", "Gedackt", "Piccolo")),
    (("violin", "viola", "string", "strings", "pad", "ensemble", "harp", "guitar"), ("Schwellwerk",), ("Gambe", "Viola", "Salicional", "Voix")),
    (("organ", "piano", "keyboard", "harpsichord", "clavier"), ("Hauptwerk",), ("Principal", "Oktave")),
]


def _program_family(program):
    if program is None:
        return None
    if 32 <= program <= 39 or program in (42, 43, 58, 70):
        return ("Pedal",), ("Subbass", "Bourdon", "Posaune")
    if 52 <= program <= 54 or program in (85, 91):
        return ("Hauptwerk",), ("Principal", "Octave")
    if 40 <= program <= 55 or 88 <= program <= 95 or 104 <= program <= 111 or 24 <= program <= 31:
        return ("Schwellwerk",), ("Gambe", "Viola", "Salicional")
    if 56 <= program <= 63:
        return ("Solowerk",), ("Trompete", "Posaune", "Horn")
    if 64 <= program <= 79 or 80 <= program <= 87:
        return ("Solowerk",), ("Oboe", "Flöte", "Krummhorn")
    if 0 <= program <= 23:
        return ("Hauptwerk",), ("Principal", "Oktave")
    return None


def suggest(name="", program=None, median=60):
    """-> (manual names, stop name hints, why) for a track from its name / GM program / typical pitch."""
    low = (name or "").casefold()
    for words, manuals, stops in _NAME_RULES:
        if any(w in low for w in words):
            if manuals == ("Hauptwerk",) and median < 45:
                return ("Pedal",), ("Subbass",), f'"{name}" sits low'
            return manuals, stops, f'name "{name}"'
    fam = _program_family(program)
    if fam:
        return fam[0], fam[1], f"GM program {program}"
    if median < 48:
        return ("Pedal",), ("Subbass",), "low register"
    return ("Hauptwerk",), ("Principal",), "default"


def suggest_stops(manual, hints):
    """Stops of that manual whose names contain a hint: [{"name","path"}] (for tooltips / picking)."""
    index = [m[0] for m in MANUALS].index(manual) if manual in [m[0] for m in MANUALS] else -1
    return [s for s in load_stops() if s["manual"] == index and any(h.casefold() in s["name"].casefold() for h in hints)]


def file_voices(path):
    """{channel 0-15: {"name", "program", "median"}} read straight from a MIDI file (first track name seen per channel)."""
    import mido
    voices, names, notes = {}, {}, {}
    try:
        for ti, track in enumerate(mido.MidiFile(path).tracks):
            tname = next((m.name for m in track if m.type == "track_name"), "")
            for m in track:
                if m.type == "program_change":
                    voices.setdefault(m.channel, {})["program"] = m.program
                if m.type == "note_on" and m.velocity > 0:
                    notes.setdefault(m.channel, []).append(m.note)
                    names.setdefault(m.channel, tname)
    except Exception:
        return {}
    result = {}
    for ch, ns in notes.items():
        ns.sort()
        result[ch] = {"name": names.get(ch, ""), "program": voices.get(ch, {}).get("program"), "median": ns[len(ns) // 2]}
    return result


def auto_channel_map(path):
    """Map each channel of a multi-voice file to the manual its instrument suggests: {source ch 0-15: target ch 0-15}.
    Empty for single-channel files (the bridge splits those by key range) and for files already on manual channels."""
    voices = file_voices(path)
    manual_chs = {ch - 1 for _n, _p, ch in manual_channels()}
    if len(voices) < 2 or all(ch in manual_chs for ch in voices):
        return {}
    by_name = {n: ch - 1 for n, _p, ch in manual_channels()}
    result = {}
    for ch, v in voices.items():
        if ch == 9:
            continue
        manuals, _stops, _why = suggest(v["name"], v["program"], v["median"])
        result[ch] = by_name[manuals[0]]
    return result


# ---------------------------------------------------------------- registration strings: Gt.: Principal 8', 4', 2' | Sw.: ...
DIVISION_ABBR = {0: "Ped.", 1: "Gt.", 2: "Sw.", 3: "Solo"}
_FOOT = None


def _split_foot(name):
    """"Principal 8'" -> ("Principal", "8'"); "Quinte 2 2/3'" -> ("Quinte", "2 2/3'"); no foot -> (name, "")."""
    import re
    m = re.search(r"\s(\d+(?:\s\d/\d)?)\s*['\u2032]\s*$", name)
    return (name[:m.start()].strip(), m.group(1) + "'") if m else (name.strip(), "")


def _foot_value(foot):
    try:
        parts = foot.rstrip("'").split()
        return -(float(parts[0]) + (eval(parts[1]) if len(parts) > 1 else 0.0))
    except Exception:
        return 0.0


def registration_text(paths):
    """Organists' shorthand for a set of stops: stops of one family are joined ("Principal 8', 4', 2'"), feet in descending
    order (pitch tags 16' / 8' / 4' ...), one division after the other: "Ped.: Subbass 16' | Gt.: Principal 8', 4'"."""
    wanted, by_div = set(paths), {}
    for stop in load_stops():
        if stop["path"] in wanted:
            by_div.setdefault(stop["manual"], []).append(stop["name"])
    out = []
    for manual in sorted(by_div):
        families, order = {}, []
        for name in by_div[manual]:
            base, foot = _split_foot(name)
            if base not in families:
                families[base] = []
                order.append(base)
            families[base].append(foot)
        parts = []
        for base in order:
            feet = sorted((f for f in families[base] if f), key=_foot_value)
            parts.append(f"{base} {', '.join(feet)}" if feet else base)
        out.append(f"{DIVISION_ABBR.get(manual, 'Div.')}: " + ", ".join(parts))
    return " | ".join(out)
