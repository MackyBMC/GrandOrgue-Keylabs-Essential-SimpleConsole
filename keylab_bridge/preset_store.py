"""Configuration and file-backed setter persistence."""

import os
import re

from .organ_layout import ITEMS, configure_layout, rebuild_layout
from .midi_protocol import LINE_WIDTH, VOLS
from translations import LANGUAGE_NAMES


def default_config_path():
    import os
    import sys
    # A Nuitka --onefile .exe extracts itself into a temp folder at runtime, so __file__
    # points there, not at the real .exe - config.yaml would silently fail to be found.
    # sys.executable correctly reflects the actual .exe location in that case; only fall
    # back to __file__ when genuinely running as a plain .py script (sys.executable is
    # then Python itself, not this script).
    base = sys.executable if getattr(sys, "frozen", False) or "__compiled__" in globals() \
        else os.path.abspath(__file__)
    locations = [
        os.path.dirname(base),
        os.path.dirname(os.path.dirname(base)),
        os.path.dirname(os.path.dirname(os.path.dirname(base))),
        os.path.dirname(os.path.abspath(sys.argv[0])),
        os.getcwd(),
        os.path.dirname(os.path.abspath(__file__)),
    ]
    locations = list(dict.fromkeys(locations))
    locations += [os.path.dirname(location) for location in locations if os.path.dirname(location)]
    locations = list(dict.fromkeys(locations))
    try:                                         # 2.0: installed / portable / source all agree via keylab_bridge.paths
        from .paths import data_dir, first_run_config
        if data_dir() != os.path.dirname(base):
            return first_run_config()
    except Exception:
        pass
    for location in locations:
        candidate = os.path.join(location, "config.yaml")
        if os.path.exists(candidate):
            return candidate
    return os.path.join(locations[0], "config.yaml")


def load_config(path):
    """Read config.yaml (if it exists) and return (flat dict of command-line defaults, other settings)."""
    import os
    if not path or not os.path.exists(path):
        return {}, {}
    import yaml
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    ports, faders, disp = raw.get("ports") or {}, raw.get("faders") or {}, raw.get("display") or {}
    flat = {"go": ports.get("go"), "go_out": ports.get("go_out") or None,
            "kl_in": ports.get("keylab_in"), "kl_out": ports.get("keylab_out"), "kl_main": ports.get("keylab_main_in") or None,
            "relay_main": ports.get("relay_main_out") or None, "relay_main_in": ports.get("relay_main_in") or None,
            "threshold": faders.get("threshold"), "hold": disp.get("hold"), "live": disp.get("live"),
            "refresh": disp.get("refresh"), "verbose": raw.get("verbose"), "ui": raw.get("ui")}
    return {k: v for k, v in flat.items() if v is not None}, raw


def load_language(config_path, raw):
    language = str(raw.get("language", "")).lower()
    language_path = os.path.join(os.path.dirname(config_path), "language.txt") if config_path else ""
    if language_path and os.path.isfile(language_path):
        try:
            with open(language_path, encoding="utf-8") as language_file:
                language = language_file.read().strip().lower()
        except OSError:
            pass
    return language if language in LANGUAGE_NAMES else "en"


def load_theme(config_path, raw):
    theme = str(raw.get("theme", "light")).lower()
    theme_path = os.path.join(os.path.dirname(config_path), "theme.txt") if config_path else ""
    if theme_path and os.path.isfile(theme_path):
        try:
            with open(theme_path, encoding="utf-8") as theme_file:
                theme = theme_file.read().strip().lower()
        except OSError:
            pass
    return theme if theme in ("light", "dark", "contrast") else "light"


def load_preset_activation(config_path, raw):
    mode = str(raw.get("preset_activation", "staged")).lower()
    mode_path = os.path.join(os.path.dirname(config_path), "preset_activation.txt") if config_path else ""
    if mode_path and os.path.isfile(mode_path):
        try:
            with open(mode_path, encoding="utf-8") as mode_file:
                mode = mode_file.read().strip().lower()
        except OSError:
            pass
    return mode if mode in ("staged", "direct") else "staged"


def load_combinations(config_path, raw):
    import yaml

    set_name = str(raw.get("combination_set", "Friesach"))
    folder = os.path.join(combination_root(config_path, set_name), "Combinations", set_name)
    combinations = []
    if not os.path.isdir(folder):
        return combinations
    for filename in sorted(os.listdir(folder), key=str.casefold):
        if not filename.lower().endswith((".yaml", ".yml")):
            continue
        path = os.path.join(folder, filename)
        try:
            with open(path, encoding="utf-8") as combination_file:
                data = yaml.safe_load(combination_file) or {}
        except (OSError, yaml.YAMLError):
            continue
        info = data.get("info") or {}
        if str(info.get("content-type", "")).casefold() != "grandorgue combinations":
            continue
        sequences = data.get("sequencer") or {}
        if not isinstance(sequences, dict):
            continue
        seen_internal_ids = set()
        for internal_id, sequence in sequences.items():
            try:
                normalized_id = f"{int(internal_id):03d}"
            except (TypeError, ValueError):
                continue
            if normalized_id in seen_internal_ids or not isinstance(sequence, dict):
                continue
            seen_internal_ids.add(normalized_id)
            switch_paths = set()
            for manual_id, manual in (sequence.get("manuals") or {}).items():
                for category in MANUAL_OBJECT_KINDS:      # the setter file names a category after its path segment
                    for object_id in (manual.get(category) or {}):
                        switch_paths.add(f"manuals/{int(manual_id):03d}/{category}/{int(object_id):03d}")
            for switch_id in (sequence.get("switches") or {}):
                switch_paths.add(f"{int(switch_id):03d}")
            combinations.append({
                "name": str(sequence.get("name") or os.path.splitext(filename)[0]),
                "filename": filename,
                "internal_id": normalized_id,
                "switch_paths": switch_paths,
            })
    return combinations


MANUAL_OBJECT_KINDS = ("switches", "stops", "couplers")


def _normalized_mapping_key(mapping, identifier):
    normalized = str(identifier).zfill(3)
    return next((key for key in mapping if str(key).zfill(3) == normalized), int(identifier))


def _replace_managed_switch(mapping, switch_id, value):
    normalized = str(switch_id).zfill(3)
    for key in list(mapping):
        if str(key).zfill(3) == normalized:
            del mapping[key]
    if value is not None:
        mapping[int(switch_id)] = value


def _write_managed_switches(sequence, active_paths):
    active_paths = set(active_paths)
    manuals = sequence.setdefault("manuals", {})
    global_switches = sequence.setdefault("switches", {})
    for item in ITEMS:
        if item.path.startswith("manuals/"):
            _prefix, manual_id, category, switch_id = item.path.split("/")
            manual_key = _normalized_mapping_key(manuals, manual_id)
            manual = manuals.get(manual_key)
            if manual is None:
                if item.path not in active_paths:
                    continue
                manual = manuals.setdefault(manual_key, {})
            switches = manual.setdefault(category, {})
            _replace_managed_switch(
                switches, switch_id, item.name if item.path in active_paths else None,
            )
        else:
            switch_id = int(item.path)
            _replace_managed_switch(
                global_switches, switch_id, item.name if item.path in active_paths else None,
            )


def bridge_settings(raw):
    """Bridge() keyword arguments taken from the 'controls' section of the config."""
    c, out = raw.get("controls") or {}, {}
    for key, arg in (("encoder_step", "encoder_step"), ("volume_start", "volume_start"),
                     ("jog_max_steps", "jog_max"), ("loop_restart", "loop_restart_s")):
        if c.get(key) is not None:
            out[arg] = c[key]
    p = raw.get("pads") or {}
    if p.get("enabled") is not None:
        out["pads_enabled"] = bool(p["enabled"])
    if p.get("ccs"):
        out["pad_ccs"] = [int(x) for x in p["ccs"]]
    if p.get("refresh") is not None:
        out["led_refresh_s"] = float(p["refresh"])
    if p.get("shared_window") is not None:
        out["pad_shared_window"] = float(p["shared_window"])
    if p.get("dim") is not None:
        out["pad_dim"] = float(p["dim"])
    if p.get("verbosity") is not None:
        out["pad_verbosity"] = max(1, min(3, int(p["verbosity"])))
    if p.get("off_grey") is not None:
        out["pad_off_grey"] = max(0, min(127, int(p["off_grey"])))
    if p.get("colors"):
        names = {"pedal": "P", "hw": "H", "sw": "S", "sl": "L", "other": "C",
             "p1": "P1", "p2": "P2", "h1": "H1", "h2": "H2",
             "s1": "S1", "s2": "S2", "s3": "S3"}
        out["pad_colors"] = {names[k]: tuple(int(x) for x in v) for k, v in p["colors"].items() if k in names}
    t = raw.get("testing") or {}
    for key, arg, cast in (("accept_note_pads", "note_pads", bool), ("note_pad_channel", "note_pad_channel", int),
                           ("note_pad_first", "note_pad_first", int),
                           ("accept_ch1_aftertouch_pads", "ch1_aftertouch_pads", bool), ("pad_trace", "pad_trace", bool),
                           ("daw_trace", "daw_trace", bool)):
        if t.get(key) is not None:
            out[arg] = cast(t[key])
    if c.get("tremulant_encoders") is not None:
        out["tremulant_encoders"] = {int(k) - 1: int(v) for k, v in (c["tremulant_encoders"] or {}).items()}
    if c.get("encoders"):
        out["encoder_vols"] = {int(k) - 1: v for k, v in c["encoders"].items() if v in VOLS}
    return out


def describe_encoders(mapping):
    return ", ".join(f"enc {n + 1} = {VOLS[k][2]}" for n, k in sorted(mapping.items())) or "none"


def describe_tremolos(mapping):
    names = {it.number: it.name for it in ITEMS if it.kind == "tremulant"}
    return ", ".join(f"enc {n + 1} = {names.get(t, t)}" for n, t in sorted(mapping.items())) or "none"


def project_root(config_path):
    return os.path.dirname(os.path.dirname(os.path.abspath(config_path)))


def combination_root(config_path, set_name=None):
    """Find the shared GrandOrgue data root, with source-tree fallbacks."""
    from .paths import data_dir, go_folder

    config_dir = os.path.dirname(os.path.abspath(config_path))
    roots = (go_folder(), project_root(config_path), config_dir)
    unique_roots = list(dict.fromkeys(os.path.normcase(os.path.abspath(root)) for root in roots))

    if set_name:
        for root in unique_roots:
            if os.path.isdir(os.path.join(root, "Combinations", str(set_name))):
                return root
    for root in unique_roots:
        if os.path.isdir(os.path.join(root, "Combinations")):
            return root

    if os.path.normcase(config_dir) == os.path.normcase(os.path.abspath(data_dir())):
        return os.path.abspath(go_folder())
    if os.path.basename(config_dir).casefold() == "scripts":
        return project_root(config_path)
    return config_dir


def set_config_key(config_path, key, value):
    """Set one top-level key in config.yaml in place, keeping every comment and the file's line endings."""
    text = open(config_path, newline="", encoding="utf-8").read()
    eol = "\r\n" if "\r\n" in text else "\n"
    quoted = "'" + str(value).replace("'", "''") + "'"
    lines, found = text.split(eol), False
    for i, line in enumerate(lines):
        match = re.match(rf"^({re.escape(key)}:\s*)(.*?)(\s+#.*)?$", line)
        if match:
            lines[i] = f"{key}: {quoted}" + (match.group(3) or "")
            found = True
            break
    if not found:
        lines.insert(len(lines) - 1 if lines and lines[-1] == "" else len(lines), f"{key}: {quoted}")
    with open(config_path, "w", newline="", encoding="utf-8") as out:
        out.write(eol.join(lines))


def _format_yaml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_yaml_value(v) for v in value) + "]"
    text = str(value)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", text) and text.lower() not in ("true", "false", "yes", "no", "null", "on", "off"):
        return text
    return "'" + text.replace("'", "''") + "'"


def _split_value_comment(rest):
    """'value   # note' -> ('value', '   # note'); a # inside quotes does not start a comment."""
    quote = None
    for i, ch in enumerate(rest):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or rest[i - 1] in " \t"):
            return rest[:i].rstrip(), " " * max(1, len(rest[:i]) - len(rest[:i].rstrip())) + rest[i:]
    return rest.rstrip(), ""


def set_config_value(config_path, key_path, value):
    """Set one (possibly nested) key, e.g. ("pads", "dim"), in config.yaml in place. Comments, key order and the
    file's line endings are kept. Returns False when the key is not in the file (nothing is changed)."""
    text = open(config_path, newline="", encoding="utf-8").read()
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    stack = []                                   # [(indent, key)]
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)(['\"]?)([^:'\"]+)\2:(\s*)(.*)$", line)
        if not match:
            continue
        indent, key = len(match.group(1)), match.group(3).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        if [k for _, k in stack] == [str(k) for k in key_path]:
            current, comment = _split_value_comment(match.group(5))
            if current == "" :                     # a section header, not a value
                return False
            quote = match.group(2)
            lines[i] = f"{match.group(1)}{quote}{key}{quote}:{match.group(4) or ' '}{_format_yaml_value(value)}{comment}"
            with open(config_path, "w", newline="", encoding="utf-8") as out:
                out.write(eol.join(lines))
            return True
    return False


def apply_layout(raw, config_path=None):
    """organ_layout_file: Organs/<organ>.layout.yaml swaps in another organ's layout (else the built-in Friesach one).
    Which division's fader/pad bank each tremolo sits in:  layout: {tremolos: {1: sw, 2: sl}}"""
    layout_file = raw.get("organ_layout_file")
    if layout_file and config_path:
        import yaml
        path = layout_file if os.path.isabs(layout_file) else os.path.join(project_root(config_path), layout_file)
        try:
            with open(path, encoding="utf-8") as layout_stream:
                configure_layout(yaml.safe_load(layout_stream) or {}, source=os.path.basename(path))
        except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
            print(f"Could not load organ layout {path}: {exc}. Using the built-in layout.")
    t = (raw.get("layout") or {}).get("tremolos")
    if t is not None:
        codes = {"pedal": "P", "hw": "H", "sw": "S", "sl": "L"}
        rebuild_layout({int(k): codes[v] for k, v in t.items() if v in codes})


def apply_lcd_names(raw):
    """Optional display names for stops/couplers/tremulants: lcd_names: {"manuals/000/couplers/Coupler 1": "III/P"}"""
    names = raw.get("lcd_names") or {}
    for it in ITEMS:
        if it.path in names:
            it.name = str(names[it.path])[:LINE_WIDTH]


def learn_pads(backend, wanted):
    """Ask for pads 1-8 (top row left to right, then bottom row) and print the CC numbers."""
    port = backend.open_input(find_port(backend.get_input_names(), wanted))
    found, raws = [], []
    print("Press each pad once, top row left to right, then bottom row left to right.")
    for n in range(1, 9):
        print(f"  pad {n} ... ", end="", flush=True)
        while True:
            m = port.receive()
            if m.type == "control_change" and m.value >= 64:
                found.append(m.control)
                raws.append(" ".join(f"{x:02X}" for x in m.bytes()))
                print(f"CC {m.control}, channel {m.channel + 1}   raw {raws[-1]}")
                break
            if m.type == "note_on" and m.velocity > 0:
                print(f"note {m.note} - these pads send notes, tell me and I will add support")
                return
            print(f"[other message: {m}]")
    port.close()
    dups = sorted({c for c in found if found.count(c) > 1})
    if dups:
        print(f"\nWarning: CC {dups} is sent by more than one pad, so those pads cannot be told apart by CC alone.")
        print("Run keylab_sniffer.py and press those pads one at a time to see what else differs.")
    print("\nPut this in config.yaml:\npads:\n  ccs: " + str(found))


def find_port(names, wanted):
    for n in names:
        if wanted.lower() in n.lower():
            return n
    raise SystemExit(f"No MIDI port containing '{wanted}'. Use --list to see the names.")


def find_matching_port(names, wanted):
    for name in names:
        if wanted and wanted.lower() in name.lower():
            return name
    raise ValueError(f"no MIDI port containing {wanted!r}")
