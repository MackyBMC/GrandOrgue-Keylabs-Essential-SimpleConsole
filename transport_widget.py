"""One MIDI file transport for the whole app (main, stave editor, piano roll): the same buttons everywhere.

CHANGELOG
2026-11-12  New. Play / Pause, Stop / Panic, Loop, Metronome (+ Save), position slider, time and loaded-file label. Device agnostic: it only
            posts bridge events ("transport", "take_seek", "metro_down" ...) and reads the bridge's one MIDI take, exactly what any
            controller's transport keys do. The window it sits in does not matter: there is one MIDI source for the whole app.
"""
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QWidget

import polish

BUTTONS = (("gui_play", "Play / Pause", "play"), ("gui_panic", "Stop / Panic", "stop"), ("gui_loop", "Loop", "loop"),
           ("gui_metro", "Metronome", "metro"), ("gui_save", "Save", "save"))
MIDI_COLOUR = "#d58b2a"


def clock(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


class TransportBar(QWidget):
    """vertical=True: 2-column grid with slider underneath (main window box); False: one row (stave / roll tool bar)."""

    def __init__(self, bridge, vertical=False, save_cb=None, parent=None):
        super().__init__(parent)
        self.bridge, self.save_cb, self.metro_pressed = bridge, save_cb, False
        self.buttons = {}
        lay = QGridLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)
        for index, (key, text, action) in enumerate(BUTTONS):
            if action == "save" and save_cb is None:
                continue
            b = QPushButton(text)
            b.setMinimumHeight(28)
            b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            b.setToolTip("MIDI file player (one MIDI for the whole app)")
            if action == "metro":
                b.setCheckable(True)
                b.setAutoDefault(False)
                b.pressed.connect(self._metro_down)
                b.released.connect(self._metro_up)
            else:
                b.clicked.connect(lambda checked=False, a=action: self.act(a))
            self.buttons[key] = b
            lay.addWidget(b, index // 2, index % 2) if vertical else lay.addWidget(b, 0, index)
        self.slider = polish.make_seek_slider()
        self.slider.setToolTip("Click or drag to move to a position in the MIDI file")
        self.slider.seek.connect(self._seek)
        self.slider.moved.connect(self._moved)
        self.time_label = QLabel("0:00 / 0:00")
        self.file_label = QLabel("MIDI: none")
        self.file_label.setWordWrap(vertical)
        self.file_label.setMinimumWidth(60)
        self.file_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)   # long names never push the layout out
        if vertical:
            lay.addWidget(self.slider, 3, 0, 1, 2)
            lay.addWidget(self.time_label, 4, 0, 1, 2)
            lay.addWidget(self.file_label, 5, 0, 1, 2)
        else:
            lay.addWidget(self.slider, 0, 6)
            lay.addWidget(self.time_label, 0, 7)
            lay.addWidget(self.file_label, 0, 8)
            lay.setColumnStretch(6, 3)
            lay.setColumnStretch(8, 2)
            self.setMinimumWidth(640)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)

    # ------------------------------------------------------------------ actions (all go through the bridge)
    def act(self, name):
        if name == "save":
            if self.save_cb:
                self.save_cb()
        else:
            self.bridge.post_ui_event("transport", name)

    def _metro_down(self):
        self.metro_pressed = True
        self.bridge.post_ui_event("metro_down")

    def _metro_up(self):
        self.metro_pressed = False
        self.bridge.post_ui_event("metro_up")

    def _length(self):
        return getattr(self.bridge, "take_length", 0.0) or 0.0

    def _seek(self, value):
        if self._length() > 0 and getattr(self.bridge, "take_to_play", None):
            self.bridge.post_ui_event("take_seek", value / 1000.0 * self._length())

    def _moved(self, value):
        self.time_label.setText(f"{clock(value / 1000.0 * self._length())} / {clock(self._length())}")

    # ------------------------------------------------------------------ state from the bridge
    def refresh(self):
        if not self.isVisible():
            return
        b = self.bridge
        path = getattr(b, "take_to_play", None)
        player = getattr(b, "take_player", None)
        playing = getattr(player, "active", False)
        recording = getattr(b, "midi_rec", None) is not None
        text = "Recording..." if recording else ("Loaded: " + os.path.basename(path) if path else "MIDI: nothing loaded")
        self.file_label.setText(text + ("  [PLAYING]" if playing else ""))
        self.file_label.setToolTip((path or "") + "\n" + getattr(b, "take_info", ""))
        length = self._length()
        pos = (player.position() or 0.0) if playing else 0.0
        if length > 0 and not self.slider.dragging:
            self.slider.setValue(int(min(1.0, pos / length) * 1000))
        self.time_label.setText(f"{clock(pos)} / {clock(length)}")

    def set_metro(self, lit, bpm, label="Metronome"):
        b = self.buttons["gui_metro"]
        if not self.metro_pressed and b.isChecked() != lit:
            b.blockSignals(True)
            b.setChecked(lit)
            b.blockSignals(False)
        b.setText(f"{label}  {bpm}" if bpm else label)

    def retranslate(self, t):
        for key, button in self.buttons.items():
            button.setText(t(key))

    def set_ready(self, ready):
        for button in self.buttons.values():
            button.setEnabled(ready)
