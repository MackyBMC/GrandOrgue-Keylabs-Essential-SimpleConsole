"""Track list for the MIDI Track / Piano Roll Editor: one row per voice (MIDI track + channel) in the file.

Each row: active (the voice new notes and piano keys use), show on the stave, editable name (also the stave's title),
channel (re-channels the voice's notes), instrument and note count. Tracks can be added and removed.
Everything edited here goes through the stave editor, so the engraved score follows.

CHANGELOG
2026-10-26  New.
2026-10-26  Organ column + "Organ..." dialog: each track chooses the manual(s) (MIDI channel) it plays on and its registration changes
            (setters / stops, bar by bar), whatever the stave layout is. Like choosing an instrument for a track in a DAW.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QDockWidget, QHBoxLayout, QHeaderView,
                               QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


class OrganDialog(QDialog):
    """Which manual(s) of the organ a track plays on (= the MIDI channel GrandOrgue listens on) and its registration changes."""

    def __init__(self, stave, key, name):
        super().__init__(stave)
        import midi_stave as M
        self.M, self.stave, self.key = M, stave, key
        current = stave.track_map.get(key, {})
        self.reg = [dict(e) for e in current.get("reg", [])]
        self.setWindowTitle(f"Organ - {name}")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Play track \"{name}\" on:"))
        self.boxes = {}
        for manual, _path, channel in stave.manuals:
            box = QCheckBox(f"{manual}   (MIDI channel {channel})")
            box.setChecked(manual in current.get("manuals", []))
            self.boxes[manual] = box
            lay.addWidget(box)
        self.split = QCheckBox("Bass to pedal: the lowest note of every chord plays on the Pedal (mono bass line);\n"
                               "the other notes play on the manual(s) ticked above")
        self.split.setToolTip("For a polyphonic track whose lowest notes are a bass part. Nothing in the track is changed.")
        self.split.setChecked(bool(current.get("bass_split")))
        lay.addWidget(self.split)
        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("   Bass notes: at or below MIDI note"))
        self.limit = QSpinBox()
        self.limit.setRange(24, 96)
        self.limit.setValue(int((current.get("bass_split") or {}).get("limit", 55)))
        self.limit.setToolTip("A lone note above this stays on the manual (melody); 55 = G3, 60 = middle C")
        limit_row.addWidget(self.limit)
        limit_row.addStretch(1)
        lay.addLayout(limit_row)
        extract = QPushButton("Extract the bass to its own pedal track now")
        extract.setToolTip("Moves the lowest note of every chord into a new real track (own stave and piano-roll row), mapped to the Pedal")
        extract.clicked.connect(self.extract)
        lay.addWidget(extract)
        self.extract_requested = False
        row = QHBoxLayout()
        suggest = QPushButton("Suggest from the track")
        suggest.setToolTip("Pick the manual from the track's name, instrument and register")
        suggest.clicked.connect(self.suggest)
        if "Pedal" in current.get("manuals", []) or current.get("bass_split"):
            pass
        self.reg_button = QPushButton()
        self.reg_button.setToolTip("Setters or individual stops that apply from a chosen bar, for the manuals ticked above")
        self.reg_button.clicked.connect(self.edit_reg)
        row.addWidget(suggest)
        row.addWidget(self.reg_button)
        lay.addLayout(row)
        self.hint = QLabel("A track with no manual ticked follows the stave layout.")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._reg_text()

    def _reg_text(self):
        self.reg_button.setText(f"Registration... ({len(self.reg)} change{'s' if len(self.reg) != 1 else ''})")

    def suggest(self):
        import sessionmeta
        st, key = self.stave, self.key
        row = next((r for r in (st.info or {}).get("tracks", []) if (r["track"], r["channel"]) == key), {})
        pitches = sorted(n.pitch for n in st.notes if (n.track, n.ch) == key) or [60]
        name = (st.info or {}).get("voice_names", {}).get(key) or row.get("name", "")
        manuals, stops, why = sessionmeta.suggest(name, row.get("program"), pitches[len(pitches) // 2])
        poly = core_is_poly(st.notes, key)
        if poly and "Pedal" in manuals:                       # a polyphonic "bass" track: bass line on the pedal, the rest on a manual
            manuals = tuple(manuals) + tuple(m for m in ("Hauptwerk",) if m not in manuals)
            self.split.setChecked(True)
        for manual, box in self.boxes.items():
            box.setChecked(manual in manuals)
        tip = ", ".join(x["name"] for x in sessionmeta.suggest_stops(manuals[0], stops)[:6])
        self.hint.setText(f"Suggested {'/'.join(manuals)} ({why})" + (f" - stops such as {tip}" if tip else ""))

    def edit_reg(self):
        self.M.VoiceRegDialog(self.stave, entries=self.reg).exec()
        self._reg_text()

    def extract(self):
        self.extract_requested = True
        self.accept()

    def result_map(self):
        ticked = [m for m, b in self.boxes.items() if b.isChecked()]
        out = {"manuals": ticked, "reg": self.reg}
        rest = [m for m in ticked if m != "Pedal"]
        if self.split.isChecked() and rest:
            out["manuals"] = rest
            out["bass_split"] = {"rest": rest, "limit": self.limit.value()}
        return out


def core_is_poly(notes, key):
    import core
    return core.is_polyphonic(notes, key)


COLS = ("", "Show", "Track name", "Ch", "Instrument", "Organ", "Notes")


class TrackPanel(QDockWidget):
    def __init__(self, stave, parent=None):
        super().__init__("Tracks", parent)
        self.stave = stave
        self.setObjectName("trackPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self._busy = False
        self.keys = []
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(4, 4, 4, 4)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 3, 5, 6):
            head.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setToolTip("Click a row to make it the active track: new notes and the piano keys use it.\n"
                              "Double-click the name to rename (the stave title follows). Edit Ch to move the track to another channel.")
        self.table.itemSelectionChanged.connect(self._row_selected)
        self.table.itemChanged.connect(self._item_changed)
        self.table.cellDoubleClicked.connect(lambda r, c: self.map_organ() if c == 5 else None)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        add, remove, organ = QPushButton("Add track"), QPushButton("Remove"), QPushButton("Organ...")
        organ.setToolTip("Choose the manual (MIDI channel) and registration this track plays with")
        organ.clicked.connect(self.map_organ)
        add.setToolTip("Add an empty track; click the roll to write notes into it")
        remove.setToolTip("Delete the selected track and all its notes (undo with Ctrl+Z)")
        add.clicked.connect(self.add_track)
        remove.clicked.connect(self.remove_track)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(organ)
        lay.addLayout(row)
        self.setWidget(body)
        self.refresh()

    # ---- model
    def _voices(self):
        st = self.stave
        info = st.info or {}
        meta = {}
        for r in info.get("tracks", []):
            if r.get("channel") is not None:
                meta[(r["track"], r["channel"])] = r
        counts = {}
        for n in st.notes:
            counts[(n.track, n.ch)] = counts.get((n.track, n.ch), 0) + 1
        keys = set(counts) | set(getattr(st, "extra_voices", set()))
        names = info.get("voice_names", {})
        out = []
        for k in sorted(keys):
            m = meta.get(k, {})
            out.append((k, names.get(k) or m.get("name") or f"Track {k[0] + 1}", m.get("instrument", ""), counts.get(k, 0)))
        return out

    def _organ_text(self, key):
        import sessionmeta
        m = self.stave.track_map.get(key)
        if not m or not m.get("manuals"):
            return "stave layout"
        text = "+".join(sessionmeta.MANUAL_SHORT.get(n, n) for n in m["manuals"])
        if m.get("bass_split"):
            text = "bass P / " + text
        return text + (f"  ({len(m['reg'])} reg)" if m.get("reg") else "")

    def map_organ(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self.keys):
            return
        key = self.keys[rows[0].row()]
        dialog = OrganDialog(self.stave, key, self.table.item(rows[0].row(), 2).text())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.result_map()
            if dialog.extract_requested:
                self.extract_bass(key, result)
                return
            if result["manuals"] or result["reg"]:
                self.stave.track_map[key] = result
            else:
                self.stave.track_map.pop(key, None)
            self.stave.staves_for_export()                         # publish the routes now
            self.refresh()
            self.stave.statusBar().showMessage("Track mapped to the organ: playback, export and piano keys use it.", 5000)

    def extract_bass(self, key, rest_map):
        """Move the lowest note of every chord of this track into a new track on the Pedal (a real, editable track)."""
        import core
        st = self.stave
        leads = core.pedal_leads(st.notes, [key], st.chord.value() / 1000.0, (rest_map.get("bass_split") or {}).get("limit", 55))
        if not leads:
            return
        st.push_undo()
        track = max([k[0] for k in self.keys] + [0]) + 1
        new_key = (track, key[1])
        for _i, n in leads:
            n.track = track
        name = (st.info or {}).get("voice_names", {}).get(key) or f"Track {key[0] + 1}"
        st.info.setdefault("voice_names", {})[new_key] = f"{name} (pedal)"
        st.track_map[new_key] = {"manuals": ["Pedal"], "reg": []}
        if rest_map["manuals"] and "Pedal" not in rest_map["manuals"]:
            st.track_map[key] = {"manuals": rest_map["manuals"], "reg": rest_map["reg"]}
        st.active_voice = new_key
        st.after_edit()
        st.show_tracks()
        st.changed(delay=50)                                       # the stave layout and score pick up the new track
        self.refresh()
        st.statusBar().showMessage(f"{len(leads)} bass notes moved to a new pedal track. Ctrl+Z undoes it.", 6000)

    def refresh(self):
        st = self.stave
        if not hasattr(st, "extra_voices"):
            st.extra_voices = set()
        voices = self._voices()
        palette = st.voice_colours()
        self.keys = [v[0] for v in voices]
        if getattr(st, "active_voice", None) not in self.keys:
            st.active_voice = self.keys[0] if self.keys else None
        self._busy = True
        self.table.setRowCount(len(voices))
        for r, (k, name, inst, count) in enumerate(voices):
            dot = QTableWidgetItem("▶" if k == st.active_voice else "●")
            dot.setForeground(palette.get(k, QColor(200, 200, 200)))
            dot.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            show = QTableWidgetItem()
            show.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            show.setCheckState(Qt.CheckState.Unchecked if k in st.hidden_tracks else Qt.CheckState.Checked)
            label = QTableWidgetItem(name)
            ch = QTableWidgetItem(str(k[1] + 1))
            ins = QTableWidgetItem(inst)
            ins.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            cnt = QTableWidgetItem(str(count))
            cnt.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            organ = QTableWidgetItem(self._organ_text(k))
            organ.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            organ.setToolTip("Double-click (or Organ...) to choose the manual and registration for this track")
            for c, item in enumerate((dot, show, label, ch, ins, organ, cnt)):
                self.table.setItem(r, c, item)
        if st.active_voice in self.keys:
            self.table.selectRow(self.keys.index(st.active_voice))
        self._busy = False

    # ---- events
    def _row_selected(self):
        if self._busy:
            return
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self.keys):
            return
        self.stave.active_voice = self.keys[rows[0].row()]
        self._busy = True
        for r in range(self.table.rowCount()):
            self.table.item(r, 0).setText("▶" if self.keys[r] == self.stave.active_voice else "●")
        self._busy = False
        self.stave.refresh_roll(keep_view=True)                                  # fade the other tracks
        self.stave.statusBar().showMessage(f"Active track: {self.table.item(rows[0].row(), 2).text()} - new notes and piano keys use it.")

    def _item_changed(self, item):
        if self._busy or item.row() >= len(self.keys):
            return
        st, key = self.stave, self.keys[item.row()]
        if item.column() == 1:
            (st.hidden_tracks.discard if item.checkState() == Qt.CheckState.Checked else st.hidden_tracks.add)(key)
            st.show_tracks()
            st.changed()
            st.refresh_roll(keep_view=True)
        elif item.column() == 2:
            text = item.text().strip() or f"Track {key[0] + 1}"
            st.info.setdefault("voice_names", {})[key] = text
            st.show_tracks()
            st.changed()
        elif item.column() == 3:
            try:
                new = int(item.text()) - 1
            except ValueError:
                new = -1
            if not 0 <= new <= 15 or new == key[1]:
                self.refresh()
                return
            st.push_undo()
            for n in st.notes:
                if (n.track, n.ch) == key:
                    n.ch = new
            self._rekey(key, (key[0], new))
            st.after_edit()
            st.show_tracks()
            self.refresh()

    def _rekey(self, old, new):
        st = self.stave
        names = st.info.setdefault("voice_names", {})
        if old in names:
            names[new] = names.pop(old)
        if old in st.hidden_tracks:
            st.hidden_tracks.discard(old)
            st.hidden_tracks.add(new)
        if old in st.extra_voices:
            st.extra_voices.discard(old)
            st.extra_voices.add(new)
        if old in st.track_map:
            st.track_map[new] = st.track_map.pop(old)
            st.staves_for_export()
        if st.active_voice == old:
            st.active_voice = new

    def add_track(self):
        st = self.stave
        used = {k[0] for k in self.keys}
        track = (max(used) + 1) if used else 0
        free = [c for c in range(16) if c != 9 and c not in {k[1] for k in self.keys}]
        key = (track, free[0] if free else 0)
        st.extra_voices.add(key)
        st.info.setdefault("voice_names", {})[key] = f"Track {track + 1}"
        st.active_voice = key
        self.refresh()
        st.statusBar().showMessage("Track added and active - click the roll to write notes into it.")

    def remove_track(self):
        st = self.stave
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self.keys):
            return
        key = self.keys[rows[0].row()]
        count = sum(1 for n in st.notes if (n.track, n.ch) == key)
        if count and QMessageBox.question(self, "Remove track", f"Delete this track and its {count} notes?") != QMessageBox.StandardButton.Yes:
            return
        st.push_undo()
        st.notes[:] = [n for n in st.notes if (n.track, n.ch) != key]
        st.sel_notes = set()
        st.extra_voices.discard(key)
        st.track_map.pop(key, None)
        st.hidden_tracks.discard(key)
        st.info.get("voice_names", {}).pop(key, None)
        st.active_voice = None
        st.after_edit()
        st.show_tracks()
        self.refresh()
