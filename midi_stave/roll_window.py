"""Piano roll as its own window: tools, snap, zoom, edit / select / view menus, note names on the notes, a bar ruler, an overview
strip, a keyboard and a velocity lane that all share two scroll bars (one horizontal, one vertical).

CHANGELOG
2026-10-25  New: the roll moved out of the main window into this pop-up.
2026-10-26  Keys taller / shorter = Ctrl+Up / Ctrl+Down, wheel zoom reversible and centred, grid fills the window, saved layouts (Layout menu).
2026-10-26  Edit > Shape MIDI timing.
2026-10-26  Renamed MIDI Track / Piano Roll Editor; track list panel (track_panel.py): active track, show, names, channel, add / remove.
"""
import json
from PySide6.QtCore import QByteArray, QRectF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QComboBox, QGridLayout, QLabel, QMainWindow, QScrollBar, QSlider, QSpacerItem, QToolBar,
                               QWidget)

SNAPS = (("Off", 0), ("Bar", -1), ("1 beat", 1.0), ("1/2 beat", 0.5), ("1/4 beat", 0.25), ("1/8 beat", 0.125),
         ("1/3 beat (triplet)", 1 / 3), ("1/6 beat (triplet)", 1 / 6), ("Score grid (Smallest note)", None))


class Ruler(QWidget):
    """Bar numbers and beat ticks above the roll; click a bar to select it."""

    def __init__(self, stave):
        super().__init__()
        self.stave = stave
        self.setFixedHeight(22)

    def paintEvent(self, event):
        st, roll = self.stave, self.stave.roll
        p = QPainter(self)
        pal = self.palette()
        p.fillRect(self.rect(), pal.window())
        if not st.notes or not roll.bar_items:
            return
        accent = pal.highlight().color()
        for i, item in enumerate(roll.bar_items):
            x = roll.mapFromScene(item.x(), 0).x()
            if x < -50 or x > self.width() + 50:
                continue
            nxt = roll.bar_items[i + 1].x() if i + 1 < len(roll.bar_items) else item.x()
            p.setPen(QPen(accent if i == st.selected_bar else pal.text().color(), 1))
            p.drawLine(x, 4, x, self.height())
            if nxt > item.x() and i < st.barmap.bar_count:
                p.drawText(x + 4, 14, str(i + 1))
                beats = st.barmap.beats[i]
                p.setPen(QPen(QColor(128, 138, 150, 140), 1))
                width = roll.mapFromScene(nxt, 0).x() - x
                if width / max(1.0, beats) >= 9:
                    for b in range(1, int(beats)):
                        bx = x + width * b / beats
                        p.drawLine(int(bx), 14, int(bx), self.height())
        if roll.playhead is not None and roll.playhead.isVisible():
            p.setPen(QPen(QColor(255, 60, 60), 2))
            px = roll.mapFromScene(roll.playhead.line().x1(), 0).x()
            p.drawLine(px, 0, px, self.height())
        p.end()

    def mousePressEvent(self, event):
        roll = self.stave.roll
        x = roll.mapToScene(int(event.position().x()), 0).x()
        index = max(0, sum(1 for b in roll.bar_items if b.x() <= x) - 1)
        roll.barSelected.emit(index)
        roll.cursor_sec = max(0.0, x / roll.pps)
        self.update()


class Overview(QWidget):
    """The whole piece in one thin strip; the lit frame is what the roll shows. Click / drag to move there."""

    def __init__(self, stave):
        super().__init__()
        self.stave = stave
        self.setFixedHeight(34)

    def _span(self):
        st = self.stave
        end = max([n.end for n in st.notes] + [st.barmap.anchors[-1]]) if st.notes else 1.0
        return max(1.0, end)

    def paintEvent(self, event):
        st, roll = self.stave, self.stave.roll
        p = QPainter(self)
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        if not st.notes:
            return
        span, w, h = self._span(), self.width(), self.height()
        lo, hi = min(n.pitch for n in st.notes), max(n.pitch for n in st.notes)
        rng = max(12, hi - lo)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(140, 170, 190, 170))
        for n in st.notes:
            x = n.start / span * w
            y = h - 4 - (n.pitch - lo) / rng * (h - 8)
            p.drawRect(QRectF(x, y, max(1.0, (n.end - n.start) / span * w), 2))
        view_l = roll.horizontalScrollBar().value() / roll.pps / span * w
        view_w = roll.viewport().width() / roll.pps / span * w
        accent = QColor(pal.highlight().color())
        p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 45))
        p.setPen(QPen(accent, 1.5))
        p.drawRect(QRectF(view_l, 1, max(6.0, view_w), h - 2))
        p.end()

    def _go(self, event):
        roll = self.stave.roll
        t = event.position().x() / max(1, self.width()) * self._span()
        bar = roll.horizontalScrollBar()
        bar.setValue(int(t * roll.pps - roll.viewport().width() / 2))

    mousePressEvent = mouseMoveEvent = _go


class RollWindow(QMainWindow):
    def __init__(self, stave):
        super().__init__(stave)
        import midi_stave as M
        self.M, self.stave = M, stave
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("MIDI Track / Piano Roll Editor")
        self.settings = QSettings("KeyLabGrandOrgue", "MidiStave")
        self.resize(1100, 640)
        geo = self.settings.value("roll_geometry")
        if geo:
            self.restoreGeometry(geo)
        roll = stave.roll
        stave.keys, stave.velocity_lane = M.PianoKeys(stave), M.VelocityLane(stave)
        self.ruler, self.overview = Ruler(stave), Overview(stave)
        self.hbar, self.vbar = QScrollBar(Qt.Orientation.Horizontal), QScrollBar(Qt.Orientation.Vertical)
        root = QWidget()
        grid = QGridLayout(root)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self.lane_label = QLabel(" Velocity")
        self.lane_label.setFixedWidth(46)
        self.lane_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(self.overview, 0, 1)
        grid.addWidget(self.ruler, 1, 1)
        grid.addWidget(stave.keys, 2, 0)
        grid.addWidget(roll, 2, 1)
        grid.addWidget(self.vbar, 2, 2)
        grid.addWidget(self.lane_label, 3, 0)
        grid.addWidget(stave.velocity_lane, 3, 1)
        grid.addWidget(self.hbar, 4, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(2, 1)
        self.setCentralWidget(root)
        # one pair of scroll bars drives the roll, ruler, overview, keys and lane
        hs, vs = roll.horizontalScrollBar(), roll.verticalScrollBar()
        hs.rangeChanged.connect(self.hbar.setRange)
        vs.rangeChanged.connect(self.vbar.setRange)
        hs.valueChanged.connect(self.hbar.setValue)
        vs.valueChanged.connect(self.vbar.setValue)
        self.hbar.valueChanged.connect(hs.setValue)
        self.vbar.valueChanged.connect(vs.setValue)
        for bar_roll, bar_mine in ((hs, self.hbar), (vs, self.vbar)):
            bar_roll.rangeChanged.connect(lambda lo, hi, b=bar_roll, m=bar_mine: m.setPageStep(b.pageStep()))
        hs.valueChanged.connect(lambda _v: (self.ruler.update(), self.overview.update()))
        roll.hoverInfo.connect(lambda text: self.statusBar().showMessage(text))
        import track_panel
        self.tracks = track_panel.TrackPanel(stave, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tracks)
        self.tracks.setMinimumWidth(260)
        self._build_tools()
        self._build_menus()
        self.statusBar().showMessage("Select a tool above. Wheel = up / down, Shift + wheel = sideways, Ctrl + wheel = zoom time, Alt + wheel = zoom keys.")
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(120)
        self.refresh_timer.timeout.connect(self._tick)
        self.refresh_timer.start()
        self._shortcuts()
        try:
            last = json.loads(self.settings.value("roll_last", "") or "{}")
            if last:
                QTimer.singleShot(0, lambda: self.apply_layout(last))
        except ValueError:
            pass

    # ---- bars
    def _tick(self):
        if self.isVisible():
            self.ruler.update()
            self.overview.update()
            st = self.stave
            t = st.pos_hook() if st.pos_hook else None
            self.time_label.setText(f"  bar {st.barmap.bar_of_beat(st.barmap.sec_to_beat(st.barmap.beat_to_sec(t * st.barmap.average_bpm() / 60.0))) + 1}  " if t is not None else "  ")

    def _build_tools(self):
        st, M = self.stave, self.M
        bar = QToolBar("Tools")
        bar.setObjectName("rollTools")
        bar.setMovable(False)
        bar.setIconSize(QSize(22, 22))
        self.addToolBar(bar)
        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        from chrome import icon as make_icon
        for kind, text, tip, key in (("select", "Select", "Select / move / resize notes (V)", "V"),
                                     ("add", "Draw", "Draw notes: click to add, drag the note ends to resize (D)", "D"),
                                     ("erase", "Erase", "Erase notes (E)", "E"),
                                     ("slice", "Slice", "Slice a note in two where you click (S)", "S"),
                                     ("mute", "Mute", "Mute / unmute notes (M)", "M")):
            act = QAction(text, self)
            if kind in ("select", "add", "erase"):
                act.setIcon(make_icon(kind, st.palette().windowText().color(), 22))
            act.setToolTip(tip)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(key))
            act.triggered.connect(lambda _=False, k=kind: self.set_tool(k))
            self.tool_group.addAction(act)
            bar.addAction(act)
            self.tool_actions[kind] = act
        self.tool_actions["select"].setChecked(True)
        bar.addSeparator()
        bar.addWidget(QLabel(" Snap "))
        self.snap_box = QComboBox()
        for label, value in SNAPS:
            self.snap_box.addItem(label, value)
        self.snap_box.setCurrentIndex(len(SNAPS) - 1)
        self.snap_box.currentIndexChanged.connect(self._snap_changed)
        bar.addWidget(self.snap_box)
        bar.addWidget(QLabel("  Note length "))
        bar.addWidget(self._shared_combo(st.new_len))
        bar.addSeparator()
        bar.addWidget(QLabel(" Time "))
        self.h_zoom = QSlider(Qt.Orientation.Horizontal)
        self.h_zoom.setRange(8, 600)
        self.h_zoom.setValue(int(st.roll.pps))
        self.h_zoom.setFixedWidth(110)
        self.h_zoom.valueChanged.connect(self._set_pps)
        bar.addWidget(self.h_zoom)
        bar.addWidget(QLabel(" Keys "))
        self.v_zoom = QSlider(Qt.Orientation.Horizontal)
        self.v_zoom.setRange(3, 40)
        self.v_zoom.setValue(M.ROW)
        self.v_zoom.setFixedWidth(80)
        self.v_zoom.valueChanged.connect(self._set_row)
        bar.addWidget(self.v_zoom)
        bar.addSeparator()
        for text, handler, tip in (("Play", st.play_on_organ, "Play on the organ from where it paused (Space)"),
                                   ("Pause", st.pause_on_organ, "Pause"), ("Stop", st.stop_on_organ, "Stop and rewind")):
            act = QAction(text, self)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, h=handler: h())
            bar.addAction(act)
        audition = QAction("Audition", self)
        audition.setCheckable(True)
        audition.setToolTip("Click or drag on the roll: hear the notes under the line, on the manuals the tracks are mapped to, "
                            "for as long as the button is held")
        audition.toggled.connect(st.set_audition_mode)
        bar.addAction(audition)
        self.audition_action = audition
        self.time_label = QLabel("  ")
        bar.addWidget(self.time_label)

    def _shared_combo(self, source):
        box = QComboBox()
        box.addItems([source.itemText(i) for i in range(source.count())])
        box.setCurrentText(source.currentText())
        box.currentTextChanged.connect(source.setCurrentText)
        source.currentTextChanged.connect(box.setCurrentText)
        return box

    def _snap_changed(self):
        st = self.stave
        value = self.snap_box.currentData()
        st.snap.setChecked(value != 0)
        if value == -1:
            value = st.barmap.beats[0] if st.barmap.bar_count else 4.0
        st.roll_snap = value or None
        st.refresh_roll(keep_view=True)

    def _set_pps(self, value):
        self.stave.roll.pps = float(value)
        self.stave.refresh_roll(keep_view=True)

    def _set_row(self, value):
        """Change the key height, keeping the pitch in the middle of the window where it was."""
        roll, M = self.stave.roll, self.M
        vbar = roll.verticalScrollBar()
        centre = roll.top - (vbar.value() + roll.viewport().height() / 2) / max(1, M.ROW)
        M.ROW = int(value)
        self.stave.refresh_roll(keep_view=True)
        vbar.setValue(int((roll.top - centre) * M.ROW - roll.viewport().height() / 2))
        self.stave.keys.update()

    def zoom_keys(self, step):
        value = max(self.v_zoom.minimum(), min(self.v_zoom.maximum(), self.v_zoom.value() + step))
        self.v_zoom.setValue(value)                    # the slider calls _set_row

    def set_tool(self, kind):
        from chrome import set_tool
        set_tool(self.stave, kind)
        if kind in self.tool_actions:
            self.tool_actions[kind].setChecked(True)

    # ---- menus
    def _menus_action(self, menu, text, handler, shortcut=None, checkable=False, checked=False):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
            act.toggled.connect(handler)
        else:
            act.triggered.connect(lambda _=False: handler())
        menu.addAction(act)
        return act

    def _build_menus(self):
        st, roll = self.stave, self.stave.roll
        a = self._menus_action
        m = self.menuBar().addMenu("&File")
        a(m, "Import MIDI / MusicXML...", st.open_dialog, "Ctrl+M")
        a(m, "New blank score...", st.new_blank, "Ctrl+N")
        a(m, "Save as MIDI...", st.save_edited_midi, "Ctrl+S")
        a(m, "Export score as PDF...", st.export_pdf)
        m.addSeparator()
        a(m, "Close roll", self.close)
        m = self.menuBar().addMenu("&Edit")
        a(m, "Undo", st.undo, "Ctrl+Z")
        a(m, "Redo", st.redo, "Ctrl+Y")
        m.addSeparator()
        a(m, "Shape MIDI timing (quantise, swing, humanise, legato)...", st.open_shape, "Ctrl+Q")
        m.addSeparator()
        a(m, "Cut", lambda: st.copy_notes(True), "Ctrl+X")
        a(m, "Copy", st.copy_notes, "Ctrl+C")
        a(m, "Paste (at the last click / selected bar)", st.paste_notes, "Ctrl+V")
        a(m, "Duplicate", lambda: st.duplicate_notes(st.selected_notes()), "Ctrl+D")
        a(m, "Delete", lambda: st.delete_notes(st.selected_notes()), "Del")
        m.addSeparator()
        a(m, "Shift left by one snap step", lambda: st.shift_selected(-1), "Shift+Left")
        a(m, "Shift right by one snap step", lambda: st.shift_selected(1), "Shift+Right")
        a(m, "Transpose up", lambda: st.transpose_selected(1), "Shift+Up")
        a(m, "Transpose down", lambda: st.transpose_selected(-1), "Shift+Down")
        a(m, "Octave up", lambda: st.transpose_selected(12), "Ctrl+Shift+Up")
        a(m, "Octave down", lambda: st.transpose_selected(-12), "Ctrl+Shift+Down")
        m.addSeparator()
        a(m, "Snap the starts to the grid", st.quantise_starts, "Ctrl+Q")
        a(m, "Discard lengths (one snap step each)", st.discard_lengths, "Shift+D")
        a(m, "Legato (run on to the next start)", st.legato_selected, "Ctrl+L")
        a(m, "Mute selected", lambda: st.set_mute(st.selected_notes(), True), "Alt+M")
        a(m, "Unmute selected", lambda: st.set_mute(st.selected_notes(), False), "Shift+Alt+M")
        m.addSeparator()
        a(m, "Insert a bar of space here", st.insert_space, "Ctrl+I")
        a(m, "Add 4 bars at the end", lambda: st.add_bars(4))
        m = self.menuBar().addMenu("&Select")
        a(m, "All", lambda: st.select_all_notes("all"), "Ctrl+A")
        a(m, "None", lambda: st.select_all_notes("none"), "Ctrl+Shift+A")
        a(m, "Invert", lambda: st.select_all_notes("invert"), "Ctrl+Shift+I")
        a(m, "Same pitch as the selection", lambda: st.select_all_notes("pitch"))
        a(m, "Everything in the selected bar", lambda: st.select_all_notes("bar"))
        a(m, "Everything from here on", lambda: st.select_all_notes("after"))
        m = self.menuBar().addMenu("&View")
        a(m, "Note names on the notes", lambda on: (setattr(self.M.NoteItem, "show_labels", on), roll.viewport().update()), checkable=True, checked=True)
        a(m, "Show the score's quantised notes as shadows", lambda on: (setattr(roll, "show_ghosts", on), st.refresh_roll(True)), checkable=True, checked=True)
        a(m, "Colour notes by track", lambda on: (setattr(roll, "colour_by_track", on), st.refresh_roll(True)), checkable=True, checked=True)
        a(m, "Fade the notes of the other tracks", lambda on: (setattr(roll, "dim_inactive", on), st.refresh_roll(True)), checkable=True, checked=True)
        a(m, "Highlight the notes of the key", lambda on: (setattr(roll, "highlight_scale", on), st.refresh_roll(True)), checkable=True)
        a(m, "Invert the row shading", lambda on: (setattr(roll, "invert_grid", on), st.refresh_roll(True)), checkable=True)
        grid = m.addMenu("Grid lines")
        group = QActionGroup(self)
        self.grid_acts = {}
        for label, mode in (("None", "none"), ("Bars", "bars"), ("Beats", "beats"), ("Snap steps", "grid")):
            act = QAction(label, self, checkable=True)
            act.setChecked(mode == "grid")
            act.triggered.connect(lambda _=False, md=mode: (setattr(roll, "grid_mode", md), st.refresh_roll(True)))
            group.addAction(act)
            grid.addAction(act)
            self.grid_acts[mode] = act
        a(m, "Velocity lane", lambda on: (st.velocity_lane.setVisible(on), self.lane_label.setVisible(on)), checkable=True, checked=True)
        a(m, "Overview strip", self.overview.setVisible, checkable=True, checked=True)
        a(m, "Follow the music while playing", lambda on: setattr(roll, "follow", on), checkable=True, checked=True)
        m = self.menuBar().addMenu("&Zoom")
        a(m, "Time in", lambda: self.h_zoom.setValue(int(self.h_zoom.value() * 1.3)), "Ctrl+=")
        a(m, "Time out", lambda: self.h_zoom.setValue(int(self.h_zoom.value() / 1.3)), "Ctrl+-")
        a(m, "Keys taller", lambda: self.zoom_keys(2), "Ctrl+Up")
        a(m, "Keys shorter", lambda: self.zoom_keys(-2), "Ctrl+Down")
        a(m, "Fit the whole piece", self.fit_all, "Ctrl+0")
        a(m, "Zoom to the selection", self.fit_selection, "Ctrl+Shift+0")
        self.layout_menu = self.menuBar().addMenu("&Layout")
        self.layout_menu.aboutToShow.connect(self._fill_layout_menu)

    def _shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.stave.toggle_play)

    def fit_all(self):
        st = self.stave
        if st.notes:
            end = max(n.end for n in st.notes) + 0.5
            self.h_zoom.setValue(max(8, min(600, int(self.stave.roll.viewport().width() / end))))
            self.stave.roll.horizontalScrollBar().setValue(0)

    def fit_selection(self):
        notes = self.stave.selected_notes()
        if not notes:
            return
        a, b = min(n.start for n in notes), max(n.end for n in notes)
        roll = self.stave.roll
        self.h_zoom.setValue(max(8, min(600, int(roll.viewport().width() / max(0.3, b - a + 0.4)))))
        roll.horizontalScrollBar().setValue(int((a - 0.1) * roll.pps))
        roll.verticalScrollBar().setValue(int((roll.top - max(n.pitch for n in notes) - 3) * self.M.ROW))

    def center_on_notes(self):
        st, roll = self.stave, self.stave.roll
        if st.notes:
            mid = sum(n.pitch for n in st.notes) / len(st.notes)
            roll.verticalScrollBar().setValue(int((roll.top - mid) * self.M.ROW - roll.viewport().height() / 2))

    # ---- layouts: zoom, snap, grid, panels, window and toolbar arrangement
    TOGGLES = (("Note names on the notes", "labels"), ("Show the score's quantised notes as shadows", "ghosts"),
               ("Highlight the notes of the key", "scale"), ("Colour notes by track", "bytrack"), ("Fade the notes of the other tracks", "fade"), ("Invert the row shading", "invert"),
               ("Velocity lane", "lane"), ("Overview strip", "overview"), ("Follow the music while playing", "follow"))

    def _toggle_actions(self):
        found = {}
        for act in self.findChildren(QAction):
            for text, key in self.TOGGLES:
                if act.text() == text and act.isCheckable():
                    found[key] = act
        return found

    def capture_layout(self):
        roll = self.stave.roll
        centre = roll.top - (roll.verticalScrollBar().value() + roll.viewport().height() / 2) / max(1, self.M.ROW)
        return {"pps": int(roll.pps), "row": int(self.M.ROW), "snap": self.snap_box.currentIndex(), "grid": roll.grid_mode,
                "toggles": {k: a.isChecked() for k, a in self._toggle_actions().items()}, "centre_pitch": round(centre, 1),
                "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                "state": bytes(self.saveState().toBase64()).decode("ascii")}

    def apply_layout(self, d):
        roll = self.stave.roll
        try:
            if "geometry" in d:
                self.restoreGeometry(QByteArray.fromBase64(d["geometry"].encode("ascii")))
            if "state" in d:
                self.restoreState(QByteArray.fromBase64(d["state"].encode("ascii")))
            if d.get("grid") in self.grid_acts:
                self.grid_acts[d["grid"]].setChecked(True)
                roll.grid_mode = d["grid"]
            for key, act in self._toggle_actions().items():
                if key in d.get("toggles", {}) and act.isChecked() != d["toggles"][key]:
                    act.setChecked(d["toggles"][key])                  # fires the menu's own handler
            if "snap" in d and 0 <= d["snap"] < self.snap_box.count():
                self.snap_box.setCurrentIndex(d["snap"])
            if "pps" in d:
                self.h_zoom.setValue(int(d["pps"]))
            if "row" in d:
                self.v_zoom.setValue(int(d["row"]))
            if "centre_pitch" in d:
                roll.verticalScrollBar().setValue(int((roll.top - d["centre_pitch"]) * self.M.ROW - roll.viewport().height() / 2))
        except (TypeError, ValueError, KeyError):
            pass

    def _layouts(self):
        try:
            data = json.loads(self.settings.value("roll_layouts", "{}") or "{}")
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    def _fill_layout_menu(self):
        menu = self.layout_menu
        menu.clear()
        menu.addAction("Save current layout as...", self.save_layout_as)
        menu.addSeparator()
        layouts = self._layouts()
        for name in sorted(layouts):
            menu.addAction(name, lambda n=name: self.apply_layout(self._layouts().get(n, {})))
        if layouts:
            menu.addSeparator()
            remove = menu.addMenu("Delete layout")
            for name in sorted(layouts):
                remove.addAction(name, lambda n=name: self._delete_layout(n))
        menu.addSeparator()
        menu.addAction("Default layout", lambda: self.apply_layout({"pps": 60, "row": 6, "snap": len(SNAPS) - 1, "grid": "grid",
                                                                     "toggles": {k: True for _t, k in self.TOGGLES if k not in ("scale", "invert")}}))

    def save_layout_as(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save layout", "Name this layout (zoom, snap, grid, panels, window):")
        if ok and name.strip():
            data = self._layouts()
            data[name.strip()] = self.capture_layout()
            self.settings.setValue("roll_layouts", json.dumps(data))
            self.statusBar().showMessage(f"Layout '{name.strip()}' saved.", 4000)

    def _delete_layout(self, name):
        data = self._layouts()
        data.pop(name, None)
        self.settings.setValue("roll_layouts", json.dumps(data))

    def closeEvent(self, event):
        self.settings.setValue("roll_geometry", self.saveGeometry())
        try:
            self.settings.setValue("roll_last", json.dumps(self.capture_layout()))      # reopens exactly as you left it
        except Exception:
            pass
        super().closeEvent(event)
