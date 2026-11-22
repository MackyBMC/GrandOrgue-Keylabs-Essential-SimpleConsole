"""Record Center: record, live plot, step-by-step input, extra parts and the list of takes. Shown under the Piano Roll.

One record engine (the bridge's Record button / the KeyLab Record key); this panel is its screen and its options:
  Input   Live, or Step by step (the chord you hold is written at the cursor with the chosen step length, Rest / Back).
  Target  A new file, or a new part (track + next free channel) added to the MIDI that is loaded. A live part plays the loaded MIDI along.
The live plot shows what has been played so far; when the take stops it opens in the Piano Roll as usual.

CHANGELOG
2026-11-23  Open in roll goes through the main window (loads the take into the roll at once); the status shows what is playing or why playback did not start.
2026-11-23  A plain widget with tight margins (no group box), so the dock around it wastes no space.
2026-11-22  Selecting a take plots it in the area above the list (each channel / part in its own colour, play position); a finished take is selected automatically.
2026-11-22  Count-in, Play / Stop of a listed take, no collapse box (the dock around it floats / resizes).
2026-11-22  New.
"""
import os
import shutil
import time
from typing import Any

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

STEPS = (("Whole", 4.0), ("Half", 2.0), ("Quarter", 1.0), ("Eighth", 0.5), ("Sixteenth", 0.25), ("32nd", 0.125))


def _accent():
    try:
        import themes
        return QColor(themes.tokens().get("accent", "#0b6f5c"))
    except Exception:
        return QColor("#0b6f5c")


class LiveTakeView(QWidget):
    """Notes of the running take as a small scrolling piano roll (time to the right, pitch up), plus the step cursor."""
    WINDOW = 20.0

    def __init__(self, bridge: Any):
        super().__init__()
        self.bridge = bridge
        self.setMinimumHeight(90)
        self.preview_path = ""
        self._cache = ("", 0.0, [], 0.0)          # path, mtime, notes (pitch, start, end, velocity, channel), length

    def set_preview(self, path):
        self.preview_path = path
        self.update()

    def _preview_notes(self):
        path = self.preview_path
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            return [], 0.0
        if self._cache[0] == path and self._cache[1] == stamp:
            return self._cache[2], self._cache[3]
        notes, open_notes, length = [], {}, 0.0
        try:
            import mido
            clock = 0.0
            for message in mido.MidiFile(path):
                clock += message.time
                if message.type == "note_on" and message.velocity > 0:
                    open_notes[(message.channel, message.note)] = (clock, message.velocity)
                elif message.type in ("note_off", "note_on") and (message.channel, message.note) in open_notes:
                    start, velocity = open_notes.pop((message.channel, message.note))
                    notes.append((message.note, start, clock, velocity, message.channel))
                if len(notes) > 20000:
                    break
            for (channel, note), (start, velocity) in open_notes.items():
                notes.append((note, start, clock, velocity, channel))
            length = clock
        except Exception:
            notes, length = [], 0.0
        self._cache = (path, stamp, notes, length)
        return notes, length

    def _paint_preview(self, painter):
        notes, length = self._preview_notes()
        if not notes or length <= 0:
            painter.setPen(self.palette().mid().color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Press Record: the notes you play appear here. Select a take below to look at it.")
            return
        pitches = [n[0] for n in notes]
        low, high = min(min(pitches) - 2, 48), max(max(pitches) + 2, 72)
        height, width = self.height(), self.width()
        base = _accent()
        for pitch, start, end, velocity, channel in notes:
            colour = QColor(base)
            if channel:
                colour = QColor.fromHsv((base.hue() + channel * 47) % 360, 170, 215)      # every part (channel) its own colour
            colour.setAlphaF(0.45 + 0.55 * min(1.0, velocity / 127.0))
            x0 = start / length * width
            y = height - (pitch - low + 1) / (high - low + 1) * height
            painter.fillRect(QRectF(x0, y, max(2.0, (end - start) / length * width), max(2.0, height / (high - low + 1))), colour)
        channels = sorted({n[4] for n in notes})
        painter.setPen(self.palette().text().color())
        painter.drawText(4, 14, f"{os.path.basename(self.preview_path)}  \u00b7  {int(length) // 60}:{int(length) % 60:02d}  \u00b7  "
                                f"{len(notes)} notes  \u00b7  channel{'s' if len(channels) > 1 else ''} {', '.join(str(c + 1) for c in channels)}")
        player = getattr(self.bridge, "take_player", None)
        playing = getattr(self.bridge, "take_to_play", "") or ""
        if player is not None and getattr(player, "active", False) and os.path.normcase(os.path.abspath(playing)) == os.path.normcase(os.path.abspath(self.preview_path)):
            try:
                x = float(player.position()) / length * width
                painter.setPen(QColor("#e53935"))
                painter.drawLine(int(x), 0, int(x), height)
            except Exception:
                pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        rec = getattr(self.bridge, "midi_rec", None)
        if rec is None or getattr(rec, "started", None) is None:
            self._paint_preview(painter)
            painter.end()
            return
        step = hasattr(rec, "cursor")
        now_t = float(rec.cursor) if step else max(0.0, time.time() - float(rec.started))
        events = list(rec.events)
        notes, open_notes = [], {}
        for at, kind, a, b in events:
            if kind == "on":
                open_notes[a] = (at, b)
            elif kind == "off" and a in open_notes:
                start, velocity = open_notes.pop(a)
                notes.append((a, start, at, velocity))
        for note, (start, velocity) in open_notes.items():
            notes.append((note, start, now_t, velocity))
        t1 = max(self.WINDOW, now_t + 1.0)
        t0 = t1 - self.WINDOW
        pitches = [n[0] for n in notes] or [60]
        low, high = min(min(pitches) - 2, 48), max(max(pitches) + 2, 72)
        height, width = self.height(), self.width()
        accent = _accent()
        for note, start, end, velocity in notes:
            if end < t0:
                continue
            x0 = (max(start, t0) - t0) / self.WINDOW * width
            x1 = (end - t0) / self.WINDOW * width
            y = height - (note - low + 1) / (high - low + 1) * height
            shade = QColor(accent)
            shade.setAlphaF(0.45 + 0.55 * min(1.0, velocity / 127.0))
            painter.fillRect(QRectF(x0, y, max(2.0, x1 - x0), max(2.0, height / (high - low + 1))), shade)
        x = (now_t - t0) / self.WINDOW * width
        painter.setPen(QColor("#e53935"))
        painter.drawLine(int(x), 0, int(x), height)
        painter.end()


class RecordCenter(QWidget):
    def __init__(self, bridge: Any):
        super().__init__()
        self.bridge = bridge
        self.open_hook: Any = None                 # set by the main window: opens a file in the Piano Roll
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(3)
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.body)

        row = QHBoxLayout()
        self.record_button = QPushButton("● Record")
        self.record_button.setMinimumHeight(30)
        self.record_button.clicked.connect(lambda: self.bridge.post_ui_event("record"))
        row.addWidget(self.record_button)
        self.input_box = QComboBox()
        self.input_box.addItem("Live", "live")
        self.input_box.addItem("Step by step", "step")
        self.target_box = QComboBox()
        self.target_box.addItem("New file", "new")
        self.target_box.addItem("New part in the loaded MIDI", "part")
        self.step_box = QComboBox()
        for label, beats in STEPS:
            self.step_box.addItem(label, beats)
        self.step_box.setCurrentIndex(2)
        self.count_box = QComboBox()
        for label, beats in (("Off", 0), ("1 bar", 4), ("2 bars", 8)):
            self.count_box.addItem(label, beats)
        self.count_box.setToolTip("Metronome clicks before the recording starts (4/4); the metronome returns to how it was")
        for label, widget in (("Input", self.input_box), ("Add to", self.target_box), ("Step", self.step_box), ("Count-in", self.count_box)):
            row.addWidget(QLabel(label))
            row.addWidget(widget)
        self.rest_button = QPushButton("Rest")
        self.back_button = QPushButton("Back")
        self.rest_button.clicked.connect(lambda: self.bridge.post_ui_event("step_rest"))
        self.back_button.clicked.connect(lambda: self.bridge.post_ui_event("step_back"))
        row.addWidget(self.rest_button)
        row.addWidget(self.back_button)
        row.addStretch(1)
        self.status = QLabel()
        row.addWidget(self.status)
        body.addLayout(row)
        for widget in (self.input_box, self.target_box):
            widget.currentIndexChanged.connect(self._options_changed)
        self.step_box.currentIndexChanged.connect(self._options_changed)
        self.count_box.currentIndexChanged.connect(self._options_changed)

        self.view = LiveTakeView(bridge)
        body.addWidget(self.view)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Take", "Recorded", "Length"])
        self.tree.setRootIsDecorated(False)
        self.tree.setMinimumHeight(90)
        self.tree.itemDoubleClicked.connect(lambda *_: self._open())
        self.tree.itemSelectionChanged.connect(lambda: self.view.set_preview(self._current()))
        body.addWidget(self.tree, 1)
        buttons = QHBoxLayout()
        for text, handler in (("Open in roll", self._open), ("Play / Stop", self._play), ("Rename...", self._rename),
                              ("Delete", self._delete), ("Refresh", self.refresh_list)):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, h=handler: h())
            buttons.addWidget(button)
        buttons.addStretch(1)
        body.addLayout(buttons)

        self._signature = None
        self._was_recording = False
        self._lengths = {}
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._options_changed()
        self.refresh_list()

    # -- options
    def _options_changed(self, _=0):
        self.bridge.post_ui_event("record_options", {"input": self.input_box.currentData(), "target": self.target_box.currentData(),
                                                     "step": float(self.step_box.currentData()), "count": int(self.count_box.currentData())})
        self._enable()

    def _enable(self):
        recording = getattr(self.bridge, "midi_rec", None) is not None
        step = self.input_box.currentData() == "step"
        self.input_box.setEnabled(not recording)
        self.target_box.setEnabled(not recording)
        self.step_box.setEnabled(step)
        self.rest_button.setEnabled(step and recording)
        self.back_button.setEnabled(step and recording)

    def _tick(self):
        if not self.isVisible():
            return
        rec = getattr(self.bridge, "midi_rec", None)
        recording = rec is not None
        if self._was_recording and not recording:
            self.refresh_list()                              # the take just finished: show it, ready to check
            if self.tree.topLevelItemCount():
                self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._was_recording = recording
        counting = float(getattr(self.bridge, "count_in_end", 0.0) or 0.0) - time.time()
        self.record_button.setText("■ Stop" if recording else "● Record")
        self.record_button.setStyleSheet("color: #e53935; font-weight: 700;" if recording else "")
        if counting > 0 and not recording:
            self.record_button.setText("\u25a0 Cancel")
            self.status.setText(f"Count-in ... {int(counting) + 1}")
        elif recording:
            started = getattr(rec, "started", None)
            elapsed = max(0.0, time.time() - float(started)) if started else 0.0
            where = f"step {float(getattr(rec, 'cursor', 0.0)):.1f}s" if hasattr(rec, "cursor") else f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}"
            self.status.setText(f"Recording {where}  ·  {int(getattr(rec, 'notes', 0))} notes")
        else:
            player = getattr(self.bridge, "take_player", None)
            notice = str(getattr(self.bridge, "record_notice", "") or "")
            if player is not None and getattr(player, "active", False):
                self.status.setText("Playing " + os.path.basename(str(getattr(self.bridge, "take_to_play", "") or "")))
            else:
                self.status.setText(notice)
        self._enable()
        self.view.update()
        self._maybe_refresh()

    # -- takes
    def _folder(self):
        return str(getattr(self.bridge, "midi_dir", "") or "")

    def _files(self):
        folder = self._folder()
        try:
            names = [n for n in os.listdir(folder) if n.lower().endswith((".mid", ".midi", ".kar"))
                     and "(stave)" not in n and not n.startswith("_preview")]
        except OSError:
            return []
        paths = [os.path.join(folder, n) for n in names]
        return sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)[:300]

    def _maybe_refresh(self):
        files = self._files()
        signature = tuple((p, os.path.getmtime(p)) for p in files)
        if signature != self._signature:
            self.refresh_list(files)

    def _length(self, path):
        stamp = os.path.getmtime(path)
        cached = self._lengths.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            import mido
            seconds = float(mido.MidiFile(path).length)
            text = f"{int(seconds) // 60}:{int(seconds) % 60:02d}"
        except Exception:
            text = "?"
        self._lengths[path] = (stamp, text)
        return text

    def refresh_list(self, files=None):
        files = self._files() if files is None else files
        self._signature = tuple((p, os.path.getmtime(p)) for p in files)
        current = self._current()
        self.tree.clear()
        for path in files:
            item = QTreeWidgetItem([os.path.splitext(os.path.basename(path))[0],
                                    time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))), self._length(path)])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            self.tree.addTopLevelItem(item)
            if path == current:
                self.tree.setCurrentItem(item)
        for column in (1, 2):
            self.tree.resizeColumnToContents(column)

    def _current(self):
        item = self.tree.currentItem()
        return str(item.data(0, Qt.ItemDataRole.UserRole)) if item is not None else ""

    def _open(self):
        path = self._current()
        if path:
            if self.open_hook is not None:
                self.open_hook(path)
            else:
                self.bridge.post_ui_event("take_open", path)

    def _play(self):
        path = self._current()
        if path:
            self.bridge.post_ui_event("take_play_file", path)

    def _rename(self):
        path = self._current()
        if not path:
            return
        stem, ext = os.path.splitext(os.path.basename(path))
        name, ok = QInputDialog.getText(self, "Rename take", "New name", text=stem)
        name = name.strip().replace("/", "-").replace("\\", "-")
        if not ok or not name or name == stem:
            return
        target = os.path.join(os.path.dirname(path), name + ext)
        if os.path.exists(target):
            QMessageBox.information(self, "Rename take", "A take with that name exists already.")
            return
        try:
            os.replace(path, target)
            twin = os.path.join(os.path.dirname(path), stem + " (stave)" + ext)
            if os.path.isfile(twin):
                os.replace(twin, os.path.join(os.path.dirname(path), name + " (stave)" + ext))
        except OSError as error:
            QMessageBox.warning(self, "Rename take", f"Could not rename: {error}")
        self.refresh_list()

    def _delete(self):
        path = self._current()
        if not path or QMessageBox.question(self, "Delete take", f"Move {os.path.basename(path)} to the _trash folder?") != QMessageBox.StandardButton.Yes:
            return
        trash = os.path.join(os.path.dirname(path), "_trash")
        try:
            os.makedirs(trash, exist_ok=True)
            for source in (path, path[:-4] + " (stave).mid"):
                if os.path.isfile(source):
                    target = os.path.join(trash, os.path.basename(source))
                    if os.path.exists(target):
                        target = os.path.join(trash, time.strftime("%H%M%S ") + os.path.basename(source))
                    shutil.move(source, target)
        except OSError as error:
            QMessageBox.warning(self, "Delete take", f"Could not move it: {error}")
        self.refresh_list()
