"""Floating always-on-top LCD panel (vintage Casio / Yamaha style): the KeyLab LCD text, the active setter and its drawn
stops as a tick list per division. Drag it anywhere, right-click for options; it remembers its place.

CHANGELOG
2026-11-09  New (first version, to be shaped by use): LCD lines, setter name / step / cued state, drawn stops by division.
"""
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QMenu, QSizeGrip, QWidget

AMBER, DIM, BACK, BEZEL = QColor("#ffb84d"), QColor("#7a5a22"), QColor("#16130c"), QColor("#2a2a2e")


class LcdFloat(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowTitle("LCD")
        self.settings = QSettings("KeyLabGrandOrgue", "LcdFloat")
        self.lcd = ("", "")
        self.setter, self.position, self.cued, self.bank = "", "", False, ""
        self.divisions = {}                          # division -> [stop names] drawn
        self.compact = self.settings.value("compact", "false") == "true"
        self.size_pt = int(self.settings.value("font", 15))
        self._drag = None
        self.grip = QSizeGrip(self)
        self.setMinimumSize(300, 90)
        self.resize(460, 330)
        pos = self.settings.value("pos")
        if isinstance(pos, QPoint):
            self.move(pos)
        self.setWindowOpacity(float(self.settings.value("opacity", 0.95)))

    # ---- data
    def update_state(self, snap):
        lcd = tuple(snap.get("lcd", ("", "")))
        names = snap.get("combinations", [])
        index = snap.get("active_combination_index")
        cued = snap.get("combination_index")
        loaded = names[index]["name"] if isinstance(index, int) and 0 <= index < len(names) else ""
        cue = names[cued]["name"] if isinstance(cued, int) and 0 <= cued < len(names) and cued != index else ""
        divisions = {}
        for division, name in snap.get("active_stop_items", []):
            divisions.setdefault(division, []).append(name)
        state = (lcd, loaded, cue, snap.get("internal_position", ""), divisions)
        if state == getattr(self, "_state", None):
            return
        self._state = state
        self.lcd, self.setter, self.cued, self.position, self.divisions = lcd, loaded, cue, snap.get("internal_position", ""), divisions
        self.update()

    # ---- drawing
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), BEZEL)
        screen = self.rect().adjusted(8, 8, -8, -8)
        p.fillRect(screen, BACK)
        p.setPen(QPen(DIM, 1))
        p.drawRect(screen)
        mono = QFont("Consolas", self.size_pt)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setBold(True)
        p.setFont(mono)
        x, y = screen.left() + 12, screen.top() + 8
        line_h = p.fontMetrics().height() + 2
        for line in self.lcd[:2]:
            p.setPen(QPen(AMBER)); p.drawText(x, y, screen.width() - 24, line_h, Qt.AlignmentFlag.AlignLeft, str(line)[:16].ljust(16))
            y += line_h
        if self.compact:
            return
        small = QFont("Consolas", max(8, self.size_pt - 5))
        p.setFont(small)
        y += 4
        p.setPen(QPen(DIM, 1)); p.drawLine(x, y, screen.right() - 12, y); y += 4
        head = f"{self.setter or '-'}" + (f"   step {self.position}" if self.position else "")
        p.setPen(QPen(AMBER)); p.drawText(x, y, screen.width() - 24, line_h, Qt.AlignmentFlag.AlignLeft, head); y += line_h
        if self.cued:
            p.setPen(QPen(QColor("#ffe0a0"))); p.drawText(x, y, screen.width() - 24, line_h, Qt.AlignmentFlag.AlignLeft, f"cued: {self.cued}"); y += line_h
        y += 2
        if not self.divisions:
            p.setPen(QPen(DIM)); p.drawText(x, y, "no stops drawn")
            return
        cols = len(self.divisions)
        col_w = max(80, (screen.width() - 24) // max(1, cols))
        for i, (division, stops) in enumerate(self.divisions.items()):
            cx, cy = x + i * col_w, y
            p.setPen(QPen(DIM)); p.drawText(cx, cy, col_w, line_h, Qt.AlignmentFlag.AlignLeft, division.upper()[:12]); cy += line_h
            p.setPen(QPen(AMBER))
            for name in stops:
                if cy + line_h > screen.bottom():
                    p.drawText(cx, cy, col_w, line_h, Qt.AlignmentFlag.AlignLeft, "..."); break
                p.drawText(cx, cy, col_w, line_h, Qt.AlignmentFlag.AlignLeft, "☑ " + name[:14]); cy += line_h

    def resizeEvent(self, event):
        self.grip.move(self.width() - 16, self.height() - 16)
        super().resizeEvent(event)

    # ---- moving / options
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _event):
        self._drag = None
        self.settings.setValue("pos", self.pos())

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        compact = menu.addAction("LCD only (compact)")
        compact.setCheckable(True); compact.setChecked(self.compact)
        compact.triggered.connect(self._set_compact)
        sizes = menu.addMenu("Text size")
        for pt in (12, 15, 18, 22, 28):
            a = sizes.addAction(f"{pt} pt"); a.triggered.connect(lambda _=False, v=pt: self._set_size(v))
        ops = menu.addMenu("Opacity")
        for pct in (100, 90, 75, 55):
            a = ops.addAction(f"{pct} %"); a.triggered.connect(lambda _=False, v=pct: self._set_opacity(v / 100))
        menu.addSeparator()
        menu.addAction("Hide").triggered.connect(self.hide)
        menu.exec(event.globalPos())

    def _set_compact(self, on):
        self.compact = on
        self.settings.setValue("compact", "true" if on else "false")
        self.resize(self.width(), 120 + 2 * self.size_pt if on else 330)
        self.update()

    def _set_size(self, pt):
        self.size_pt = pt
        self.settings.setValue("font", pt)
        self.update()

    def _set_opacity(self, value):
        self.setWindowOpacity(value)
        self.settings.setValue("opacity", value)

    def hideEvent(self, event):
        self.settings.setValue("pos", self.pos())
        super().hideEvent(event)
