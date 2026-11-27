"""Dialogs and pickers of the Stave editor (solfa, lyrics, stop / setter pickers, voice registration).

Split out of midi_stave.py without behaviour change (imported by bare name like core / render; midi_stave.py re-imports every name).

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  Moved verbatim from midi_stave.py (modularisation, v2.0.9-69).
"""

import core
import sessionmeta
import solfa
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from PySide6.QtGui import (
    QPageSize,
    QPdfWriter,
)
from PySide6.QtCore import (
    Qt,
)


class SolfaDialog(QDialog):
    """Tonic sol-fa view of the voices (SATB alone, or with the organ) for printing."""

    VOICE_WORDS = ("soprano", "alto", "tenor", "bass", "sop", "choir", "chor", "voice", "vocal", "satb", "vox")

    def __init__(self, stave):
        super().__init__(stave)
        self.stave = stave
        self.setWindowTitle("Tonic sol-fa")
        self.resize(1000, 760)
        p = stave.params()
        self.staves = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], stave.notes,
                                       stave.info.get("voice_names"), organ=p.get("organ"))
        per = core.assign(stave.qnotes, self.staves)
        typed = [n for n in p["names"]]
        self.voices = []
        for i, (spec, notes) in enumerate(zip(self.staves, per)):
            name = typed[i] if i < len(typed) and typed[i] else spec.name
            self.voices.append((name, notes))
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.checks = []
        for name, notes in self.voices:
            box = QCheckBox(name)
            box.setChecked(True)
            box.toggled.connect(self.render)
            self.checks.append(box)
            top.addWidget(box)
        top.addStretch(1)
        lay.addLayout(top)
        quick = QHBoxLayout()
        for text, handler in (("SATB alone", self.pick_choir), ("With organ (everything)", self.pick_all)):
            b = QPushButton(text)
            b.clicked.connect(handler)
            quick.addWidget(b)
        tonic, minor, text = stave.key_for_solfa()
        self.doh = QComboBox()
        self.doh.addItems(["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"])
        self.doh.setCurrentIndex(tonic)
        self.minor = QCheckBox("minor key (lah-based: doh = relative major)")
        self.minor.setChecked(minor)
        self.per_line = QSpinBox()
        self.per_line.setRange(1, 8)
        self.per_line.setValue(4)
        self.per_line.setPrefix("bars per line: ")
        quick.addWidget(QLabel("  Key:"))
        quick.addWidget(self.doh)
        quick.addWidget(self.minor)
        quick.addWidget(self.per_line)
        quick.addStretch(1)
        lay.addLayout(quick)
        from PySide6.QtWidgets import QTextBrowser
        self.view = QTextBrowser()
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        pdf = QPushButton("Save PDF...")
        pdf.clicked.connect(self.save_pdf)
        prt = QPushButton("Print...")
        prt.clicked.connect(self.print_it)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        for b in (pdf, prt, close):
            row.addWidget(b)
        lay.addLayout(row)
        for w in (self.doh,):
            w.currentIndexChanged.connect(self.render)
        self.minor.toggled.connect(self.render)
        self.per_line.valueChanged.connect(self.render)
        if any(any(w in n.casefold() for w in self.VOICE_WORDS) for n, _ in self.voices):
            self.pick_choir()
        else:
            self.render()

    def pick_choir(self):
        voice = [any(w in name.casefold() for w in self.VOICE_WORDS) for name, _ in self.voices] if self.stave.layout_kind.currentText().lower().find("choir") < 0 else [True] * len(self.voices)
        for box, on in zip(self.checks, voice):
            box.blockSignals(True)
            box.setChecked(on)
            box.blockSignals(False)
        self.render()

    def pick_all(self):
        for box in self.checks:
            box.blockSignals(True)
            box.setChecked(True)
            box.blockSignals(False)
        self.render()

    def render(self, *_):
        stave = self.stave
        chosen = [v for v, box in zip(self.voices, self.checks) if box.isChecked()]
        tonic = self.doh.currentIndex()
        doh_pc = solfa.doh_for(tonic, self.minor.isChecked())
        cum = stave.barmap.cumulative()
        key_text = f"{self.doh.currentText()} {'minor' if self.minor.isChecked() else 'major'}"
        beats = [float(b) for b in stave.barmap.beats]
        self.html = solfa.build_html(stave.title.text() or "Untitled", key_text, stave.meter.currentText(), chosen,
                                     [float(c) if False else c for c in cum], beats, doh_pc, stave.transpose.value(),
                                     self.per_line.value())
        self.view.setHtml(self.html)

    def _document(self, writer):
        from PySide6.QtGui import QTextDocument
        doc = QTextDocument()
        doc.setHtml(self.html)
        doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size())
        return doc

    def save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save tonic sol-fa PDF", self.stave._suggest(" (solfa).pdf"), "PDF (*.pdf)")
        if path:
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setResolution(150)
            self._document(writer).print_(writer)

    def print_it(self):
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter()
        if QPrintDialog(printer, self).exec():
            self._document(printer).print_(printer)


class LyricsDialog(QDialog):
    """Words under the staves: up to six verses, for all voices or one voice. One syllable per note, in time order."""

    def __init__(self, stave):
        super().__init__(stave)
        self.stave = stave
        self.setWindowTitle("Words (lyrics)")
        self.resize(760, 560)
        p = stave.params()
        staves = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], stave.notes,
                                  stave.info.get("voice_names"), organ=p.get("organ"))
        typed = p["names"]
        self.scopes = [("all", "All voices (same words under every stave)")] + [
            (str(i), typed[i] if i < len(typed) and typed[i] else spec.name) for i, spec in enumerate(staves)]
        self.data = {k: list(v) for k, v in stave.lyrics.items()}
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Words for:"))
        self.scope = QComboBox()
        for key, label in self.scopes:
            self.scope.addItem(label, key)
        top.addWidget(self.scope, 1)
        lay.addLayout(top)
        lay.addWidget(QLabel("Type the words of each verse. Split a word into syllables with hyphens (Je-su, right-eous-ness); "
                             "type _ for a note that gets no new syllable. A voice's own words replace the \"All voices\" words."))
        from PySide6.QtWidgets import QPlainTextEdit, QTabWidget
        self.tabs = QTabWidget()
        self.edits = []
        for v in range(6):
            edit = QPlainTextEdit()
            edit.setPlaceholderText("Je-su, thy blood and right-eous-ness My beau-ty are, my glo-rious dress ...")
            edit.textChanged.connect(self._store)
            self.edits.append(edit)
            self.tabs.addTab(edit, f"Verse {v + 1}")
        lay.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        clear = QPushButton("Clear these words")
        clear.clicked.connect(self.clear_scope)
        row.addWidget(clear)
        row.addStretch(1)
        ok = QPushButton("Apply to score")
        ok.clicked.connect(self.apply)
        cancel = QPushButton("Close")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.scope.currentIndexChanged.connect(self._load_scope)
        self._load_scope()

    def _key(self):
        return self.scope.currentData()

    def _load_scope(self, *_):
        verses = self.data.get(self._key(), [])
        for i, edit in enumerate(self.edits):
            edit.blockSignals(True)
            edit.setPlainText(verses[i] if i < len(verses) else "")
            edit.blockSignals(False)

    def _store(self):
        verses = [e.toPlainText() for e in self.edits]
        while verses and not verses[-1].strip():
            verses.pop()
        if verses:
            self.data[self._key()] = verses
        else:
            self.data.pop(self._key(), None)

    def clear_scope(self):
        for e in self.edits:
            e.clear()

    def apply(self):
        self.stave.lyrics = {k: v for k, v in self.data.items() if any(t.strip() for t in v)}
        self.stave.save_lyrics()
        self.stave.changed(delay=50)
        self.accept()


# ---------------------------------------------------------------------------------------------- main window
class StopPicker(QDialog):
    """Tick individual stops (grouped by manual) and the bar they apply from."""

    def __init__(self, stops, manuals, bar, bars, preset=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stops")
        self.stops, self.paths, self.label = stops, [], ""
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("From bar"))
        self.bar_spin = QSpinBox()
        self.bar_spin.setRange(1, bars)
        self.bar_spin.setValue(min(bar, bars))
        row.addWidget(self.bar_spin)
        row.addStretch(1)
        layout.addLayout(row)
        self.list = QListWidget()
        names = {i: n for i, (n, _p, _c) in enumerate(manuals)}
        last = None
        for st in stops:
            if st["manual"] != last:
                last = st["manual"]
                head = QListWidgetItem(f"-- {names.get(last, last)} --")
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(head)
            item = QListWidgetItem(f'{st["name"]}')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if preset and st["path"] in preset else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, st["path"])
            self.list.addItem(item)
        layout.addWidget(self.list)
        layout.addWidget(QLabel("Stops of a manual not ticked here are switched off on that manual."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(360, 520)

    def bar(self):
        return self.bar_spin.value()

    def _ok(self):
        self.paths = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                      if self.list.item(i).checkState() == Qt.CheckState.Checked]
        by_path = {s["path"]: s["name"] for s in self.stops}
        self.label = ", ".join(by_path[p] for p in self.paths[:4]) + ("..." if len(self.paths) > 4 else "")
        self.accept()


class _Ticked:
    """Stands in for a ticked check box when a track (not a stave voice) carries the registration."""

    def __init__(self, value):
        self.value = value

    def isChecked(self):
        return self.value


class VoiceRegDialog(QDialog):
    """A voice's registration changes, bar by bar: setters or individual stops."""

    def __init__(self, stave, index=None, entries=None):
        super().__init__(stave)
        self.stave, self.index = stave, index
        self.entries = entries if entries is not None else stave.voice_reg[index]
        self.setWindowTitle("Registration changes for this voice")
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list)
        row = QHBoxLayout()
        for text, handler in (("Add setter...", self.add_setter), ("Add stops...", self.add_stops), ("Remove", self.remove)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            row.addWidget(btn)
        layout.addLayout(row)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.refresh()
        self.resize(420, 340)

    def refresh(self):
        self.entries.sort(key=lambda e: e["bar"])
        self.list.clear()
        for e in self.entries:
            what = (f'Setter {e["id"]} {e["name"]}  [{e["filename"]}]' if e["kind"] == "setter"
                    else f'Stops: {e.get("label", "")} ({len(e["paths"])})')
            self.list.addItem(f'Bar {e["bar"] + 1}: {what}')

    def _bar(self):
        sel = self.stave.selected_bar
        return (sel if sel is not None else 0) + 1

    def add_setter(self):
        if not self.stave.combos:
            QMessageBox.information(self, "Setters", "No setter list found (stave editor must sit in the Scripts folder).")
            return
        d = SetterPicker(self.stave.combos, self._bar(), max(1, self.stave.barmap.bar_count), self)
        if d.exec() == QDialog.DialogCode.Accepted and d.choice:
            c = d.choice
            self.entries[:] = [e for e in self.entries if e["bar"] != d.bar() - 1]
            self.entries.append({"bar": d.bar() - 1, "kind": "setter", "filename": c["filename"], "id": c["internal_id"], "name": c["name"]})
            self.refresh()

    def add_stops(self):
        stops = sessionmeta.load_stops()
        if not stops:
            QMessageBox.information(self, "Stops", "No stop list found (stave editor must sit in the Scripts folder).")
            return
        d = StopPicker(stops, self.stave.manuals, self._bar(), max(1, self.stave.barmap.bar_count), None, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.entries[:] = [e for e in self.entries if e["bar"] != d.bar() - 1]
            self.entries.append({"bar": d.bar() - 1, "kind": "stops", "paths": d.paths, "label": d.label})
            self.refresh()

    def remove(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.entries):
            del self.entries[row]
            self.refresh()


class SetterPicker(QDialog):
    """Pick an existing stop combination: setter file, then its step (000-0xx), and the bar it starts at."""

    def __init__(self, combos, bar, bars, parent=None, with_bar=True, allow_none=False):
        super().__init__(parent)
        self.setWindowTitle("Organ setter")
        self.allow_none = allow_none
        self.combos, self.choice = combos, None
        layout = QFormLayout(self)
        self.files = QComboBox()
        self.files.addItems(list(dict.fromkeys(c["filename"] for c in combos)))
        self.steps = QListWidget()
        self.bar_spin = QSpinBox()
        self.bar_spin.setRange(1, bars)
        self.bar_spin.setValue(min(bar, bars))
        if with_bar:
            layout.addRow("Starts at bar", self.bar_spin)
        layout.addRow("Setter file", self.files)
        layout.addRow("Step", self.steps)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        if allow_none:
            clear = buttons.addButton("No registration", QDialogButtonBox.ButtonRole.ResetRole)
            clear.clicked.connect(self.accept)           # accepted with choice None
        layout.addRow(buttons)
        self.files.currentTextChanged.connect(self._fill)
        self.steps.itemDoubleClicked.connect(lambda *_: self._ok())
        self._fill(self.files.currentText())
        self.resize(420, 420)

    def _fill(self, filename):
        self.steps.clear()
        self.mine = [c for c in self.combos if c["filename"] == filename]
        for c in self.mine:
            self.steps.addItem(f'{c["internal_id"]}  {c["name"]}')
        self.steps.setCurrentRow(0)

    def bar(self):
        return self.bar_spin.value()

    def _ok(self):
        row = self.steps.currentRow()
        if row >= 0:
            self.choice = self.mine[row]
            self.accept()
