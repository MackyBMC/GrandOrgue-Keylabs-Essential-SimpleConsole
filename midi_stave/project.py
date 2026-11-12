"""Stave Station project file (.ss): everything the stave editor needs to come back exactly as you left it.

A .ss file is plain YAML (open it in Notepad, edit it by hand). It holds the settings, bar lines, per-bar overrides, track and
manual mapping, setters, division labels, pedal marks, lyrics and - only when you edited notes in the piano roll - the edited notes.
It LINKS to the MIDI / MusicXML it was made from (relative to the .ss, plus the absolute path, size and SHA-1) instead of copying
it, so the MIDI can live anywhere and the project folder can be moved. No Qt in here: the editor does the widget work.

CHANGELOG
2026-11-12  New.
"""
import hashlib
import os
from fractions import Fraction

FORMAT = "stave-station-project"
VERSION = 1
EXT = ".ss"
HEADER = "# Stave Station project. Plain YAML: safe to edit by hand. The MIDI it links to is never changed.\n"


def default_path(media_path):
    """<name>.ss next to the MIDI / MusicXML file."""
    return os.path.splitext(media_path)[0] + EXT


def fingerprint(path):
    """{"size", "sha1"} of a file, or {} if it cannot be read."""
    try:
        digest = hashlib.sha1()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return {"size": os.path.getsize(path), "sha1": digest.hexdigest()}
    except OSError:
        return {}


def link_for(media_path, project_path):
    """The "midi" block: path relative to the project file (when it can be made), absolute path, size and hash."""
    block = {}
    if media_path:
        try:
            block["file"] = os.path.relpath(media_path, os.path.dirname(os.path.abspath(project_path))).replace("\\", "/")
        except ValueError:                                  # another drive on Windows: no relative path exists
            block["file"] = ""
        block["abs"] = os.path.abspath(media_path).replace("\\", "/")
        block.update(fingerprint(media_path))
    return block


def resolve_media(project_path, link):
    """Where the linked MIDI is now: relative to the project first, then the stored absolute path, else None."""
    link = link or {}
    here = os.path.dirname(os.path.abspath(project_path))
    for candidate in (os.path.normpath(os.path.join(here, link["file"])) if link.get("file") else None, link.get("abs")):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def media_changed(link, media_path):
    """True when the file on disk is not the one the project was saved against (size or hash differ)."""
    link = link or {}
    if not link.get("sha1"):
        return False
    return fingerprint(media_path).get("sha1") != link["sha1"]


# ----------------------------------------------------------------------------------------------- plain-data helpers
def plain(value):
    """Deep copy as YAML-safe plain data: tuples / sets -> lists, Fractions -> "1/8", dict keys -> str."""
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value) if isinstance(value, (set, frozenset)) else value
        return [plain(v) for v in items]
    if isinstance(value, float):
        return round(value, 6)
    return value


def key_text(key):
    return f"{int(key[0])}:{int(key[1])}"


def key_parse(text):
    a, b = str(text).split(":")
    return int(a), int(b)


def grid_text(value):
    return "t" if value == "t" else str(Fraction(value))


def grid_parse(value):
    return "t" if str(value) == "t" else Fraction(str(value))


# ------------------------------------------------------------------------------------------------------- file i/o
def save(path, data):
    """Write atomically (temp file, then replace) and keep the previous version as <path>.bak. Raises OSError."""
    import yaml

    class Dumper(yaml.SafeDumper):                          # block layout; a list of plain values stays on one line
        pass
    Dumper.add_representer(list, lambda d, v: d.represent_sequence("tag:yaml.org,2002:seq", v, flow_style=not any(isinstance(x, (dict, list)) for x in v)))
    body = HEADER + yaml.dump(plain(dict(data, format=FORMAT, version=VERSION)), Dumper=Dumper, sort_keys=False, allow_unicode=True,
                              default_flow_style=False, width=10000)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    if os.path.isfile(path):
        try:
            os.replace(path, path + ".bak")
        except OSError:
            pass
    os.replace(tmp, path)


def load(path):
    """-> dict, or None when the file is missing / not a stave project. Reads the .bak when the file itself is damaged."""
    import yaml
    for candidate in (path, path + ".bak"):
        try:
            with open(candidate, encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict) and data.get("format") == FORMAT:
            return data
    return None
