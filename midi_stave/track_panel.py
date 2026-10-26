"""Track list for the MIDI Track / Piano Roll Editor: one row per voice (MIDI track + channel) in the file.

Each row: active (the voice new notes and piano keys use), show on the stave, editable name (also the stave's title),
channel (re-channels the voice's notes), instrument and note count. Tracks can be added and removed.
Everything edited here goes through the stave editor, so the engraved score follows.

CHANGELOG
2026-10-26  New.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDockWidget, QHBoxLayout, QHeaderView, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

COLS = ("", "Show", "Track name", "Ch", "Instrument", "Notes")


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
        for c in (0, 1, 3, 5):
            head.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setToolTip("Click a row to make it the active track: new notes and the piano keys use it.\n"
                              "Double-click the name to rename (the stave title follows). Edit Ch to move the track to another channel.")
        self.table.itemSelectionChanged.connect(self._row_selected)
        self.table.itemChanged.connect(self._item_changed)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        add, remove = QPushButton("Add track"), QPushButton("Remove")
        add.setToolTip("Add an empty track; click the roll to write notes into it")
        remove.setToolTip("Delete the selected track and all its notes (undo with Ctrl+Z)")
        add.clicked.connect(self.add_track)
        remove.clicked.connect(self.remove_track)
        row.addWidget(add)
        row.addWidget(remove)
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

    def refresh(self):
        st = self.stave
        if not hasattr(st, "extra_voices"):
            st.extra_voices = set()
        voices = self._voices()
        self.keys = [v[0] for v in voices]
        if getattr(st, "active_voice", None) not in self.keys:
            st.active_voice = self.keys[0] if self.keys else None
        self._busy = True
        self.table.setRowCount(len(voices))
        for r, (k, name, inst, count) in enumerate(voices):
            dot = QTableWidgetItem("●" if k == st.active_voice else "")
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
            for c, item in enumerate((dot, show, label, ch, ins, cnt)):
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
            self.table.item(r, 0).setText("●" if self.keys[r] == self.stave.active_voice else "")
        self._busy = False
        self.stave.statusBar().showMessage(f"Active track: {self.table.item(rows[0].row(), 2).text()} - new notes and piano keys use it.")

    def _item_changed(self, item):
        if self._busy or item.row() >= len(self.keys):
            return
        st, key = self.stave, self.keys[item.row()]
        if item.column() == 1:
            (st.hidden_tracks.discard if item.checkState() == Qt.CheckState.Checked else st.hidden_tracks.add)(key)
            st.show_tracks()
            st.changed()
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
        st.hidden_tracks.discard(key)
        st.info.get("voice_names", {}).pop(key, None)
        st.active_voice = None
        st.after_edit()
        st.show_tracks()
        self.refresh()
