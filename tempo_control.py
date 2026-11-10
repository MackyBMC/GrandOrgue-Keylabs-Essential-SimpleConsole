"""Reusable, session-synchronized BPM fader with major/minor ticks and tempo undo/redo.

CHANGELOG
2026-11-10  "Keep BPM" (default on: the BPM you set stays when you open files; off: each file sets its own), "file: NN" shows the
            opened file's written tempo, "= file" plays it as written. Until you set a BPM yourself, opened files still set it.
"""

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget

from keylab_bridge.tempo import MAX_BPM, MIN_BPM, TempoSession


class TempoTicks(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(29)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setPen(QPen(self.palette().mid().color(), 1))
        width = max(1, self.width() - 14)
        for bpm in range(MIN_BPM, MAX_BPM + 1, 5):
            x = 7 + round((bpm - MIN_BPM) * width / (MAX_BPM - MIN_BPM))
            major = bpm % 20 == 0 or bpm in (MIN_BPM, MAX_BPM)
            painter.setPen(QPen(self.palette().text().color() if major else self.palette().mid().color(), 1))
            painter.drawLine(x, 0, x, 8 if major else 4)
            if major:
                painter.drawText(max(0, min(self.width() - 30, x - 15)), 25, 30, 14,
                                 Qt.AlignmentFlag.AlignHCenter, str(bpm))
        painter.end()


class TempoControl(QWidget):
    tempoChanged = Signal(int)

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = None
        self._listener = self._controller_changed
        self.setFixedWidth(370)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(4)
        label = QLabel("Tempo")
        label.setFixedWidth(46)
        row.addWidget(label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(MIN_BPM, MAX_BPM)
        self.slider.setPageStep(10)
        self.slider.setSingleStep(1)
        self.slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.slider.setToolTip("Global tempo target. Existing tempo maps keep their relative changes.")
        row.addWidget(self.slider, 1)
        self.spin = QSpinBox()
        self.spin.setRange(MIN_BPM, MAX_BPM)
        self.spin.setSuffix(" BPM")
        self.spin.setFixedWidth(88)
        self.spin.setToolTip("Global tempo target, applied to all playback windows.")
        row.addWidget(self.spin)
        ticks = TempoTicks(self)
        layout.addLayout(row)
        tick_row = QHBoxLayout()
        tick_row.setContentsMargins(0, 0, 0, 0)
        tick_row.setSpacing(4)
        tick_row.addSpacing(46)
        tick_row.addWidget(ticks, 1)
        tick_row.addSpacing(88)
        layout.addLayout(tick_row)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setToolTip("Undo the last tempo change in this session.")
        self.redo_button = QPushButton("Redo")
        self.redo_button.setToolTip("Redo the last undone tempo change.")
        self.file_label = QLabel("")
        self.file_label.setToolTip("The tempo written in the file you opened. Click '= file' to play it as written.")
        self.file_button = QPushButton("= file")
        self.file_button.setToolTip("Set the BPM to the opened file's own tempo (can be undone).")
        self.keep_box = QCheckBox("Keep BPM")
        self.keep_box.setToolTip("On: the BPM you set stays when you open another file (universal tempo).\n"
                                 "Off: every file opened sets the BPM to its own written tempo.")
        actions.insertWidget(0, self.file_label)
        actions.addWidget(self.file_button)
        actions.addWidget(self.keep_box)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        layout.addLayout(actions)
        self.slider.valueChanged.connect(self._set_bpm)
        self.spin.valueChanged.connect(self._set_bpm)
        self.file_button.clicked.connect(self._use_file_tempo)
        self.keep_box.toggled.connect(self._keep_changed)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button.clicked.connect(self._redo)
        self.tempoChanged.connect(self._sync_controls)
        self.set_controller(controller or TempoSession())
        self._file_timer = QTimer(self)                      # the written tempo of the opened file changes without a BPM change
        self._file_timer.timeout.connect(self._refresh_file_label)
        self._file_timer.start(500)

    def set_controller(self, controller):
        if self.controller is not None:
            self.controller.remove_listener(self._listener)
        self.controller = controller
        self.controller.add_listener(self._listener)
        keep = str(QSettings("KeyLabGrandOrgue", "Tempo").value("keep_on_load", "true")) == "true"
        self.controller.keep_on_load = keep
        self.keep_box.blockSignals(True); self.keep_box.setChecked(keep); self.keep_box.blockSignals(False)
        self._sync_controls(self.controller.bpm)

    def _keep_changed(self, on):
        self.controller.keep_on_load = bool(on)
        QSettings("KeyLabGrandOrgue", "Tempo").setValue("keep_on_load", "true" if on else "false")

    def _use_file_tempo(self):
        if getattr(self.controller, "file_bpm", None):
            self.controller.set_bpm(self.controller.file_bpm)

    def _refresh_file_label(self):
        fb = getattr(self.controller, "file_bpm", None)
        self.file_label.setText(f"file: {fb:.0f}" if fb else "")
        self.file_button.setEnabled(bool(fb))

    def _controller_changed(self, bpm, _origin):
        self.tempoChanged.emit(bpm)

    def _sync_controls(self, bpm):
        for control in (self.slider, self.spin):
            control.blockSignals(True)
            control.setValue(bpm)
            control.blockSignals(False)
        self.undo_button.setEnabled(bool(self.controller._undo))
        self.redo_button.setEnabled(bool(self.controller._redo))

    def _set_bpm(self, bpm):
        self.controller.set_bpm(bpm)

    def _undo(self):
        self.controller.undo()

    def _redo(self):
        self.controller.redo()

    def value(self):
        return self.controller.bpm

    def setValue(self, bpm):
        self.controller.set_bpm(bpm)

    def closeEvent(self, event):
        if self.controller is not None:
            self.controller.remove_listener(self._listener)
        super().closeEvent(event)
