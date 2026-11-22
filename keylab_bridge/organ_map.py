"""Organ map: the bridge's own keys <-> the loaded organ's ids and exact names.

The bridge works with canonical keys (stops P1..Pn, H1..Hn, S1..Sn ..., couplers Cp<manual>.<n>, tremulants T<n>) and never
with organ names. Everything that has to carry the organ's own name (setter files, GrandOrgue feedback) asks this map,
so a name can never drift. One map file per organ (Organs/<organ>.map.yaml), so another organ is only another map.

CHANGELOG
2026-11-21  apply_map() (organ / display names onto the layout items), list_maps(), map_path(); the map also holds the setter names matrix ("setters"), organ_file and combination_set.
2026-11-21  New: build_map() (keys from the layout items, organ names from the .organ file, a fallback for names the .organ file
            does not give), save_map(), load_map(), labels_for_setters() (what setter_format uses as the organ's names).
"""

import os
import re

_FALLBACK = re.compile(r"(Coupler|Stop|Switch|Manual)\d{3}")      # the scanner's stand-in when an ODF section has no Name


def item_key(item):
    """Canonical key of a layout item: stop P3 (division code + number), coupler Cp1.2, tremulant T1."""
    if item.kind == "stop":
        code = str(item.bank_code)[:1] if str(item.bank_code)[:1].isalpha() else "X"
        return f"{code}{item.number}"
    if item.kind == "coupler":
        return f"Cp{item.manual}.{item.number}"
    return f"T{item.number}"


def map_path(cfg_path, organ_path):
    """Organs/<organ file name>.map.yaml next to the layout files."""
    stem = re.sub(r'[<>:"/\\|?*]', "_", os.path.splitext(os.path.basename(str(organ_path)))[0]) or "organ"
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(cfg_path))), "Organs", f"{stem}.map.yaml")


def _real(name):
    name = str(name or "").strip()
    return name if name and not _FALLBACK.fullmatch(name) else ""


def build_map(organ, profile, items, fallback_names=None, existing=None, combination_set=""):
    """{"organ": name, "items": {key: {kind, path, manual, switch, stop, organ_name, display}}}.
    organ_name: the .organ file's real name, else the name most intact setter files use (fallback_names[(manual, category)][id]),
    else what the layout calls it. `existing` keeps hand-edited display names."""
    fallback_names = fallback_names or {}
    switches = {}
    for manual in (profile or {}).get("manuals", []):
        for entry in manual.get("switches", []):
            switches[(int(manual["number"]), int(entry["index"]))] = entry.get("name")
    stops = {}
    for manual in (profile or {}).get("manuals", []):
        for entry in manual.get("stops", []):
            stops[(int(manual["number"]), int(entry["index"]))] = entry.get("name")
    globals_ = {int(k): v for k, v in (profile or {}).get("global_switches", {}).items()}
    old = (existing or {}).get("items", {})
    result = {}
    for item in items:
        key = item_key(item)
        path = item.path
        entry = {"kind": item.kind, "path": path, "manual": item.manual}
        match = re.fullmatch(r"manuals/(\d+)/(switches|stops|couplers)/(\d+)", path)
        if match:
            manual, category, index = int(match.group(1)), match.group(2), int(match.group(3))
            if category == "switches":
                entry["switch"] = index
                name = _real(switches.get((manual, index)))
                if item.kind == "stop":
                    entry["stop"] = item.number
                    name = name or _real(stops.get((manual, item.number)))
            elif category == "stops":                               # a Stop object without a panel switch
                entry["stop"] = index
                name = _real(stops.get((manual, index)))
            else:
                entry["coupler"] = index
                name = None
            name = name or _real(fallback_names.get((manual, category), {}).get(index))
        else:
            entry["switch"] = int(path)
            name = _real(globals_.get(int(path)))
        organ_name = name or _real((old.get(key) or {}).get("organ_name")) or str(item.odf_name or item.name)
        entry["organ_name"] = organ_name
        entry["display"] = dict((old.get(key) or {}).get("display") or {"default": str(item.name)})
        result[key] = entry
    mapping = {"organ": organ, "organ_file": (profile or {}).get("file", (existing or {}).get("organ_file", "")),
               "combination_set": combination_set or (existing or {}).get("combination_set", ""), "items": result}
    if (existing or {}).get("character"):
        mapping["character"] = existing["character"]                   # what the organ was built for (setter_guide ratings + text)
    else:
        from .known_organs import character_for
        known = character_for(organ, (profile or {}).get("file", ""))
        if known:
            mapping["character"] = known                               # first time: from the sample maker's page
    if (existing or {}).get("layout_file"):
        mapping["layout_file"] = existing["layout_file"]
    if (existing or {}).get("setters"):
        mapping["setters"] = existing["setters"]                      # the names matrix (setter file names) lives in the map too
    return mapping


def apply_map(mapping, language, items, skip=()):
    """Give every layout item its organ name (go_name, used in setter files) and display name (chosen language)."""
    from .midi_protocol import LINE_WIDTH
    entries = (mapping or {}).get("items", {})
    for item in items:
        entry = entries.get(item_key(item))
        if not entry:
            continue
        item.go_name = str(entry.get("organ_name") or "")
        display = entry.get("display") or {}
        shown = str(display.get(language) or display.get("default") or item.name)
        item.display_name = shown
        if item.path not in skip:
            item.name = shown[:LINE_WIDTH]


def list_maps(organs_folder):
    """The organs that have a map: [{"stem", "organ", "organ_file", "combination_set"}]."""
    found = []
    if os.path.isdir(organs_folder):
        for name in sorted(os.listdir(organs_folder), key=str.casefold):
            if name.endswith(".map.yaml"):
                data = load_map(os.path.join(organs_folder, name))
                if data:
                    found.append({"stem": name[:-len(".map.yaml")], "organ": str(data.get("organ", "")),
                                  "organ_file": str(data.get("organ_file", "")), "combination_set": str(data.get("combination_set", "")),
                                  "layout_file": str(data.get("layout_file", ""))})
    return found


def labels_for_setters(organ_map):
    """{(manual, category): {organ name: id}} for setter_format: switches always, stops and couplers where they exist."""
    labels = {}
    for entry in (organ_map or {}).get("items", {}).values():
        manual, name = entry.get("manual"), entry.get("organ_name")
        if not name:
            continue
        if entry["kind"] == "tremulant":                       # organ-wide switch (no manual)
            labels.setdefault(("step", "switches"), {}).setdefault(name, int(entry["switch"]))
            continue
        if "switch" in entry:
            labels.setdefault((int(manual), "switches"), {}).setdefault(name, int(entry["switch"]))
            if entry["kind"] == "coupler":
                labels.setdefault((int(manual), "couplers"), {}).setdefault(name, int(entry["switch"]))
        if "stop" in entry:
            labels.setdefault((int(manual), "stops"), {}).setdefault(name, int(entry["stop"]))
        if "coupler" in entry:
            labels.setdefault((int(manual), "couplers"), {}).setdefault(name, int(entry["coupler"]))
    return labels


class _SpecItem:
    def __init__(self, kind, manual, number, name, path, bank_code, odf_name=""):
        self.kind, self.manual, self.number, self.name, self.path = kind, manual, number, name, path
        self.bank_code, self.odf_name = bank_code, odf_name


def items_from_spec(spec):
    """Layout items of a spec (a scanned organ) without touching the live layout tables."""
    items = []
    for div in spec["divisions"]:
        for i, stop in enumerate(div["stops"]):
            if isinstance(stop, dict):
                path, name = stop["path"], stop["name"]
            else:
                path, name = f"manuals/{int(div['manual']):03d}/switches/{i + 1 + int(div.get('switch_offset', 0)):03d}", stop
            items.append(_SpecItem("stop", int(div["manual"]), i + 1, name, path, str(div["code"])))
    for c in spec.get("couplers") or []:
        path = c.get("path") or f"manuals/{int(c['manual']):03d}/switches/{int(c['number']):03d}"
        items.append(_SpecItem("coupler", int(c["manual"]), int(c["number"]), c["name"], path, "C", str(c.get("odf_name", ""))))
    for t in spec.get("tremulants") or []:
        items.append(_SpecItem("tremulant", 0, int(t["number"]), t["name"], t.get("path") or f"{int(t['switch']):03d}", "T"))
    return items


def save_map(path, organ_map):
    import yaml
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Organ map: the bridge's keys (P1, H3, Cp1.2, T1 ...) -> this organ's ids and exact GrandOrgue names.\n"
                     "# organ_name is what GrandOrgue checks in setter files; display holds the names shown by language (add en, de, af ...).\n")
        yaml.safe_dump(organ_map, handle, sort_keys=False, allow_unicode=True, default_flow_style=False)


def load_map(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) and isinstance(data.get("items"), dict) else {}
