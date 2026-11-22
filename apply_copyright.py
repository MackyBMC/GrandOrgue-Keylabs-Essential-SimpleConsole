"""Puts "Basil Mc Helm" in as copyright holder wherever the app shows or embeds one. Safe to run twice; it edits by text, not by line number,
so it works on a tree that differs from the one the patches were built on.

Usage (repo root):  python apply_copyright.py

CHANGELOG
2026-11-22  New.
"""
import os
import re
import sys

ROOT = os.getcwd()
AUTHOR = "Basil Mc Helm"
done, skipped = [], []


def rw(path, fn):
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        skipped.append(f"{path}: file not found")
        return
    with open(full, encoding="utf-8", newline="") as handle:
        old = handle.read()
    new = fn(old)
    if new == old:
        skipped.append(f"{path}: nothing to change (already done, or text not found)")
        return
    with open(full, "w", encoding="utf-8", newline="") as handle:
        handle.write(new)
    done.append(path)


def license_(s):
    return re.sub(r"Copyright \(c\) 2026 MackyBMC\b(?! \()", f"Copyright (c) 2026 {AUTHOR} (GitHub: MackyBMC)", s)


def installer(s):
    return s.replace("AppPublisher=MackyBMC", f"AppPublisher={AUTHOR}")


def version(s):
    if "COPYRIGHT" in s:
        return s
    eol = "\r\n" if "\r\n" in s else "\n"
    return re.sub(r'^(APP_NAME = .*)$', lambda m: m.group(1) + eol + f'AUTHOR = "{AUTHOR}"' + eol +
                  'COPYRIGHT = f"Copyright (c) 2026 {AUTHOR}"', s, count=1, flags=re.M)


def nuitka(s):
    if "COPYRIGHT" in s:
        return s
    s = re.sub(r"from version import ([^\r\n#]*?)(\s*#.*)?$",
               lambda m: f"from version import {m.group(1)}, COPYRIGHT{m.group(2) or ''}", s, count=1, flags=re.M)
    return s.replace('"--company-name=MackyBMC",', f'"--company-name={AUTHOR}",\n    f"--copyright={{COPYRIGHT}}",')


def gui(s):
    if "COPYRIGHT" in s:
        return s
    s = s.replace("        from version import APP_VERSION\n        ask = QMessageBox(self)\n        ask.setWindowTitle(\"About\")",
                  "        from version import APP_VERSION, COPYRIGHT\n        ask = QMessageBox(self)\n        ask.setWindowTitle(\"About\")", 1)
    return s.replace('"Application code: MIT License.<br><br>"',
                     "f\"&copy; {COPYRIGHT.split('(c) ', 1)[-1]}. Application code: MIT License.<br><br>\"", 1)


def readme(s):
    a = "This project is MIT licensed; see [LICENSE](LICENSE)."
    return s if f"Copyright (c) 2026 {AUTHOR}" in s else s.replace(a, f"Copyright (c) 2026 {AUTHOR} (GitHub: MackyBMC). " + a, 1)


def changelog(s):
    line = f"- Copyright: {AUTHOR} is named as the copyright holder in LICENSE, Help > About, the README, the Windows executable properties and the installer publisher.\n"
    if "- Copyright:" in s:
        return s
    return s.replace("### New\n", "### New\n" + line, 1)


rw("LICENSE", license_)
rw("packaging/installer.iss", installer)
rw("version.py", version)
rw("packaging/nuitka_build.py", nuitka)
rw("qt_gui.py", gui)
rw("README.md", readme)
rw("CHANGELOG.md", changelog)
print("Changed:", ", ".join(done) or "nothing")
for line in skipped:
    print("Skipped:", line)
sys.exit(0)
