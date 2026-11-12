"""The "Mixer" tab: one slider + mute per audio application, plus scenes (Interlude / Service ...).

CHANGELOG
2026-11-12  New. Rows refresh every 1.5 s (apps appear when they start playing); a slider being dragged is never overwritten.
"""
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QInputDialog, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
                               QScrollArea, QGridLayout)

import audio_mixer


class MixerPanel(QWidget):
    def __init__(self, config_path, backend=None, parent=None):
        super().__init__(parent)
        self.backend = backend or audio_mixer.PycawBackend()
        self.scenes = audio_mixer.Scenes(os.path.join(os.path.dirname(os.path.abspath(config_path)) if config_path else ".", "mixer_scenes.json"))
        self.rows = {}                                    # key -> (label, slider, value label, mute box)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Scene:"))
        self.scene_box = QComboBox()
        self.scene_box.setMinimumWidth(160)
        top.addWidget(self.scene_box)
        for text, slot, tip in (("Apply", self.apply_scene, "Set every listed program to the saved level"),
                                ("Save levels as...", self.save_scene, "Remember the current levels under a name, e.g. Interlude or Service"),
                                ("Delete", self.delete_scene, "")):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda checked=False, f=slot: f())
            top.addWidget(button)
        top.addStretch(1)
        layout.addLayout(top)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        area = QScrollArea()
        area.setWidgetResizable(True)
        inner = QWidget()
        self.grid = QGridLayout(inner)
        self.grid.setColumnStretch(1, 1)
        area.setWidget(inner)
        layout.addWidget(area, 1)
        self._refresh_scenes()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        if self.backend.available():
            self.note.setText("Windows volume of each program that is playing sound. Start the orchestral player and it appears here. "
                              "These do not change GrandOrgue's own organ volumes.")
            self.timer.start(1500)
            self.refresh()
        else:
            self.note.setText(self.backend.reason)

    # ------------------------------------------------------------------ rows
    def refresh(self):
        try:
            strips = self.backend.strips()
        except Exception as exc:
            self.note.setText(f"Audio sessions could not be read: {exc}")
            return
        keys = [s.key for s in strips]
        if keys != list(self.rows):
            self._rebuild(strips)
        for strip in strips:
            label, slider, value, mute = self.rows[strip.key]
            if not slider.isSliderDown():
                slider.blockSignals(True)
                slider.setValue(round(strip.volume * 100))
                slider.blockSignals(False)
                value.setText(f"{round(strip.volume * 100)} %")
            if mute.isChecked() != strip.muted:
                mute.blockSignals(True)
                mute.setChecked(strip.muted)
                mute.blockSignals(False)

    def _rebuild(self, strips):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.rows = {}
        for row, strip in enumerate(sorted(strips, key=lambda s: (s.key != audio_mixer.PycawBackend.MASTER, "grandorgue" not in s.name.lower(), s.name.lower()))):
            label = QLabel(strip.name)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            value = QLabel("")
            value.setMinimumWidth(48)
            mute = QCheckBox("Mute")
            slider.valueChanged.connect(lambda v, k=strip.key, lab=value: (lab.setText(f"{v} %"), self.backend.set_volume(k, v / 100.0)))
            mute.toggled.connect(lambda m, k=strip.key: self.backend.set_mute(k, m))
            for col, widget in enumerate((label, slider, value, mute)):
                self.grid.addWidget(widget, row, col)
            self.rows[strip.key] = (label, slider, value, mute)
        self.grid.setRowStretch(len(strips), 1)

    # ---------------------------------------------------------------- scenes
    def _refresh_scenes(self, select=None):
        self.scene_box.clear()
        self.scene_box.addItems(self.scenes.names())
        if select:
            self.scene_box.setCurrentText(select)

    def save_scene(self):
        name, ok = QInputDialog.getText(self, "Save levels", "Scene name (e.g. Interlude, Service):", text=self.scene_box.currentText())
        if ok and name.strip():
            self.scenes.save(name.strip(), self.backend.strips())
            self._refresh_scenes(name.strip())

    def apply_scene(self):
        levels = self.scenes.levels(self.scene_box.currentText())
        for strip in self.backend.strips():
            level = levels.get(audio_mixer.app_name(strip.key))
            if level:
                self.backend.set_volume(strip.key, level.get("v", strip.volume))
                self.backend.set_mute(strip.key, bool(level.get("m", False)))
        self.refresh()

    def delete_scene(self):
        if self.scene_box.currentText():
            self.scenes.delete(self.scene_box.currentText())
            self._refresh_scenes()
