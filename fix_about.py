"""Makes Help > About import COPYRIGHT (the first copyright script could add the use but miss the import on a tree that differs).
Run from the repo root: python fix_about.py   (safe to run twice)

CHANGELOG
2026-11-22  New.
"""
import re

path = "qt_gui.py"
with open(path, encoding="utf-8", newline="") as handle:
    s = handle.read()
eol = "\r\n" if "\r\n" in s else "\n"
match = re.search(r"    def show_about\(self\):\r?\n", s)
if not match:
    print("show_about not found")
else:
    end = s.find("\n    def ", match.end())
    body = s[match.end():end if end > 0 else len(s)]
    if re.search(r"^\s+from version import .*\bCOPYRIGHT\b", body, re.M):
        print("Already imports COPYRIGHT; nothing changed. If About is still empty, send the console error.")
    else:
        s = s[:match.end()] + "        from version import COPYRIGHT" + eol + s[match.end():]
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(s)
        print("Added the COPYRIGHT import to show_about.")
