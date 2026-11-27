"""Score page and bar line widgets of the Stave editor.

Split out of midi_stave.py without behaviour change (imported by bare name like core / render; midi_stave.py re-imports every name).

CHANGELOG
2026-11-28  Changelog labels of the module split now use the v2.0.9 patch numbers (comments only, no code change).
2026-11-27  Moved verbatim from midi_stave.py (modularisation, v2.0.9-69).
"""

from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsRectItem,
)
from PySide6.QtCore import (
    QPointF,
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtSvgWidgets import (
    QSvgWidget,
)


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
