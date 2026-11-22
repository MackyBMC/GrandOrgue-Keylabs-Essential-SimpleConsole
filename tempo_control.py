"""Reusable, session-synchronized BPM fader with major/minor ticks and tempo undo/redo.

CHANGELOG
2026-11-23  Compact mode (one row, options in a menu); the piano roll tool bar uses it. "Full tempo panel" in the menu goes back.
2026-11-19  Engine sync indicator: "GrandOrgue 80 ✓" (confirmed by GrandOrgue), "GrandOrgue 80 ..." (sent, not yet confirmed), "GrandOrgue ?" (unknown).
2026-11-10  "Keep BPM" (default on: the BPM you set stays when you open files; off: each file sets its own), "file: NN" shows the
            opened file's written tempo, "= file" plays it as written. Until you set a BPM yourself, opened files still set it.
"""

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QMenu, QPushButton, QSlider, QSpinBox, QToolButton, QVBoxLayout, QWidget

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
        self.compact = str(QSettings("KeyLabGrandOrgue", "Tempo").value("compact", "false")) == "true"
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
        self.ticks = ticks
        self.more = QToolButton()
        self.more.setText("\u22ef")
        self.more.setToolTip("Tempo options: = file, Keep BPM, Undo, Redo, compact bar")
        self.more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(self.more)
        self.more_menu.aboutToShow.connect(self._fill_menu)
        self.more.setMenu(self.more_menu)
        row.addWidget(self.more)
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
        self.go_label = QLabel("")
        self.go_label.setToolTip("GrandOrgue metronome BPM versus the session BPM: check = GrandOrgue reported the same value.")
        actions.insertWidget(0, self.file_label)
        actions.insertWidget(1, self.go_label)
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
        self.set_compact(self.compact, save=False)
        self._file_timer = QTimer(self)                      # the written tempo of the opened file changes without a BPM change
        self._file_timer.timeout.connect(self._refresh_file_label)
        self._file_timer.start(500)

    def set_compact(self, on, save=True):
        """Compact: one row (label, fader, BPM, menu). The file / Keep / Undo / Redo / engine items move into the menu."""
        self.compact = bool(on)
        self.ticks.setVisible(not on)
        for w in (self.file_label, self.go_label, self.file_button, self.keep_box, self.undo_button, self.redo_button):
            w.setVisible(not on)
        self.more.setVisible(bool(on))
        self.setFixedWidth(300 if on else 370)
        if save:
            QSettings("KeyLabGrandOrgue", "Tempo").setValue("compact", "true" if on else "false")

    def _fill_menu(self):
        menu = self.more_menu
        menu.clear()
        file_bpm = getattr(self.controller, "file_bpm", None)
        menu.addAction(self.file_label.text() or "file: -").setEnabled(False)
        menu.addAction(self.go_label.text()).setEnabled(False)
        act = menu.addAction("= file tempo")
        act.setEnabled(bool(file_bpm))
        act.triggered.connect(self._use_file_tempo)
        keep = menu.addAction("Keep BPM when opening files")
        keep.setCheckable(True)
        keep.setChecked(self.keep_box.isChecked())
        keep.toggled.connect(self.keep_box.setChecked)
        undo = menu.addAction("Undo tempo")
        undo.setEnabled(self.undo_button.isEnabled())
        undo.triggered.connect(self._undo)
        redo = menu.addAction("Redo tempo")
        redo.setEnabled(self.redo_button.isEnabled())
        redo.triggered.connect(self._redo)
        menu.addSeparator()
        menu.addAction("Full tempo panel").triggered.connect(lambda: self.set_compact(False))

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
        eb = getattr(self.controller, "engine_bpm", None)
        ok = bool(getattr(self.controller, "engine_confirmed", False)) and eb == self.controller.bpm
        if eb is None:
            self.go_label.setText("GrandOrgue ?")
            self.go_label.setStyleSheet("color: #8a94a0;")
        else:
            self.go_label.setText(f"GrandOrgue {eb} " + ("\u2713" if ok else "..."))
            self.go_label.setStyleSheet("color: #3ecf6e;" if ok else "color: #e0a030;")

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
