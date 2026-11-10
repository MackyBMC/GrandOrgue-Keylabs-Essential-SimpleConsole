"""Dev tool: checks that every library the program needs imports properly in THIS Python (the venv you run it with), and
can reinstall the broken ones.  Usage (from the repo or the deployed Scripts folder):
    .venv-build\\Scripts\\python.exe tools\\check_env.py          # report
    .venv-build\\Scripts\\python.exe tools\\check_env.py --fix    # force-reinstall whatever fails

CHANGELOG
2026-11-10  New: catches half-installed packages (e.g. "No module named 'music21.midi'", a pip with a missing vendor folder).
"""
import importlib
import subprocess
import sys

# (import name, pip package, required)
CHECKS = [
    ("mido", "mido", True), ("rtmidi", "python-rtmidi", True), ("yaml", "PyYAML", True), ("PySide6.QtWidgets", "PySide6", True),
    ("PySide6.QtPdf", "PySide6", True), ("textual", "textual", True), ("qtawesome", "qtawesome", False),
    ("numpy", "numpy", True), ("music21", "music21", True), ("music21.midi", "music21", True), ("music21.stream", "music21", True),
    ("verovio", "verovio", True), ("packaging.version", "packaging", True), ("pip", "pip", True),
    ("pyaudiowpatch", "PyAudioWPatch", False),
]


def main():
    fix = "--fix" in sys.argv
    print(f"Python {sys.version.split()[0]}  ({sys.executable})")
    broken = {}
    for module, package, required in CHECKS:
        try:
            importlib.import_module(module)
            print(f"  ok       {module}")
        except Exception as exc:
            tag = "MISSING " if required else "optional"
            print(f"  {tag} {module}: {exc}")
            if required:
                broken.setdefault(package, []).append(module)
    if not broken:
        print("All required libraries import.")
        return 0
    packages = sorted(broken)
    print("\nBroken / missing packages:", ", ".join(packages))
    cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-cache-dir", *packages]
    if not fix:
        print("Fix with:  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        print("or run this tool again with --fix. If pip itself is broken, recreate the venv (see below).")
        print("  py -3.13 -m venv .venv-build   then   .venv-build\\Scripts\\python.exe -m pip install -r requirements.txt")
        return 1
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
