"""Organ Setter Wiki: hides the empty PAD MAP strip above the stop editor. Text-based edit (no line numbers), safe to run twice.
Usage (repo root): python hide_padmap.py

CHANGELOG
2026-11-22  New (replaces patch v2.0.9-48, whose header context no longer matched).
"""
import re

LINE = "Organ Setter Wiki: the empty PAD MAP strip is hidden above the stop editor."


def rw(path, fn):
    with open(path, encoding="utf-8", newline="") as handle:
        old = handle.read()
    new = fn(old, "\r\n" if "\r\n" in old else "\n")
    if new != old:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(new)
    print(("Changed: " if new != old else "Unchanged: ") + path)


def gui(s, e):
    if "set_pad_map_visible" in s:
        return s
    pairs = [
        (f"        self.preview_grid = QGridLayout(){e}        self.preview_grid.setSpacing(4){e}        layout.addLayout(self.preview_grid){e}",
         f"        self.preview_box = QWidget(){e}        self.preview_grid = QGridLayout(self.preview_box){e}"
         f"        self.preview_grid.setContentsMargins(0, 0, 0, 0){e}        self.preview_grid.setSpacing(4){e}        layout.addWidget(self.preview_box){e}"),
        (f"    def selected_paths(self):{e}        return set(self._selected_paths){e}",
         f"    def set_pad_map_visible(self, visible):{e}        \"\"\"The PAD MAP strip (which stops sit on the KeyLab pads) only means something beside the live pads.\"\"\"{e}"
         f"        self.mapping_label.setVisible(visible){e}        self.preview_box.setVisible(visible){e}{e}"
         f"    def selected_paths(self):{e}        return set(self._selected_paths){e}"),
        (f"        self.grid = StopGridWidget(draft=True){e}        editor_layout.addWidget(self.grid, 1){e}",
         f"        self.grid = StopGridWidget(draft=True){e}        self.grid.set_pad_map_visible(False)             # no pad window here{e}        editor_layout.addWidget(self.grid, 1){e}"),
    ]
    for old, new in pairs:
        if s.count(old) != 1:
            print("Text not found (file differs):", old.strip().splitlines()[0])
            return s
        s = s.replace(old, new, 1)
    return re.sub(r"(\nCHANGELOG\r?\n)", lambda m: m.group(1) + "2026-11-22  " + LINE + e, s, count=1)


def changelog(s, e):
    if LINE in s:
        return s
    return re.sub(r"(### New\r?\n)", lambda m: m.group(1) + "- " + LINE + e, s, count=1)


rw("qt_gui.py", gui)
rw("CHANGELOG.md", changelog)
