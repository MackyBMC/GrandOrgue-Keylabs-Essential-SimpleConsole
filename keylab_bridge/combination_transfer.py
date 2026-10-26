"""Copy GrandOrgue combination structure while resolving objects for another organ."""

import difflib
import os
import re
import unicodedata


MANUAL_CATEGORIES = ("stops", "switches", "couplers")
NOISE_NAME = re.compile(r"\bstop\s+(?:attack|release)\s+noise\b", re.I)


def _name_key(value):
    value = unicodedata.normalize("NFKD", str(value).casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _manual_key(value):
    return re.sub(r"^\d+\s*", "", _name_key(value)).strip()


def _object_key(value):
    return re.sub(r"^(?:p|hw|sw|sl)\s+", "", _name_key(value))


def _alias_value(mapping, source_name):
    source_key = _name_key(source_name)
    for name, target in (mapping or {}).items():
        if _name_key(name) == source_key and str(target).strip():
            return str(target).strip()
    return ""


def _match_name(source_name, targets, aliases=None, manual=False):
    alias = _alias_value(aliases, source_name)
    wanted = _manual_key(alias or source_name) if manual else _name_key(alias or source_name)
    if not wanted:
        return None, "empty name"
    target_key = _manual_key if manual else _name_key
    keyed = [target for target in targets if target_key(target["name"]) == wanted]
    if not manual and not keyed:
        source_object_key = _object_key(alias or source_name)
        keyed = [target for target in targets if _object_key(target["name"]) == source_object_key]
    if len(keyed) == 1:
        return keyed[0], "alias" if alias else "exact"
    if len(keyed) > 1:
        return None, "ambiguous exact match"
    if alias:
        return None, f"alias target not found: {alias}"

    score_key = _manual_key if manual else _object_key
    threshold = 0.92 if manual else 0.84
    scored = sorted(
        ((difflib.SequenceMatcher(None, wanted, score_key(target["name"])).ratio(), target)
         for target in targets), key=lambda result: result[0], reverse=True,
    )
    if not scored or scored[0][0] < threshold:
        return None, "no close title match"
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.08:
        return None, "ambiguous close title match"
    return scored[0][1], "heuristic"


def _target_manual_items(manual, category):
    items = manual.get(category) or []
    if category == "stops":
        items = [item for item in items if not NOISE_NAME.search(item.get("name", ""))]
    return [{"index": item["index"], "name": item["name"]} for item in items]


def _manual_alias(aliases, source_name):
    source_key = _manual_key(source_name)
    for name, value in (aliases.get("manuals") or {}).items():
        if _manual_key(name) == source_key:
            return value if isinstance(value, dict) else {"target-manual": value}
    return {}


def _record_unmatched(report, filename, step_id, division, category, name, reason):
    report["unmatched"].append({
        "file": filename, "step": step_id, "division": division,
        "category": category, "name": str(name), "reason": reason,
    })


def _translate_sequence(sequence, filename, step_id, target_profile, aliases, report):
    translated = dict(sequence)
    manuals_by_name = {}
    for manual in target_profile.get("manuals", []):
        manuals_by_name.setdefault(_manual_key(manual["name"]), []).append(manual)

    target_manuals = {}
    for source_manual_id, source_manual in (sequence.get("manuals") or {}).items():
        source_name = str(source_manual.get("name") or f"Manual {source_manual_id}")
        alias_entry = _manual_alias(aliases, source_name)
        manual_alias = alias_entry.get("target-manual") or alias_entry.get("target")
        if manual_alias:
            target_manual, reason = _match_name(
                source_name, [{"name": candidate["name"], "manual": candidate}
                              for candidate in target_profile.get("manuals", [])
                              if _manual_key(candidate["name"]) == _manual_key(manual_alias)],
                manual=True,
            )
        else:
            candidates = manuals_by_name.get(_manual_key(source_name), [])
            if len(candidates) == 1:
                target_manual, reason = candidates[0], "exact"
            elif len(candidates) > 1:
                target_manual, reason = None, "ambiguous manual name"
            else:
                target_manual, reason = _match_name(
                    source_name,
                    [{"name": manual["name"], "manual": manual}
                     for manual in target_profile.get("manuals", [])],
                    manual=True,
                )
        if target_manual is None:
            _record_unmatched(report, filename, step_id, source_name, "manuals", source_name, reason)
            continue
        if "manual" in target_manual:
            target_manual = target_manual["manual"]
        target_id = int(target_manual["number"])
        if target_id in target_manuals:
            _record_unmatched(report, filename, step_id, source_name, "manuals", source_name,
                              "multiple source manuals map to one target manual")
            continue

        translated_manual = {"name": target_manual["name"]}
        for category in MANUAL_CATEGORIES:
            source_items = source_manual.get(category) or {}
            if not isinstance(source_items, dict):
                continue
            candidates = _target_manual_items(target_manual, category)
            category_aliases = alias_entry.get(category) or {}
            mapped_items = {}
            for source_name_value in source_items.values():
                source_item_name = str(source_name_value)
                target_item, match_type = _match_name(source_item_name, candidates, category_aliases)
                if target_item is None:
                    _record_unmatched(report, filename, step_id, source_name, category,
                                      source_item_name, match_type)
                    continue
                target_item_id = int(target_item["index"])
                if target_item_id in mapped_items:
                    _record_unmatched(report, filename, step_id, source_name, category,
                                      source_item_name, "multiple source entries map to one target object")
                    continue
                mapped_items[target_item_id] = target_item["name"]
                report["matched_objects"] += 1
                if match_type == "heuristic":
                    report["heuristic_matches"] += 1
            if mapped_items:
                translated_manual[category] = mapped_items
        for field, value in source_manual.items():
            if field not in ("name", *MANUAL_CATEGORIES) and value:
                _record_unmatched(report, filename, step_id, source_name, field, "", "unsupported manual object category")
        target_manuals[target_id] = translated_manual
    if sequence.get("manuals") is not None:
        translated["manuals"] = target_manuals

    if isinstance(sequence.get("switches"), dict):
        global_targets = [{"index": int(identifier), "name": name}
                          for identifier, name in (target_profile.get("global_switches") or {}).items()]
        global_aliases = aliases.get("global-switches") or {}
        mapped_globals = {}
        for name in sequence["switches"].values():
            target_switch, match_type = _match_name(str(name), global_targets, global_aliases)
            if target_switch is None:
                _record_unmatched(report, filename, step_id, "", "global switches", name, match_type)
                continue
            mapped_globals[target_switch["index"]] = target_switch["name"]
            report["matched_objects"] += 1
            if match_type == "heuristic":
                report["heuristic_matches"] += 1
        translated["switches"] = mapped_globals
    return translated


def transfer_combinations(source_folder, target_folder, target_profile, aliases=None):
    """Copy combination files with target-organ object IDs/names; never overwrite a populated target."""
    import yaml

    report = {"files": 0, "steps": 0, "matched_objects": 0, "heuristic_matches": 0,
              "unmatched": [], "status": "ok"}
    if not os.path.isdir(source_folder):
        report["status"] = "source-missing"
        return report
    if os.path.isdir(target_folder) and _contains_combinations(target_folder):
        report["status"] = "target-not-empty"
        return report

    documents = []
    for filename in sorted(os.listdir(source_folder), key=str.casefold):
        if not filename.lower().endswith((".yaml", ".yml")):
            continue
        try:
            with open(os.path.join(source_folder, filename), encoding="utf-8") as source_file:
                data = yaml.safe_load(source_file) or {}
        except (OSError, yaml.YAMLError):
            continue
        info = data.get("info") or {}
        if str(info.get("content-type", "")).casefold() != "grandorgue combinations":
            continue
        sequences = data.get("sequencer") or {}
        if not isinstance(sequences, dict):
            continue
        seen_ids = set()
        translated_sequences = {}
        for internal_id, sequence in sequences.items():
            try:
                normalized_id = f"{int(internal_id):03d}"
            except (TypeError, ValueError):
                continue
            if normalized_id in seen_ids or not isinstance(sequence, dict):
                continue
            seen_ids.add(normalized_id)
            translated_sequences[int(normalized_id)] = _translate_sequence(
                sequence, filename, normalized_id, target_profile, aliases or {}, report,
            )
            report["steps"] += 1
        data["sequencer"] = translated_sequences
        info["organ-name"] = target_profile.get("name", "")
        data["info"] = info
        documents.append((filename, data))

    if not documents:
        report["status"] = "no-source-combinations"
        return report
    os.makedirs(target_folder, exist_ok=True)
    for filename, data in documents:
        path = os.path.join(target_folder, filename)
        with open(path, "w", encoding="utf-8") as target_file:
            yaml.safe_dump(data, target_file, sort_keys=False, allow_unicode=True, default_flow_style=False)
        report["files"] += 1
    return report


def _contains_combinations(folder):
    import yaml

    if not os.path.isdir(folder):
        return False
    for filename in os.listdir(folder):
        if not filename.lower().endswith((".yaml", ".yml")):
            continue
        try:
            with open(os.path.join(folder, filename), encoding="utf-8") as candidate_file:
                data = yaml.safe_load(candidate_file) or {}
        except (OSError, yaml.YAMLError):
            continue
        info = data.get("info") or {}
        if str(info.get("content-type", "")).casefold() == "grandorgue combinations":
            return True
    return False


def load_transfer_aliases(path):
    import yaml

    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as alias_file:
        data = yaml.safe_load(alias_file) or {}
    if not isinstance(data, dict):
        raise ValueError("combination alias file must contain a YAML mapping")
    return data


def write_transfer_alias_template(path, source_set):
    import yaml

    if os.path.exists(path):
        return
    template = {
        "source-combination-set": source_set,
        "manuals": {},
        "global-switches": {},
    }
    with open(path, "w", encoding="utf-8") as alias_file:
        yaml.safe_dump(template, alias_file, sort_keys=False, allow_unicode=True, default_flow_style=False)