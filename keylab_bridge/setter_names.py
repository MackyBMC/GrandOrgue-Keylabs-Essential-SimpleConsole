"""GrandOrgue-safe setter file names and the names matrix (multilingual display names).

GrandOrgue sends the current setter file name as a 7-bit text label cut at 32 characters ("Récit doux" arrives as
"R_cit doux"). So the bridge never trusts label text: every setter file has an ASCII-safe stem of at most 32 characters
(the GrandOrgue name) and the nice, possibly accented or multilingual, name lives in the names matrix
(Settings/<organ>.names.yaml). Older setter folders are repaired silently when they are loaded.

CHANGELOG
2026-11-20  New: safe_stem(), name_problems(), repair_folder() (backs the folder up, renames files, records the original names and the old file
            names in the matrix), load_matrix(), file_names(), canonical_filename().
"""

import datetime
import os
import re
import shutil
import unicodedata

LABEL_WIDTH = 32                                    # GrandOrgue's file-name label is 32 characters wide
_EXTRA = {"ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L"}
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _ascii(text):
    text = "".join(_EXTRA.get(c, c) for c in str(text))
    folded = unicodedata.normalize("NFKD", text)
    return "".join(c for c in folded if ord(c) < 128)


def _shorten(text, width):
    """Cut at `width`; do not leave a half-open bracket or a dangling separator."""
    if len(text) <= width:
        return text
    cut = text[:width]
    if text[width] != " " and " " in cut and cut.rindex(" ") >= width * 0.6:
        cut = cut[:cut.rindex(" ")]                      # end on a whole word
    cut = cut.rstrip(" -.,;:")
    if cut.count("(") > cut.count(")"):
        cut = cut[:cut.rindex("(")].rstrip(" -.,;:")
    return cut or text[:width]


def safe_stem(stem, taken=()):
    """ASCII-safe, at most 32 characters, unique among `taken` (case-insensitive)."""
    base = _ILLEGAL.sub("-", _ascii(stem))
    base = " ".join(base.split()).strip(". ")
    base = _shorten(base, LABEL_WIDTH) or "Setter"
    used = {t.casefold() for t in taken}
    candidate, counter = base, 2
    while candidate.casefold() in used:
        suffix = f" {counter}"
        candidate = _shorten(base, LABEL_WIDTH - len(suffix)) + suffix
        counter += 1
    return candidate


def stem_problems(stem):
    """Why GrandOrgue would mangle this file stem (empty list = fine)."""
    problems = []
    if any(ord(c) > 127 for c in stem):
        problems.append("non-ASCII letters")
    if len(stem) > LABEL_WIDTH:
        problems.append(f"longer than {LABEL_WIDTH} characters")
    if _ILLEGAL.search(stem):
        problems.append("illegal characters")
    return problems


def name_problems(folder):
    """{file name: [problems]} for a setter folder."""
    found = {}
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder), key=str.casefold):
            if name.lower().endswith((".yaml", ".yml")):
                problems = stem_problems(os.path.splitext(name)[0])
                if problems:
                    found[name] = problems
    return found


def matrix_path(root, set_name):
    return os.path.join(root, "Settings", f"{set_name}.names.yaml")


def load_matrix(path):
    """{"setters": {stem: {"display": {lang: name}, "aliases": [old file names]}}}; empty when missing or unreadable."""
    try:
        import yaml
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return {"setters": {}}
    setters = data.get("setters") if isinstance(data, dict) else None
    return {"organ": data.get("organ", "") if isinstance(data, dict) else "",
            "setters": {str(k): v for k, v in (setters or {}).items() if isinstance(v, dict)}}


def save_matrix(path, matrix, organ=""):
    import yaml
    os.makedirs(os.path.dirname(path), exist_ok=True)
    document = {"organ": organ or matrix.get("organ", ""), "setters": matrix.get("setters", {})}
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# Names matrix: GrandOrgue-safe setter file names (the keys) and the names shown in the bridge.\n"
                     "# Add languages under display: (for example en, de, af). 'default' is used when a language is missing.\n")
        yaml.safe_dump(document, handle, sort_keys=True, allow_unicode=True, default_flow_style=False)


def file_names(matrix, filename):
    """{language: display name} for a setter file name (always has 'default')."""
    stem = os.path.splitext(filename)[0]
    names = dict((matrix.get("setters", {}).get(stem) or {}).get("display") or {})
    names.setdefault("default", stem)
    return names


def canonical_filename(matrix, filename):
    """A file name recorded before a repair (a saved MIDI marker or project) -> the file name it has now."""
    wanted = str(filename).casefold()
    for stem, entry in matrix.get("setters", {}).items():
        for old in entry.get("aliases") or []:
            if str(old).casefold() == wanted:
                return stem + os.path.splitext(filename)[1]
    return filename


def repair_folder(folder, matrix_file, organ="", log=None):
    """Rename setter files GrandOrgue would mangle. Silent and idempotent: a folder that is fine is not touched.
    The folder is copied to Combinations/_backup first; the original names go into the names matrix.
    Returns {"renamed": [(old, new)], "backup": path or ""}."""
    result = {"renamed": [], "backup": ""}
    problems = name_problems(folder)
    if not problems:
        return result
    log = log or (lambda text: None)
    parent = os.path.dirname(os.path.abspath(folder))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(parent, "_backup", f"{os.path.basename(os.path.abspath(folder))}-{stamp}")
    try:
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        original, counter = backup, 2
        while os.path.exists(backup):                   # a second repair within the same second
            backup, counter = f"{original}-{counter}", counter + 1
        shutil.copytree(folder, backup)
        result["backup"] = backup
    except OSError as exc:
        log(f"Setter name repair skipped: could not back up {folder} ({exc})")
        return result
    existing = [os.path.splitext(n)[0] for n in os.listdir(folder) if n.lower().endswith((".yaml", ".yml"))]
    taken = list(existing)
    matrix = load_matrix(matrix_file)
    entries = matrix.setdefault("setters", {})
    for name in sorted(problems, key=str.casefold):
        stem, extension = os.path.splitext(name)
        taken.remove(stem)
        new_stem = safe_stem(stem, taken)
        taken.append(new_stem)
        try:
            os.replace(os.path.join(folder, name), os.path.join(folder, new_stem + extension))
        except OSError as exc:                         # e.g. GrandOrgue has the file open: try again next start
            log(f"Setter name repair: could not rename {name} ({exc})")
            taken.remove(new_stem)
            taken.append(stem)
            continue
        entry = entries.setdefault(new_stem, {})
        entry.setdefault("display", {}).setdefault("default", stem)
        aliases = entry.setdefault("aliases", [])
        if name not in aliases:
            aliases.append(name)
        result["renamed"].append((name, new_stem + extension))
    if result["renamed"]:
        try:
            save_matrix(matrix_file, matrix, organ)
        except OSError as exc:
            log(f"Setter name repair: could not write the names matrix ({exc})")
    return result
