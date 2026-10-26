"""Remembers the last folder of each file dialog between sessions (last_dirs.json next to the scripts).

CHANGELOG
2026-10-24  New.
"""
import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_dirs.json")


def get(key, default=""):
    try:
        with open(_FILE, encoding="utf-8") as handle:
            folder = json.load(handle).get(key)
        if folder and os.path.isdir(folder):
            return folder
    except (OSError, ValueError):
        pass
    return default


def put(key, path):
    """Remember the folder of a chosen file (or a folder itself)."""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    try:
        try:
            with open(_FILE, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            data = {}
        data[key] = folder
        with open(_FILE, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
    except OSError:
        pass
