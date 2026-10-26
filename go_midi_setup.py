"""One place that keeps GrandOrgue's MIDI settings in step with the bridge.

GrandOrgue only obeys the bridge (commands, stops, volumes) and only plays MIDI-file notes on the manual channels because
of a MIDI-settings file you import once. Whenever the bridge changes what it needs (manual channels, organ layout, new
commands) that file must be regenerated and imported again. This module does the regenerating and notices when it is
out of date; GrandOrgue itself has no way to import settings from outside, so the import is the one manual click.

    1. In GrandOrgue export your MIDI settings (Organ settings > Export), or point this at an export once.
    2. The bridge writes "<name> midi import.yaml" next to it - automatically when it notices a change.
    3. In GrandOrgue: Import that file.

CHANGELOG
2026-10-24  GrandOrgue user folder is detected (config.yaml go_user_dir, else the folder above Scripts), not assumed under C:.
2026-10-24  New: automatic regeneration + stale check (GUI button "GrandOrgue MIDI setup").
"""
import contextlib
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "go_setup.json")


def _load():
    try:
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _save(data):
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)


def user_dir():
    """GrandOrgue's user folder. Not always under C:\\Users: here it is H:\\Users\\bmche\\Documents\\GrandOrgue.
    Order: config.yaml 'go_user_dir' (the future install script writes this) > the folder holding Scripts > Documents."""
    try:
        import yaml
        with open(os.path.join(HERE, "config.yaml"), encoding="utf-8") as handle:
            configured = (yaml.safe_load(handle) or {}).get("go_user_dir")
        if configured and os.path.isdir(configured):
            return configured
    except Exception:
        pass
    parent = os.path.dirname(HERE)
    if os.path.basename(HERE).lower() == "scripts" and os.path.isdir(os.path.join(parent, "Settings")):
        return parent
    return os.path.join(os.path.expanduser("~"), "Documents", "GrandOrgue")


def default_folder():
    saved = _load().get("folder")
    if saved and os.path.isdir(saved):
        return saved
    settings = os.path.join(user_dir(), "Settings")
    return settings if os.path.isdir(settings) else user_dir()


def is_import_file(name):
    return name.casefold().endswith("midi import.yaml") or name.casefold().endswith("midi import.yml")


def find_source(folder=None):
    """The newest GrandOrgue MIDI-settings export in the folder (never one of our own import files)."""
    folder = folder or default_folder()
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith((".yaml", ".yml")) and not is_import_file(f)]
    except OSError:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def fingerprint():
    """Everything the generated file depends on: manual channels, command / volume tables, organ controls."""
    sys.path.insert(0, os.path.join(HERE, "midi_stave"))
    import sessionmeta
    import keylab_go_bridge as kb
    blob = json.dumps([sessionmeta.manual_channels(), sorted(kb.CMD.items()), sorted(kb.VOLS), len(kb.ITEMS),
                       [(i.path, i.cc) for i in kb.ITEMS]], default=str, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


def output_for(src):
    stem = os.path.splitext(os.path.basename(src))[0]
    for tail in (" midi import", "-KeyLab"):
        if stem.endswith(tail):
            stem = stem[: -len(tail)]
    return os.path.join(os.path.dirname(src), stem + " midi import.yaml")


def build(src=None):
    """Write the import file. Returns (output path, text of what was done)."""
    import make_go_midi_import
    src = src or _load().get("source") or find_source()
    if not src or not os.path.isfile(src):
        raise FileNotFoundError("No GrandOrgue MIDI-settings export found. Export one from GrandOrgue first.")
    dst = output_for(src)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        make_go_midi_import.main(src, dst)
    state = _load()
    state.update({"source": src, "output": dst, "folder": os.path.dirname(src), "fingerprint": fingerprint()})
    _save(state)
    return dst, log.getvalue().strip()


def status():
    """('none' | 'ok' | 'stale', message): is the import file you last made still what the bridge needs?"""
    state = _load()
    if not state.get("source"):
        return "none", "Not set up yet: export your MIDI settings from GrandOrgue, then choose that file."
    try:
        current = fingerprint()
    except Exception as exc:
        return "none", f"Could not check ({exc})"
    if state.get("fingerprint") != current:
        return "stale", "The bridge needs different GrandOrgue MIDI settings than the last file made. Create and import a new one."
    return "ok", f"Up to date: {os.path.basename(state.get('output', ''))}"


def refresh_if_stale():
    """Called when the bridge starts: regenerate the file when it is out of date. Returns a message or None."""
    kind, _text = status()
    if kind != "stale":
        return None
    try:
        dst, _ = build()
        return f"GrandOrgue MIDI settings changed - new file written: {dst}. Import it in GrandOrgue."
    except Exception as exc:
        return f"GrandOrgue MIDI settings need refreshing but the file could not be made: {exc}"
