"""Finds a picture of the organ for the Organ Setter Wiki: the first panel / case image an ODF (.organ) file refers to.

CHANGELOG
2026-11-22  New: organ_image().
"""
import os
import re

_KEY = re.compile(r"^\s*(?:Image|Bitmap|PanelImage|DispImage\w*)\s*=\s*(.+?)\s*$", re.I)
_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
_HINT = re.compile(r"facade|fa[cç]ade|front|case|church|exterior|organ|pipes|console|overview", re.I)


def _resolve(folder, name):
    name = name.strip().strip('"').replace("\\", "/")
    if not name.lower().endswith(_EXT):
        return ""
    path = os.path.normpath(os.path.join(folder, name))
    if os.path.isfile(path):
        return path
    parent, leaf = os.path.split(path)                       # ODFs often differ in letter case from the files on disk
    try:
        for entry in os.listdir(parent):
            if entry.casefold() == leaf.casefold():
                return os.path.join(parent, entry)
    except OSError:
        pass
    return ""


def organ_image(organ_path):
    """Path of the best picture next to the organ definition, or "" when there is none."""
    if not organ_path or not os.path.isfile(organ_path):
        return ""
    folder = os.path.dirname(organ_path)
    found = []
    try:
        with open(organ_path, "rb") as handle:
            text = handle.read().decode("utf-8", "replace") if os.path.getsize(organ_path) < 40_000_000 else ""
    except OSError:
        return ""
    for line in text.splitlines():
        match = _KEY.match(line)
        if match:
            path = _resolve(folder, match.group(1))
            if path and path not in found:
                found.append(path)
    for path in found:
        if _HINT.search(os.path.basename(path)):
            return path
    return found[0] if found else ""
