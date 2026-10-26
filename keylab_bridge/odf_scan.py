"""GrandOrgue ODF (.organ) scanner.

Reads the organ definition file and reports what it literally contains: manuals, the stops / couplers /
switches each manual references, global switches, tremulants and enclosures. It does NOT guess GrandOrgue's
MIDI-settings import format; it only describes the organ and proposes a bridge-side CC allocation.

The parser is deliberately tolerant: ODF files are hand-edited INI with BOMs, mixed encodings, duplicate
keys, comments after ';' or '#', and keys with no value, which configparser rejects.
"""
import os
import re

from .organ_layout import (CCS_PER_CHANNEL, DEFAULT_SPILL_CHANNELS, DIVISIONS, SWITCH_OFFSET, TREMULANT_SWITCH,
                           items_for_spec)

COUPLER_WORDS = re.compile(r"coupl|koppel|accoupl|acopl", re.I)
TREMULANT_WORDS = re.compile(r"tremul|tremolo|tremblant", re.I)
INTERNAL_STOP_NOISE = re.compile(r"\bstop\s+(?:attack|release)\s+noise\b", re.I)
LCD_WIDTH = 16
NOISE_WORDS = re.compile(r"key\s*action|\battack\b|\brelease\b|\bnoise\b", re.I)


def _norm(name):
    return re.sub(r"[\W_]+", "", str(name).casefold())


def _short_names(names):
    """Drop a shared upper-case division tag ("P  ", "HW  ") so the 16-character LCD shows the stop itself."""
    tags = [m.group(1) for m in (re.match(r"^([A-Z]{1,4})\s+\S", n) for n in names) if m]
    if len(names) >= 3 and tags and len(tags) >= 0.8 * len(names) and len(set(tags)) == 1:
        names = [re.sub(r"^" + tags[0] + r"\s+", "", n) for n in names]
    return [n[:LCD_WIDTH] for n in names]


def _read_text(path):
    raw = open(path, "rb").read()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def parse_odf(text):
    """-> {lower-case section name: {"_name": original section name, lower-case key: value}} in file order."""
    sections, current = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in ";#":
            continue
        if line.startswith("[") and "]" in line:
            name = line[1:line.index("]")].strip()
            current = sections.setdefault(name.lower(), {"_name": name})
        elif current is not None and "=" in line:
            key, value = line.split("=", 1)
            current[key.strip().lower()] = value.strip()
    return sections


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _name_of(sections, section_name, fallback):
    return sections.get(section_name.lower(), {}).get("name") or fallback


def scan_odf(path):
    """Scan an ODF file. Raises OSError if unreadable; returns a profile dict."""
    sections = parse_odf(_read_text(path))
    organ = sections.get("organ")
    if organ is None:
        raise ValueError("no [Organ] section - this does not look like a GrandOrgue ODF")
    warnings = []
    manuals = []
    for key in sorted(k for k in sections if re.fullmatch(r"manual\d{3}", k)):
        number = int(key[6:])
        section = sections[key]
        switches = []
        for n in range(1, _int(section.get("numberofswitches")) + 1):
            ref = _int(section.get(f"switch{n:03d}"), None)
            if ref is None:
                warnings.append(f"{section['_name']}: Switch{n:03d} is missing")
                continue
            switches.append({"index": n, "ref": ref, "name": _name_of(sections, f"switch{ref:03d}", f"Switch{ref:03d}")})
        stops = []
        for n in range(1, _int(section.get("numberofstops")) + 1):
            ref = _int(section.get(f"stop{n:03d}"), None)
            if ref is not None:
                stops.append({"index": n, "ref": ref, "name": _name_of(sections, f"stop{ref:03d}", f"Stop{ref:03d}")})
        couplers = [{"index": n, "name": _name_of(sections, f"manual{number:03d}coupler{n:03d}", f"Coupler{n:03d}")}
                    for n in range(1, _int(section.get("numberofcouplers")) + 1)]
        manuals.append({"number": number, "name": section.get("name", f"Manual{number:03d}"),
                        "stops": stops, "couplers": couplers, "switches": switches,
                        "divisionals": _int(section.get("numberofdivisionals"))})
    declared = _int(organ.get("numberofmanuals"), None)
    if declared is not None and declared != len([m for m in manuals if m["number"] != 0]):
        warnings.append(f"[Organ] declares {declared} manuals but {len([m for m in manuals if m['number'] != 0])} "
                        "non-pedal [ManualNNN] sections were found")
    global_switches = {}
    for key in sections:
        match = re.fullmatch(r"switch(\d{3})", key)
        if match:
            global_switches[int(match.group(1))] = sections[key].get("name", key)
    return {
        "file": os.path.abspath(path),
        "name": organ.get("churchname") or os.path.splitext(os.path.basename(path))[0],
        "manuals": manuals,
        "global_switches": global_switches,
        "tremulants": [{"number": int(k[9:]), "name": v.get("name", v["_name"])}
                       for k, v in sections.items() if re.fullmatch(r"tremulant\d{3}", k)],
        "windchests": [{"number": int(k[15:]), "name": v.get("name", v["_name"])}
                       for k, v in sections.items() if re.fullmatch(r"windchestgroup\d{3}", k)],
        "enclosures": [{"number": int(k[9:]), "name": v.get("name", v["_name"])}
                       for k, v in sections.items() if re.fullmatch(r"enclosure\d{3}", k)],
        "warnings": warnings,
    }


def compare_with_builtin(profile):
    """Does the layout compiled into the bridge (the Friesach layout) fit this organ? -> list of differences."""
    problems = []
    by_number = {m["number"]: m for m in profile["manuals"]}
    for _code, name, manual, stop_names in DIVISIONS:
        found = by_number.get(manual)
        if found is None:
            problems.append(f"built-in {name} (manual {manual:03d}) has no matching [Manual{manual:03d}] section")
            continue
        expected = len(stop_names) + SWITCH_OFFSET[manual]
        if len(found["switches"]) != expected:
            problems.append(f"{name}: built-in layout expects {expected} panel switches "
                            f"({len(stop_names)} stops + {SWITCH_OFFSET[manual]} couplers), ODF has {len(found['switches'])}")
    for extra in sorted(set(by_number) - {d[2] for d in DIVISIONS}):
        problems.append(f"ODF has [Manual{extra:03d}] ({by_number[extra]['name']}) which the built-in layout does not cover")
    for number, switch in TREMULANT_SWITCH.items():
        if switch not in profile["global_switches"]:
            problems.append(f"built-in tremulant {number} uses global switch {switch:03d}, which the ODF does not define")
    return problems


def summarize(profile, problems):
    parts = [f"{profile['name']}: {len([m for m in profile['manuals'] if m['number'] != 0])} manuals"
             f"{' + pedal' if any(m['number'] == 0 for m in profile['manuals']) else ''}, "
             f"{sum(len(m['switches']) for m in profile['manuals'])} panel switches"
             + (f" + {sum(len(m['stops']) for m in profile['manuals'])} stops" if any(m['stops'] for m in profile['manuals']) else "")
             + (f" + {sum(len(m['couplers']) for m in profile['manuals'])} couplers" if any(m['couplers'] for m in profile['manuals']) else "")
             + ", "
             f"{len(profile['global_switches'])} global switches, "
             f"{len(profile['tremulants'])} tremulants, {len(profile['enclosures'])} enclosures."]
    parts.append("Built-in bridge layout fits this organ." if not problems else
                 "Built-in bridge layout does NOT fit: " + "; ".join(problems[:4]) +
                 (f" (+{len(problems) - 4} more)" if len(problems) > 4 else ""))
    if profile["warnings"]:
        parts.append("Scan warnings: " + "; ".join(profile["warnings"][:3]))
    return "  ".join(parts)


def _division_code(name, used):
    letters = [ch.upper() for ch in name if ch.isalpha()] or ["M"]
    for ch in letters + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        if ch not in used:
            used.add(ch)
            return ch
    raise ValueError("ran out of single-letter division codes")


def spec_from_profile(profile):
    """Derive a bridge layout spec from a scan. Heuristics, reported in `notes` so nothing is silent:
    leading coupler-named switches of a manual are couplers, the rest are stops, and unreferenced global
    switches named like tremulants become tremulants."""
    divisions, couplers, tremulants, notes, used = [], [], [], [], set()
    uses_objects = False
    noise = twins = 0
    for manual in sorted(profile["manuals"], key=lambda m: m["number"]):
        switches = manual["switches"]
        lead = 0
        while lead < len(switches) and COUPLER_WORDS.search(switches[lead]["name"]):
            lead += 1
        name = re.sub(r"^\d+\.\s*", "", manual["name"]).strip() or f"Manual {manual['number']}"
        code = _division_code(name, used)
        n = manual["number"]
        panel = switches[lead:]
        panel_keys = {_norm(sw["name"]) for sw in panel}
        real_stops = [st for st in manual["stops"] if not (INTERNAL_STOP_NOISE.search(st["name"]) or NOISE_WORDS.search(st["name"]))]
        noise += len(manual["stops"]) - len(real_stops)
        unmatched = [st for st in real_stops if _norm(st["name"]) not in panel_keys] if panel else real_stops
        if panel and len(panel) >= len(real_stops):   # the panel switches already cover every real stop
            unmatched = []
        twins += len(real_stops) - len(unmatched)
        names = _short_names([sw["name"].strip() for sw in panel] + [st["name"].strip() for st in unmatched])
        if unmatched or not panel:     # some Stop objects have no panel switch: map those directly
            stops = [{"name": nm, "path": f"manuals/{n:03d}/switches/{sw['index']:03d}"} for nm, sw in zip(names, panel)]
            stops += [{"name": nm, "path": f"manuals/{n:03d}/stops/{st['index']:03d}"} for nm, st in zip(names[len(panel):], unmatched)]
            offset = 0
            uses_objects = True
        else:                          # panel switches cover every stop (Friesach): stops follow the couplers
            stops, offset = names, lead
        divisions.append({"code": code, "name": name, "manual": n, "switch_offset": offset, "stops": stops})
        if switches[:lead] and len(switches[:lead]) >= len(manual["couplers"]):
            for sw in switches[:lead]:
                couplers.append({"manual": n, "number": sw["index"], "name": f"{sw['name'].strip()} ({code})"[:LCD_WIDTH],
                                 "odf_name": sw["name"].strip()})
        else:
            for c in manual["couplers"]:
                couplers.append({"manual": n, "number": 100 + c["index"], "name": f"{c['name'].strip()} ({code})"[:LCD_WIDTH],
                                 "odf_name": c["name"].strip(), "path": f"manuals/{n:03d}/couplers/{c['index']:03d}"})
                uses_objects = True
        if any(COUPLER_WORDS.search(s["name"]) for s in switches[lead:]):
            notes.append(f"{name}: coupler-named switches after the first stop are treated as stops")
        if not switches:
            notes.append(f"{name}: no panel switches; it appears in the layout with no stops")
    referenced = {s["ref"] for m in profile["manuals"] for s in m["switches"]}
    loose = []
    for ref, label in sorted(profile["global_switches"].items()):
        if ref in referenced:
            continue
        if TREMULANT_WORDS.search(label):
            hit = re.search(r"(\d+)\s*man", label, re.I)       # "Tremulant 2 Man" belongs to manual 2
            home = next((d["code"] for d in divisions if hit and d["manual"] == int(hit.group(1))), divisions[-1]["code"] if divisions else "")
            tremulants.append({"number": len(tremulants) + 1, "name": label.strip()[:LCD_WIDTH], "switch": ref, "division": home})
        else:
            loose.append(label)
    if loose:
        notes.append(f"{len(loose)} global switch(es) not mapped: " + ", ".join(loose[:3]) + (" ..." if len(loose) > 3 else ""))
    if twins or noise:
        notes.append(f"{twins} Stop objects are driven by their panel switches (not mapped twice); {noise} key-action/noise stops skipped")
    spec = {"stop_channels": [15], "divisions": divisions, "couplers": couplers, "tremulants": tremulants}
    needed = len(items_for_spec(spec))
    channels_needed = max(1, -(-needed // CCS_PER_CHANNEL))
    available = [15] + DEFAULT_SPILL_CHANNELS
    problems = []
    if channels_needed > len(available):
        problems.append(f"needs {needed} controls but only {len(available) * CCS_PER_CHANNEL} fit on {len(available)} channels")
    else:
        spec["stop_channels"] = available[:channels_needed]
        if channels_needed > 1:
            notes.insert(0, f"{needed} controls on MIDI channels {', '.join(str(c) for c in spec['stop_channels'])}")
    if uses_objects:
        notes.insert(0, "Stop/Coupler object paths (manuals/NNN/stops/NNN, .../couplers/NNN) follow GrandOrgue's naming "
                        "pattern but are UNVERIFIED: import, export from GrandOrgue, and use the check-against field")
    spec["notes"], spec["problems"] = notes, problems
    return spec
