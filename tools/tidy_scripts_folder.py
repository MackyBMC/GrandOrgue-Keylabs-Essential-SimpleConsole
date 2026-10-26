"""Sort out the GrandOrgue user folder: find what the bridge app really needs and move the rest into an archive folder.

    python tools/tidy_scripts_folder.py "H:\\Users\\bmche\\Documents\\GrandOrgue\\Scripts"          (dry run: only prints the plan)
    python tools/tidy_scripts_folder.py "H:\\Users\\bmche\\Documents\\GrandOrgue\\Scripts" --apply  (moves; nothing is ever deleted)

NEEDED = every .py file reachable by imports from the entry points (keylab_go_bridge.py, midi_stave/stave_station.py), plus
config / data files by name or extension. Everything else (test scripts, dumps, screenshots, .pyc, old .bat) goes to
_archive/<date>/ keeping its relative path, so any move can be undone by dragging it back.
Your GrandOrgue data (Organs, Settings, Combinations, Cache...) is never touched: only the folder you pass in is scanned and
only the top-level names in KEEP_FOLDERS are protected inside it.
"""
import argparse
import ast
import datetime
import os
import shutil

ENTRY = ("keylab_go_bridge.py", os.path.join("midi_stave", "stave_station.py"))
KEEP_FILES = {"config.yaml", "window_layout.json", "README.md", "LICENSE", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md",
              "requirements.txt", "requirements-build.txt", "version.py", "start_stave_station.bat", ".gitignore"}
KEEP_FOLDERS = {"Combinations", "midi", "takes", "Takes", "packaging", "tools", "docs", ".github", "assets", "themes", "_archive", ".git"}
KEEP_EXT = {".yaml", ".yml", ".json", ".ico", ".icns", ".md", ".iss", ".ps1", ".sh"}
JUNK_DIRS = {"__pycache__", ".pytest_cache", ".venv-build", "build", "dist"}


def modules_in(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names |= {f"{base}.{a.name}".strip(".") for a in node.names}
            if node.level:                                   # relative import inside a package: resolve against the file's folder
                names.add(("." * node.level) + base)
    return names


def resolve(name, here, root):
    """Local file for an imported module name, or None."""
    dots = len(name) - len(name.lstrip("."))
    bare = name.lstrip(".").replace(".", os.sep)
    folders = [here] if dots else [root, os.path.join(root, "midi_stave"), here]
    for folder in folders:
        for candidate in (bare + ".py", os.path.join(bare, "__init__.py")):
            full = os.path.join(folder, candidate)
            if bare and os.path.isfile(full):
                return full
    return None


def needed_python(root):
    seen, queue = set(), [os.path.join(root, e) for e in ENTRY if os.path.isfile(os.path.join(root, e))]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        folder = os.path.dirname(path)
        init = os.path.join(folder, "__init__.py")
        if os.path.isfile(init):
            queue.append(init)
        for name in modules_in(path):
            hit = resolve(name, folder, root)
            if hit:
                queue.append(hit)
    return seen


def plan(root):
    keep = needed_python(root)
    move = []
    for folder, dirs, files in os.walk(root):
        rel = os.path.relpath(folder, root)
        top = rel.split(os.sep)[0]
        if top in KEEP_FOLDERS and top != ".":
            dirs[:] = []
            continue
        for d in list(dirs):
            if d in JUNK_DIRS:
                move.append(os.path.join(folder, d))
                dirs.remove(d)
        for f in files:
            full = os.path.join(folder, f)
            ext = os.path.splitext(f)[1].lower()
            if full in keep or f in KEEP_FILES:
                continue
            if ext in KEEP_EXT and ext != ".json" or (ext == ".json" and f in KEEP_FILES):
                continue
            move.append(full)
    return sorted(keep), sorted(move)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--list-needed", action="store_true", help="print needed program files (relative paths) and exit")
    a = ap.parse_args()
    root = os.path.abspath(a.folder)
    keep, move = plan(root)
    if a.list_needed:
        for k in keep:
            print(os.path.relpath(k, root))
        for pkg in {os.path.dirname(k) for k in keep}:
            pass
        return
    print(f"{len(keep)} program files are needed; {len(move)} items are not.\n")
    for path in move:
        print("  archive:", os.path.relpath(path, root))
    if not a.apply:
        print("\nDry run. Add --apply to move them.")
        return
    stamp = os.path.join(root, "_archive", datetime.date.today().isoformat())
    for path in move:
        target = os.path.join(stamp, os.path.relpath(path, root))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(path, target)
    print(f"\nMoved to {stamp}")


if __name__ == "__main__":
    main()
