"""Record Center for the Piano Roll tab: Record / Stop button, live plot of the running take, step-by-step input, new parts added to the
loaded MIDI (next free channel, a live part plays the loaded MIDI along) and a list of takes (open, play, rename, delete to _trash).
Text-based edits (no line numbers), safe to run twice. Usage (repo root): python add_record_center.py

CHANGELOG
2026-11-22  New.
"""
import os
import re

RECORD_CENTER = '"""Record Center: record, live plot, step-by-step input, extra parts and the list of takes. Shown under the Piano Roll.\n\nOne record engine (the bridge\'s Record button / the KeyLab Record key); this panel is its screen and its options:\n  Input   Live, or Step by step (the chord you hold is written at the cursor with the chosen step length, Rest / Back).\n  Target  A new file, or a new part (track + next free channel) added to the MIDI that is loaded. A live part plays the loaded MIDI along.\nThe live plot shows what has been played so far; when the take stops it opens in the Piano Roll as usual.\n\nCHANGELOG\n2026-11-22  New.\n"""\nimport os\nimport shutil\nimport time\nfrom typing import Any\n\nfrom PySide6.QtCore import QRectF, Qt, QTimer\nfrom PySide6.QtGui import QColor, QPainter\nfrom PySide6.QtWidgets import (QComboBox, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTreeWidget,\n                               QTreeWidgetItem, QVBoxLayout, QWidget)\n\nSTEPS = (("Whole", 4.0), ("Half", 2.0), ("Quarter", 1.0), ("Eighth", 0.5), ("Sixteenth", 0.25), ("32nd", 0.125))\n\n\ndef _accent():\n    try:\n        import themes\n        return QColor(themes.tokens().get("accent", "#0b6f5c"))\n    except Exception:\n        return QColor("#0b6f5c")\n\n\nclass LiveTakeView(QWidget):\n    """Notes of the running take as a small scrolling piano roll (time to the right, pitch up), plus the step cursor."""\n    WINDOW = 20.0\n\n    def __init__(self, bridge: Any):\n        super().__init__()\n        self.bridge = bridge\n        self.setMinimumHeight(90)\n\n    def paintEvent(self, event):\n        painter = QPainter(self)\n        painter.fillRect(self.rect(), self.palette().base())\n        rec = getattr(self.bridge, "midi_rec", None)\n        if rec is None or getattr(rec, "started", None) is None:\n            painter.setPen(self.palette().mid().color())\n            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Press Record: the notes you play appear here")\n            painter.end()\n            return\n        step = hasattr(rec, "cursor")\n        now_t = float(rec.cursor) if step else max(0.0, time.time() - float(rec.started))\n        events = list(rec.events)\n        notes, open_notes = [], {}\n        for at, kind, a, b in events:\n            if kind == "on":\n                open_notes[a] = (at, b)\n            elif kind == "off" and a in open_notes:\n                start, velocity = open_notes.pop(a)\n                notes.append((a, start, at, velocity))\n        for note, (start, velocity) in open_notes.items():\n            notes.append((note, start, now_t, velocity))\n        t1 = max(self.WINDOW, now_t + 1.0)\n        t0 = t1 - self.WINDOW\n        pitches = [n[0] for n in notes] or [60]\n        low, high = min(min(pitches) - 2, 48), max(max(pitches) + 2, 72)\n        height, width = self.height(), self.width()\n        accent = _accent()\n        for note, start, end, velocity in notes:\n            if end < t0:\n                continue\n            x0 = (max(start, t0) - t0) / self.WINDOW * width\n            x1 = (end - t0) / self.WINDOW * width\n            y = height - (note - low + 1) / (high - low + 1) * height\n            shade = QColor(accent)\n            shade.setAlphaF(0.45 + 0.55 * min(1.0, velocity / 127.0))\n            painter.fillRect(QRectF(x0, y, max(2.0, x1 - x0), max(2.0, height / (high - low + 1))), shade)\n        x = (now_t - t0) / self.WINDOW * width\n        painter.setPen(QColor("#e53935"))\n        painter.drawLine(int(x), 0, int(x), height)\n        painter.end()\n\n\nclass RecordCenter(QGroupBox):\n    def __init__(self, bridge: Any):\n        super().__init__("Record center")\n        self.bridge = bridge\n        self.setCheckable(True)\n        self.setChecked(True)\n        layout = QVBoxLayout(self)\n        self.body = QWidget()\n        body = QVBoxLayout(self.body)\n        body.setContentsMargins(0, 0, 0, 0)\n        layout.addWidget(self.body)\n        self.toggled.connect(self.body.setVisible)\n\n        row = QHBoxLayout()\n        self.record_button = QPushButton("● Record")\n        self.record_button.setMinimumHeight(30)\n        self.record_button.clicked.connect(lambda: self.bridge.post_ui_event("record"))\n        row.addWidget(self.record_button)\n        self.input_box = QComboBox()\n        self.input_box.addItem("Live", "live")\n        self.input_box.addItem("Step by step", "step")\n        self.target_box = QComboBox()\n        self.target_box.addItem("New file", "new")\n        self.target_box.addItem("New part in the loaded MIDI", "part")\n        self.step_box = QComboBox()\n        for label, beats in STEPS:\n            self.step_box.addItem(label, beats)\n        self.step_box.setCurrentIndex(2)\n        for label, widget in (("Input", self.input_box), ("Add to", self.target_box), ("Step", self.step_box)):\n            row.addWidget(QLabel(label))\n            row.addWidget(widget)\n        self.rest_button = QPushButton("Rest")\n        self.back_button = QPushButton("Back")\n        self.rest_button.clicked.connect(lambda: self.bridge.post_ui_event("step_rest"))\n        self.back_button.clicked.connect(lambda: self.bridge.post_ui_event("step_back"))\n        row.addWidget(self.rest_button)\n        row.addWidget(self.back_button)\n        row.addStretch(1)\n        self.status = QLabel()\n        row.addWidget(self.status)\n        body.addLayout(row)\n        for widget in (self.input_box, self.target_box):\n            widget.currentIndexChanged.connect(self._options_changed)\n        self.step_box.currentIndexChanged.connect(self._options_changed)\n\n        self.view = LiveTakeView(bridge)\n        body.addWidget(self.view)\n\n        self.tree = QTreeWidget()\n        self.tree.setHeaderLabels(["Take", "Recorded", "Length"])\n        self.tree.setRootIsDecorated(False)\n        self.tree.setMinimumHeight(90)\n        self.tree.itemDoubleClicked.connect(lambda *_: self._open())\n        body.addWidget(self.tree, 1)\n        buttons = QHBoxLayout()\n        for text, handler in (("Open in roll", self._open), ("Play", self._play), ("Rename...", self._rename),\n                              ("Delete", self._delete), ("Refresh", self.refresh_list)):\n            button = QPushButton(text)\n            button.clicked.connect(lambda checked=False, h=handler: h())\n            buttons.addWidget(button)\n        buttons.addStretch(1)\n        body.addLayout(buttons)\n\n        self._signature = None\n        self._lengths = {}\n        self.timer = QTimer(self)\n        self.timer.setInterval(200)\n        self.timer.timeout.connect(self._tick)\n        self.timer.start()\n        self._options_changed()\n        self.refresh_list()\n\n    # -- options\n    def _options_changed(self, _=0):\n        self.bridge.post_ui_event("record_options", {"input": self.input_box.currentData(), "target": self.target_box.currentData(),\n                                                     "step": float(self.step_box.currentData())})\n        self._enable()\n\n    def _enable(self):\n        recording = getattr(self.bridge, "midi_rec", None) is not None\n        step = self.input_box.currentData() == "step"\n        self.input_box.setEnabled(not recording)\n        self.target_box.setEnabled(not recording)\n        self.step_box.setEnabled(step)\n        self.rest_button.setEnabled(step and recording)\n        self.back_button.setEnabled(step and recording)\n\n    def _tick(self):\n        if not self.isVisible():\n            return\n        rec = getattr(self.bridge, "midi_rec", None)\n        recording = rec is not None\n        self.record_button.setText("■ Stop" if recording else "● Record")\n        self.record_button.setStyleSheet("color: #e53935; font-weight: 700;" if recording else "")\n        if recording:\n            started = getattr(rec, "started", None)\n            elapsed = max(0.0, time.time() - float(started)) if started else 0.0\n            where = f"step {float(getattr(rec, \'cursor\', 0.0)):.1f}s" if hasattr(rec, "cursor") else f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}"\n            self.status.setText(f"Recording {where}  ·  {int(getattr(rec, \'notes\', 0))} notes")\n        else:\n            self.status.setText("")\n        self._enable()\n        self.view.update()\n        self._maybe_refresh()\n\n    # -- takes\n    def _folder(self):\n        return str(getattr(self.bridge, "midi_dir", "") or "")\n\n    def _files(self):\n        folder = self._folder()\n        try:\n            names = [n for n in os.listdir(folder) if n.lower().endswith((".mid", ".midi", ".kar"))\n                     and "(stave)" not in n and not n.startswith("_preview")]\n        except OSError:\n            return []\n        paths = [os.path.join(folder, n) for n in names]\n        return sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)[:300]\n\n    def _maybe_refresh(self):\n        files = self._files()\n        signature = tuple((p, os.path.getmtime(p)) for p in files)\n        if signature != self._signature:\n            self.refresh_list(files)\n\n    def _length(self, path):\n        stamp = os.path.getmtime(path)\n        cached = self._lengths.get(path)\n        if cached and cached[0] == stamp:\n            return cached[1]\n        try:\n            import mido\n            seconds = float(mido.MidiFile(path).length)\n            text = f"{int(seconds) // 60}:{int(seconds) % 60:02d}"\n        except Exception:\n            text = "?"\n        self._lengths[path] = (stamp, text)\n        return text\n\n    def refresh_list(self, files=None):\n        files = self._files() if files is None else files\n        self._signature = tuple((p, os.path.getmtime(p)) for p in files)\n        current = self._current()\n        self.tree.clear()\n        for path in files:\n            item = QTreeWidgetItem([os.path.splitext(os.path.basename(path))[0],\n                                    time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))), self._length(path)])\n            item.setData(0, Qt.ItemDataRole.UserRole, path)\n            self.tree.addTopLevelItem(item)\n            if path == current:\n                self.tree.setCurrentItem(item)\n        for column in (1, 2):\n            self.tree.resizeColumnToContents(column)\n\n    def _current(self):\n        item = self.tree.currentItem()\n        return str(item.data(0, Qt.ItemDataRole.UserRole)) if item is not None else ""\n\n    def _open(self):\n        path = self._current()\n        if path:\n            self.bridge.post_ui_event("take_open", path)\n\n    def _play(self):\n        path = self._current()\n        if path:\n            self.bridge.post_ui_event("take_open", path)\n            self.bridge.post_ui_event("take_toggle")\n\n    def _rename(self):\n        path = self._current()\n        if not path:\n            return\n        stem, ext = os.path.splitext(os.path.basename(path))\n        name, ok = QInputDialog.getText(self, "Rename take", "New name", text=stem)\n        name = name.strip().replace("/", "-").replace("\\\\", "-")\n        if not ok or not name or name == stem:\n            return\n        target = os.path.join(os.path.dirname(path), name + ext)\n        if os.path.exists(target):\n            QMessageBox.information(self, "Rename take", "A take with that name exists already.")\n            return\n        try:\n            os.replace(path, target)\n            twin = os.path.join(os.path.dirname(path), stem + " (stave)" + ext)\n            if os.path.isfile(twin):\n                os.replace(twin, os.path.join(os.path.dirname(path), name + " (stave)" + ext))\n        except OSError as error:\n            QMessageBox.warning(self, "Rename take", f"Could not rename: {error}")\n        self.refresh_list()\n\n    def _delete(self):\n        path = self._current()\n        if not path or QMessageBox.question(self, "Delete take", f"Move {os.path.basename(path)} to the _trash folder?") != QMessageBox.StandardButton.Yes:\n            return\n        trash = os.path.join(os.path.dirname(path), "_trash")\n        try:\n            os.makedirs(trash, exist_ok=True)\n            for source in (path, path[:-4] + " (stave).mid"):\n                if os.path.isfile(source):\n                    target = os.path.join(trash, os.path.basename(source))\n                    if os.path.exists(target):\n                        target = os.path.join(trash, time.strftime("%H%M%S ") + os.path.basename(source))\n                    shutil.move(source, target)\n        except OSError as error:\n            QMessageBox.warning(self, "Delete take", f"Could not move it: {error}")\n        self.refresh_list()\n'

TAKE_PART = '# ---------------------------------------------------------------------- step-by-step recording and extra parts (Record Center)\nclass StepRecorder(TakeRecorder):\n    """Step-by-step input: the chord held on the keyboard is written at the cursor with the chosen step length when the keys are\n    released, then the cursor moves on. rest() skips a step, back() takes the last chord (or rest) away again."""\n\n    def __init__(self, folder, gap=1e12, min_notes=1, autosave=10, log=None):\n        super().__init__(folder, gap=gap, min_notes=min_notes, autosave=autosave, log=log)\n        self.step_beats = 1.0                 # length of one step in quarter-note beats (1.0 = quarter, 0.5 = eighth ...)\n        self.cursor = 0.0                     # seconds from the start of the take\n        self.pressed = {}                     # note -> velocity of the chord being played\n        self.down = set()                     # keys held right now\n        self.stack = []                       # (events, cursor, notes) before each step, for back()\n\n    def step_seconds(self):\n        return max(0.01, self.step_beats * 60.0 / max(1.0, self.take_bpm))\n\n    def feed(self, message, now):\n        kind = getattr(message, "type", "")\n        if kind not in ("note_on", "note_off") or message.channel != 0 or self.started is None:\n            return\n        self.last_activity = now\n        if kind == "note_on" and message.velocity > 0:\n            self.pressed[message.note] = message.velocity\n            self.down.add(message.note)\n        else:\n            self.down.discard(message.note)\n            if self.pressed and not self.down:\n                self._commit()                      # the last key of the chord came up\n\n    def _commit(self):\n        length = self.step_seconds()\n        self.stack.append((len(self.events), self.cursor, self.notes))\n        for note, velocity in sorted(self.pressed.items()):\n            self.events.append((self.cursor, "on", note, velocity))\n            self.events.append((self.cursor + length * 0.92, "off", note, 0))\n            self.notes += 1\n        self.cursor += length\n        self.pressed = {}\n        self.down = set()\n        self.dirty = True\n\n    def rest(self):\n        self.stack.append((len(self.events), self.cursor, self.notes))\n        self.cursor += self.step_seconds()\n\n    def back(self):\n        if self.stack:\n            count, self.cursor, self.notes = self.stack.pop()\n            del self.events[count:]\n            self.pressed = {}\n            self.down = set()\n            self.dirty = True\n\n\ndef merge_part(base_path, part_path, out_path):\n    """The recorded take as a new track (and the next free channel) of the base MIDI file; written to out_path. Returns the channel\n    used (1-16) or 0 when it could not be done. Times follow the base file\'s own tempo map in ticks, so a take recorded at the session\n    tempo lines up when the base plays at that tempo."""\n    try:\n        import mido\n        base = mido.MidiFile(base_path)\n        part = mido.MidiFile(part_path)\n        used = {m.channel for track in base.tracks for m in track if hasattr(m, "channel")}\n        free = [c for c in range(16) if c != 9 and c not in used]\n        channel = free[0] if free else 0\n        scale = base.ticks_per_beat / float(part.ticks_per_beat or 480)\n        names = [m.name for track in base.tracks for m in track if m.type == "track_name"]\n        track = mido.MidiTrack()\n        track.append(mido.MetaMessage("track_name", name=f"Part {sum(1 for n in names if str(n).startswith(\'Part \')) + 1}", time=0))\n        absolute_in = absolute_out = 0\n        for track_in in part.tracks:\n            absolute_in = absolute_out = 0\n            for message in track_in:\n                absolute_in += message.time\n                if message.type in ("set_tempo", "track_name", "end_of_track", "time_signature"):\n                    continue\n                tick = int(round(absolute_in * scale))\n                copy = message.copy(time=tick - absolute_out)\n                absolute_out = tick\n                if hasattr(copy, "channel"):\n                    copy = copy.copy(channel=channel)\n                track.append(copy)\n        track.append(mido.MetaMessage("end_of_track", time=0))\n        if base.type == 0:\n            base.type = 1\n        base.tracks.append(track)\n        base.save(out_path)\n        return channel + 1\n    except Exception:\n        return 0\n'

LINE = ("Piano Roll: Record center under the roll - Record / Stop, a live plot of the running take, step-by-step input (Rest / Back), "
        "new parts added to the loaded MIDI on the next free channel (a live part plays the loaded MIDI along) and a list of takes "
        "(open, play, rename, delete to _trash). One record engine: the same one as the KeyLab Record key.")


def read(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def edits(path, pairs, marker):
    text = read(path)
    if marker in text:
        print("Unchanged:", path)
        return
    eol = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", eol), new.replace("\n", eol)
        if text.count(old) != 1:
            print("Text not found (file differs), nothing changed in", path + ":", old.strip().splitlines()[0][:70])
            return
        text = text.replace(old, new, 1)
    write(path, text)
    print("Changed:", path)


# --- record_center.py
if os.path.isfile("record_center.py") and read("record_center.py") == RECORD_CENTER:
    print("Unchanged: record_center.py")
else:
    write("record_center.py", RECORD_CENTER)
    print("Written: record_center.py")

# --- take_recorder.py
MARK = "# ---------------------------------------------------------------------- explicit recording (Record button)"
edits("keylab_bridge/take_recorder.py", [
    (MARK, TAKE_PART + "\n\n" + MARK),
    ('def make_midi_recorder(folder, log=None):\n    """Explicit recorder for the Record button: starts at once, never ends on silence, keeps even a short take."""\n    return TakeRecorder(folder, gap=1e12, min_notes=1, autosave=10, log=log)',
     'def make_midi_recorder(folder, log=None, mode="live"):\n    """Explicit recorder for the Record button: starts at once, never ends on silence, keeps even a short take. mode "step" = step-by-step."""\n    if mode == "step":\n        return StepRecorder(folder, log=log)\n    return TakeRecorder(folder, gap=1e12, min_notes=1, autosave=10, log=log)'),
], "class StepRecorder")

# --- application.py
edits("keylab_bridge/application.py", [
    ("        self.midi_rec = None                    # explicit Record-button session\n",
     "        self.midi_rec = None                    # explicit Record-button session\n"
     "        self.record_input = \"live\"             # Record center: \"live\" or \"step\"\n"
     "        self.record_target = \"new\"             # \"new\" file or a new \"part\" in the loaded MIDI\n"
     "        self.record_step_beats = 1.0\n"
     "        self._part_base = \"\"\n"),
    ("        from .take_recorder import make_midi_recorder, write_stave_friendly\n",
     "        from .take_recorder import make_midi_recorder, merge_part, write_stave_friendly\n"),
    ("            self.midi_rec = make_midi_recorder(self.midi_dir, log=lambda t, **k: self.log(t, notify=False))\n",
     "            self.midi_rec = make_midi_recorder(self.midi_dir, log=lambda t, **k: self.log(t, notify=False), mode=self.record_input)\n"
     "            if hasattr(self.midi_rec, \"step_beats\"):\n                setattr(self.midi_rec, \"step_beats\", self.record_step_beats)\n"
     "            base = self.take_to_play if self.record_target == \"part\" else \"\"\n"
     "            self._part_base = base if base and os.path.isfile(base) and not os.path.basename(base).startswith(\"_preview\") else \"\"\n"
     "            if self.record_target == \"part\" and not self._part_base:\n                self.log(\"No MIDI is loaded: recording a new file\")\n"),
    ('            self.log("Recording started (Record button again to stop)")\n            return\n',
     '            self.log("Recording started (Record button again to stop)")\n'
     '            if self._part_base and self.record_input == "live":\n                self.toggle_take_playback()            # the loaded MIDI plays along while the new part is played\n'
     '            return\n'),
    ("        rec, self.midi_rec = self.midi_rec, None\n        path = rec.path\n        rec.close()\n",
     "        rec, self.midi_rec = self.midi_rec, None\n        path = rec.path\n        rec.close()\n"
     "        base, self._part_base = self._part_base, \"\"\n"
     "        if base:\n            self.take_player.stop()\n"
     "        if base and path and os.path.isfile(base) and os.path.isfile(path):\n"
     "            stem = re.sub(r\" \\+part \\d+$\", \"\", os.path.splitext(os.path.basename(base))[0])\n"
     "            number = 1\n"
     "            while os.path.exists(os.path.join(os.path.dirname(base), f\"{stem} +part {number}.mid\")):\n                number += 1\n"
     "            merged = os.path.join(os.path.dirname(base), f\"{stem} +part {number}.mid\")\n"
     "            channel = merge_part(base, path, merged)\n"
     "            if channel:\n                self.set_take(merged)\n"
     "                self.log(f\"New part saved on channel {channel}: {os.path.basename(merged)} (the recording itself is kept too)\")\n"
     "                return\n"
     "            self.log(\"The part could not be added to the loaded MIDI; the recording is kept as its own file\")\n"),
    ('        elif event == "take_open":\n',
     '        elif event == "record":\n            self.toggle_record()\n'
     '        elif event == "record_options" and isinstance(value, dict):\n'
     '            self.record_input = "step" if value.get("input") == "step" else "live"\n'
     '            self.record_target = "part" if value.get("target") == "part" else "new"\n'
     '            self.record_step_beats = max(0.0625, float(value.get("step", 1.0) or 1.0))\n'
     '            if hasattr(self.midi_rec, "step_beats"):\n                setattr(self.midi_rec, "step_beats", self.record_step_beats)\n'
     '        elif event in ("step_rest", "step_back"):\n'
     '            action = getattr(self.midi_rec, "rest" if event == "step_rest" else "back", None)\n'
     '            if callable(action):\n                action()\n'
     '        elif event == "take_open":\n'),
], "record_options")

# --- qt_gui.py
edits("qt_gui.py", [
    ("            self._tab_pages[key] = (page, page_layout)\n            self.top_tabs.addTab(page, title)\n",
     "            self._tab_pages[key] = (page, page_layout)\n            self.top_tabs.addTab(page, title)\n"
     "        from record_center import RecordCenter\n        self.record_center = RecordCenter(self.bridge)\n"
     "        self._tab_pages[\"roll\"][1].addWidget(self.record_center)\n"),
    ("            widget.setWindowFlags(Qt.WindowType.Widget)\n            page_layout.addWidget(widget)\n        widget.show()\n",
     "            widget.setWindowFlags(Qt.WindowType.Widget)\n            page_layout.addWidget(widget)\n"
     "            if key == \"roll\" and getattr(self, \"record_center\", None) is not None:\n"
     "                page_layout.removeWidget(self.record_center)\n                page_layout.addWidget(self.record_center)      # the Record center stays under the roll\n"
     "        widget.show()\n"),
], "record_center")

# --- changelog
text = read("CHANGELOG.md")
if "Record center" not in text:
    eol = "\r\n" if "\r\n" in text else "\n"
    text = re.sub(r"(### New\r?\n)", lambda m: m.group(1) + "- " + LINE + eol, text, count=1)
    write("CHANGELOG.md", text)
    print("Changed: CHANGELOG.md")
