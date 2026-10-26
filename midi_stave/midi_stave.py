"""
CHANGELOG
2026-10-24  Words: "Words (lyrics)..." - up to six verses under the staves, for all voices or one voice (hyphens split
            syllables, _ = note without a new syllable); kept next to the file as <file>.lyrics.json.
2026-10-24  Timeline is a seek bar: click or drag to move to a position (plays from there); "Bar N" box goes to a bar.
2026-10-24  Look: Material Design icons (qtawesome, optional - painted icons are the fallback), tool strip and transport
            bar can be dragged to any edge or torn off as floating palettes (layout remembered; View > Reset window
            layout), Properties panel folds to a slim strip (button or F4) and can be detached; polished style sheet.
2026-10-24  Tonic sol-fa (solfa.py): choose the voices (SATB alone, or with the organ staves), the key (doh; minor keys
            lah-based) and bars per line; preview, Save PDF or Print. Export section button "Tonic sol-fa...".
2026-10-24  "Advanced organ notation" section: multi-measure rests (only where every stave is silent; the pedal alone
            gets "Ped. tacet"), clef switch on the manual staves, "Organ (for rehearsal only)" label, registrations
            printed as Gt.: Principal 8', 4', 2' | Sw.: ... with the feet in descending order.
2026-10-24  New layout (chrome.py): slim icon tool strip on the left (open, save, PDF, undo / redo, tools Select / Add /
            Erase / Toe / Heel with keys V A E T H, step, play, stop) and a Properties panel on the right showing the
            selected note(s) - pitch, start, length, velocity, pedal mark, manuals - above folding sections that
            hold all the other options. Piano roll and score get the whole middle.
2026-10-24  Score is edited by hand: grab a note head and drag it up / down (snaps to the key's scale steps, an orange
            ghost shows where it lands and its name, the new pitch sounds on the organ as you pass it) or sideways (snaps
            to the neighbouring note positions); release to apply to the whole selection. Pedal marks: drag Toe (^) /
            Heel (U) from the top palette onto a note head (or right-click > Pedal mark). Engraving follows organ
            practice: brace over Manual I/II + bracket over all staves, Manual I / Manual II / Pedal names (Man. / Ped.
            on later systems), "Ped. tacet" over 4+ bars of pedal rest.
2026-10-24  Red playing-bar fixed (a self-closing SVG group threw the bar search off, so some bars never lit up). Fixed
            transport bar on top (Play / Stop / Play selection, timeline, loaded file); Space = play / stop. Loading a
            file while playing stops it and shows the top of the new score. Voices are given manuals from what the file
            says they are (track name, GM instrument, register); the voice row tooltip lists suggested stops.
2026-10-23  Engraving runs in a separate process (engrave_job.py): the heavy music21 / Verovio work no longer freezes the
            console or starves its MIDI threads. The engraved score is interactive: click a note head to select it
            (Shift = add), drag a box to select many, right-click for the note menu, arrow keys / Del edit it. Step
            sequence: select notes, then Step > / < Step (or KeyLab >> / << in Step mode) plays them chord by chord on
            the organ; "Play selection" plays the selection in time.
MIDI -> Stave: turn a recording (or any MIDI file) into sheet music you can tune before printing.

Top: the performance as a piano roll with draggable bar lines. Where you played slow, rushed or lagged, drag the bar
line to where the bar really starts; every note inside the bar re-fits. Orange outlines show where each note will land
after quantising. Bottom: the engraved score, redrawn a moment after every change. Export PDF / MusicXML / straightened MIDI.

CHANGELOG
2026-10-20  Added: transpose (semitones, or "Move piece to key" from the detected key, e.g. Eb -> C), editable stave
            names (Organ, Trombone, ...), 1/64 notes, final double bar, slurs on joined-up phrases and optional
            staccato dots (taken from how legato you actually played), and MusicXML / .mxl files can be opened
            (their written bars, tempo and parts are used as they are, one stave per part).
2026-10-20  First version. Piano roll with draggable bar lines (right-click: insert / delete a bar line), per-bar length
            and grid, nudge buttons, ghost outlines of the quantised notes, automatic bar / tempo / triplet detection
            that follows rubato, layouts (solo, grand staff, organ, choir SATB, per channel), key, dynamics from
            velocity, live preview (Verovio) and PDF / MusicXML / straightened-MIDI export. Takes recorded by the
            console (Scripts\\midi) are listed on the left: double-click one to load it.
"""

import json
import os
import time
import sys
import threading
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PySide6.QtCore import QByteArray, QPointF, QRect, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QPageSize, QPainter, QPdfWriter, QPen, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QListWidgetItem, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGraphicsRectItem, QGraphicsScene,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

import core
import render
import sessionmeta
import chrome
if os.path.dirname(HERE) not in sys.path:
    sys.path.append(os.path.dirname(HERE))          # polish.py lives next to the midi_stave folder
import polish
import solfa
sys.path.insert(1, os.path.dirname(HERE))      # so keylab_bridge (setter list) can be imported

ROW = 6                                    # piano-roll pixel height of one semitone
SHEET_FOLDER = r"C:\Audio\sheet music"
PAGE_SIZES = {"A4": (2100, 2970, QPageSize.PageSizeId.A4), "Letter": (2159, 2794, QPageSize.PageSizeId.Letter)}
KEYS = ["auto"] + ["C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db", "Gb",
                   "a", "e", "b", "f#", "c#", "d", "g", "c", "f", "bb", "eb"]
def tonic_pc(name):
    """'Eb' -> 3, 'f#' -> 6, 'bb' (B-flat minor) -> 10."""
    value = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name[0].upper()]
    for ch in name[1:]:
        value += 1 if ch == "#" else -1 if ch == "b" else 0
    return value % 12


TIME_SIGS = {"4/4": 4.0, "3/4": 3.0, "2/4": 2.0, "6/8": 3.0, "5/4": 5.0, "12/8": 6.0, "2/2": 4.0, "3/8": 1.5}


# ------------------------------------------------------------------------------------------- piano roll
class BarLine(QGraphicsRectItem):
    def __init__(self, index, x, height, view):
        super().__init__(-3, 0, 6, height)
        self.index, self.view = index, view
        self.setPos(x, 0)
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable | QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.set_selected(False)
        self.setZValue(10)

    def set_selected(self, on):
        self.setBrush(QBrush(QColor(242, 163, 58, 200) if on else QColor(79, 209, 197, 70)))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        painter.drawLine(0, 0, 0, int(self.rect().height()))

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange:
            items = self.view.bar_items
            lo = items[self.index - 1].x() + 10 if self.index > 0 else -1e9
            hi = items[self.index + 1].x() - 10 if self.index + 1 < len(items) else 1e9
            return QPointF(max(lo, min(hi, value.x())), 0)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.view.barSelected.emit(self.index)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.view.barMoved.emit(self.index, self.x() / self.view.pps)


class ScorePage(QSvgWidget):
    """One engraved page that can be clicked: note heads are hit-tested against positions Verovio reported.
    Click = select (Shift = add), drag on empty space = rubber-band select, right-click = note menu, keys = edit."""

    def __init__(self, stave, index):
        super().__init__()
        self.stave, self.index = stave, index
        self.marks = []                    # (x, y) outer SVG units of selected note heads
        self.band = None
        self.press = None
        self.drag = None                   # note head being dragged: {"hit", "note", "start", "plan", "last"}
        self.drop_hit = None               # note head a palette sign is hovering over
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def to_svg(self, pos):
        vw, vh = self.stave.page_dims[self.index] if self.index < len(self.stave.page_dims) else (1.0, 1.0)
        return pos.x() / max(1, self.width()) * vw, pos.y() / max(1, self.height()) * vh

    def paintEvent(self, event):
        super().paintEvent(event)
        bands = [b for b in (self.stave.stave_bands[self.index] if self.index < len(getattr(self.stave, "stave_bands", [])) else [])
                 if b["idx"] == self.stave.sel_stave] if self.stave.sel_stave is not None else []
        if not self.marks and self.band is None and self.drag is None and self.drop_hit is None and not bands:
            return
        vw, vh = self.stave.page_dims[self.index]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(30, 110, 255), 2))
        p.setBrush(QBrush(QColor(30, 110, 255, 60)))
        if bands:                                          # the selected stave, in every system
            try:
                import themes
                tint = QColor(themes.tokens()["accent"])
            except Exception:
                tint = QColor(30, 110, 255)
            sx_, sy_ = self.width() / vw, self.height() / vh
            for b in bands:
                pad = (b["y1"] - b["y0"]) * 0.35
                rect = QRectF(b["x0"] * sx_ - 6, (b["y0"] - pad) * sy_, (b["x1"] - b["x0"]) * sx_ + 12, (b["y1"] - b["y0"] + 2 * pad) * sy_)
                fill = QColor(tint)
                fill.setAlpha(42)
                p.setPen(QPen(tint, 2))
                p.setBrush(QBrush(fill))
                p.drawRoundedRect(rect, 6, 6)
        r = 9.0 * self.width() / vw                # about one staff space around the note head
        space = self.stave.spaces[self.index] if self.index < len(self.stave.spaces) else 18.0
        rx, ry = 0.68 * space * self.width() / vw, 0.56 * space * self.height() / vh       # same size as the engraved head
        try:
            import themes
            accent = QColor(themes.tokens()["accent"])
        except Exception:
            accent = QColor(30, 110, 255)
        for x, y in self.marks:
            fill = QColor(accent)
            fill.setAlpha(150)
            p.setPen(QPen(accent, 1.5))
            p.setBrush(QBrush(fill))
            p.drawEllipse(QPointF(x / vw * self.width(), y / vh * self.height()), rx, ry)
        p.setPen(QPen(QColor(30, 110, 255), 2))
        p.setBrush(QBrush(QColor(30, 110, 255, 60)))
        if self.band is not None:
            p.setBrush(QBrush(QColor(30, 110, 255, 30)))
            p.drawRect(self.band)
        sx, sy = self.width() / vw, self.height() / vh
        if self.drag is not None and self.drag["plan"] is not None:       # live ghost of the head where it will land
            hit, (steps, pitch, beat, x_off, y_off) = self.drag["hit"], self.drag["plan"]
            gx, gy = (hit[0] + x_off) * sx, (hit[1] + y_off) * sy
            p.setPen(QPen(QColor(230, 120, 20), 2))
            p.setBrush(QBrush(QColor(255, 150, 30, 150)))
            p.drawEllipse(QPointF(gx, gy), r * 0.9, r * 0.65)
            p.setPen(QPen(QColor(120, 50, 0), 1))
            p.drawText(QPointF(gx + r * 1.4, gy + 4), self.stave.pitch_name(pitch))
        if self.drop_hit is not None:                                       # note head a palette mark would attach to
            p.setPen(QPen(QColor(30, 170, 80), 3))
            p.setBrush(QBrush(QColor(30, 170, 80, 70)))
            p.drawEllipse(QPointF(self.drop_hit[0] * sx, self.drop_hit[1] * sy), r * 1.3, r * 1.3)
        p.end()

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self.to_svg(event.position())
            hit, note = self.stave.hit_near(self.index, x, y, 1.0)
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if note is not None and self.stave.tool_click(note):       # erase / toe / heel tools act on the click
                return
            if note is None and self.stave.tool == "select" and self.stave.click_page_area(self.index, x, y):
                return
            if note is None and self.stave.tool == "add":
                self.stave.add_note_from_score(self.index, x, y)
                return
            if note is not None:
                self.stave.select_note(note, shift)
                self.drag = {"hit": hit, "note": note, "start": event.position().toPoint(), "plan": None, "last": None,
                             "moved": False}
                self.stave.preview_pitch(hit[2], note)                  # hear the note you grabbed
            else:
                self.press = event.position().toPoint()
                if not shift:
                    self.stave.select_note(None, False)
        elif event.button() == Qt.MouseButton.RightButton:
            hit = self.stave.hit_at(self.index, *self.to_svg(event.position()))
            if hit is not None:
                self.stave.note_menu(hit, event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self.drag is not None:
            d = self.drag
            moved = event.position().toPoint() - d["start"]
            if not d["moved"] and moved.manhattanLength() < 5:
                return
            d["moved"] = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            sx, sy = self.to_svg(event.position())
            plan = self.stave.drag_plan(self.index, d["hit"], sx - d["hit"][0], sy - d["hit"][1])
            d["plan"] = plan
            if plan[1] != d["last"]:                                    # a new pitch passed under the cursor: sound it
                d["last"] = plan[1]
                self.stave.preview_pitch(plan[1], d["note"])
            self.update()
        elif self.press is not None:
            self.band = QRect(self.press, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag is not None:
            d, self.drag = self.drag, None
            self.unsetCursor()
            if d["moved"] and d["plan"] is not None:
                self.stave.commit_drag(self.index, d["hit"], d["note"], d["plan"])
            self.update()
            return
        if self.press is not None and self.band is None and event.button() == Qt.MouseButton.LeftButton:
            self.stave.click_stave(self.index, *self.to_svg(event.position()))          # a plain click inside a stave selects that stave
        if self.press is not None and self.band is not None:
            a, b = self.to_svg(self.band.topLeft()), self.to_svg(self.band.bottomRight())
            self.stave.select_in_rect(self.index, a[0], a[1], b[0], b[1], bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
        self.press, self.band = None, None
        self.update()

    # palette marks (Toe / Heel) dropped onto a note head
    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("sign:"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        hit, _note = self.stave.hit_near(self.index, *self.to_svg(event.position()), 1.8)
        self.drop_hit = hit
        self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_hit = None
        self.update()

    def dropEvent(self, event):
        hit, note = self.stave.hit_near(self.index, *self.to_svg(event.position()), 1.8)
        self.drop_hit = None
        if note is not None and event.mimeData().text().startswith("sign:"):
            targets = self.stave.selected_notes() if id(note) in self.stave.sel_notes else [note]
            for n in targets:
                self.stave.apply_sign(n, event.mimeData().text()[5:])
        self.update()
        event.acceptProposedAction()

    def keyPressEvent(self, event):
        if not self.stave.key_edit(event):
            super().keyPressEvent(event)


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
                                       stave.info.get("voice_names"))
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
                                  stave.info.get("voice_names"))
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


class NoteItem(QGraphicsRectItem):
    """One note of the piano roll; `note` is the core.Note it edits."""

    def __init__(self, note, x, y, w, h, colour):
        super().__init__(x, y, w, h)
        self.note, self.colour = note, colour
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(colour))
        self.setZValue(1)

    show_labels = True
    NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        r = self.rect()
        if self.show_labels and r.width() >= 20 and ROW >= 9:
            f = painter.font()
            f.setPixelSize(max(7, ROW - 4))
            painter.setFont(f)
            painter.setPen(QColor(10, 14, 18))
            painter.setClipRect(r)
            painter.drawText(QRectF(r.left() + 2, r.top(), r.width() - 3, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             f"{self.NAMES[self.note.pitch % 12]}{self.note.pitch // 12 - 1}")

    def style(self, selected, sounding):
        self.setOpacity(0.35 if getattr(self.note, "mute", False) else 1.0)
        self.setBrush(QBrush(QColor(230, 40, 40) if sounding else self.colour))
        self.setPen(QPen(QColor(255, 255, 255), 2) if selected else QPen(Qt.PenStyle.NoPen))
        self.setZValue(3 if selected else 1)


class PianoKeys(QWidget):
    """Keyboard down the left of the roll, lined up with its rows; click a key to hear it on the organ."""

    def __init__(self, stave):
        super().__init__()
        self.stave = stave
        self.setFixedWidth(46)
        self.down = None

    def pitch_at(self, y):
        roll = self.stave.roll
        return roll.top - int(roll.mapToScene(0, y).y() // ROW)

    def paintEvent(self, event):
        p = QPainter(self)
        roll = self.stave.roll
        pal = self.palette()
        p.fillRect(self.rect(), pal.window())
        if not self.stave.notes:
            return
        top_pitch = self.pitch_at(0) + 1
        black = (1, 3, 6, 8, 10)
        names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        for pitch in range(top_pitch, top_pitch - self.height() // ROW - 3, -1):
            y = roll.mapFromScene(0, (roll.top - pitch) * ROW).y()
            rect = QRectF(0, y, self.width(), ROW)
            dark = pitch % 12 in black
            colour = QColor(40, 44, 50) if dark else QColor(232, 235, 238)
            if pitch == self.down:
                colour = QColor(pal.highlight().color())
            p.fillRect(rect.adjusted(0, 0, -(0 if not dark else 14), 0), colour)
            p.setPen(QPen(QColor(120, 128, 136, 120), 1))
            p.drawLine(0, int(y), self.width(), int(y))
            if pitch % 12 == 0 and ROW >= 6:
                p.setPen(QColor(60, 66, 72))
                p.drawText(QRectF(2, y - 2, self.width() - 4, ROW + 4), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"C{pitch // 12 - 1}")
        p.end()

    def mousePressEvent(self, event):
        self.down = self.pitch_at(int(event.position().y()))
        self.stave.audition(self.down)
        self.update()

    def mouseMoveEvent(self, event):
        if self.down is not None:
            pitch = self.pitch_at(int(event.position().y()))
            if pitch != self.down:
                self.down = pitch
                self.stave.audition(pitch)
                self.update()

    def mouseReleaseEvent(self, event):
        self.down = None
        self.update()


class VelocityLane(QWidget):
    """One bar per note under the roll, lined up with it: drag a bar up / down to set how hard the note is played
    (a group of selected notes moves together)."""

    def __init__(self, stave):
        super().__init__()
        self.stave = stave
        self.setFixedHeight(76)
        self.edit = None

    def _x(self, note):
        return self.stave.roll.mapFromScene(note.start * self.stave.roll.pps, 0).x()

    def paintEvent(self, event):
        p = QPainter(self)
        st = self.stave
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        p.setPen(QPen(QColor(128, 128, 128, 60), 1))
        for frac in (0.25, 0.5, 0.75):
            p.drawLine(0, int(self.height() * frac), self.width(), int(self.height() * frac))
        h, left = self.height() - 4, st.roll.pps
        vw = self.width()
        accent = QColor(pal.highlight().color())
        for n in st.notes:
            x = self._x(n)
            if x < -4 or x > vw + 4:
                continue
            v = n.vel / 127.0
            sel = id(n) in st.sel_notes
            col = accent if sel else QColor(int(60 + 190 * v), int(190 - 60 * v), 200 - int(120 * v))
            p.fillRect(QRectF(x, self.height() - 2 - v * h, 4 if not sel else 5, v * h), col)
        p.end()

    def _pick(self, x):
        near = [(abs(self._x(n) - x), n) for n in self.stave.notes]
        near = [t for t in near if t[0] <= 6]
        if not near:
            return None
        sel = [t for t in near if id(t[1]) in self.stave.sel_notes]
        return min(sel or near, key=lambda t: (t[0], -t[1].vel))[1]

    def _set(self, y):
        v = max(1, min(127, int(round((1 - (y - 2) / max(1, self.height() - 4)) * 127))))
        note, base, group = self.edit
        delta = v - base
        for n in group:
            n.vel = max(1, min(127, n.vel0 + delta)) if hasattr(n, "vel0") else n.vel
        self.update()

    def mousePressEvent(self, event):
        n = self._pick(int(event.position().x()))
        if n is None:
            return
        st = self.stave
        if id(n) not in st.sel_notes:
            st.sel_notes = {id(n)}
        group = st.selected_notes()
        st.push_undo()
        for g in group:
            g.vel0 = g.vel
        self.edit = (n, n.vel, group)
        self._set(event.position().y())

    def mouseMoveEvent(self, event):
        if self.edit:
            self._set(event.position().y())

    def mouseReleaseEvent(self, event):
        if self.edit:
            note, _b, group = self.edit
            self.edit = None
            st = self.stave
            st.audition(note.pitch, note.vel)
            st.refresh_roll(keep_view=True)
            st.changed(delay=300)


class RollView(QGraphicsView):
    hoverInfo = Signal(str)
    barMoved = Signal(int, float)
    barSelected = Signal(int)
    insertRequested = Signal(float)
    deleteRequested = Signal(int)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(QColor(20, 26, 31)))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)       # the roll window draws its own, shared with ruler / keys / lane
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.pps = 60.0                       # pixels per second
        self.bar_items = []
        self.selected = None
        self.top = 0
        self.note_items = []
        self.playhead = None
        self.play_time = None
        self.drag = None
        self.stretch = None
        self.sel_notes = set()
        self.highlight_scale, self.invert_grid, self.grid_mode, self.show_ghosts = False, False, "grid", True
        self.cursor_sec = 0.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def populate(self, notes, barmap, ghosts, selected, sel_notes=None):
        scene = self.scene()
        scene.clear()
        self.bar_items = []
        self.note_items = []
        self.playhead = None
        self.sel_notes = sel_notes if sel_notes is not None else set()
        if not notes:
            return
        lo, hi = min(36, min(n.pitch for n in notes) - 2), max(96, max(n.pitch for n in notes) + 2)
        self.top = hi
        height = max(120, (hi - lo + 1) * ROW)
        end = max(n.end for n in notes) + 2.0
        end = max(end, barmap.anchors[-1] + 1.0)
        scene.setSceneRect(QRectF(0, 0, end * self.pps, height))
        scale = self.window_ref._scale_pcs() if self.highlight_scale and self.window_ref.notes else set()
        accent = QColor(self.palette().highlight().color())
        for pc in range(lo, hi + 1):                                # rows: keys tinted (or the black ones, inverted), scale notes in the accent
            white = pc % 12 in (0, 2, 4, 5, 7, 9, 11)
            tinted = (not white) if self.invert_grid else white
            if pc % 12 in scale:
                shade = QColor(accent)
                shade.setAlpha(34 if pc % 12 else 56)
            elif tinted:
                shade = QColor(255, 255, 255, 10 if pc % 12 else 22)
            else:
                continue
            row = scene.addRect(0, (hi - pc) * ROW, end * self.pps, ROW, QPen(Qt.PenStyle.NoPen), QBrush(shade))
            row.setZValue(0)
        if self.grid_mode != "none":                                 # vertical grid from the snap step / beats / bars
            from PySide6.QtGui import QPainterPath
            cum = [float(c) for c in barmap.cumulative()]
            unit = {"beats": 1.0, "bars": None, "grid": self.window_ref.snap_unit()}.get(self.grid_mode, 1.0)
            fine, beat_p, bar_p, big_p = QPainterPath(), QPainterPath(), QPainterPath(), QPainterPath()
            count = 0
            for bi in range(barmap.bar_count):
                a0, a1, blen = barmap.anchors[bi], barmap.anchors[bi + 1], barmap.beats[bi]
                (big_p if bi % 4 == 0 else bar_p).moveTo(a0 * self.pps, 0)
                (big_p if bi % 4 == 0 else bar_p).lineTo(a0 * self.pps, height)
                step = unit if unit else blen
                if self.grid_mode == "bars" or not step or step * (a1 - a0) / blen * self.pps < 7:
                    step = 1.0 if self.grid_mode != "bars" and (a1 - a0) / blen * self.pps >= 7 else blen
                k = step
                while k < blen - 1e-6 and count < 6000:
                    x = (a0 + (a1 - a0) * k / blen) * self.pps
                    target = beat_p if abs(k - round(k)) < 1e-6 else fine
                    target.moveTo(x, 0)
                    target.lineTo(x, height)
                    k += step
                    count += 1
            for path, alpha, width in ((fine, 22, 1), (beat_p, 46, 1), (bar_p, 90, 1), (big_p, 150, 1.5)):
                item = scene.addPath(path, QPen(QColor(150, 165, 180, alpha), width))
                item.setZValue(0.2)
        for n in notes:
            v = n.vel / 127.0
            colour = QColor(int(60 + 190 * v), int(190 - 60 * v), 200 - int(120 * v))
            r = NoteItem(n, n.start * self.pps, (hi - n.pitch) * ROW + 1, max(2.0, (n.end - n.start) * self.pps),
                         ROW - 2, colour)
            scene.addItem(r)
            self.note_items.append(r)
        pen = QPen(QColor(242, 163, 58), 1)
        for g_start, g_end, pitch in ghosts:
            r = scene.addRect(g_start * self.pps, (hi - pitch) * ROW, max(2.0, (g_end - g_start) * self.pps), ROW, pen,
                              QBrush(Qt.BrushStyle.NoBrush))
            r.setZValue(0.5)                       # under the notes so clicks reach the notes
        for i, t in enumerate(barmap.anchors):
            item = BarLine(i, t * self.pps, height, self)
            scene.addItem(item)
            self.bar_items.append(item)
        self.playhead = scene.addLine(0, 0, 0, height, QPen(QColor(255, 60, 60), 2))
        self.playhead.setZValue(30)
        self.playhead.setVisible(False)
        self.apply_selection()
        self.set_playhead(self.play_time)
        self.select(selected)

    def apply_selection(self, sel=None):
        if sel is not None:
            self.sel_notes = sel
        t = self.play_time
        for it in self.note_items:
            n = it.note
            it.style(id(n) in self.sel_notes, t is not None and n.start <= t < n.end)

    def set_playhead(self, t):
        """Red line at time t (seconds) and the sounding notes in red; None hides it."""
        self.play_time = t
        if self.playhead is None:
            return
        if t is None:
            self.playhead.setVisible(False)
        else:
            x = t * self.pps
            self.playhead.setPos(x, 0)
            self.playhead.setVisible(True)
            view = self.viewport().width()
            bar = self.horizontalScrollBar()
            if getattr(self, "follow", True) and not (bar.value() + 20 < x < bar.value() + view - 40) and self.drag is None:
                bar.setValue(int(x - view * 0.25))
        self.apply_selection()

    # ---- note editing with the mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.mapToScene(event.pos()).y() < 0 and self.bar_items:
            x = self.mapToScene(event.pos()).x()                   # the bar-number ruler: a click selects that bar
            index = max(0, sum(1 for b in self.bar_items if b.x() <= x) - 1)
            self.barSelected.emit(index)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            self.setFocus()
            if isinstance(item, NoteItem) and self.window_ref.tool_click(item.note, self.mapToScene(event.pos()).x() / self.pps):
                return
            if not isinstance(item, (NoteItem, BarLine)):
                self.cursor_sec = max(0.0, self.mapToScene(event.pos()).x() / self.pps)
            if (not isinstance(item, (NoteItem, BarLine)) and self.window_ref.tool == "add"):
                pos = self.mapToScene(event.pos())
                self.window_ref.add_note_at(pos.x() / self.pps, self.top - int(pos.y() // ROW))
                return
            if isinstance(item, NoteItem):
                side = self._edge(item, self.mapToScene(event.pos()))
                if side and id(item.note) not in self.sel_notes:
                    self.window_ref.select_note(item.note, bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                elif not side:
                    self.window_ref.select_note(item.note, bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                if side:                                            # grab the left / right end: change the length
                    self.stretch = {"side": side, "origin": self.mapToScene(event.pos()), "note": item.note, "moved": False}
                    return
                self.drag = (self.mapToScene(event.pos()), item.note, False)
                return
            if not isinstance(item, BarLine):
                self.window_ref.select_note(None, False)
        super().mousePressEvent(event)

    def _edge(self, item, pos):
        """'L' / 'R' when the pointer is on the left / right end of a note bar (the grab zone shrinks on very short notes)."""
        r = item.rect()
        zone = max(2.0, min(7.0, r.width() / 3.0))
        if abs(pos.x() - r.left()) <= zone:
            return "L"
        if abs(pos.x() - r.right()) <= zone:
            return "R"
        return None

    def mouseMoveEvent(self, event):
        st = getattr(self, "stretch", None)
        if st is not None:
            dx = self.mapToScene(event.pos()).x() - st["origin"].x()
            if abs(dx) > 1 or st["moved"]:
                st["moved"] = True
                for it in self.note_items:
                    if id(it.note) in self.sel_notes:
                        r = QRectF(it.note.start * self.pps, it.rect().y(), max(2.0, (it.note.end - it.note.start) * self.pps), it.rect().height())
                        if st["side"] == "R":
                            r.setRight(max(r.left() + 2.0, r.right() + dx))
                        else:
                            r.setLeft(min(r.right() - 2.0, r.left() + dx))
                        it.setRect(r)
            return
        if self.drag is None:
            item = self.itemAt(event.pos())
            self.hoverInfo.emit(self.window_ref.describe_at(self.mapToScene(event.pos()), item.note if isinstance(item, NoteItem) else None))
            self.viewport().setCursor(Qt.CursorShape.SizeHorCursor if isinstance(item, NoteItem)
                                      and self._edge(item, self.mapToScene(event.pos())) else Qt.CursorShape.ArrowCursor)
        if self.drag is not None:
            origin, note, _moved = self.drag
            pos = self.mapToScene(event.pos())
            dx, dy = pos.x() - origin.x(), pos.y() - origin.y()
            if abs(dx) > 2 or abs(dy) > 2 or _moved:
                self.drag = (origin, note, True)
                dp = -round(dy / ROW)
                for it in self.note_items:
                    if id(it.note) in self.sel_notes:
                        it.setPos(dx, -dp * ROW)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        st = getattr(self, "stretch", None)
        if st is not None:
            self.stretch = None
            if st["moved"]:
                dx = self.mapToScene(event.pos()).x() - st["origin"].x()
                free = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                self.window_ref.stretch_selected(st["side"], dx / self.pps, st["note"], free)
            return
        if self.drag is not None:
            origin, note, moved = self.drag
            self.drag = None
            if moved:
                pos = self.mapToScene(event.pos())
                self.window_ref._free = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                self.window_ref.move_selected((pos.x() - origin.x()) / self.pps, -round((pos.y() - origin.y()) / ROW), note)
                self.window_ref._free = False
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and not isinstance(item, (NoteItem, BarLine)):
            pos = self.mapToScene(event.pos())
            self.window_ref.add_note_at(pos.x() / self.pps, self.top - int(pos.y() // ROW))
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self.window_ref.key_edit(event):
            return
        super().keyPressEvent(event)

    def select(self, index):
        self.selected = index
        for i, item in enumerate(self.bar_items):
            item.set_selected(i == index)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:          # Alt + wheel: taller / shorter keys
            global ROW
            ROW = max(3, min(24, ROW + (1 if event.angleDelta().y() > 0 else -1)))
            self.window_ref.refresh_roll(keep_view=True)
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.pps = max(8.0, min(600.0, self.pps * factor))
            self.window_ref.refresh_roll(keep_view=True)
        elif event.modifiers() & Qt.KeyboardModifier.ShiftModifier:        # Shift + wheel: sideways
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - event.angleDelta().y())
        else:                                                                # wheel: up / down the keyboard
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() - event.angleDelta().y() // 2)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        item = self.itemAt(event.pos())
        if isinstance(item, NoteItem):
            self.window_ref.note_menu(item.note, event.globalPos())
            return
        near = next((i for i, b in enumerate(self.bar_items) if abs(b.x() - scene_pos.x()) < 8), None)
        menu = QMenu(self)
        if near is not None:
            menu.addAction(f"Delete bar line {near + 1}", lambda: self.deleteRequested.emit(near))
        menu.addAction("Add 4 bars at the end", lambda: self.window_ref.add_bars(4))
        menu.addAction("Insert a bar line here", lambda: self.insertRequested.emit(max(0.0, scene_pos.x() / self.pps)))
        menu.addAction("Add a note here", lambda: self.window_ref.add_note_at(max(0.0, scene_pos.x() / self.pps),
                                                                              self.top - int(scene_pos.y() // ROW)))
        menu.exec(event.globalPos())


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


class VoiceRegDialog(QDialog):
    """A voice's registration changes, bar by bar: setters or individual stops."""

    def __init__(self, stave, index):
        super().__init__(stave)
        self.stave, self.index = stave, index
        self.entries = stave.voice_reg[index]
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


KINDS = ['solo', 'grand', 'organ', 'choir', 'channels', 'voices']


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


class Stave(QMainWindow):
    result_ready = Signal(int, object)
    hwStep = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI to Stave")
        self.notes, self.info, self.path = [], {}, None
        self.barmap = core.BarMap([0.0, 2.0])
        self.bar_grid = {}
        self.selected_bar = None
        self.qnotes = []
        self.pages = []
        self.xml = ""
        self.generation = 0
        self.lock = threading.Lock()
        self.settings = QSettings("KeyLabGrandOrgue", "MidiStave")
        self.result_ready.connect(self._on_result)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.rebuild)
        self._build_ui()
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1500, 950)
        state = self.settings.value("splitters")
        if state:
            self.splitter.restoreState(state)
            self.body.restoreState(self.settings.value("body", self.body.saveState()))

    # ---- ui
    def _build_ui(self):
        self.body = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.body)
        side = QScrollArea()
        side.setWidgetResizable(True)
        side.setMinimumWidth(455)
        side.setMaximumWidth(600)
        side.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QWidget()
        column = QVBoxLayout(panel)
        side.setWidget(panel)
        self.body.addWidget(side)

        files = QGroupBox("Recording")
        f = QVBoxLayout(files)
        row = QHBoxLayout()
        open_btn = QPushButton("Open MIDI...")
        open_btn.clicked.connect(self.open_dialog)
        takes_btn = QPushButton("Takes folder...")
        takes_btn.clicked.connect(self.choose_takes)
        row.addWidget(open_btn)
        row.addWidget(takes_btn)
        f.addLayout(row)
        self.takes_list = QListWidget()
        self.takes_list.setMaximumHeight(130)
        self.takes_list.itemDoubleClicked.connect(lambda item: self.load(item.data(Qt.ItemDataRole.UserRole)))
        f.addWidget(self.takes_list)
        column.addWidget(files)

        bars = QGroupBox("Bars (drag the orange/teal lines on the roll)")
        b = QFormLayout(bars)
        self.meter = QComboBox()
        self.meter.addItems(list(TIME_SIGS))
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(0, 240)
        self.bpm.setSpecialValueText("auto")
        self.follow = QSlider(Qt.Orientation.Horizontal)
        self.follow.setRange(0, 100)
        self.follow.setValue(60)
        detect = QPushButton("Detect bars")
        detect.clicked.connect(self.detect_bars)
        shift_row = QHBoxLayout()
        for text, step in (("<< bar 1 earlier", -1), ("later >>", 1)):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, s=step: self.shift_downbeat(s))
            shift_row.addWidget(btn)
        b.addRow("Time signature", self.meter)
        b.addRow("Tempo (BPM)", self.bpm)
        b.addRow("Follow my timing", self.follow)
        b.addRow(detect)
        b.addRow("Start on another beat", shift_row)
        self.sel_label = QLabel("No bar selected - click a bar line")
        self.bar_beats = QDoubleSpinBox()
        self.bar_beats.setRange(0.5, 16)
        self.bar_beats.setSingleStep(0.5)
        self.bar_beats.setValue(4)
        self.bar_beats.valueChanged.connect(self.bar_beats_changed)
        self.bar_grid_box = QComboBox()
        self.bar_grid_box.addItems(["as global", "1/8", "1/16", "1/32", "1/64", "triplets"])
        self.bar_grid_box.currentIndexChanged.connect(self.bar_grid_changed)
        nudge = QHBoxLayout()
        for text, delta in (("-20 ms", -0.02), ("-5 ms", -0.005), ("+5 ms", 0.005), ("+20 ms", 0.02)):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, d=delta: self.nudge_selected(d))
            nudge.addWidget(btn)
        b.addRow(self.sel_label)
        b.addRow("Selected bar: beats", self.bar_beats)
        b.addRow("Selected bar: grid", self.bar_grid_box)
        b.addRow("Nudge its start", nudge)
        column.addWidget(bars)

        quant = QGroupBox("Quantise")
        q = QFormLayout(quant)
        self.grid = QComboBox()
        self.grid.addItems(list(core.GRID_CHOICES))
        self.grid.setCurrentText("1/16")
        self.triplets = QCheckBox("Find triplets automatically")
        self.triplets.setChecked(True)
        self.legato = QDoubleSpinBox()
        self.legato.setRange(0, 2)
        self.legato.setSingleStep(0.25)
        self.legato.setValue(0.5)
        self.chord = QSpinBox()
        self.chord.setRange(0, 150)
        self.chord.setValue(45)
        self.chord.setSuffix(" ms")
        q.addRow("Smallest note", self.grid)
        q.addRow(self.triplets)
        q.addRow("Close gaps up to (beats)", self.legato)
        q.addRow("Chord window", self.chord)
        column.addWidget(quant)

        lay = QGroupBox("Staves")
        l = QFormLayout(lay)
        self.layout_kind = QComboBox()
        self.layout_kind.addItems(["Solo (one stave)", "Grand staff (piano)", "Organ (2 manuals + pedal)",
                                   "Choir SATB", "One stave per channel",
                                   "Orchestral: one stave per MIDI track / channel"])
        self.split = QSpinBox()
        self.split.setRange(24, 100)
        self.split.setValue(60)
        self.split2 = QSpinBox()
        self.split2.setRange(24, 100)
        self.split2.setValue(53)
        self.split3 = QSpinBox()
        self.split3.setRange(24, 100)
        self.split3.setValue(67)
        self.pedal = QSpinBox()
        self.pedal.setRange(24, 80)
        self.pedal.setValue(48)
        self.stave_names = QLineEdit()
        l.addRow("Layout", self.layout_kind)
        l.addRow("Stave names (comma separated)", self.stave_names)
        self.manuals = sessionmeta.manual_channels()
        self.manual_channel = {n: ch for n, _p, ch in self.manuals}
        self.manual_box = QGroupBox("Each stave plays on (GrandOrgue manuals)")
        outer = QVBoxLayout(self.manual_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(110)
        scroll.setMaximumHeight(260)
        holder = QWidget()
        self.manual_rows = QVBoxLayout(holder)
        scroll.setWidget(holder)
        outer.addWidget(scroll)
        outer.addWidget(QLabel("Tick the manuals a voice plays (many voices can share one). "
                               "'Reg' gives the voice its own stop registration from an existing setter."))
        self.manual_checks = []                      # per stave: {manual name: QCheckBox}
        self.voice_reg = []                          # per stave: [{"bar", "kind": "setter"|"stops", ...}] registration changes
        self.seek_hook = None
        self.lyrics = {}
        self.play_hook = self.stop_hook = self.pos_hook = None   # set by the bridge: play a file / stop / playback position
        self.sel_notes, self.undo_stack, self.redo_stack = set(), [], []
        self.hl_bar, self.page_widgets = None, []
        self.pool, self.job_running, self.job_dirty = None, False, False
        self.hits, self.page_dims, self.hit_params, self.spaces = [], [], {}, []
        self.signs = {}                              # pedal marks: (track, channel, pitch, start s) -> 'toe' | 'heel'
        self.chord_hook = None                       # set by the bridge: sound notes on the organ at once
        self.step_groups, self.step_index, self.step_ids, self.step_until = [], 0, frozenset(), 0.0
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.poll_playhead)
        self.play_timer.start(50)
        l.addRow(self.manual_box)
        l.addRow("Split note (60 = middle C)", self.split)
        l.addRow("Choir: tenor / soprano split", self.split2)
        l.addRow("Choir: alto / soprano split", self.split3)
        l.addRow("Organ: pedal below", self.pedal)
        self.hold = QDoubleSpinBox()
        self.hold.setRange(0, 8)
        self.hold.setSingleStep(0.5)
        self.hold.setToolTip("A line that dips just below / above a split point stays on its stave when the next note follows "
                             "within this many beats (0 = strict split). Use right-click > Show on stave for single notes.")
        self.hold.valueChanged.connect(self.changed)
        l.addRow("Keep a line on its stave (beats)", self.hold)
        column.addWidget(lay)

        tg = QGroupBox("MIDI tracks in this file")
        tl = QVBoxLayout(tg)
        self.track_list = QListWidget()
        self.track_list.setMaximumHeight(170)
        self.track_list.setToolTip("Every track with the name stored in the file, its MIDI channel, instrument (General MIDI "
                                   "program), note count and range. (empty) = the track carries no notes.")
        tl.addWidget(QLabel("Tick the tracks that are shown on the stave (one instrument or choir voice per sheet)."))
        tl.addWidget(self.track_list)
        row = QHBoxLayout()
        for text, state in (("Show all", True), ("Show none", False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, st=state: self.set_all_tracks(st))
            row.addWidget(b)
        only = QPushButton("Only highlighted")
        only.clicked.connect(self.only_current_track)
        row.addWidget(only)
        tl.addLayout(row)
        self.track_list.itemChanged.connect(self._track_toggled)
        column.addWidget(tg)

        self.sel_stave = None
        self.stave_bands = []
        self.hidden_tracks = set()           # (track, channel) pairs left off the stave
        self.setters = []                    # [{"bar": 0-based, "filename", "id", "name"}]
        self.combos = sessionmeta.load_combos()
        sg = QGroupBox("Organ setters (stop combinations by bar)")
        sl = QVBoxLayout(sg)
        self.setter_list = QListWidget()
        self.setter_list.setMaximumHeight(130)
        sl.addWidget(self.setter_list)
        row = QHBoxLayout()
        for text, handler in (("Add at selected bar...", self.add_setter), ("Remove", self.remove_setter)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            row.addWidget(btn)
        sl.addLayout(row)
        self.setter_hint = QLabel("" if self.combos else "No setter list found (config.yaml / Combinations folder).")
        sl.addWidget(self.setter_hint)
        column.addWidget(sg)

        nota = QGroupBox("Notation")
        n = QFormLayout(nota)
        self.key = QComboBox()
        self.key.addItems(KEYS)
        self.dynamics = QCheckBox("Dynamics from how hard I played (pp, mf, ...)")
        self.dynamics.setChecked(True)
        self.dyn_bias = QSpinBox()
        self.dyn_bias.setRange(-3, 3)
        self.title = QLineEdit()
        self.composer = QLineEdit()
        self.arranger = QLineEdit()
        self.arranger.textChanged.connect(lambda *_: self.changed(delay=700))
        self.page = QComboBox()
        self.page.addItems(list(PAGE_SIZES))
        self.scale = QSpinBox()
        self.scale.setRange(20, 80)
        self.scale.setValue(40)
        self.scale.setSuffix(" %")
        self.transpose = QSpinBox()
        self.transpose.setRange(-12, 12)
        self.transpose.setSuffix(" semitones")
        self.to_key = QComboBox()
        self.to_key.addItem("-")
        self.to_key.addItems(KEYS[1:])
        self.src_key_label = QLabel("Detected key: -")
        self.slurs = QCheckBox("Slur joined-up (legato) phrases")
        self.slurs.setChecked(True)
        self.staccato = QCheckBox("Staccato dots on short, detached notes")
        self.final_bar = QCheckBox("Final double bar at the end")
        self.final_bar.setChecked(True)
        n.addRow("Key signature", self.key)
        n.addRow(self.src_key_label)
        n.addRow("Move piece to key", self.to_key)
        n.addRow("Transpose by", self.transpose)
        n.addRow(self.slurs)
        n.addRow(self.staccato)
        n.addRow(self.final_bar)
        n.addRow(self.dynamics)
        n.addRow("Dynamics louder/softer", self.dyn_bias)
        n.addRow("Title", self.title)
        n.addRow("Composer", self.composer)
        n.addRow("Arranger", self.arranger)
        self.sp_staff, self.sp_group, self.sp_system = QSpinBox(), QSpinBox(), QSpinBox()
        self.sp_staff.setRange(4, 30); self.sp_staff.setValue(12)
        self.sp_group.setRange(4, 30); self.sp_group.setValue(12)
        self.sp_system.setRange(2, 20); self.sp_system.setValue(4)
        self.sp_note = QDoubleSpinBox()
        self.sp_note.setRange(0.1, 1.0); self.sp_note.setSingleStep(0.05); self.sp_note.setValue(0.25)
        for w, label, tip in ((self.sp_staff, "Gap between staves", "Staff spaces between unrelated staves (manuals to pedal: raise to ~14 for room for ledger lines and footings)"),
                              (self.sp_group, "Gap inside a brace / bracket", "Staff spaces between the two manuals (or the choir staves)"),
                              (self.sp_system, "Gap between systems", "Staff spaces between one system and the next"),
                              (self.sp_note, "Note spacing", "Horizontal spacing: bigger = airier bars")):
            w.setToolTip(tip)
            w.valueChanged.connect(lambda *_: self.changed(delay=500))
            n.addRow(label, w)
        n.addRow("Page", self.page)
        n.addRow("Notation size", self.scale)
        column.addWidget(nota)

        adv = QGroupBox("Advanced organ notation")
        al = QVBoxLayout(adv)
        self.adv_multirest = QCheckBox("Multi-measure rests (a bar-count rest where every stave is silent)")
        self.adv_multirest_n = QSpinBox()
        self.adv_multirest_n.setRange(2, 32)
        self.adv_multirest_n.setValue(4)
        self.adv_multirest_n.setPrefix("from ")
        self.adv_multirest_n.setSuffix(" bars")
        self.adv_clef = QCheckBox("Clef switch on the manual staves (bass clef when the hand plays low)")
        self.adv_rehearsal = QCheckBox('Label the organ "Organ (for rehearsal only)"')
        self.adv_registration = QCheckBox("Print registrations as Gt.: Principal 8', 4', 2' | Sw.: ... (feet in descending order)")
        self.adv_voices = QCheckBox("Separate held notes from moving notes into two voices (stems up / down)")
        self.adv_voices.setChecked(True)
        self.adv_nvoices = QSpinBox()
        self.adv_nvoices.setRange(1, 4)
        self.adv_nvoices.setValue(2)
        self.adv_nvoices.setPrefix("up to ")
        self.adv_nvoices.setSuffix(" voices per stave")
        self.adv_nvoices.valueChanged.connect(self.changed)
        self.adv_tidy = QCheckBox("Tidy rests: beat-aligned, one whole-bar rest, hidden in the second voice")
        self.adv_tidy.setChecked(True)
        for w in (self.adv_voices, self.adv_tidy):
            w.toggled.connect(self.changed)
        al.addWidget(self.adv_nvoices)
        for w in (self.adv_voices, self.adv_tidy, self.adv_multirest, self.adv_clef, self.adv_rehearsal, self.adv_registration):
            al.addWidget(w)
            w.toggled.connect(self.changed)
        self.divisions = {}                                  # bar index -> label printed above the first stave
        dv = QHBoxLayout()
        self.div_box = QComboBox()
        self.div_box.setEditable(True)
        self.div_box.addItems(["Great", "Swell", "Choir", "Positiv", "Pedal", "Man. I", "Man. II", "r.h.", "l.h.",
                               "II/I", "III/I", "I/P", "II/P", "Gt. to Ped."])
        add = QPushButton("Label at selected bar")
        add.clicked.connect(self.add_division)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear_division)
        dv.addWidget(self.div_box, 1)
        dv.addWidget(add)
        dv.addWidget(clear)
        al.addLayout(dv)
        self.div_list = QLabel("Division / coupler labels: none")
        al.addWidget(self.div_list)
        row_ = QHBoxLayout()
        row_.addSpacing(24)
        row_.addWidget(self.adv_multirest_n)
        row_.addStretch(1)
        al.addLayout(row_)
        self.adv_multirest_n.valueChanged.connect(self.changed)
        column.addWidget(adv)

        ed = QGroupBox("Note editor (piano roll)")
        el = QFormLayout(ed)
        self.snap = QCheckBox("Snap to the grid above")
        self.snap.setChecked(True)
        self.new_len = QComboBox()
        self.new_len.addItems([t for t, _b in self.LENGTHS])
        self.new_len.setCurrentText("Quarter note (crotchet)")
        el.addRow(self.snap)
        el.addRow("New note length", self.new_len)
        self.play_quantised = QCheckBox("Play what the stave shows (quantised, transposed)")
        self.play_quantised.setChecked(True)
        el.addRow(self.play_quantised)
        el.addRow(QLabel("Click a note to select (Shift = several), drag to move in time / pitch.\n"
                         "Up / Down = pitch (Shift = octave), Left / Right = nudge (Ctrl = 10 ms),\n"
                         "Del = delete, Ctrl+D = duplicate, double-click empty space = add a note,\n"
                         "right-click a note = length / velocity / delete, Ctrl+Z / Ctrl+Y = undo / redo."))
        self.step_mode = QCheckBox("Step mode: KeyLab >> / << (or Enter) plays the next / previous chord of the selection")
        el.addRow(self.step_mode)
        sbtns = QHBoxLayout()
        for text, handler in (("< Step", lambda: self.step_play(-1)), ("Step >", lambda: self.step_play(1)),
                              ("Play selection", lambda: self.play_on_organ(True))):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, h=handler: h())
            sbtns.addWidget(btn)
        el.addRow(sbtns)
        self.hwStep.connect(self.step_play)
        QShortcut(QKeySequence("Return"), self, lambda: self.step_play(1))
        ebtns = QHBoxLayout()
        for text, handler in (("Undo", self.undo), ("Redo", self.redo), ("Save edited MIDI...", self.save_edited_midi)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            ebtns.addWidget(btn)
        el.addRow(ebtns)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_blank)
        QShortcut(QKeySequence("F2"), self, self.show_roll)
        column.addWidget(ed)

        out = QGroupBox("Export")
        o = QVBoxLayout(out)
        hear = QHBoxLayout()
        for text, handler in (("Play on organ", self.play_on_organ), ("Stop", self.stop_on_organ)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            hear.addWidget(btn)
        o.addLayout(hear)
        for text, handler in (("Words (lyrics)...", self.open_lyrics), ("Tonic sol-fa...", self.open_solfa), ("Export PDF...", self.export_pdf), ("Export MusicXML...", self.export_xml),
                              ("Export straightened MIDI...", self.export_midi)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            o.addWidget(btn)
        column.addWidget(out)
        column.addStretch(1)

        for widget in (self.grid, self.layout_kind, self.key, self.page):
            widget.currentIndexChanged.connect(self.changed)
        for widget in (self.triplets, self.dynamics, self.slurs, self.staccato, self.final_bar):
            widget.toggled.connect(self.changed)
        self.transpose.valueChanged.connect(self.transpose_edited)
        self.to_key.currentIndexChanged.connect(self.apply_target_key)
        self.layout_kind.currentIndexChanged.connect(self.update_name_hint)
        self.stave_names.textChanged.connect(lambda *_: self.changed(delay=700))

        self.src_key = None
        self.need_probe = True
        for widget in (self.legato, self.chord, self.split, self.split2, self.split3, self.pedal, self.dyn_bias, self.scale):
            widget.valueChanged.connect(self.changed)
        for widget in (self.title, self.composer):
            widget.textChanged.connect(lambda *_: self.changed(delay=700))
        self.meter.currentIndexChanged.connect(self.detect_bars)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.body.addWidget(self.splitter)
        self.roll = RollView()
        self.roll.window_ref = self
        self.roll.barMoved.connect(self.bar_moved)
        self.roll.barSelected.connect(self.select_bar)
        self.roll.insertRequested.connect(self.insert_bar_line)
        self.roll.deleteRequested.connect(self.delete_bar_line)
        self.roll_window = None                          # the piano roll lives in its own window (roll_window.py), opened on demand
        self.preview = QScrollArea()
        self.preview.setWidgetResizable(True)
        self.preview_host = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_host)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.preview.setWidget(self.preview_host)
        self.preview.setStyleSheet("background: #888;")
        self.splitter.addWidget(self.preview)
        self.splitter.setSizes([260, 700])
        self.body.setSizes([470, 1030])
        self._build_transport_bar()
        chrome.build_chrome(self)
        chrome.restore_layout(self)
        self.statusBar().showMessage("Open a recording to begin.")
        self.refresh_takes()

    # ---- transpose / names
    def transpose_edited(self, *_):
        self.to_key.blockSignals(True)
        self.to_key.setCurrentIndex(0)
        self.to_key.blockSignals(False)
        self.changed()

    def apply_target_key(self, index):
        if index <= 0:
            return
        if self.src_key is None:
            self.statusBar().showMessage("The key is still being detected - try again in a moment.")
            return
        semis = (tonic_pc(KEYS[index]) - self.src_key[0]) % 12
        if semis > 6:
            semis -= 12
        self.transpose.blockSignals(True)
        self.transpose.setValue(semis)
        self.transpose.blockSignals(False)
        self.changed()

    def update_name_hint(self, *_):
        kind = KINDS[self.layout_kind.currentIndex()]
        staves = core.make_staves(kind, self.split.value(), self.split2.value(), self.split3.value(), self.pedal.value(),
                                  self.notes, self.info.get("voice_names"))
        self.stave_names.setPlaceholderText(", ".join(s.name for s in staves))
        self.build_manual_rows(kind, staves)

    # ---- files
    def takes_folder(self):
        return self.settings.value("takes", os.path.join(os.path.dirname(HERE), "midi"))

    def choose_takes(self):
        folder = QFileDialog.getExistingDirectory(self, "Takes folder", self.takes_folder())
        if folder:
            self.settings.setValue("takes", folder)
            self.refresh_takes()

    def refresh_takes(self):
        self.takes_list.clear()
        folder = self.takes_folder()
        if os.path.isdir(folder):
            names = sorted((n for n in os.listdir(folder) if n.lower().endswith((".mid", ".midi"))), reverse=True)
            for name in names:
                item = self.takes_list.addItem(name)
                self.takes_list.item(self.takes_list.count() - 1).setData(Qt.ItemDataRole.UserRole, os.path.join(folder, name))

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open MIDI", self.settings.value("last_dir", self.takes_folder()),
                                              "MIDI and MusicXML (*.mid *.midi *.musicxml *.xml *.mxl);;MIDI (*.mid *.midi);;MusicXML (*.musicxml *.xml *.mxl)")
        if path:
            self.settings.setValue("last_dir", os.path.dirname(path))
            self.load(path)

    def click_page_area(self, page, x, y):
        """Clicking the engraved page away from the notes: the header (title / composer / arranger) opens its fields, the clef /
        key / stave-name area opens the Staves panel. True when it handled the click."""
        if page != 0 or not self.hits or not self.hits[0] or self.job_running:
            return False
        space = self.spaces[0] if self.spaces else 18.0
        top = min(h[1] for h in self.hits[0]) - 5 * space
        left = min(h[0] for h in self.hits[0]) - 2.5 * space
        width = self.page_dims[0][0]
        if y < top:
            field = "composer" if x > width * 0.62 else ("arranger" if x < width * 0.3 else "title")
            self.edit_header(field)
            return True
        if x < left:
            for act in self.panels_bar.actions() if getattr(self, "panels_bar", None) else []:
                if act.text() == "Staves":
                    act.trigger()
                    return True
        return False

    def click_stave(self, page, x, y):
        bands = self.stave_bands[page] if page < len(getattr(self, "stave_bands", [])) else []
        space = self.spaces[page] if page < len(self.spaces) else 18.0
        hit = next((b for b in bands if b["y0"] - 2 * space <= y <= b["y1"] + 2 * space and b["x0"] - 4 * space <= x <= b["x1"] + space), None)
        new = None if hit is None or hit["idx"] == self.sel_stave else hit["idx"]
        if new != self.sel_stave:
            self.sel_stave = new
            for w in self.page_widgets:
                w.update()
            if new is None:
                self.statusBar().showMessage("No stave selected", 2000)
            else:
                p = self.params()
                specs = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], self.notes, self.info.get("voice_names"))
                name = (p["names"][new] if new < len(p["names"]) and p["names"][new] else specs[new].name if new < len(specs) else f"stave {new + 1}")
                self.statusBar().showMessage(f"Stave selected: {name}  (click it again to deselect)", 4000)

    def edit_header(self, focus="title"):
        dlg = QDialog(self)
        dlg.setWindowTitle("Title, composer, arranger")
        form = QFormLayout(dlg)
        fields = {"title": self.title, "composer": self.composer, "arranger": self.arranger}
        edits = {}
        for key, label in (("title", "Title"), ("composer", "Composer"), ("arranger", "Arranger")):
            e = QLineEdit(fields[key].text())
            edits[key] = e
            form.addRow(label, e)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        edits[focus].setFocus()
        edits[focus].selectAll()
        if dlg.exec():
            for key, e in edits.items():
                fields[key].setText(e.text())

    def add_division(self):
        if self.selected_bar is None:
            self.statusBar().showMessage("Click a bar line (or the ruler) first, then add the label.")
            return
        self.divisions[self.selected_bar] = self.div_box.currentText()
        self._show_divisions()

    def clear_division(self):
        if self.selected_bar is not None:
            self.divisions.pop(self.selected_bar, None)
        self._show_divisions()

    def _show_divisions(self):
        self.div_list.setText("Division / coupler labels: " + (", ".join(f"bar {b + 1}: {t}" for b, t in sorted(self.divisions.items())) or "none"))
        self.changed(delay=100)

    def show_roll(self, *_):
        if self.roll_window is None:
            import roll_window
            self.roll_window = roll_window.RollWindow(self)
            self.refresh_roll()
            QTimer.singleShot(50, self.roll_window.center_on_notes)
        self.roll_window.show()
        self.roll_window.raise_()
        self.roll_window.activateWindow()

    def audition(self, pitch, vel=80):
        """Hear one pitch on the organ (piano keys, velocity edits)."""
        ref = self.notes[-1] if self.notes else core.Note(0, 0, pitch, vel)
        probe = core.Note(0, 0, pitch, vel, ref.ch, ref.track)
        if self.chord_hook is None:
            self.statusBar().showMessage("No organ connected - start the bridge (or the Stave Station launcher) to hear notes.")
            return
        self.preview_pitch(pitch + self.hit_params.get("transpose", 0), probe, fallback=True)

    def add_bars(self, count=4):
        """Append empty bars (same length as the last one) after the final bar."""
        if not self.barmap.bar_count:
            return
        last = self.barmap.anchors[-1] - self.barmap.anchors[-2]
        anchors = list(self.barmap.anchors) + [self.barmap.anchors[-1] + last * (i + 1) for i in range(count)]
        beats = list(self.barmap.beats) + [self.barmap.beats[-1]] * count
        self.barmap = core.BarMap(anchors, beats)
        self.refresh_roll(keep_view=True)
        self.changed(delay=200)
        self.statusBar().showMessage(f"{count} bars added - now {self.barmap.bar_count} bars.")

    def ensure_bars(self):
        """Notes written (or stretched) past the last bar line get the bars they need."""
        if not self.notes or not self.barmap.bar_count:
            return
        end = max(n.end for n in self.notes)
        need = 0
        last = self.barmap.anchors[-1] - self.barmap.anchors[-2]
        while end > self.barmap.anchors[-1] + need * last - 1e-6 and need < 200:
            need += 1
        if need:
            anchors = list(self.barmap.anchors) + [self.barmap.anchors[-1] + last * (i + 1) for i in range(need)]
            self.barmap = core.BarMap(anchors, list(self.barmap.beats) + [self.barmap.beats[-1]] * need)

    def new_blank(self):
        """Start from nothing: N empty bars. (One placeholder note is written - click it, press Delete once you have your own notes.)"""
        from PySide6.QtWidgets import QInputDialog
        bars, ok = QInputDialog.getInt(self, "New blank score", "Number of bars:", 16, 1, 400)
        if not ok:
            return
        import tempfile, mido
        bpm = float(self.bpm.value() or 100)
        meter = self.meter.currentText()
        beats = TIME_SIGS.get(meter, 4)
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=int(60_000_000 / bpm), time=0)])
        track.append(mido.Message("note_on", note=60, velocity=80, time=0))
        track.append(mido.Message("note_off", note=60, velocity=0, time=480))
        mid.tracks.append(track)
        path = os.path.join(tempfile.gettempdir(), "untitled.mid")
        mid.save(path)
        self.load(path)
        bar_sec = 60.0 / bpm * beats
        self.barmap = core.BarMap([i * bar_sec for i in range(bars + 1)], [beats] * bars)
        self.bar_grid, self.selected_bar = {}, None
        self.loaded_label.setText("  New blank score  ")
        self.title.setText("Untitled")
        chrome.set_tool(self, "add")
        self.refresh_roll()
        self.changed(delay=50)
        self.statusBar().showMessage("Blank score: choose the Add tool (A) and click the roll or the stave to write notes.")

    def load(self, path):
        imported = None
        try:
            if os.path.splitext(path)[1].lower() in (".musicxml", ".xml", ".mxl"):
                self.notes, self.info = core.load_musicxml(path)
                imported = self.info
            else:
                self.notes, self.info = core.load_midi(path)
        except Exception as exc:
            QMessageBox.warning(self, "MIDI to Stave", f"Could not read that file:\n{exc}")
            return
        if self.stop_hook:
            self.stop_hook()                                  # loading while playing stops the old playback
        self.path = path
        self.hl_bar = None
        self.load_lyrics()
        self.roll.set_playhead(None)
        self._to_top = True
        self.preview.verticalScrollBar().setValue(0)
        self.roll.horizontalScrollBar().setValue(0)
        self.loaded_label.setText(f"  Loaded: {os.path.basename(path)}  ")
        self.hidden_tracks = set()
        if self.roll_window is None:
            QTimer.singleShot(0, self.show_roll)
        self.show_tracks()
        self.title.blockSignals(True)
        self.title.setText((imported or {}).get("title") or os.path.splitext(os.path.basename(path))[0])
        self.title.blockSignals(False)
        self.setWindowTitle(f"MIDI to Stave - {os.path.basename(path)}")
        self.bar_grid = {}
        self.setters = []
        self.sel_notes, self.undo_stack, self.redo_stack = set(), [], []
        self.setter_list.clear()
        self.selected_bar = None
        self.src_key = None
        self.need_probe = True
        self.stave_names.blockSignals(True)
        self.stave_names.setText("")
        self.stave_names.blockSignals(False)
        if imported:
            self.barmap = imported["barmap"]                 # the bar lines are already exact: nothing to detect
            if len(imported["names"]) > 1:
                self.layout_kind.blockSignals(True)
                self.layout_kind.setCurrentIndex(4)          # one stave per part
                self.layout_kind.blockSignals(False)
                self.stave_names.setText(", ".join(imported["names"]))
            self.update_name_hint()
            self.refresh_roll()
            self.changed(delay=50)
        else:
            voices = {(n.track, n.ch) for n in self.notes if n.ch != 9}
            if len(voices) >= 3:                                  # multi-track / orchestral file: one stave per voice
                self.layout_kind.blockSignals(True)
                self.layout_kind.setCurrentIndex(KINDS.index("voices"))
                self.layout_kind.blockSignals(False)
            self.update_name_hint()
            self.detect_bars()
            self.import_setters(path)

    def _track_toggled(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        if key is None:
            return
        (self.hidden_tracks.discard if item.checkState() == Qt.CheckState.Checked else self.hidden_tracks.add)(key)
        self.changed()

    def set_all_tracks(self, show):
        self.track_list.blockSignals(True)
        for i in range(self.track_list.count()):
            item = self.track_list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key is not None:
                item.setCheckState(Qt.CheckState.Checked if show else Qt.CheckState.Unchecked)
                (self.hidden_tracks.discard if show else self.hidden_tracks.add)(key)
        self.track_list.blockSignals(False)
        self.changed()

    def only_current_track(self):
        cur = self.track_list.currentItem()
        if cur is None or cur.data(Qt.ItemDataRole.UserRole) is None:
            return
        self.set_all_tracks(False)
        cur.setCheckState(Qt.CheckState.Checked)

    def show_tracks(self):
        names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        note = lambda p: f"{names[p % 12]}{p // 12 - 1}"
        self.track_list.blockSignals(True)
        self.track_list.clear()
        for r in self.info.get("tracks", []):
            label = f'T{r["track"] + 1}  "{r["name"]}"' if r["name"] else f'T{r["track"] + 1}'
            if r["channel"] is None:
                self.track_list.addItem(f"{label}  (empty)")
            else:
                inst = f'  {r.get("instrument")}' if r.get("instrument") else ""
                item = QListWidgetItem(f'{label}  ch{r["channel"] + 1}{inst}  {r["notes"]} notes  {note(r["lo"])}-{note(r["hi"])}')
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked if (r["track"], r["channel"]) in self.hidden_tracks else Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, (r["track"], r["channel"]))
                self.track_list.addItem(item)
        self.track_list.blockSignals(False)

    # ---- organ setters
    def import_setters(self, path):
        self.setters = []
        for t, filename, internal_id, name in sessionmeta.read_markers(path):
            bar = self.barmap.bar_of_beat(self.barmap.sec_to_beat(t))
            self.setters.append({"bar": int(bar), "filename": filename, "id": internal_id, "name": name})
        self.refresh_setters()

    def setter_label(self, x):
        """Text printed over the score for a setter change: "012 Name", or the registration in organists' shorthand."""
        plain = f'{x["id"]} {x["name"]}'
        if not self.adv_registration.isChecked():
            return plain
        cache = self.__dict__.setdefault("_reg_cache", {})
        key = (x["filename"], x["id"])
        if key not in cache:
            combo = next((c for c in sessionmeta.load_combos() if c["filename"] == x["filename"] and c["internal_id"] == x["id"]), None)
            cache[key] = sessionmeta.registration_text(combo["switch_paths"]) if combo else ""
        return f'{x["name"]}  -  {cache[key]}' if cache[key] else plain

    def refresh_setters(self):
        self.setters.sort(key=lambda x: x["bar"])
        self.setter_list.clear()
        for x in self.setters:
            self.setter_list.addItem(f'Bar {x["bar"] + 1}: {x["id"]} {x["name"]}  [{x["filename"]}]')
        self.changed(delay=100)

    def add_setter(self):
        if not self.combos:
            QMessageBox.information(self, "Setters", "No setter list found. Put the stave editor inside the Scripts folder "
                                    "(next to config.yaml and the Combinations folder).")
            return
        bar = self.selected_bar if self.selected_bar is not None else 0
        dialog = SetterPicker(self.combos, bar + 1, max(1, self.barmap.bar_count), self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.choice:
            c = dialog.choice
            self.setters = [x for x in self.setters if x["bar"] != dialog.bar() - 1]      # one setter per bar
            self.setters.append({"bar": dialog.bar() - 1, "filename": c["filename"], "id": c["internal_id"], "name": c["name"]})
            self.refresh_setters()

    def remove_setter(self):
        row = self.setter_list.currentRow()
        if 0 <= row < len(self.setters):
            del self.setters[row]
            self.refresh_setters()

    def build_manual_rows(self, kind, staves):
        """One row per stave with a check box per manual (Pedal, Hauptwerk, Schwellwerk, Solowerk). Several ticks = the
        stave plays those manuals together. Keeps earlier ticks while the stave count stays the same."""
        old = [{n: c.isChecked() for n, c in row.items() if n != '__reg__'} for row in self.manual_checks]
        while self.manual_rows.count():
            item = self.manual_rows.takeAt(0)
            if item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
            elif item.widget():
                item.widget().deleteLater()
        keep_reg = self.voice_reg if len(self.voice_reg) == len(staves) else [[] for _ in staves]
        self.manual_checks, self.voice_reg = [], keep_reg
        defaults = {"Pedal": ("Pedal",), "Manual II": ("Schwellwerk",), "Left hand": ("Schwellwerk",)}
        for i, spec in enumerate(staves):
            row = QHBoxLayout()
            sugg = self._suggest_voice(spec)
            label = QLabel(spec.name)
            label.setToolTip(getattr(self, "voice_hint", {}).get(spec.name, ""))
            row.addWidget(label)
            checks = {}
            for name, _path, _ch in self.manuals:
                box = QCheckBox(sessionmeta.MANUAL_SHORT[name])
                box.setToolTip(f"{name}: MIDI channel {self.manual_channel[name]}")
                if len(old) == len(staves) and old[i]:
                    box.setChecked(old[i].get(name, False))
                else:
                    box.setChecked(name in (sugg or defaults.get(spec.name, ("Hauptwerk",))))
                checks[name] = box
                row.addWidget(box)
            if kind == "voices" and i == len(staves) - 1 and spec.clef == "bass" and len(staves) > 1:
                for name, box in checks.items():
                    box.setChecked(name == "Pedal")
            reg = QPushButton("Reg: " + self._reg_text(keep_reg[i]))
            reg.setToolTip("Registration for this voice, bar by bar: a setter's stops or individual stops")
            reg.clicked.connect(lambda _=False, idx=i: self.pick_voice_reg(idx))
            row.addWidget(reg)
            checks["__reg__"] = reg
            self.manual_checks.append(checks)
            self.manual_rows.addLayout(row)

    def _suggest_voice(self, spec):
        """Manuals suggested by what the file says this voice is (track name, GM program, register); None when unknown."""
        if not getattr(spec, "voices", None):
            return None
        track, ch = spec.voices[0]
        row = next((r for r in self.info.get("tracks", []) if r["track"] == track and r["channel"] == ch), None)
        mine = sorted(n.pitch for n in self.notes if (n.track, n.ch) == (track, ch)) or [60]
        name = (row or {}).get("name") or spec.name
        manuals, stops, why = sessionmeta.suggest(name, (row or {}).get("program"), mine[len(mine) // 2])
        spec_tip = ", ".join(s["name"] for s in sessionmeta.suggest_stops(manuals[0], stops)[:6])
        self.statusBar().showMessage(f"{spec.name}: {'/'.join(manuals)} ({why})" + (f" - suggested stops: {spec_tip}" if spec_tip else ""), 6000)
        self.voice_hint = getattr(self, "voice_hint", {})
        self.voice_hint[spec.name] = f"{'/'.join(manuals)} suggested from {why}" + (f"\nSuggested stops: {spec_tip}" if spec_tip else "")
        return manuals

    @staticmethod
    def _reg_text(entries):
        return "-" if not entries else f"{len(entries)} change{'s' if len(entries) != 1 else ''}"

    def pick_voice_reg(self, index):
        dialog = VoiceRegDialog(self, index)
        dialog.exec()
        self.manual_checks[index]["__reg__"].setText("Reg: " + self._reg_text(self.voice_reg[index]))
        self.changed(delay=100)

    def manual_of_stop(self, path):
        number = int(path.split("/")[1])
        return self.manuals[number][0] if 0 <= number < len(self.manuals) else None

    def voice_markers(self):
        """Registration markers per voice and bar. 'setter' entries give the manuals the voice plays that setter's
        stops; 'stops' entries set the named stops of their own manual exactly. Both apply from that bar on."""
        cum = self.barmap.cumulative()
        marks = []
        for entries, checks in zip(self.voice_reg, self.manual_checks):
            for e in entries or []:
                beat = float(cum[min(e["bar"], len(cum) - 1)])
                if e["kind"] == "setter":
                    for name, box in checks.items():
                        if name != "__reg__" and box.isChecked():
                            marks.append((beat, sessionmeta.format_reg(name, e["filename"], e["id"], e["name"])))
                else:
                    groups = {}
                    for path in e["paths"]:
                        groups.setdefault(self.manual_of_stop(path), []).append(path)
                    for manual, paths in groups.items():
                        if manual:
                            marks.append((beat, sessionmeta.format_stops(manual, paths, e.get("label", ""))))
        return marks

    # ---- hear it on the organ (needs the bridge: open the editor with its "Stave editor" button)
    def play_on_organ(self, selection_only=False, offset=None):
        if not self.notes:
            return
        if offset is None or offset is False:               # Play after Pause carries on from where it paused
            offset = 0.0 if selection_only else float(getattr(self, "_paused_at", None) or 0.0)
        self._paused_at = None
        notes = self.selected_notes() if selection_only else self.notes
        if not notes:
            self.statusBar().showMessage("Select some notes first.")
            return
        if self.play_hook is None:
            self.statusBar().showMessage("Open the stave editor from the bridge (Stave editor button) to play on the organ.")
            return
        folder = getattr(self, "default_dir", "") or os.path.join(os.path.dirname(HERE), "midi")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "_preview.mid")
        hidden = self.hidden_tracks                       # what you see on the stave is what you hear
        notes = [n for n in notes if (n.track, n.ch) not in hidden and not n.mute]
        quant = None
        if (not selection_only and self.play_quantised.isChecked() and self.qnotes and not self.job_dirty
                and not self.job_running):                 # the quantised score, in the stave's key (transpose) as engraved
            quant = [q for q in self.qnotes if (q.track, q.ch) not in hidden
                     and not (0 <= q.src < len(self.notes) and self.notes[q.src].mute)]
        core.export_fixed_midi(notes, self.barmap, path, quantised=quant, staves=self.staves_for_export(),
                               markers=[] if selection_only else self.setter_markers() + self.voice_markers(),
                               transpose=self.transpose.value())
        try:
            self.play_hook(path, offset)
        except TypeError:
            self.play_hook(path)
        self.statusBar().showMessage("Playing on the organ" + (f" from {offset:.1f} s" if offset else ""))

    def stop_on_organ(self, *_):
        self._paused_at = None                                # Stop rewinds; Space / Pause keeps the place
        if self.stop_hook:
            self.stop_hook()

    def pause_on_organ(self):
        t = self.pos_hook() if self.pos_hook else None
        if t is not None:
            self._paused_at = float(t)
            self.statusBar().showMessage("Paused - press Play (or Space) to carry on")
        if self.stop_hook:
            self.stop_hook()

    def staves_for_export(self):
        p = self.params()
        staves = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], self.notes,
                                  self.info.get("voice_names"))
        for spec, checks in zip(staves, self.manual_checks):
            spec.go_chs = tuple(self.manual_channel[n] for n, box in checks.items() if box.isChecked())   # none ticked = not written
        return staves

    def setter_markers(self):
        cum = self.barmap.cumulative()
        return [(float(cum[min(x["bar"], len(cum) - 1)]), sessionmeta.format_marker(x["filename"], x["id"], x["name"]))
                for x in self.setters]

    # ---- bar editing
    def detect_bars(self, *_):
        if not self.notes:
            return
        bpb = TIME_SIGS[self.meter.currentText()]
        bpm = self.bpm.value() or None
        try:
            self.barmap = core.estimate_bars(self.notes, bpb, bpm, follow=self.follow.value() / 100.0)
        except Exception:                                      # too few notes to find a beat: one plain bar at the given tempo
            end = max(n.end for n in self.notes)
            bar_sec = 60.0 / (bpm or 100.0) * bpb
            self.barmap = core.BarMap([i * bar_sec for i in range(int(end // bar_sec) + 2)], [bpb] * (int(end // bar_sec) + 1))
        self.bar_grid = {}
        self.selected_bar = None
        self.refresh_roll()
        self.changed(delay=50)

    def shift_downbeat(self, step):
        if self.barmap.bar_count < 2:
            return
        period = (self.barmap.anchors[-1] - self.barmap.anchors[0]) / sum(self.barmap.beats)
        anchors = [a + step * period * 1.0 for a in self.barmap.anchors]
        self.barmap = core.BarMap(anchors, self.barmap.beats)
        self.refresh_roll()
        self.changed(delay=50)

    def select_bar(self, index):
        self.selected_bar = index if index < self.barmap.bar_count else None
        if self.selected_bar is None:
            self.sel_label.setText("Last bar line - select a bar line before it")
            return
        self.sel_label.setText(f"Bar {self.selected_bar + 1} selected (its start is the line you picked)")
        self.bar_beats.blockSignals(True)
        self.bar_beats.setValue(self.barmap.beats[self.selected_bar])
        self.bar_beats.blockSignals(False)
        override = self.bar_grid.get(self.selected_bar)
        index = {None: 0, Fraction(1, 2): 1, Fraction(1, 4): 2, Fraction(1, 8): 3, Fraction(1, 16): 4, "t": 5}.get(override, 0)
        self.bar_grid_box.blockSignals(True)
        self.bar_grid_box.setCurrentIndex(index)
        self.bar_grid_box.blockSignals(False)
        self.roll.select(self.selected_bar)
        self.highlight_bar(self.selected_bar, "#2a6df0")            # show the bar in the score and go there
        self.scroll_to_bar(self.selected_bar, always=True)

    def bar_moved(self, index, seconds):
        anchors = list(self.barmap.anchors)
        anchors[index] = seconds
        self.barmap = core.BarMap(anchors, self.barmap.beats)
        self.refresh_roll(keep_view=True)
        self.changed(delay=80)

    def nudge_selected(self, delta):
        if self.selected_bar is None:
            return
        anchors = list(self.barmap.anchors)
        i = self.selected_bar
        lo = anchors[i - 1] + 0.05 if i > 0 else -1e9
        hi = anchors[i + 1] - 0.05
        anchors[i] = max(lo, min(hi, anchors[i] + delta))
        self.barmap = core.BarMap(anchors, self.barmap.beats)
        self.refresh_roll(keep_view=True)
        self.changed(delay=120)

    def bar_beats_changed(self, value):
        if self.selected_bar is None or self.selected_bar >= self.barmap.bar_count:
            return
        beats = list(self.barmap.beats)
        beats[self.selected_bar] = float(value)
        self.barmap = core.BarMap(self.barmap.anchors, beats)
        self.changed(delay=200)

    def bar_grid_changed(self, index):
        if self.selected_bar is None:
            return
        value = [None, Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 16), "t"][index]
        if value is None:
            self.bar_grid.pop(self.selected_bar, None)
        else:
            self.bar_grid[self.selected_bar] = value
        self.changed(delay=100)

    def insert_bar_line(self, seconds):
        anchors, beats = list(self.barmap.anchors), list(self.barmap.beats)
        import bisect
        i = bisect.bisect_right(anchors, seconds)
        if i <= 0 or i >= len(anchors):
            return
        whole = beats[i - 1]
        share = (seconds - anchors[i - 1]) / (anchors[i] - anchors[i - 1])
        first = max(0.5, round(whole * share * 2) / 2)
        anchors.insert(i, seconds)
        beats[i - 1:i] = [first, max(0.5, whole - first)]
        self.barmap = core.BarMap(anchors, beats)
        self.bar_grid = {}
        self.refresh_roll(keep_view=True)
        self.changed(delay=50)

    def delete_bar_line(self, index):
        anchors, beats = list(self.barmap.anchors), list(self.barmap.beats)
        if index <= 0 or index >= len(anchors) - 1:
            return
        del anchors[index]
        beats[index - 1:index + 1] = [beats[index - 1] + beats[index]]
        self.barmap = core.BarMap(anchors, beats)
        self.bar_grid = {}
        self.refresh_roll(keep_view=True)
        self.changed(delay=50)

    # ---- roll + preview
    # ---- note editor (piano roll): select / drag / arrows / double-click to add / right-click menu, with undo
    LENGTHS = (("Whole note (semibreve)", 4.0), ("Dotted half", 3.0), ("Half note (minim)", 2.0),
               ("Dotted quarter", 1.5), ("Quarter note (crotchet)", 1.0), ("Dotted eighth", 0.75),
               ("Eighth note (quaver)", 0.5), ("Sixteenth (semiquaver)", 0.25), ("Thirty-second", 0.125),
               ("Sixty-fourth", 0.0625))

    def _snapshot(self):
        return [(n.start, n.end, n.pitch, n.vel, n.ch, n.track, n.stave, n.mute) for n in self.notes]

    def _restore(self, snap):
        self.notes[:] = [core.Note(*t) for t in snap]
        self.sel_notes = set()
        self.after_edit()

    def push_undo(self):
        self.undo_stack.append(self._snapshot())
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self._snapshot())
            self._restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self._snapshot())
            self._restore(self.redo_stack.pop())

    def after_edit(self):
        self.ensure_bars()
        self.notes.sort(key=lambda n: (n.start, n.pitch))
        self.refresh_roll(keep_view=True)
        self.changed(delay=150)

    def selected_notes(self):
        return [n for n in self.notes if id(n) in self.sel_notes]

    def select_note(self, note, add):
        if note is None:
            self.sel_notes = set()
        elif add:
            self.sel_notes ^= {id(note)}
        elif id(note) not in self.sel_notes:
            self.sel_notes = {id(note)}
        self.roll.apply_selection(self.sel_notes)
        self.mark_score()

    # ---- the engraved score as an editor: note heads -> notes
    def _note_of_hit(self, hit):
        """Hit (x, y, pitch, beat, id) -> the source core.Note it shows, or None."""
        transpose = self.hit_params.get("transpose", 0)
        pitch, beat = hit[2] - transpose, hit[3]
        best, gap = None, 1e9
        for q in self.qnotes:
            if q.pitch == pitch and q.src >= 0 and abs(float(q.start) - beat) < gap and float(q.start) - 0.05 <= beat < float(q.end) + 0.05:
                best, gap = q, abs(float(q.start) - beat)
        if best is None:                                   # fall back to the nearest onset of that pitch
            for q in self.qnotes:
                if q.pitch == pitch and q.src >= 0 and abs(float(q.start) - beat) < min(gap, 0.6):
                    best, gap = q, abs(float(q.start) - beat)
        return self.notes[best.src] if best is not None and best.src < len(self.notes) else None

    def hit_at(self, page, x, y):
        if self.job_running or self.job_dirty or page >= len(self.hits):
            return None                                    # the page is being redrawn: positions are stale
        near, gap = None, (9.0 * self.page_dims[page][0] / self.page_dims[page][0]) ** 2   # 9 SVG units = one staff space
        for hit in self.hits[page]:
            d = (hit[0] - x) ** 2 + (hit[1] - y) ** 2
            if d < gap:
                near, gap = hit, d
        return self._note_of_hit(near) if near else None

    def select_in_rect(self, page, x0, y0, x1, y1, add):
        if self.job_running or self.job_dirty or page >= len(self.hits):
            return
        found = set(self.sel_notes) if add else set()
        for hit in self.hits[page]:
            if x0 <= hit[0] <= x1 and y0 <= hit[1] <= y1:
                n = self._note_of_hit(hit)
                if n is not None:
                    found.add(id(n))
        self.sel_notes = found
        self.roll.apply_selection(self.sel_notes)
        self.mark_score()

    @staticmethod
    def pitch_name(m):
        return ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"][m % 12] + str(m // 12 - 1)

    def _build_sign_palette(self):
        """A second toolbar row: marks you drag onto note heads (Toe ^, Heel U)."""
        from PySide6.QtWidgets import QToolBar
        from PySide6.QtGui import QDrag
        from PySide6.QtCore import QMimeData
        bar = QToolBar("Signs")
        bar.setMovable(False)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        bar.addWidget(QLabel("  Drag onto a note:  "))

        class SignButton(QPushButton):
            def mouseMoveEvent(inner, event):
                if event.buttons() & Qt.MouseButton.LeftButton:
                    drag = QDrag(inner)
                    mime = QMimeData()
                    mime.setText(inner.property("sign"))
                    drag.setMimeData(mime)
                    drag.setPixmap(inner.grab())
                    drag.exec(Qt.DropAction.CopyAction)
                else:
                    super().mouseMoveEvent(event)

        for text, sign, tip in (("^  Toe", "sign:toe", "Pedal toe (Spitze): drag onto a pedal note"),
                                ("U  Heel", "sign:heel", "Pedal heel (Absatz): drag onto a pedal note"),
                                ("x  Clear", "sign:none", "Drag onto a note to remove its pedal mark")):
            btn = SignButton(text)
            btn.setProperty("sign", sign)
            btn.setToolTip(tip)
            bar.addWidget(btn)
        bar.addWidget(QLabel("   Drag a note head up / down to change its pitch (you hear it), sideways to move it in time."))

    # ---- direct manipulation helpers (drag note heads, drop pedal marks)
    @staticmethod
    def _sign_key(n):
        return (n.track, n.ch, n.pitch, round(n.start, 3))

    def sign_params(self):
        out = {}
        for q in self.qnotes:
            if 0 <= q.src < len(self.notes):
                sign = self.signs.get(self._sign_key(self.notes[q.src]))
                if sign:
                    out[(int(q.pitch), round(float(q.start), 3))] = sign
        return out

    def tool_click(self, note, t=None):
        """The active tool acts on a clicked note. True when it did (so the click is not also a selection)."""
        tool = getattr(self, "tool", "select")
        if tool == "erase":
            self.delete_notes([note])
        elif tool == "mute":
            self.set_mute([note], not note.mute)
        elif tool == "slice" and t is not None:
            self.slice_note(note, t)
        elif tool == "slice":
            return False
        elif tool in ("toe", "heel"):
            self.apply_sign(note, tool)
        else:
            return False
        return True

    def apply_sign(self, note, sign):
        key = self._sign_key(note)
        if sign in ("toe", "heel", "slide") or (sign and sign.startswith("f:")):
            self.signs[key] = sign
        else:
            self.signs.pop(key, None)
        self.changed(delay=60)
        self.statusBar().showMessage({"toe": "Toe mark (^) added", "heel": "Heel mark (U) added"}.get(sign, "Pedal mark removed"), 3000)

    def hit_near(self, page, x, y, radius_spaces=1.6):
        """Nearest engraved note head to (x, y) -> (hit, note) or (None, None)."""
        if self.job_running or self.job_dirty or page >= len(self.hits):
            return None, None
        space = self.spaces[page] if page < len(self.spaces) else 18.0
        near, gap = None, (radius_spaces * space) ** 2
        for hit in self.hits[page]:
            d = (hit[0] - x) ** 2 + (hit[1] - y) ** 2
            if d < gap:
                near, gap = hit, d
        return (near, self._note_of_hit(near)) if near else (None, None)

    def drag_plan(self, page, hit, dx, dy):
        """What dropping a dragged head would do: (steps, displayed pitch, target beat or None, snapped x offset, y offset)."""
        space = self.spaces[page] if page < len(self.spaces) else 18.0
        steps = -int(round(dy / (space / 2.0)))          # up the page = higher pitch
        pcs = self._scale_pcs()
        ladder = [m for m in range(0, 128) if m % 12 in pcs]
        below = [i for i, m in enumerate(ladder) if m <= hit[2]]
        base = below[-1] if below else 0
        idx = max(0, min(len(ladder) - 1, base + steps))
        steps = idx - base                                   # clamped at the ends of the keyboard
        new_pitch = ladder[idx] if steps else hit[2]
        beat, x_off = None, 0.0
        if abs(dx) > space * 0.9:                            # horizontal: snap onto the neighbouring note positions
            cands = [h for h in self.hits[page] if abs(h[1] - hit[1]) < space * 6 and abs(h[0] - (hit[0] + dx)) < space * 3]
            if cands:
                best = min(cands, key=lambda h: abs(h[0] - (hit[0] + dx)))
                beat, x_off = best[3], best[0] - hit[0]
        y_off = -steps * space / 2.0
        return steps, new_pitch, beat, x_off, y_off

    def _scale_pcs(self):
        tonic, name = (self.src_key or (0, "C major"))
        minor = "minor" in str(name)
        intervals = (0, 2, 3, 5, 7, 8, 10) if minor else (0, 2, 4, 5, 7, 9, 11)
        chosen = self.key.currentText()
        if chosen not in ("auto", "", None):
            try:
                from music21 import key as _key
                k = _key.Key(chosen)
                tonic, intervals = k.tonic.pitchClass, ((0, 2, 3, 5, 7, 8, 10) if k.mode == "minor" else intervals)
            except Exception:
                pass
        return {(tonic + i + self.transpose.value()) % 12 for i in intervals}

    def preview_pitch(self, pitch, note=None, fallback=False):
        """Sound one pitch on the organ right now (live feedback while a note head is dragged)."""
        if self.chord_hook is None or note is None:
            return
        staves = self.staves_for_export()
        src = pitch - self.hit_params.get("transpose", 0)
        chans = core.stave_go_channels(src, note.ch, staves, note.track)
        if not chans and fallback:                       # piano key outside every stave's range: still sound it on the note's own channel
            chans = [note.ch]
        self.chord_hook([(ch, src, max(50, note.vel)) for ch in chans], 0.35)

    def commit_drag(self, page, hit, note, plan):
        steps, new_pitch, beat, _x, _y = plan
        dp = new_pitch - hit[2]
        dt = 0.0
        if beat is not None:
            new_sec = self.barmap.beat_to_sec(self.barmap.sec_to_beat(note.start) + (beat - hit[3]))
            dt = new_sec - note.start
        if dp == 0 and beat is None:
            return
        self.move_selected(dt, dp, note)

    def mark_score(self):
        """Blue rings on the engraved note heads of the selected notes."""
        src_of = {id(n): i for i, n in enumerate(self.notes)}
        wanted = {src_of[i] for i in self.sel_notes if i in src_of}
        transpose = self.hit_params.get("transpose", 0)
        by_pitch = {}
        for q in self.qnotes:
            if q.src in wanted:
                by_pitch.setdefault(q.pitch + transpose, []).append((float(q.start) - 0.05, float(q.end) + 0.05))
        for page, widget in enumerate(self.page_widgets):
            marks = []
            for hit in self.hits[page] if page < len(self.hits) else []:
                if any(lo <= hit[3] < hi for lo, hi in by_pitch.get(hit[2], ())):
                    marks.append((hit[0], hit[1]))
            widget.marks = marks
            widget.update()

    def stretch_selected(self, side, dt, anchor, free=False):
        """Lengthen / shorten the selected notes by dragging their right or left end (snapped to the grid; Alt = free)."""
        notes = self.selected_notes() or [anchor]
        self.push_undo()
        self._free = free
        try:
            if side == "R":
                delta = self.snap_sec(anchor.end + dt) - anchor.end
            else:
                delta = self.snap_sec(anchor.start + dt) - anchor.start
        finally:
            self._free = False
        for n in notes:
            if side == "R":
                n.end = max(n.start + 0.02, n.end + delta)
            else:
                n.start = max(0.0, min(n.end - 0.02, n.start + delta))
        self.after_edit()

    def snap_unit(self):
        """Grid step in beats used for placing / moving notes: the piano roll's own snap, else the score grid."""
        override = getattr(self, "roll_snap", None)
        return float(override) if override else float(core.GRID_CHOICES[self.grid.currentText()])

    def snap_sec(self, t):
        if getattr(self, "_free", False):
            return max(0.0, t)
        if not self.snap.isChecked():
            return max(0.0, t)
        unit = self.snap_unit()
        beat = round(self.barmap.sec_to_beat(max(0.0, t)) / unit) * unit
        return max(0.0, self.barmap.beat_to_sec(beat))

    def move_selected(self, dt, dp, anchor):
        notes = self.selected_notes()
        if not notes:
            self.after_edit()
            return
        self.push_undo()
        delta = self.snap_sec(anchor.start + dt) - anchor.start
        for n in notes:
            length = n.end - n.start
            n.start = max(0.0, n.start + delta)
            n.end = n.start + length
            n.pitch = max(0, min(127, n.pitch + dp))
        self.after_edit()

    def nudge(self, steps, fine=False):
        notes = self.selected_notes()
        if not notes:
            return
        self.push_undo()
        unit = float(core.GRID_CHOICES[self.grid.currentText()])
        for n in notes:
            length = n.end - n.start
            if fine:
                n.start = max(0.0, n.start + steps * 0.01)
            else:
                beat = self.barmap.sec_to_beat(n.start) + steps * unit
                n.start = max(0.0, self.barmap.beat_to_sec(max(0.0, beat)))
            n.end = n.start + length
        self.after_edit()

    def transpose_selected(self, semitones):
        notes = self.selected_notes()
        if notes:
            self.push_undo()
            for n in notes:
                n.pitch = max(0, min(127, n.pitch + semitones))
            self.after_edit()

    def set_stave(self, notes, index):
        self.push_undo()
        for n in notes:
            n.stave = index
        self.after_edit()

    def set_length(self, notes, beats):
        self.push_undo()
        for n in notes:
            b = self.barmap.sec_to_beat(n.start)
            n.end = self.barmap.beat_to_sec(b + beats)
        self.after_edit()

    def set_velocity(self, notes, vel):
        self.push_undo()
        for n in notes:
            n.vel = vel
        self.after_edit()

    def delete_notes(self, notes):
        if notes:
            self.push_undo()
            ids = {id(n) for n in notes}
            self.notes[:] = [n for n in self.notes if id(n) not in ids]
            self.sel_notes = set()
            self.after_edit()

    # ---- piano roll editing (used by the roll window and the shortcuts)
    def describe_at(self, scene_pos, note=None):
        t = scene_pos.x() / self.roll.pps
        pitch = self.roll.top - int(scene_pos.y() // ROW)
        names = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
        beat = self.barmap.sec_to_beat(max(0.0, t))
        bar = self.barmap.bar_of_beat(beat)
        in_bar = beat - float(self.barmap.cumulative()[bar]) + 1
        text = f"{names[pitch % 12]}{pitch // 12 - 1}   bar {bar + 1}  beat {in_bar:.2f}"
        if note is not None:
            length = self.barmap.sec_to_beat(note.end) - self.barmap.sec_to_beat(note.start)
            text = (f"{names[note.pitch % 12]}{note.pitch // 12 - 1}   bar {self.barmap.bar_of_beat(self.barmap.sec_to_beat(note.start)) + 1}"
                    f"   length {length:.2f} beats   velocity {note.vel}" + ("   MUTED" if note.mute else ""))
        return text

    def set_mute(self, notes, on):
        if notes:
            self.push_undo()
            for n in notes:
                n.mute = on
            self.after_edit()

    def slice_note(self, note, t):
        t = self.snap_sec(t)
        if not note.start + 0.02 < t < note.end - 0.02:
            return
        self.push_undo()
        tail = core.Note(t, note.end, note.pitch, note.vel, note.ch, note.track, note.stave, note.mute)
        note.end = t
        self.notes.append(tail)
        self.after_edit()

    def copy_notes(self, cut=False):
        notes = self.selected_notes()
        if not notes:
            return
        first = min(n.start for n in notes)
        self.clipboard = [(n.start - first, n.end - first, n.pitch, n.vel, n.ch, n.track, n.stave, n.mute) for n in notes]
        if cut:
            self.delete_notes(notes)
        self.statusBar().showMessage(f"{len(notes)} note(s) {'cut' if cut else 'copied'}", 2500)

    def paste_notes(self):
        clip = getattr(self, "clipboard", None)
        if not clip:
            return
        at = self.snap_sec(getattr(self.roll, "cursor_sec", 0.0))
        if self.selected_bar is not None and self.selected_bar < self.barmap.bar_count and not getattr(self.roll, "cursor_sec", 0.0):
            at = self.barmap.anchors[self.selected_bar]
        self.push_undo()
        fresh = [core.Note(at + a, at + b, *rest) for a, b, *rest in clip]
        self.notes.extend(fresh)
        self.sel_notes = {id(n) for n in fresh}
        self.after_edit()

    def shift_selected(self, steps):
        notes = self.selected_notes()
        if not notes:
            return
        self.push_undo()
        unit = self.snap_unit()
        for n in notes:
            length = n.end - n.start
            beat = self.barmap.sec_to_beat(n.start) + steps * unit
            n.start = max(0.0, self.barmap.beat_to_sec(max(0.0, beat)))
            n.end = n.start + length
        self.after_edit()

    def discard_lengths(self):
        """Every selected note gets one grid step as its length."""
        notes = self.selected_notes()
        if notes:
            self.push_undo()
            self.set_length_beats(notes, self.snap_unit())

    def set_length_beats(self, notes, beats):
        for n in notes:
            n.end = self.barmap.beat_to_sec(self.barmap.sec_to_beat(n.start) + beats)
        self.after_edit()

    def legato_selected(self):
        """Each selected note runs on to the next note start of the selection (last one keeps its length)."""
        notes = sorted(self.selected_notes(), key=lambda n: (n.start, n.pitch))
        if len(notes) < 2:
            return
        self.push_undo()
        starts = sorted({n.start for n in notes})
        for n in notes:
            later = [t for t in starts if t > n.start + 1e-6]
            if later:
                n.end = later[0]
        self.after_edit()

    def quantise_starts(self):
        notes = self.selected_notes()
        if notes:
            self.push_undo()
            for n in notes:
                length = n.end - n.start
                n.start = self.snap_sec(n.start)
                n.end = n.start + length
            self.after_edit()

    def select_all_notes(self, mode="all"):
        sel = self.selected_notes()
        if mode == "all":
            self.sel_notes = {id(n) for n in self.notes}
        elif mode == "none":
            self.sel_notes = set()
        elif mode == "invert":
            self.sel_notes = {id(n) for n in self.notes} - self.sel_notes
        elif mode == "pitch" and sel:
            pitches = {n.pitch for n in sel}
            self.sel_notes = {id(n) for n in self.notes if n.pitch in pitches}
        elif mode == "bar" and self.selected_bar is not None:
            a0, a1 = self.barmap.anchors[self.selected_bar], self.barmap.anchors[self.selected_bar + 1]
            self.sel_notes = {id(n) for n in self.notes if a0 - 1e-6 <= n.start < a1 - 1e-6}
        elif mode == "after" and sel:
            first = min(n.start for n in sel)
            self.sel_notes = {id(n) for n in self.notes if n.start >= first - 1e-6}
        self.roll.apply_selection(self.sel_notes)
        self.refresh_roll(keep_view=True)
        self.mark_score()

    def insert_space(self):
        """Push everything from the selected bar (or the click position) on by one bar and add that bar."""
        bar = self.selected_bar if self.selected_bar is not None else self.barmap.bar_of_beat(self.barmap.sec_to_beat(self.roll.cursor_sec))
        bar = max(0, min(bar, self.barmap.bar_count - 1))
        self.push_undo()
        length = self.barmap.anchors[bar + 1] - self.barmap.anchors[bar]
        at = self.barmap.anchors[bar]
        for n in self.notes:
            if n.start >= at - 1e-6:
                n.start += length
                n.end += length
        anchors = self.barmap.anchors[:bar + 1] + [a + length for a in self.barmap.anchors[bar:]]
        beats = list(self.barmap.beats[:bar + 1]) + list(self.barmap.beats[bar:])
        self.barmap = core.BarMap(anchors, beats)
        self.after_edit()

    def duplicate_notes(self, notes):
        if notes:
            self.push_undo()
            copies = []
            for n in notes:
                c = core.Note(n.start, n.end, n.pitch, n.vel, n.ch, n.track, n.stave, n.mute)
                copies.append(c)
            self.notes.extend(copies)
            self.sel_notes = {id(c) for c in copies}
            self.after_edit()

    def add_note_from_score(self, page, x, y):
        """Add tool: a click on the engraved stave puts a note there - pitch from the line / space, time from the neighbouring notes."""
        if page >= len(self.hits) or not self.hits[page]:
            self.statusBar().showMessage("The score is still being drawn - try again in a moment.")
            return
        space = self.spaces[page] if page < len(self.spaces) else 18.0
        hits = self.hits[page]
        ref = min(hits, key=lambda h: (h[1] - y) ** 2 + ((h[0] - x) * 0.05) ** 2)       # head on the staff you clicked
        if abs(ref[1] - y) > 12 * space:
            return
        pcs = self._scale_pcs()
        ladder = [m for m in range(0, 128) if m % 12 in pcs]
        below = [i for i, m in enumerate(ladder) if m <= ref[2]]
        base = below[-1] if below else 0
        steps = -int(round((y - ref[1]) / (space / 2.0)))
        pitch_shown = ladder[max(0, min(len(ladder) - 1, base + steps))]
        row = sorted((h for h in hits if abs(h[1] - ref[1]) < 14 * space), key=lambda h: h[0])
        left = [h for h in row if h[0] <= x]
        right = [h for h in row if h[0] > x]
        if left and right and right[0][0] > left[-1][0]:
            a, b = left[-1], right[0]
            beat = a[3] + (b[3] - a[3]) * (x - a[0]) / (b[0] - a[0])
        else:
            beat = min(row, key=lambda h: abs(h[0] - x))[3]
        t = self.snap_sec(self.barmap.beat_to_sec(max(0.0, beat)))
        src_note = self._note_of_hit(ref)
        self.push_undo()
        start = t
        beats = dict(self.LENGTHS).get(self.new_len.currentText(), 1.0)
        end = self.barmap.beat_to_sec(self.barmap.sec_to_beat(start) + beats)
        pitch = pitch_shown - self.hit_params.get("transpose", 0)
        n = core.Note(start, end, pitch, 80, src_note.ch if src_note else 0, src_note.track if src_note else 0)
        self.notes.append(n)
        self.sel_notes = {id(n)}
        self.after_edit()
        self.preview_pitch(pitch_shown, n)

    def add_note_at(self, t, pitch):
        if not 0 <= pitch <= 127:
            return
        self.push_undo()
        start = self.snap_sec(t)
        beats = dict(self.LENGTHS).get(self.new_len.currentText(), 1.0)
        end = self.barmap.beat_to_sec(self.barmap.sec_to_beat(start) + beats)
        channel = self.notes[-1].ch if self.notes else 0
        track = self.notes[-1].track if self.notes else 0
        n = core.Note(start, end, pitch, 80, channel, track)
        self.notes.append(n)
        self.sel_notes = {id(n)}
        self.after_edit()

    def key_edit(self, event):
        key, mods = event.key(), event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        if key == Qt.Key.Key_Up:
            self.transpose_selected(12 if shift else 1)
        elif key == Qt.Key.Key_Down:
            self.transpose_selected(-12 if shift else -1)
        elif key == Qt.Key.Key_Right:
            self.nudge(1, fine=ctrl)
        elif key == Qt.Key.Key_Left:
            self.nudge(-1, fine=ctrl)
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_notes(self.selected_notes())
        elif ctrl and key == Qt.Key.Key_A:
            self.sel_notes = {id(n) for n in self.notes}
            self.roll.apply_selection(self.sel_notes)
        elif ctrl and key == Qt.Key.Key_D:
            self.duplicate_notes(self.selected_notes())
        else:
            return False
        return True

    def note_menu(self, note, pos):
        if id(note) not in self.sel_notes:
            self.select_note(note, False)
        notes = self.selected_notes()
        menu = QMenu(self)
        length = menu.addMenu("Note length / type")
        for label, beats in self.LENGTHS:
            length.addAction(label, lambda b=beats: self.set_length(notes, b))
        loud = menu.addMenu("Velocity (dynamics)")
        for label, vel in (("pp", 30), ("p", 45), ("mp", 60), ("mf", 80), ("f", 100), ("ff", 120)):
            loud.addAction(label, lambda v=vel: self.set_velocity(notes, v))
        fing = menu.addMenu("Fingering")
        for label in ("1", "2", "3", "4", "5", "1-2", "2-3", "3-4", "4-5", "5-4", "4-3", "3-2", "2-1"):
            fing.addAction(label if "-" not in label else f"{label}  (finger change)", lambda l=label: [self.apply_sign(n, "f:" + l) for n in notes])
        fing.addAction("Clear", lambda: [self.apply_sign(n, None) for n in notes])
        mark = menu.addMenu("Pedal mark")
        mark.addAction("Slide (<)", lambda: [self.apply_sign(n, "slide") for n in notes])
        mark.addAction("Toe (^)", lambda: [self.apply_sign(n, "toe") for n in notes])
        mark.addAction("Heel (U)", lambda: [self.apply_sign(n, "heel") for n in notes])
        mark.addAction("None", lambda: [self.apply_sign(n, None) for n in notes])
        on = menu.addMenu("Show on stave (hand crossing)")
        on.addAction("Automatic (by pitch)", lambda: self.set_stave(notes, -1))
        try:
            p = self.params()
            specs = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], self.notes,
                                     self.info.get("voice_names"))
            for i, spec in enumerate(specs):
                label = p["names"][i] if i < len(p["names"]) and p["names"][i] else spec.name
                on.addAction(label, lambda i=i: self.set_stave(notes, i))
        except Exception:
            pass
        menu.addAction("Octave up", lambda: self.transpose_selected(12))
        menu.addAction("Octave down", lambda: self.transpose_selected(-12))
        menu.addAction("Duplicate (Ctrl+D)", lambda: self.duplicate_notes(notes))
        menu.addAction("Delete (Del)", lambda: self.delete_notes(notes))
        menu.exec(pos)

    # ---- step sequence: play the selected notes again, one chord per step, on the organ
    def _step_groups(self):
        notes = sorted(self.selected_notes(), key=lambda n: (n.start, n.pitch))
        groups, anchor = [], None
        for n in notes:
            if anchor is not None and n.start - anchor <= 0.05:
                groups[-1].append(n)
            else:
                anchor = n.start
                groups.append([n])
        return groups

    def step_play(self, direction=1):
        ids = frozenset(self.sel_notes)
        if ids != self.step_ids:                       # selection changed: start from its first chord
            self.step_groups, self.step_ids, self.step_index = self._step_groups(), ids, 0 if direction > 0 else -1
        if not self.step_groups:
            self.statusBar().showMessage("Select some notes first (click, Shift-click or drag a box).")
            return
        if self.chord_hook is None:
            self.statusBar().showMessage("Open the stave editor from the bridge (Stave editor button) to hear steps on the organ.")
            return
        self.step_index %= len(self.step_groups)
        group = self.step_groups[self.step_index]
        staves = self.staves_for_export()
        items = [(ch, n.pitch, n.vel) for n in group for ch in core.stave_go_channels(n.pitch, n.ch, staves, n.track)]
        hold = min(3.0, max(0.15, max(n.end - n.start for n in group)))
        self.chord_hook(items, hold)
        import time as _t
        self.step_until = _t.time() + hold
        self.roll.set_playhead(group[0].start)
        self.statusBar().showMessage(f"Step {self.step_index + 1} / {len(self.step_groups)}")
        self.step_index = (self.step_index + direction) % len(self.step_groups)

    def hw_step(self, direction):
        """Called from the bridge's engine thread for the KeyLab >> / << buttons: consumed only in step mode."""
        if self.step_mode.isChecked() and self.isVisible():
            self.hwStep.emit(direction)
            return True
        return False

    # ---- fixed transport bar (always on top, whatever the scroll position) + Space = play / stop
    def _build_transport_bar(self):
        from PySide6.QtWidgets import QToolBar
        bar = QToolBar("Transport")
        bar.setObjectName("transportBar")
        bar.setMovable(True)
        bar.setFloatable(True)
        self.transport_bar = bar
        bar.setIconSize(QSize(chrome.STYLE["size"], chrome.STYLE["size"]))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self.loaded_label = QLabel("  Nothing loaded  ")
        bar.addWidget(self.loaded_label)
        for text, handler, tip in (("New", self.new_blank, "Start a blank score: empty bars to write into (Ctrl+N)"),
                                   ("Piano roll", self.show_roll, "Open the piano roll window (F2)"),
                                   ("+ Bars", self.add_bars, "Add 4 empty bars at the end"),
                                   ("Play", self.play_on_organ, "Play on the organ (Space)"),
                                   ("Stop", self.stop_on_organ, "Stop (Space)"),
                                   ("Play selection", lambda: self.play_on_organ(True), "Play only the selected notes")):
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, h=handler: h())
            bar.addWidget(btn)
        self.time_slider = polish.make_seek_slider()
        self.time_slider.setMinimumWidth(260)
        self.time_slider.setToolTip("Click or drag to move to a position (plays from there)")
        self.time_slider.seek.connect(self.seek_fraction)
        self.time_slider.moved.connect(lambda v: self._update_timeline(self._fraction_to_file_sec(v), dragging=True))
        bar.addWidget(self.time_slider)
        self.goto_bar = QSpinBox()
        self.goto_bar.setPrefix("Bar ")
        self.goto_bar.setMinimum(1)
        self.goto_bar.setToolTip("Type a bar number and press Enter to go there")
        self.goto_bar.editingFinished.connect(self.go_to_bar)
        bar.addWidget(self.goto_bar)
        self.time_label = QLabel(" 0:00 / 0:00 ")
        bar.addWidget(self.time_label)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)

    # ---- tonic sol-fa
    def key_for_solfa(self):
        """(tonic pitch class as displayed, minor?, text such as 'Eb major')."""
        names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        chosen = self.key.currentText()
        if chosen not in ("auto", "", None):
            try:
                from music21 import key as _key
                k = _key.Key(chosen)
                return k.tonic.pitchClass, k.mode == "minor", f"{k.tonic.name.replace('-', 'b')} {k.mode}"
            except Exception:
                pass
        tonic, name = self.src_key or (0, "C major")
        tonic = (tonic + self.transpose.value()) % 12
        minor = "minor" in str(name)
        return tonic, minor, f"{names[tonic]} {'minor' if minor else 'major'}"

    # ---- words (lyrics)
    def lyrics_path(self):
        return (self.path + ".lyrics.json") if getattr(self, "path", None) else None

    def save_lyrics(self):
        target = self.lyrics_path()
        if not target:
            return
        try:
            if self.lyrics:
                with open(target, "w", encoding="utf-8") as handle:
                    json.dump(self.lyrics, handle, ensure_ascii=False, indent=1)
            elif os.path.isfile(target):
                os.remove(target)
        except OSError:
            pass

    def load_lyrics(self):
        self.lyrics = {}
        target = self.lyrics_path()
        try:
            if target and os.path.isfile(target):
                with open(target, encoding="utf-8") as handle:
                    self.lyrics = {str(k): list(v) for k, v in json.load(handle).items()}
        except (OSError, ValueError):
            pass

    def open_lyrics(self):
        if not self.notes:
            self.statusBar().showMessage("Open a MIDI file first.")
            return
        LyricsDialog(self).exec()

    def open_solfa(self):
        if not self.qnotes:
            self.statusBar().showMessage("Open a MIDI file first.")
            return
        SolfaDialog(self).exec()

    def apply_theme(self, palette, css):
        chrome.apply_theme(self, palette, css)

    def toggle_play(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QSpinBox, QDoubleSpinBox)) or (isinstance(focus, QComboBox) and focus.isEditable()):
            return
        if self.pos_hook and self.pos_hook() is not None:
            self.pause_on_organ()
        else:
            self.play_on_organ()

    def _file_total_sec(self):
        total = max((n.end for n in self.notes), default=0.0)
        return self.barmap.sec_to_beat(total) * 60.0 / max(1.0, self.barmap.average_bpm()) if total else 0.0

    def _fraction_to_file_sec(self, value):
        return value / 1000.0 * self._file_total_sec()

    def seek_fraction(self, value):
        """Timeline clicked / released: play from that point (or jump there while playing)."""
        t = self._fraction_to_file_sec(value)
        if self.pos_hook and self.pos_hook() is not None and self.seek_hook:
            self.seek_hook(t)
        else:
            self.play_on_organ(offset=t)

    def go_to_bar(self):
        """Move to a bar: shows it in the score (blue), and playback continues from its start."""
        bar = self.goto_bar.value() - 1
        if not self.notes or not 0 <= bar < self.barmap.bar_count:
            return
        self.select_bar(bar)
        t = float(self.barmap.cumulative()[bar]) * 60.0 / max(1.0, self.barmap.average_bpm())
        if self.pos_hook and self.pos_hook() is not None and self.seek_hook:
            self.seek_hook(t)

    def _update_timeline(self, t_file, dragging=False):
        total = max((n.end for n in self.notes), default=0.0)
        beat_total = self.barmap.sec_to_beat(total) * 60.0 / max(1.0, self.barmap.average_bpm()) if total else 0.0
        t = t_file or 0.0
        if beat_total > 0 and not self.time_slider.dragging:
            self.time_slider.setValue(int(min(1.0, t / beat_total) * 1000))
        fmt = lambda x: f"{int(x) // 60}:{int(x) % 60:02d}"
        bar = int(self.barmap.bar_of_beat(t * self.barmap.average_bpm() / 60.0)) + 1 if self.notes else 0
        self.goto_bar.setMaximum(max(1, self.barmap.bar_count if self.notes else 1))
        if t_file is not None and not self.goto_bar.hasFocus():
            self.goto_bar.blockSignals(True)
            self.goto_bar.setValue(max(1, bar))
            self.goto_bar.blockSignals(False)
        self.time_label.setText(f" {fmt(t)} / {fmt(beat_total)}  bar {bar}/{self.barmap.bar_count if self.notes else 0} ")

    # ---- playback indicator (fed by the bridge while a file plays)
    def poll_playhead(self):
        t_file = self.pos_hook() if self.pos_hook else None
        self._update_timeline(t_file)
        if t_file is None:
            if self.roll.play_time is not None and time.time() > self.step_until:
                self.roll.set_playhead(None)
                self.highlight_bar(None)
            return
        beat = t_file * self.barmap.average_bpm() / 60.0          # the preview is written at the average tempo
        sec = self.barmap.beat_to_sec(beat)
        self.roll.set_playhead(sec)
        bar = min(self.barmap.bar_count - 1, max(0, int(self.barmap.bar_of_beat(beat))))
        self.highlight_bar(bar)
        if bar != getattr(self, "_followed", None):                 # the score follows the music
            self._followed = bar
            self.scroll_to_bar(bar)

    def bar_y(self, bar):
        """(page index, y in that page widget's pixels) of a bar in the engraved score, from where its note heads sit."""
        if not self.hits or not self.page_dims:
            return None
        cum = self.barmap.cumulative()
        for reach in range(0, self.barmap.bar_count):
            for b in {bar - reach, bar + reach}:
                if not 0 <= b < self.barmap.bar_count:
                    continue
                lo, hi = float(cum[b]) - 0.01, float(cum[b + 1]) - 0.01
                for page, hits in enumerate(self.hits):
                    ys = [h[1] for h in hits if lo <= h[3] < hi]
                    if ys and page < len(self.page_widgets):
                        vh = self.page_dims[page][1]
                        return page, min(ys) / vh * self.page_widgets[page].height()
        return None

    def scroll_to_bar(self, bar, always=False):
        """Scroll the engraved score (down the page, on to the next page) so this bar stays in view."""
        where = self.bar_y(bar)
        if where is None:
            return
        page, y = where
        y += self.page_widgets[page].y()
        sb = self.preview.verticalScrollBar()
        view = self.preview.viewport().height()
        if always or not (sb.value() + view * 0.08 < y < sb.value() + view * 0.62):
            sb.setValue(int(max(0, y - view * 0.25)))

    def highlight_bar(self, bar, colour="#e02020"):
        """Colour the current bar in the engraved score (red = playing, blue = selected; only changed pages reload)."""
        if (bar, colour) == (self.hl_bar, getattr(self, "hl_col", None)) or not self.pages or len(self.page_widgets) != len(self.pages):
            return
        old, self.hl_bar, self.hl_col = self.hl_bar, bar, colour
        counts = [svg.count('class="measure"') for svg in self.pages]
        def locate(b):
            if b is None:
                return None
            for pi, c in enumerate(counts):
                if b < c:
                    return pi, b
                b -= c
            return None
        for loc in {locate(old), locate(bar)} - {None}:
            page = loc[0]
            svg = self.pages[page]
            if locate(bar) is not None and locate(bar)[0] == page:
                svg = render.highlight_measure(svg, locate(bar)[1], colour)
            self.page_widgets[page].load(QByteArray(svg.encode("utf-8")))

    def save_edited_midi(self):
        """Write the (edited) notes as played - real timing, original tracks' channels - to a new MIDI file."""
        if not self.notes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save edited MIDI", self._suggest(" (edited).mid"), "MIDI (*.mid)")
        if not path:
            return
        import mido
        events = []
        for n in self.notes:
            events.append((int(round(n.start * 960)), 1, n.pitch, n.vel, n.ch))
            events.append((int(round(n.end * 960)), 0, n.pitch, 0, n.ch))
        events.sort(key=lambda e: (e[0], e[1]))
        track = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000, time=0)])
        for text_beat, text in self.setter_markers():
            events.append((int(round(self.barmap.beat_to_sec(text_beat) * 960)), -1, 0, 0, text))
        events.sort(key=lambda e: (e[0], e[1]))
        prev = 0
        for tick, kind, pitch, vel, ch in events:
            if kind == -1:
                track.append(mido.MetaMessage("marker", text=ch, time=tick - prev))
            else:
                track.append(mido.Message("note_on" if kind else "note_off", channel=ch, note=pitch, velocity=vel, time=tick - prev))
            prev = tick
        mid = mido.MidiFile(type=0, ticks_per_beat=480)
        mid.tracks.append(track)
        mid.save(path)
        self.statusBar().showMessage(f"Saved {path}")

    def refresh_roll(self, keep_view=False):
        bar = self.roll.horizontalScrollBar()
        value = bar.value()
        ghosts = []
        for q in (self.qnotes if self.roll.show_ghosts else []):
            ghosts.append((self.barmap.beat_to_sec(float(q.start)), self.barmap.beat_to_sec(float(q.end)), q.pitch))
        self.roll.populate(self.notes, self.barmap, ghosts, self.selected_bar, self.sel_notes)
        if self.roll_window is not None:
            self.keys.update()
            self.velocity_lane.update()
        if keep_view:
            bar.setValue(value)

    def params(self):
        kind = KINDS[self.layout_kind.currentIndex()]
        return {
            "kind": kind, "split": self.split.value(), "split2": self.split2.value(), "split3": self.split3.value(),
            "pedal": self.pedal.value(), "grid": core.GRID_CHOICES[self.grid.currentText()],
            "triplets": self.triplets.isChecked(), "legato": Fraction(self.legato.value()).limit_denominator(8),
            "chord": self.chord.value() / 1000.0, "key": self.key.currentText(), "dynamics": self.dynamics.isChecked(),
            "dyn_bias": self.dyn_bias.value(), "title": self.title.text(), "composer": self.composer.text(),
            "page": self.page.currentText(), "scale": self.scale.value(),
            "bar_grid": dict(self.bar_grid), "meter": self.meter.currentText(),
            "transpose": self.transpose.value(), "names": [s.strip() for s in self.stave_names.text().split(",")],
            "slurs": self.slurs.isChecked(), "staccato": self.staccato.isChecked(),
            "final_bar": self.final_bar.isChecked(), "probe": self.need_probe,
            "setters": {x["bar"]: self.setter_label(x) for x in self.setters},
            "hidden": sorted(self.hidden_tracks), "hold": self.hold.value(), "signs": self.sign_params(), "lyrics": dict(getattr(self, "lyrics", {})),
            "spacing": {"spacingStaff": self.sp_staff.value(), "spacingBraceGroup": self.sp_group.value(), "spacingBracketGroup": self.sp_group.value(),
                    "spacingSystem": self.sp_system.value(), "spacingLinear": self.sp_note.value()},
            "adv": {"max_voices": self.adv_nvoices.value(), "divisions": dict(self.divisions), "arranger": self.arranger.text(), "voices": self.adv_voices.isChecked(), "tidy_rests": self.adv_tidy.isChecked(), "multirest": self.adv_multirest_n.value() if self.adv_multirest.isChecked() else 0,
                    "clef_switch": self.adv_clef.isChecked(), "rehearsal": self.adv_rehearsal.isChecked()},
        }

    def changed(self, *_, delay=250):
        if not self.notes:
            return
        self.timer.start(delay if isinstance(delay, int) else 250)

    def rebuild(self):
        if not self.notes:
            return
        self.generation += 1
        self.statusBar().showMessage("Quantising...")
        if self.job_running:
            self.job_dirty = True                          # one engraving at a time; the newest request runs next
            return
        self.start_job()

    def start_job(self):
        generation = self.generation
        self.job_dirty = False
        params = self.params()
        barmap = core.BarMap(list(self.barmap.anchors), list(self.barmap.beats))
        notes = list(self.notes)
        self.job_running = True
        names = self.info.get("voice_names")
        if self.pool is not False:
            try:
                if self.pool is None:
                    import concurrent.futures, multiprocessing
                    self.pool = concurrent.futures.ProcessPoolExecutor(max_workers=1,
                                                                       mp_context=multiprocessing.get_context("spawn"))
                import engrave_job
                future = self.pool.submit(engrave_job.run, params, notes, list(barmap.anchors), list(barmap.beats), names,
                                          PAGE_SIZES[params["page"]][:2])
                future.add_done_callback(lambda f, g=generation: self._job_done(g, f))
                return
            except Exception as exc:                       # no process pool here: fall back to a thread
                print("Engraving in a separate process failed, using a thread:", exc)
                self.pool = False
        threading.Thread(target=self._work, args=(generation, params, notes, barmap), daemon=True).start()

    def _job_done(self, generation, future):
        try:
            result = future.result()
        except Exception as exc:                           # the child died: switch to threads for the rest of the session
            self.pool = False
            result = {"error": f"engraving process failed ({exc})", "trace": ""}
        self.result_ready.emit(generation, result)

    def _work(self, generation, p, notes, barmap):
        with self.lock:
            try:
                q = core.quantise(notes, barmap, p["grid"], p["triplets"], p["chord"], legato_gap=p["legato"],
                                  bar_grid=p["bar_grid"])
                core.STAVE_HOLD = float(p.get("hold", 0.0))
                hidden = {tuple(h) for h in p.get("hidden", [])}
                if hidden:
                    q = [x for x in q if (x.track, x.ch) not in hidden]
                    notes = [n for n in notes if (n.track, n.ch) not in hidden]
                src_key = None
                if p["probe"]:
                    k = render.detect_key(q)
                    src_key = (k.tonic.pitchClass, f"{k.tonic.name.replace('-', 'b')} {k.mode}")
                staves = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], notes,
                                          self.info.get("voice_names"))
                label = p["meter"] if p["meter"] in ("6/8", "12/8", "3/8", "2/2") else None
                score = render.build_score(q, barmap, staves, p["key"], p["title"], p["composer"], p["dynamics"],
                                           p["dyn_bias"], p["legato"], barmap.average_bpm(),
                                           {0: label} if label else None, p["transpose"], p["names"], p["slurs"],
                                           p["staccato"], p["final_bar"], p["setters"], p.get("signs"), p.get("adv"), p.get("lyrics"))
                xml = render.musicxml(score)
                width, height, _ = PAGE_SIZES[p["page"]]
                pages = render.svg_pages(xml, width, height, p["scale"], spacing=p.get("spacing"))
                hits, dims, spaces = render.collect_hits(120.0)
                result = {"q": q, "xml": xml, "pages": pages, "p": p, "src_key": src_key, "hits": hits, "dims": dims,
                          "spaces": spaces}
            except Exception as exc:
                import traceback
                result = {"error": f"{exc}", "trace": traceback.format_exc()}
        self.result_ready.emit(generation, result)

    def _on_result(self, generation, result):
        self.job_running = False
        if self.job_dirty:
            self.start_job()                               # edits arrived while engraving: go again with the newest state
        if generation != self.generation:
            return
        if "error" in result:
            self.statusBar().showMessage("Could not engrave: " + result["error"])
            print(result["trace"])
            return
        self.qnotes, self.xml, self.pages = result["q"], result["xml"], result["pages"]
        self.hits, self.page_dims = result.get("hits", []), result.get("dims", [])
        self.spaces = result.get("spaces", [])
        self.hit_params = result["p"]
        if result.get("src_key"):
            self.src_key = result["src_key"]
            self.need_probe = False
            self.src_key_label.setText(f"Detected key: {self.src_key[1]}")
        self.page_ratio = PAGE_SIZES[result["p"]["page"]][1] / PAGE_SIZES[result["p"]["page"]][0]
        self.refresh_roll(keep_view=True)
        self.show_pages()
        if self.selected_bar is not None and self.selected_bar < self.barmap.bar_count:
            self.hl_bar = None
            self.highlight_bar(self.selected_bar, "#2a6df0")           # the selected bar stays marked after a redraw
        if getattr(self, "_to_top", False):                   # a newly loaded file starts at the top of its score
            self._to_top = False
            QTimer.singleShot(0, lambda: self.preview.verticalScrollBar().setValue(0))
        self.statusBar().showMessage(f"{self.barmap.bar_count} bars, {len(self.pages)} page(s), "
                                     f"{self.barmap.average_bpm():.0f} BPM average")
        try:                                                   # playing: carry on from the same place with the updated score
            now = self.pos_hook() if self.pos_hook else None
            if now is not None and not self.job_dirty and not getattr(self, "_to_top", False):
                self.play_on_organ(offset=float(now))
        except Exception:
            pass

    def show_pages(self):
        scroll = self.preview.verticalScrollBar().value()
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        width = max(400, self.preview.viewport().width() - 40)
        widgets = []
        for svg in self.pages:
            widget = ScorePage(self, len(widgets))
            widget.setCursor(self.roll.viewport().cursor())
            widget.load(QByteArray(svg.encode("utf-8")))
            widget.setFixedSize(width, int(width * self.page_ratio))
            widget.setStyleSheet("background: white;")
            self.preview_layout.addWidget(widget)
            widgets.append(widget)
        self.page_widgets, self.hl_bar = widgets, None
        try:
            self.stave_bands = [render.staff_bands(svg) for svg in self.pages]
        except Exception:
            self.stave_bands = []
        self.mark_score()
        self.preview.verticalScrollBar().setValue(scroll)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pages:
            QTimer.singleShot(150, self.show_pages)

    # ---- export
    def _suggest(self, extension):
        folder = SHEET_FOLDER if os.path.isdir(SHEET_FOLDER) else os.path.expanduser("~")
        return os.path.join(folder, (self.title.text() or "score") + extension)

    def export_pdf(self):
        if not self.pages:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", self._suggest(".pdf"), "PDF (*.pdf)")
        if path:
            self.write_pdf(path)

    def write_pdf(self, path):
        _, _, size_id = PAGE_SIZES[self.page.currentText()]
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(size_id))
        writer.setResolution(300)
        writer.setTitle(self.title.text())
        painter = QPainter(writer)
        for i, svg in enumerate(self.pages):
            if i:
                writer.newPage()
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            area = writer.pageLayout().paintRectPixels(writer.resolution())
            renderer.render(painter, QRectF(0, 0, area.width(), area.height()))
        painter.end()
        self.statusBar().showMessage(f"Saved {path}")

    def export_xml(self):
        if not self.xml:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export MusicXML", self._suggest(".musicxml"), "MusicXML (*.musicxml *.xml)")
        if path:
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(self.xml)
            self.statusBar().showMessage(f"Saved {path}")

    def export_midi(self):
        if not self.notes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export straightened MIDI", self._suggest(" (straight).mid"), "MIDI (*.mid)")
        if not path:
            return
        box = QMessageBox(self)
        box.setText("Write the notes exactly on the quantised grid, or keep your own feel inside the straightened bars?")
        grid_btn = box.addButton("On the grid", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Keep my feel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        core.export_fixed_midi(self.notes, self.barmap, path, quantised=self.qnotes if box.clickedButton() is grid_btn else None,
                               staves=self.staves_for_export(), markers=self.setter_markers() + self.voice_markers())
        self.statusBar().showMessage(f"Saved {path}")

    def closeEvent(self, event):
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        self.settings.setValue("splitters", self.splitter.saveState())
        self.settings.setValue("body", self.body.saveState())
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    render.init_verovio()
    window = Stave()
    window.show()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.load(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
