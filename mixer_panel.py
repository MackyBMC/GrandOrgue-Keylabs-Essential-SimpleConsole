"""The Mixer: a floating / dockable frame with one graduated vertical fader per audio application (and the master), plus scenes.

Every fader is a fixed-size strip with a measured scale (ticks every 5 %, numbered every 10 %, a 0 dB mark at 100 %), a % + dB readout and a
Mute button. Strips sit side by side from the left and are never stretched to the width of the frame; too many for the frame -> it scrolls.

CHANGELOG
2026-11-13  Rewritten as graduated vertical faders (Fader), fixed strip size, dockable (the main window hosts it as a dock that stays visible on
            every tab: Bridge / Stave Station / Piano Roll). Mouse wheel = 1 %, Shift+wheel = 5 %, Ctrl+click = back to 100 %, arrow keys.
2026-11-12  New (tab version).
"""
import os
from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

import audio_mixer

FADER_W, FADER_H = 62, 200
STRIP_W = 78


class Fader(QWidget):
    """Vertical fader 0..100 with a measured scale. valueChanged(int) is emitted on user changes only."""
    valueChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._value = 0
        self.setFixedSize(FADER_W, FADER_H)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._top, self._bottom, self._groove_x = 12.0, FADER_H - 12.0, FADER_W * 0.62

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        if value != self._value:
            self._value = value
            self.update()

    def _user_set(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        if value != self._value:
            self._value = value
            self.update()
            self.valueChanged.emit(value)

    def _y(self, value: float) -> float:
        return self._bottom - (self._bottom - self._top) * value / 100.0

    def _from_y(self, y: float) -> int:
        span = self._bottom - self._top
        return round(100.0 * (self._bottom - min(max(y, self._top), self._bottom)) / span)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        text, muted, accent = pal.windowText().color(), pal.mid().color(), pal.highlight().color()
        gx = self._groove_x
        groove = QRectF(gx - 3, self._top, 6, self._bottom - self._top)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal.base().color())
        painter.drawRoundedRect(groove, 3, 3)
        fill = QRectF(gx - 3, self._y(self._value), 6, self._bottom - self._y(self._value))
        painter.setBrush(accent)
        painter.drawRoundedRect(fill, 3, 3)
        font = painter.font()
        font.setPointSizeF(max(6.5, font.pointSizeF() * 0.78))
        painter.setFont(font)
        for v in range(0, 101, 5):
            major = v % 10 == 0
            y = self._y(v)
            painter.setPen(QPen(text if major else muted, 1))
            painter.drawLine(QPointF(gx - 8 - (6 if major else 0), y), QPointF(gx - 8, y))
            if major:
                label = str(v)
                painter.setPen(text)
                painter.drawText(QRectF(0, y - 7, gx - 17, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
        y = self._y(self._value)                                   # the handle
        painter.setPen(QPen(muted, 1))
        painter.setBrush(accent if self.hasFocus() else pal.button().color())
        painter.drawRoundedRect(QRectF(gx - 11, y - 6, 22, 12), 3, 3)
        painter.setPen(QPen(text, 1))
        painter.drawLine(QPointF(gx - 8, y), QPointF(gx + 8, y))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._user_set(100)
            else:
                self._user_set(self._from_y(event.position().y()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._user_set(self._from_y(event.position().y()))

    def wheelEvent(self, event: QWheelEvent) -> None:
        step = 5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        self._user_set(self._value + (step if event.angleDelta().y() > 0 else -step))
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        steps = {int(Qt.Key.Key_Up): 1, int(Qt.Key.Key_Right): 1, int(Qt.Key.Key_Down): -1, int(Qt.Key.Key_Left): -1,
                 int(Qt.Key.Key_PageUp): 10, int(Qt.Key.Key_PageDown): -10}
        key = int(event.key())
        if key in steps:
            self._user_set(self._value + steps[key])
        elif key == int(Qt.Key.Key_Home):
            self._user_set(100)
        elif key == int(Qt.Key.Key_End):
            self._user_set(0)
        else:
            super().keyPressEvent(event)


class ChannelStrip(QFrame):
    def __init__(self, strip: audio_mixer.Strip, backend, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.key = strip.key
        self.backend = backend
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedWidth(STRIP_W)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        self.name = QLabel(strip.name)
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name.setToolTip(strip.name)
        self.name.setFixedHeight(self.name.fontMetrics().height() + 2)
        self.name.setText(self.name.fontMetrics().elidedText(strip.name, Qt.TextElideMode.ElideRight, STRIP_W - 12))
        layout.addWidget(self.name)
        self.fader = Fader()
        layout.addWidget(self.fader, 0, Qt.AlignmentFlag.AlignHCenter)
        self.readout = QLabel("")
        self.readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.readout)
        self.mute = QCheckBox("Mute")
        layout.addWidget(self.mute, 0, Qt.AlignmentFlag.AlignHCenter)
        self.fader.valueChanged.connect(self._moved)
        self.mute.toggled.connect(lambda on: self.backend.set_mute(self.key, on))
        self.update_from(strip)

    def _moved(self, value: int) -> None:
        self.backend.set_volume(self.key, value / 100.0)
        self.readout.setText(f"{value} %\n{audio_mixer.to_db(value / 100.0)}")

    def update_from(self, strip: audio_mixer.Strip) -> None:
        self.fader.set_value(round(strip.volume * 100))
        self.readout.setText(f"{self.fader.value()} %\n{audio_mixer.to_db(strip.volume)}")
        if self.mute.isChecked() != strip.muted:
            self.mute.blockSignals(True)
            self.mute.setChecked(strip.muted)
            self.mute.blockSignals(False)


class MixerPanel(QWidget):
    def __init__(self, config_path: str, backend=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.backend = backend or audio_mixer.PycawBackend()
        folder = os.path.dirname(os.path.abspath(config_path)) if config_path else "."
        self.scenes = audio_mixer.Scenes(os.path.join(folder, "mixer_scenes.json"))
        self.rows: Dict[str, ChannelStrip] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        top = QHBoxLayout()
        top.addWidget(QLabel("Scene"))
        self.scene_box = QComboBox()
        self.scene_box.setMinimumContentsLength(10)
        top.addWidget(self.scene_box)
        for text, slot, tip in (("Apply", self.apply_scene, "Set every listed program to the saved level"),
                                ("Save...", self.save_scene, "Remember the current levels under a name, e.g. Interlude or Service"),
                                ("Delete", self.delete_scene, "Delete the selected scene")):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda checked=False, f=slot: f())
            top.addWidget(button)
        top.addStretch(1)
        layout.addLayout(top)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.inner = QWidget()
        self.strip_layout = QHBoxLayout(self.inner)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(6)
        self.strip_layout.addStretch(1)                      # strips stay their size, packed to the left
        self.area.setWidget(self.inner)
        layout.addWidget(self.area, 1)
        self._refresh_scenes()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        if self.backend.available():
            self.note.setText("Windows volume of each program playing sound. These do not change GrandOrgue's own organ volumes.")
            self.timer.start(1500)
            self.refresh()
        else:
            self.note.setText(self.backend.reason)

    def refresh(self) -> None:
        try:
            strips: List[audio_mixer.Strip] = self.backend.strips()
        except Exception as exc:
            self.note.setText(f"Audio sessions could not be read: {exc}")
            return
        order = sorted(strips, key=lambda s: (s.key != audio_mixer.MASTER, "grandorgue" not in s.name.lower(), s.name.lower()))
        if [s.key for s in order] != list(self.rows):
            self._rebuild(order)
        for strip in order:
            row = self.rows[strip.key]
            if not row.fader.hasFocus() and not (row.fader.underMouse() and QApplicationButtons.pressed()):
                row.update_from(strip)

    def _rebuild(self, strips: List[audio_mixer.Strip]) -> None:
        for row in self.rows.values():
            self.strip_layout.removeWidget(row)
            row.deleteLater()
        self.rows = {}
        for index, strip in enumerate(strips):
            row = ChannelStrip(strip, self.backend)
            self.strip_layout.insertWidget(index, row)
            self.rows[strip.key] = row

    def _refresh_scenes(self, select: str = "") -> None:
        self.scene_box.clear()
        self.scene_box.addItems(self.scenes.names())
        if select:
            self.scene_box.setCurrentText(select)

    def save_scene(self) -> None:
        name, ok = QInputDialog.getText(self, "Save levels", "Scene name (e.g. Interlude, Service):", text=self.scene_box.currentText())
        if ok and name.strip():
            self.scenes.save(name.strip(), self.backend.strips())
            self._refresh_scenes(name.strip())

    def apply_scene(self) -> None:
        levels = self.scenes.levels(self.scene_box.currentText())
        for strip in self.backend.strips():
            level = levels.get(audio_mixer.app_name(strip.key))
            if level:
                self.backend.set_volume(strip.key, float(level.get("v", strip.volume)))
                self.backend.set_mute(strip.key, bool(level.get("m", False)))
        self.refresh()

    def delete_scene(self) -> None:
        if self.scene_box.currentText():
            self.scenes.delete(self.scene_box.currentText())
            self._refresh_scenes()


class QApplicationButtons:
    @staticmethod
    def pressed() -> bool:
        from PySide6.QtWidgets import QApplication
        return bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
