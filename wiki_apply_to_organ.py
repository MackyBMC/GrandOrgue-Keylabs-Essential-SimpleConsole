"""Organ Setter Wiki: "Apply to organ" draws the stops of the step being edited on the live organ, so the selection can be heard.
Text-based edit (no line numbers), safe to run twice. Usage (repo root): python wiki_apply_to_organ.py

CHANGELOG
2026-11-22  New.
"""
import re

LINE = "Organ Setter Wiki: \"Apply to organ\" draws the stops of the edited step on the live organ (only stops that differ are toggled) so it can be heard before saving."


def rw(path, fn):
    with open(path, encoding="utf-8", newline="") as handle:
        old = handle.read()
    new = fn(old, "\r\n" if "\r\n" in old else "\n")
    if new != old:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(new)
    print(("Changed: " if new != old else "Unchanged: ") + path)


def replace_once(s, old, new, label):
    if s.count(old) != 1:
        print("Text not found (file differs):", label)
        return None
    return s.replace(old, new, 1)


def app(s, e):
    if '"apply_paths"' in s:
        return s
    old = '        elif event == "toggle_grid_switch":' + e
    new = ('        elif event == "apply_paths":' + e +
           '            wanted = set(value or ())' + e +
           '            changed = 0' + e +
           '            for item in self.br.stop_grid.items:' + e +
           '                if bool(self.br.state.get(item.cc)) != (item.path in wanted):' + e +
           '                    self.emit(self.br.toggle_cc(item.cc, time.time()))' + e +
           '                    changed += 1' + e +
           '            self.log(f"Wiki: applied a step to the organ ({changed} stops changed)", notify=False)' + e + old)
    return replace_once(s, old, new, "toggle_grid_switch") or s


def gui(s, e):
    if "apply_button" in s:
        return s
    steps = [
        ('        self.live_button = QPushButton("Take live stops")' + e,
         '        self.apply_button = QPushButton("Apply to organ")' + e +
         '        self.apply_button.setToolTip("Draw these stops on the organ now, to hear the selection")' + e +
         '        self.live_button = QPushButton("Take live stops")' + e),
        ("        for button in (self.live_button, self.revert_button, self.save_steps_button):" + e,
         "        for button in (self.apply_button, self.live_button, self.revert_button, self.save_steps_button):" + e),
        ("        self.live_button.clicked.connect(self._take_live)" + e,
         "        self.live_button.clicked.connect(self._take_live)" + e +
         "        self.apply_button.clicked.connect(self._apply_to_organ)" + e),
        ("    def _take_live(self):" + e,
         "    def _apply_to_organ(self):" + e +
         "        if self._step_id:" + e +
         '            self._w.bridge.post_ui_event("apply_paths", sorted(self.grid.selected_paths()))' + e + e +
         "    def _take_live(self):" + e),
    ]
    for old, new in steps:
        result = replace_once(s, old, new, old.strip()[:50])
        if result is None:
            return s
        s = result
    return re.sub(r"(\nCHANGELOG\r?\n)", lambda m: m.group(1) + "2026-11-22  " + LINE + e, s, count=1)


def changelog(s, e):
    if "Apply to organ" in s:
        return s
    return re.sub(r"(### New\r?\n)", lambda m: m.group(1) + "- " + LINE + e, s, count=1)


rw("keylab_bridge/application.py", app)
rw("qt_gui.py", gui)
rw("CHANGELOG.md", changelog)
