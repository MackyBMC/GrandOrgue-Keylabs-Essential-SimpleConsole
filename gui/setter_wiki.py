"""Organ Setter Wiki page and setter guide panel.

Split out of qt_gui.py without behaviour change.

CHANGELOG
2026-11-27  Moved verbatim from qt_gui.py (v3.0.0 modularisation, patch 06).
"""

import os
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import (
    QSettings,
    Qt,
)
from gui.organ_faq import OrganFaqDialog
from gui.stop_grid import StopGridWidget
from gui.widgets import OrganImageLabel, StarRating


class SetterWikiPage(QWidget):
    """Organ Setter Wiki: top left the guide (with a setter-file dropdown that is independent of the live setter), top right the
    organ's picture, along the bottom the stop editor of the chosen step with the heuristic reading on its right."""

    def __init__(self, window):
        super().__init__()
        self._w = window
        self._filename = ""
        self._edits = {}                      # step id -> set of switch paths edited here but not saved yet
        self._steps = []
        self._step_id = ""
        self._grid_signature = None
        self._image_organ = None
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.vertical = QSplitter(Qt.Orientation.Vertical)
        self.vertical.setChildrenCollapsible(False)
        root.addWidget(self.vertical, 1)

        top = QSplitter(Qt.Orientation.Horizontal)
        top.setChildrenCollapsible(False)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        pick = QHBoxLayout()
        self.previous_button = QPushButton("\u25c0")
        self.next_button = QPushButton("\u25b6")
        for button in (self.previous_button, self.next_button):
            button.setFixedWidth(34)
        self.file_combo = QComboBox()
        self.file_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.file_combo.setMinimumContentsLength(18)
        pick.addWidget(QLabel("Setter file"))
        pick.addWidget(self.previous_button)
        pick.addWidget(self.file_combo, 1)
        pick.addWidget(self.next_button)
        left_layout.addLayout(pick)
        self.guide_panel = SetterGuidePanel(window.bridge.post_ui_event)
        self.guide_panel.on_filter_changed = self.rebuild_files
        left_layout.addWidget(self.guide_panel, 1)
        top.addWidget(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.image = OrganImageLabel()
        right_layout.addWidget(self.image, 1)
        picture_row = QHBoxLayout()
        self.image_button = QPushButton("Choose picture...")
        self.image_button.clicked.connect(self._choose_image)
        picture_row.addWidget(self.image_button)
        self.history_button = QPushButton("Organ FAQ...")
        self.history_button.clicked.connect(self._show_history)
        picture_row.addWidget(self.history_button)
        right_layout.addLayout(picture_row)
        top.addWidget(right)
        top.setStretchFactor(0, 3)
        top.setStretchFactor(1, 2)
        self.vertical.addWidget(top)

        bottom = QSplitter(Qt.Orientation.Horizontal)
        bottom.setChildrenCollapsible(False)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step"))
        self.step_combo = QComboBox()
        step_row.addWidget(self.step_combo, 1)
        self.save_steps_button = QPushButton("Save setter")
        self.revert_button = QPushButton("Revert")
        self.apply_button = QPushButton("Apply to organ")
        self.apply_button.setToolTip("Draw these stops on the organ now, to hear the selection")
        self.live_button = QPushButton("Take live stops")
        self.live_button.setToolTip("Copy the stops drawn on the organ right now into this step")
        for button in (self.apply_button, self.live_button, self.revert_button, self.save_steps_button):
            step_row.addWidget(button)
        editor_layout.addLayout(step_row)
        self.grid = StopGridWidget(draft=True)
        self.grid.set_pad_map_visible(False)             # no pad window here
        editor_layout.addWidget(self.grid, 1)
        bottom.addWidget(editor)
        from PySide6.QtWidgets import QTextBrowser
        self.heuristic = QTextBrowser()
        self.heuristic.setMinimumWidth(240)
        bottom.addWidget(self.heuristic)
        bottom.setStretchFactor(0, 3)
        bottom.setStretchFactor(1, 1)
        self.vertical.addWidget(bottom)
        self.vertical.setStretchFactor(0, 1)
        self.vertical.setStretchFactor(1, 1)

        self._splitters = {"wiki_v": self.vertical, "wiki_top": top, "wiki_bottom": bottom}
        memory = QSettings("KeyLabGrandOrgue", "LiveLayout")
        for key, splitter in self._splitters.items():
            try:
                saved = memory.value(key)
                if saved:
                    splitter.restoreState(saved)
            except Exception:
                pass
            splitter.splitterMoved.connect(lambda _pos=0, _index=0, name=key: self._remember_layout(name))
        self.file_combo.currentIndexChanged.connect(self._file_changed)
        self.step_combo.currentIndexChanged.connect(self._step_changed)
        self.previous_button.clicked.connect(lambda: self._move(-1))
        self.next_button.clicked.connect(lambda: self._move(1))
        self.grid.toggle_requested.connect(self._toggled)
        self.save_steps_button.clicked.connect(self._save)
        self.revert_button.clicked.connect(self._revert)
        self.live_button.clicked.connect(self._take_live)
        self.apply_button.clicked.connect(self._apply_to_organ)

    def _remember_layout(self, name):
        QSettings("KeyLabGrandOrgue", "LiveLayout").setValue(name, self._splitters[name].saveState())

    # -- files
    def rebuild_files(self):
        names = [n for n in self._w._combination_files() if self.guide_panel.allows(n)]
        shown = [self.file_combo.itemData(i) for i in range(self.file_combo.count())]
        if names == shown:
            return
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for name in names:
            self.file_combo.addItem(os.path.splitext(name)[0], name)
        index = self.file_combo.findData(self._filename)
        self.file_combo.setCurrentIndex(index if index >= 0 else (0 if names else -1))
        self.file_combo.blockSignals(False)
        self._file_changed()

    def _move(self, delta):
        count = self.file_combo.count()
        if count:
            self.file_combo.setCurrentIndex((self.file_combo.currentIndex() + delta) % count)

    def _file_changed(self, _=0):
        filename = self.file_combo.currentData() or ""
        if filename != self._filename:
            self._edits = {}
        self._filename = filename
        self.guide_panel.set_setter(filename)
        self._steps = [s for s in self._w._combination_snapshot if s["filename"] == filename]
        self.step_combo.blockSignals(True)
        self.step_combo.clear()
        for step in self._steps:
            self.step_combo.addItem(f"{step['internal_id']}  {step['name']}", step["internal_id"])
        self.step_combo.blockSignals(False)
        self._step_changed()

    def _paths_of(self, step_id):
        if step_id in self._edits:
            return set(self._edits[step_id])
        for step in self._steps:
            if step["internal_id"] == step_id:
                return set(step.get("switch_paths", []))
        return set()

    def _step_changed(self, _=0):
        self._step_id = self.step_combo.currentData() or ""
        self.grid.set_selected_paths(self._paths_of(self._step_id))
        self._update_heuristic()

    def _toggled(self, path, selected):
        if not self._step_id:
            return
        paths = self.grid.selected_paths()
        (paths.add if selected else paths.discard)(path)
        self._edits[self._step_id] = paths
        self.grid.set_selected_paths(paths)
        self._update_heuristic()

    def _apply_to_organ(self):
        if self._step_id:
            self._w.bridge.post_ui_event("apply_paths", sorted(self.grid.selected_paths()))

    def _take_live(self):
        if self._step_id:
            self._edits[self._step_id] = set(self._w._active_stop_paths)
            self.grid.set_selected_paths(self._edits[self._step_id])
            self._update_heuristic()

    def _revert(self):
        self._edits.pop(self._step_id, None)
        self._step_changed()

    def _save(self):
        if not self._filename:
            return
        steps = [{"id": s["internal_id"], "name": s["name"], "stops": sorted(self._paths_of(s["internal_id"]))} for s in self._steps]
        self._w.bridge.post_ui_event("save_combination", {"filename": os.path.splitext(self._filename)[0],
                                                          "selected_id": self._step_id or "000", "steps": steps})
        self._edits = {}

    # -- heuristic reading
    def _update_heuristic(self):
        from keylab_bridge import registration_heuristic, setter_guide
        names = {s["path"]: (s["division"], s["name"]) for s in self._w._available_stops}
        chosen = [names[p] for p in sorted(self.grid.selected_paths()) if p in names]
        result = registration_heuristic.analyse(chosen)
        guide = self.guide_panel._guides.get(os.path.splitext(self._filename)[0], {})
        star = lambda n: "\u2605" * n + "\u2606" * (5 - n)
        html = [f"<h4>Heuristic reading: {result['count']} stops</h4><table>"]
        for group, rows in (("period", self.guide_panel.PERIOD_NAMES), ("tradition", self.guide_panel.TRADITION_NAMES)):
            for key, label in rows:
                written = int((guide.get(group) or {}).get(key, 0) or 0)
                note = f" &nbsp;<small>guide {star(written)}</small>" if written else ""
                html.append(f"<tr><td>{label}</td><td>{star(result[group][key])}{note}</td></tr>")
        html.append("</table>")
        best = max(result["period"], key=lambda k: result["period"][k]) if result["count"] else ""
        if best:
            html.append(f"<p><b>Leans {best}</b> ({result['period'][best]}\u2605)</p>")
        if result.get("notes"):
            html.append("<p>" + "<br>".join("\u2022 " + n for n in result["notes"]) + "</p>")
        if result["families"]:
            html.append("<p><small>" + ", ".join(f"{k} {v}" for k, v in sorted(result["families"].items())) + "</small></p>")
        html.append("<p><small>" + "<br>".join(result["lines"]) + "</small></p>")
        organ = self.guide_panel._character
        if organ and result["count"]:
            html.append(f"<p>Suits this organ: {star(setter_guide.fit({'period': result['period'], 'tradition': result['tradition']}, organ))}</p>")
        self.heuristic.setHtml("".join(html))

    # -- snapshot / picture
    def update_snapshot(self, snapshot):
        self.guide_panel.update_snapshot(snapshot)
        self.rebuild_files()
        stops = self._w._available_stops
        signature = tuple((s["path"], s["division"], s["name"]) for s in stops)
        if signature != self._grid_signature:
            self._grid_signature = signature
            self.grid.set_grid_data(stops, [], [], [], draft_paths=None)
            self._update_heuristic()
        organ = snapshot.get("organ_path") or ""
        if organ != self._image_organ:
            self._image_organ = organ
            from keylab_bridge.organ_image import organ_image
            chosen = ""
            try:
                chosen = str(QSettings("KeyLabGrandOrgue", "OrganPictures").value(organ, "") or "")
            except Exception:
                chosen = ""
            self.image.set_image(chosen if chosen and os.path.isfile(chosen) else organ_image(organ))

    def _show_history(self):
        OrganFaqDialog(self).exec()

    def _choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Picture of the organ", os.path.dirname(self._image_organ or ""),
                                              "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path and self._image_organ:
            QSettings("KeyLabGrandOrgue", "OrganPictures").setValue(self._image_organ, path)
            self.image.set_image(path)


class SetterGuidePanel(QWidget):
    """Filters for the setter list plus the guide that accompanies a setter (or the organ's character): 0-5 stars per
    period and tradition, composers, the reason for the registration and layering notes."""

    PERIOD_NAMES = (("baroque", "Baroque"), ("classical", "Classical"), ("romantic", "Romantic"), ("modern", "Modern"))
    TRADITION_NAMES = (("catholic", "Catholic"), ("early_protestant", "Early protestant"), ("modern_church", "Modern church"))

    def __init__(self, post_event):
        super().__init__()
        self._post = post_event
        self._filename = ""
        self._guides = {}
        self._character = {}
        self.on_filter_changed = lambda: None
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Filter"))
        self.period_filter = QComboBox()
        self.period_filter.addItem("Any period", "")
        for key, name in self.PERIOD_NAMES:
            self.period_filter.addItem(name, key)
        self.tradition_filter = QComboBox()
        self.tradition_filter.addItem("Any tradition", "")
        for key, name in self.TRADITION_NAMES:
            self.tradition_filter.addItem(name, key)
        self.composer_filter = QLineEdit()
        self.composer_filter.setPlaceholderText("Composer")
        self.stars_filter = QSpinBox()
        self.stars_filter.setRange(1, 5)
        self.stars_filter.setValue(3)
        self.stars_filter.setSuffix(" \u2605 or more")
        self.suits_filter = QCheckBox("Suits this organ")
        for widget in (self.period_filter, self.tradition_filter):
            widget.currentIndexChanged.connect(lambda _=0: self.on_filter_changed())
            filters.addWidget(widget)
        self.composer_filter.textChanged.connect(lambda _="": self.on_filter_changed())
        self.stars_filter.valueChanged.connect(lambda _=0: self.on_filter_changed())
        self.suits_filter.toggled.connect(lambda _=False: self.on_filter_changed())
        filters.addWidget(self.composer_filter, 1)
        filters.addWidget(self.stars_filter)
        filters.addWidget(self.suits_filter)
        layout.addLayout(filters)
        self.target_combo = QComboBox()
        self.target_combo.addItem("Guide of the selected setter", "setter")
        self.target_combo.addItem("The organ: what it was built for", "organ")
        self.target_combo.currentIndexChanged.connect(lambda _=0: self._load_fields())
        self.title_label = QLabel()
        target_row = QHBoxLayout()
        target_row.addWidget(self.target_combo, 1)
        target_row.addWidget(self.title_label)
        layout.addLayout(target_row)
        grid = QGridLayout()
        self.stars = {}
        names = self.PERIOD_NAMES + self.TRADITION_NAMES
        for position, (key, name) in enumerate(names):
            spin = StarRating()
            self.stars[key] = spin
            grid.addWidget(QLabel(name), position % 4, 0 if position < 4 else 2)
            grid.addWidget(spin, position % 4, 1 if position < 4 else 3)
        layout.addLayout(grid)
        self.composers_edit = QLineEdit()
        self.composers_edit.setPlaceholderText("Composers (comma separated)")
        layout.addWidget(self.composers_edit)
        notes_row = QHBoxLayout()
        self.reason_edit = QPlainTextEdit()
        self.reason_edit.setPlaceholderText("Why this registration (for the organ: what it was built for, builder, year)")
        notes_row.addWidget(self.reason_edit, 1)
        self.layering_edit = QPlainTextEdit()
        self.layering_edit.setPlaceholderText("Layering: which stop families, in which order to add them")
        notes_row.addWidget(self.layering_edit, 1)
        layout.addLayout(notes_row, 1)
        self.fit_label = QLabel()
        layout.addWidget(self.fit_label)
        self.save_button = QPushButton("Save guide")
        self.save_button.clicked.connect(self._save)
        layout.addWidget(self.save_button)

    # -- data in
    def update_snapshot(self, snapshot):
        guides = snapshot.get("guides") or {}
        character = snapshot.get("organ_character") or {}
        changed = guides != self._guides or character != self._character
        self._guides, self._character = guides, character
        if changed and not self._has_focus():
            self._load_fields()

    def set_setter(self, filename):
        if filename != self._filename:
            self._filename = filename
            self._load_fields()

    def _has_focus(self):
        return any(w.hasFocus() for w in (self.composers_edit, self.reason_edit, self.layering_edit, *self.stars.values()))

    def _stem(self):
        return os.path.splitext(self._filename)[0]

    def _current(self):
        if self.target_combo.currentData() == "organ":
            data = dict(self._character)
            data["reason"] = str(data.get("built_for", "") or "")
            return data
        return self._guides.get(self._stem(), {})

    def _load_fields(self):
        organ = self.target_combo.currentData() == "organ"
        data = self._current()
        for key, spin in self.stars.items():
            group = data.get("period" if key in dict(self.PERIOD_NAMES) else "tradition") or {}
            spin.setValue(int(group.get(key, 0) or 0))
        self.composers_edit.setText(", ".join(data.get("composers", [])))
        self.reason_edit.setPlainText(str(data.get("reason", "") or ""))
        self.layering_edit.setPlainText(str(data.get("layering", "") or ""))
        enabled = organ or bool(self._filename)
        for widget in (*self.stars.values(), self.composers_edit, self.reason_edit, self.layering_edit, self.save_button):
            widget.setEnabled(enabled)
        self.title_label.setText("The organ's character" if organ else (self._filename or "Select a setter in the list"))
        self.save_button.setText("Save organ character" if organ else "Save guide")
        self.fit_label.setText("" if organ or not self._filename else "Suits this organ: " + self._fit_text())

    def _fit_text(self):
        from keylab_bridge import setter_guide
        stars = setter_guide.fit(self._guides.get(self._stem(), {}), self._character)
        return "not rated yet" if not stars else "\u2605" * stars + "\u2606" * (5 - stars)

    def _fields(self):
        return {"period": {k: self.stars[k].value() for k, _ in self.PERIOD_NAMES},
                "tradition": {k: self.stars[k].value() for k, _ in self.TRADITION_NAMES},
                "composers": self.composers_edit.text(), "reason": self.reason_edit.toPlainText(),
                "layering": self.layering_edit.toPlainText()}

    def _save(self):
        data = self._fields()
        if self.target_combo.currentData() == "organ":
            data["built_for"] = data["reason"]
            self._post("character_save", data)
        elif self._filename:
            self._post("guide_save", (self._filename, data))

    # -- filter
    def allows(self, filename):
        """True when a setter file passes the filters (all off = everything)."""
        from keylab_bridge import setter_guide
        period, tradition = self.period_filter.currentData() or "", self.tradition_filter.currentData() or ""
        composer = self.composer_filter.text().strip()
        guide = self._guides.get(os.path.splitext(filename)[0], {})
        if not (period or tradition or composer or self.suits_filter.isChecked()):
            return True
        if not setter_guide.matches(guide, period, tradition, composer, self.stars_filter.value()):
            return False
        if self.suits_filter.isChecked() and setter_guide.fit(guide, self._character) < self.stars_filter.value():
            return False
        return True
