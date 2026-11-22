"""GrandOrgue setter (combination) files: read ids as decimal, write them the way GrandOrgue writes them, repair damaged files.

GrandOrgue looks a step up by its zero-padded text key ("000", "005") and expects every step to carry the full set of
entries (manual names, the "Key action" stops, the stop entries next to the switch entries, Blower / Ambient). The
bridge used to write plain integers (0, 5) and, because PyYAML reads 010 as octal 8, wrote wrong ids back. Both
ended in setter files GrandOrgue could not use. This module is the one place that writes setter files, and it
repairs the damaged ones by label: a label ("P  Subbaß 16'") has one id per manual and category in an intact file.

CHANGELOG
2026-11-21  The organ's names come from the organ map (set_organ_labels); the profile / ODF reading moved to organ_map.py.
2026-11-21  Entry names: the organ's real names (scanner stand-ins like Coupler001 ignored) or the majority of intact files decide the name of an id; docs/FRIESACH_NAMING.md.
2026-11-20  New: write_combination_file() (zero-padded text keys, plain scalars, "---", ordered like GrandOrgue's own files, steps completed from the
            folder's intact files) and repair_folder_format() (damaged files are rebuilt by label, folder backed up first, silent).
"""

import datetime
import os
import re
import shutil

import yaml

CATEGORIES = ("stops", "couplers", "switches")           # per manual
STEP_CATEGORIES = ("tremulants", "switches")               # per step (organ wide)
_PADDED_KEY = re.compile(r"^\s+\d{1,2}\s*:", re.MULTILINE)


_ODF_LABELS = {}                  # (manual number, category) -> {full label: id}, from the organ's own ODF


def set_organ_labels(labels):
    """The loaded organ's names from its organ map (organ_map.labels_for_setters): {(manual or "step", category): {name: id}}.
    They decide the name of every mapped id; an empty dict clears them."""
    _ODF_LABELS.clear()
    for key, names in (labels or {}).items():
        _ODF_LABELS[key] = dict(names)


def _pad(key):
    try:
        return f"{int(str(key)):03d}"
    except (TypeError, ValueError):
        return str(key)


class _Dumper(yaml.SafeDumper):
    pass


# "005" must come out as plain text 005 (GrandOrgue's own spelling), real integers stay integers
_Dumper.yaml_implicit_resolvers = {k: [(t, r) for t, r in v if t != "tag:yaml.org,2002:int"]
                                   for k, v in yaml.SafeDumper.yaml_implicit_resolvers.items()}
_Dumper.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^[-+]?(0|[1-9][0-9]*)$"), list("-+0123456789"))
_Dumper.ignore_aliases = lambda self, data: True


def _read(path):
    from .preset_store import read_combination_yaml
    with open(path, encoding="utf-8") as stream:
        return read_combination_yaml(stream) or {}


def _entries(node):
    return node if isinstance(node, dict) else {}


def label_dictionary(folder, skip=()):
    """{(manual or "step", category): {label: id}} from the folder's intact files (zero-padded keys, nothing ambiguous).
    Also returns the manual names, the info block and one set of organ-wide entries."""
    seen = {}
    id_votes = {}                                       # (manual, category) -> id -> {label: files showing it}
    manual_names, info = {}, {}
    step_template = {}
    skip = {s.casefold() for s in skip}
    for name in sorted(os.listdir(folder), key=str.casefold):
        if not name.lower().endswith((".yaml", ".yml")) or name.casefold() in skip:
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as stream:
                raw = stream.read()
            if _PADDED_KEY.search(raw):                      # damaged or hand-numbered: not a reference
                continue
            data = _read(path)
        except (OSError, yaml.YAMLError):
            continue
        if not info and isinstance(data.get("info"), dict):
            info = dict(data["info"])
        for sequence in _entries(data.get("sequencer")).values():
            if not isinstance(sequence, dict):
                continue
            for manual_id, manual in _entries(sequence.get("manuals")).items():
                if not isinstance(manual, dict):
                    continue
                mid = int(manual_id)
                if manual.get("name"):
                    manual_names.setdefault(mid, str(manual["name"]))
                for category in CATEGORIES:
                    for oid, label in _entries(manual.get(category)).items():
                        seen.setdefault((mid, category), {}).setdefault(str(label), set()).add(int(oid))
                        votes = id_votes.setdefault((mid, category), {}).setdefault(int(oid), {})
                        votes[str(label)] = votes.get(str(label), 0) + 1
            for category in STEP_CATEGORIES:
                for oid, label in _entries(sequence.get(category)).items():
                    seen.setdefault(("step", category), {}).setdefault(str(label), set()).add(int(oid))
            if "switches" in sequence and not step_template:
                step_template = {int(k): str(v) for k, v in _entries(sequence["switches"]).items()}
    dictionary = {key: {label: next(iter(ids)) for label, ids in labels.items() if len(ids) == 1}
                  for key, labels in seen.items()}
    for key, labels in _ODF_LABELS.items():                  # the organ's full names fill in what no intact file shows
        target = dictionary.setdefault(key, {})
        for label, oid in labels.items():
            target.setdefault(label, oid)
    for key, labels in dictionary.items():                   # a label cut short by the old bridge is not a label: drop it when the same id has a longer one
        for label in [l for l in labels if len(l) >= 8 and any(o != l and o.startswith(l) and labels[o] == labels[l] for o in labels)]:
            del labels[label]
    offsets = {}                                       # switch id - stop id of the same label, per manual (3 / 2 / 1 / 0 in Friesach)
    for (mid, category), labels in dictionary.items():
        if category == "switches" and mid != "step":
            counts = {}
            for label, switch_id in labels.items():
                stop_id = dictionary.get((mid, "stops"), {}).get(label)
                if stop_id is not None:
                    counts[switch_id - stop_id] = counts.get(switch_id - stop_id, 0) + 1
            if counts:
                offsets[mid] = max(counts, key=lambda k: counts[k])
    by_id = {key: {oid: max(labels, key=lambda l: (labels[l], len(l))) for oid, labels in ids.items()}   # most files agree
             for key, ids in id_votes.items()}
    for key, labels in _ODF_LABELS.items():                  # the organ's own (real) names win
        by_id.setdefault(key, {}).update({oid: label for label, oid in labels.items()})
    return {"by_id": by_id, "ids": dictionary, "manual_names": manual_names, "info": info, "step_switches": step_template, "offsets": offsets}


def _always_on(dictionary, mid, category="stops"):
    """The 'Key action ...' stops of a manual: GrandOrgue records them in every step (the longest spelling of each id)."""
    found = {}
    for label, oid in dictionary["ids"].get((mid, category), {}).items():
        if label.startswith("Key action") and len(label) > len(found.get(oid, "")):
            found[oid] = label
    return found


def _complete(known, label, oid=None):
    """A label the old bridge cut short on the 16-character LCD ("Key action Manua") -> the full label of an intact file
    (the one with the same id when several begin alike)."""
    label = str(label)
    if label in known:
        return label
    longer = [k for k in known if k.startswith(label) and len(label) >= 8]
    if len(longer) > 1 and oid is not None:
        longer = [k for k in longer if known[k] == int(oid)] or longer
    return longer[0] if len(longer) == 1 else label


def _repair_step(sequence, dictionary, add_missing=True):
    """Fix ids by label and add what GrandOrgue expects. Returns the step as {text key: ...} with sorted, padded keys."""
    ids = dictionary["ids"]
    result = {}
    if "name" in sequence:
        result["name"] = sequence["name"]
    manuals = {}
    for manual_id, manual in _entries(sequence.get("manuals")).items():
        if not isinstance(manual, dict):
            continue
        mid = int(manual_id)
        fixed = {category: {} for category in CATEGORIES}
        for category in CATEGORIES:
            known = ids.get((mid, category), {})
            for oid, label in _entries(manual.get(category)).items():
                label = _complete(known, label, oid)
                fixed[category][known.get(label, int(oid))] = label
        if add_missing:
            for category in ("stops", "couplers"):                  # the stop / coupler entry next to a switch entry
                known = ids.get((mid, category), {})
                for switch_id, label in list(fixed["switches"].items()):
                    if label in known:
                        fixed[category].setdefault(known[label], label)
                    elif category == "stops" and mid in dictionary.get("offsets", {}) and not str(label).startswith("Coupler"):
                        fixed["stops"].setdefault(switch_id - dictionary["offsets"][mid], label)   # a label no intact file shows
            for oid, label in _always_on(dictionary, mid).items():
                fixed["stops"].setdefault(oid, label)
            known_switches = ids.get((mid, "switches"), {})          # a stop entry without its switch entry
            have = set(fixed["switches"].values())
            for stop_id, label in list(fixed["stops"].items()):
                if label.startswith("Key action") or label in have:
                    continue
                if label in known_switches:
                    fixed["switches"].setdefault(known_switches[label], label)
                elif mid in dictionary.get("offsets", {}):
                    fixed["switches"].setdefault(stop_id + dictionary["offsets"][mid], label)
        for category in CATEGORIES:                                 # GrandOrgue checks every entry against the organ's own name for that id
            names = dictionary.get("by_id", {}).get((mid, category), {})
            fixed[category] = {oid: names.get(oid, label) for oid, label in fixed[category].items()}
        entry = {}
        name = manual.get("name") or dictionary["manual_names"].get(mid)
        if name:
            entry["name"] = name
        for category in CATEGORIES:
            if fixed[category] or category in manual or (add_missing and category in ("stops", "switches")):
                entry[category] = {_pad(k): v for k, v in sorted(fixed[category].items())}
        manuals[_pad(mid)] = entry
    if add_missing:
        for mid, name in dictionary["manual_names"].items():       # every manual appears in every step, as in GrandOrgue's own files
            if _pad(mid) not in manuals:
                entry = {"name": name}
                keys = _always_on(dictionary, mid)
                if keys:
                    entry["stops"] = {_pad(k): v for k, v in sorted(keys.items())}
                entry["switches"] = {}
                manuals[_pad(mid)] = entry
    result["manuals"] = dict(sorted(manuals.items()))
    step_ids = {c: {} for c in STEP_CATEGORIES}
    for category in STEP_CATEGORIES:
        known = ids.get(("step", category), {})
        for oid, label in _entries(sequence.get(category)).items():
            label = _complete(known, label, oid)
            step_ids[category][known.get(label, int(oid))] = label
    if add_missing:
        for oid, label in dictionary["step_switches"].items():
            if label in ("Blower", "Ambient"):
                step_ids["switches"].setdefault(oid, label)
        known_trem = ids.get(("step", "tremulants"), {})
        for label in list(step_ids["switches"].values()):
            if label in known_trem:
                step_ids["tremulants"].setdefault(known_trem[label], label)
    names = dictionary.get("by_id", {}).get(("step", "switches"), {})
    step_ids["switches"] = {oid: names.get(oid, label) for oid, label in step_ids["switches"].items()}
    if step_ids["tremulants"]:
        result["tremulants"] = {_pad(k): v for k, v in sorted(step_ids["tremulants"].items())}
    result["switches"] = {_pad(k): v for k, v in sorted(step_ids["switches"].items())}
    return result


def canonical_data(data, dictionary, add_missing=True):
    """The whole file as plain, ordered, zero-padded data."""
    info = dict(data.get("info") or {})
    for key, value in (dictionary.get("info") or {}).items():
        if key in ("grandorgue-version",):
            info.setdefault(key, value)
    steps = {}
    for sid, sequence in _entries(data.get("sequencer")).items():
        if isinstance(sequence, dict):
            steps[_pad(sid)] = _repair_step(sequence, dictionary, add_missing)
    return {"info": info, "sequencer": dict(sorted(steps.items()))}


def dump_text(data):
    return "---\n" + yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)


def write_combination_file(path, data, folder=None):
    """Write one setter file in GrandOrgue's spelling, completing steps from the folder's intact files."""
    folder = folder or os.path.dirname(os.path.abspath(path))
    try:
        dictionary = label_dictionary(folder, skip=(os.path.basename(path),))
    except OSError:
        dictionary = {"ids": {}, "manual_names": {}, "info": {}, "step_switches": {}, "offsets": {}, "by_id": {}}
    text = dump_text(canonical_data(data, dictionary))
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def _short_labels(data, dictionary):
    """True when an entry carries a label GrandOrgue would reject: cut short (16-character LCD name) or not the organ's name for that id."""
    for sequence in _entries(data.get("sequencer")).values():
        if not isinstance(sequence, dict):
            continue
        groups = [(dictionary["ids"].get(("step", c), {}), _entries(sequence.get(c)),
                   dictionary.get("by_id", {}).get(("step", c), {})) for c in STEP_CATEGORIES]
        for manual_id, manual in _entries(sequence.get("manuals")).items():
            if isinstance(manual, dict):
                groups += [(dictionary["ids"].get((int(manual_id), c), {}), _entries(manual.get(c)),
                            dictionary.get("by_id", {}).get((int(manual_id), c), {})) for c in CATEGORIES]
        for known, entries, by_id in groups:
            for oid, label in entries.items():
                if str(label) not in known and _complete(known, label, oid) != str(label):
                    return True
                if by_id.get(int(oid), str(label)) != str(label):
                    return True
    return False


def damaged_files(folder, dictionary=None):
    """Files whose keys are not zero-padded text (written by the old bridge) or whose labels were cut short."""
    found = []
    for name in sorted(os.listdir(folder), key=str.casefold):
        if name.lower().endswith((".yaml", ".yml")):
            try:
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as stream:
                    if _PADDED_KEY.search(stream.read()):
                        found.append(name)
                    elif dictionary is not None and dictionary["ids"] and _short_labels(_read(path), dictionary):
                        found.append(name)
            except (OSError, yaml.YAMLError, ValueError):
                pass
    return found


def repair_folder_format(folder, log=None):
    """Rebuild damaged setter files by label. Silent and idempotent. Returns {"repaired": [names], "backup": path}."""
    result = {"repaired": [], "backup": ""}
    if not os.path.isdir(folder):
        return result
    dictionary = label_dictionary(folder)
    damaged = damaged_files(folder, dictionary)
    if not damaged:
        return result
    log = log or (lambda text: None)
    if not dictionary["ids"]:
        log("Setter repair skipped: no intact setter file to learn the ids from")
        return result
    parent = os.path.dirname(os.path.abspath(folder))
    backup = os.path.join(parent, "_backup", f"{os.path.basename(os.path.abspath(folder))}-format-"
                          f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
    try:
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        original, counter = backup, 2
        while os.path.exists(backup):                   # a second repair within the same second
            backup, counter = f"{original}-{counter}", counter + 1
        shutil.copytree(folder, backup)
        result["backup"] = backup
    except OSError as exc:
        log(f"Setter repair skipped: could not back up {folder} ({exc})")
        return result
    for name in damaged:
        path = os.path.join(folder, name)
        try:
            text = dump_text(canonical_data(_read(path), dictionary))
            with open(path, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            result["repaired"].append(name)
        except (OSError, yaml.YAMLError, ValueError) as exc:
            log(f"Setter repair: could not rebuild {name} ({exc})")
    return result
