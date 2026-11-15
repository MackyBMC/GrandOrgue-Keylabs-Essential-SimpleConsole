"""Small piano-roll picture of the MIDI file that is loaded (a take just recorded, a file just opened).

Time across, pitch up, one colour per MIDI channel. Double-click opens the file in the full Piano Roll tab.

CHANGELOG
2026-11-15  New.
"""
import os
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

Note = Tuple[float, float, int, int]                    # start s, end s, pitch, channel
COLOURS = ["#4da3ff", "#ffb24d", "#6bd48a", "#e06c9f", "#b58cf0", "#e0d45c", "#5cd6d6", "#ff7a59"]


def read_notes(path: str) -> Tuple[List[Note], float]:
    """(notes, length in seconds) of a MIDI file; ([], 0) when it cannot be read."""
    try:
        import mido
        now, open_at, notes = 0.0, {}, []
        for msg in mido.MidiFile(path):
            now += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                open_at.setdefault((msg.channel, msg.note), now)
            elif msg.type in ("note_off", "note_on") and (msg.channel, msg.note) in open_at:
                notes.append((open_at.pop((msg.channel, msg.note)), now, msg.note, msg.channel))
        for (ch, pitch), start in open_at.items():
            notes.append((start, now, pitch, ch))
        return notes, now
    except Exception:
        return [], 0.0


class TakePreview(QWidget):
    def __init__(self, on_open: Optional[Callable[[], None]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.on_open = on_open
        self.notes: List[Note] = []
        self.length = 0.0
        self.key = ("", 0.0)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("The loaded MIDI file. Double-click to open it in the Piano Roll.")

    def show_file(self, path: str) -> None:
        """Reads the file again only when the path or its modification time changed."""
        try:
            stamp = os.path.getmtime(path) if path else 0.0
        except OSError:
            stamp = 0.0
        if (path, stamp) == self.key:
            return
        self.key = (path, stamp)
        self.notes, self.length = read_notes(path) if path and stamp else ([], 0.0)
        self.setVisible(bool(self.notes))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().base())
        if self.notes and self.length > 0:
            lo, hi = min(n[2] for n in self.notes), max(n[2] for n in self.notes)
            span = max(12, hi - lo + 1)
            w, h = self.width() - 4, self.height() - 4
            row = max(1.0, h / span)
            for start, end, pitch, ch in self.notes:
                x = 2 + start / self.length * w
                p.fillRect(int(x), int(2 + (hi - pitch) / span * (h - row)), max(1, int((end - start) / self.length * w)), max(1, int(row)),
                           QColor(COLOURS[ch % len(COLOURS)]))
        p.setPen(QPen(self.palette().mid().color()))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.on_open is not None:
            self.on_open()
        event.accept()
