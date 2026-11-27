"""Piano roll widgets of the Stave editor (note items, keys, velocity lane, roll view).

Split out of midi_stave.py without behaviour change (imported by bare name like core / render; midi_stave.py re-imports every name).

CHANGELOG
2026-11-27  Moved verbatim from midi_stave.py (v3.0.0 modularisation, patch 10).
"""

from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QWidget,
)
from PySide6.QtCore import (
    QRect,
    QRectF,
    QSize,
    QTimer,
    Qt,
    Signal,
)
from score_widgets import BarLine


ROW = 6                                    # piano-roll pixel height of one semitone


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

    dim = False                                    # set for notes of tracks other than the active one

    def style(self, selected, sounding):
        self.setOpacity(0.35 if getattr(self.note, "mute", False) else (0.4 if self.dim and not selected else 1.0))
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
        self.stave.audition_on(self.down)               # sounds for as long as the button is held
        self.update()

    def mouseMoveEvent(self, event):
        if self.down is not None:
            pitch = self.pitch_at(int(event.position().y()))
            if pitch != self.down:
                self.down = pitch
                self.stave.audition_on(pitch)
                self.update()

    def mouseReleaseEvent(self, event):
        self.down = None
        self.stave.audition_off()
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
        self.colour_by_track, self.dim_inactive = True, True       # roll: colour each track differently, fade the tracks that are not active
        self.band = None                      # rubber-band selection: [origin point, QRubberBand, add-to-selection]
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
        lo, hi = 0, 127                                              # the whole keyboard, so the vertical scroll always has somewhere to go
        self.top = hi
        view = self.viewport()
        height = max(120, (hi - lo + 1) * ROW, view.height())        # grid and rows fill the whole window, not just the notes
        end = max(n.end for n in notes) + 2.0
        end = max(end, barmap.anchors[-1] + 1.0)
        width = max(end * self.pps, float(view.width()))
        scene.setSceneRect(QRectF(0, 0, width, height))
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
            row = scene.addRect(0, (hi - pc) * ROW, width, ROW, QPen(Qt.PenStyle.NoPen), QBrush(shade))
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
        owner = self.window_ref
        hidden = getattr(owner, "hidden_tracks", set())
        active = getattr(owner, "active_voice", None)
        palette = owner.voice_colours() if hasattr(owner, "voice_colours") else {}
        for n in notes:
            key = (n.track, n.ch)
            if key in hidden:                                          # tracks unticked in the Tracks list are not drawn
                continue
            v = n.vel / 127.0
            if self.colour_by_track and key in palette:
                base = palette[key]
                colour = QColor.fromHsv(base.hue(), base.saturation(), int(150 + 105 * v))
            else:
                colour = QColor(int(60 + 190 * v), int(190 - 60 * v), 200 - int(120 * v))
            r = NoteItem(n, n.start * self.pps, (hi - n.pitch) * ROW + 1, max(2.0, (n.end - n.start) * self.pps),
                         ROW - 2, colour)
            r.dim = bool(self.dim_inactive and active is not None and key != active and len(palette) > 1)
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
        self._aud_line = None
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
    def show_audition(self, t):
        """The audition line (None hides it); redrawn after the roll is rebuilt."""
        self.audition_t = t
        item = getattr(self, "_aud_line", None)
        if item is not None and item.scene() is not self.scene():
            item = None
        if t is None:
            if item is not None:
                item.setVisible(False)
            return
        if item is None:
            item = self.scene().addLine(0, 0, 0, max(120, self.scene().sceneRect().height()), QPen(QColor(120, 220, 255), 2))
            item.setZValue(40)
            self._aud_line = item
        item.setVisible(True)
        item.setPos(t * self.pps, 0)

    def _scrub_event(self, event):
        self.window_ref.scrub_to(max(0.0, self.mapToScene(event.pos()).x() / self.pps))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and getattr(self.window_ref, "audition_mode", False):
            self.scrubbing = True
            self._scrub_event(event)
            return
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
                self.window_ref.add_note_at(pos.x() / self.pps, self.top - int(pos.y() // ROW), bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
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
                shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                if not shift:
                    self.window_ref.select_note(None, False)
                if self.window_ref.tool == "select":                  # drag on empty space: rubber-band select (Shift adds)
                    from PySide6.QtWidgets import QRubberBand
                    box = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
                    box.setGeometry(QRect(event.pos(), QSize()))
                    box.show()
                    self.band = [event.pos(), box, shift]
                    return
        super().mousePressEvent(event)

    def _snapped_dx(self, edge_sec, dx, event):
        """Horizontal drag distance (scene px) after snapping the dragged edge / note start to the snap step; Alt = free."""
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            return dx
        target = self.window_ref.snap_sec(edge_sec + dx / self.pps)
        return (target - edge_sec) * self.pps

    def _edge(self, item, pos):
        """'L' / 'R' when the pointer is on the left / right end of a note bar (the grab zone shrinks on very short notes)."""
        r = item.rect()
        zone = max(2.0, min(7.0, r.width() / 3.0))
        if abs(pos.x() - r.left()) <= zone:
            return "L"
        if abs(pos.x() - r.right()) <= zone:
            return "R"
        return None

    def _band_finish(self, event):
        origin, box, add = self.band
        self.band = None
        rect = QRect(origin, event.pos()).normalized()
        box.hide()
        box.deleteLater()
        if rect.width() < 4 and rect.height() < 4:
            return
        area = self.mapToScene(rect).boundingRect()
        hit = {id(it.note) for it in self.note_items if it.sceneBoundingRect().intersects(area)}
        chosen = (set(self.window_ref.sel_notes) | hit) if add else hit
        self.window_ref.sel_notes = chosen
        self.apply_selection(chosen)
        self.window_ref.mark_score()
        self.window_ref.statusBar().showMessage(f"{len(chosen)} notes selected", 3000)

    def mouseMoveEvent(self, event):
        if getattr(self, "scrubbing", False):
            self._scrub_event(event)
            return
        if self.band is not None:
            origin, box, _add = self.band
            box.setGeometry(QRect(origin, event.pos()).normalized())
            edge = 24                                                   # drag to the edge of the window to scroll on
            if event.pos().x() > self.viewport().width() - edge:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 12)
            elif event.pos().x() < edge:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 12)
            if event.pos().y() > self.viewport().height() - edge:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 12)
            elif event.pos().y() < edge:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 12)
            return
        st = getattr(self, "stretch", None)
        if st is not None:
            dx = self.mapToScene(event.pos()).x() - st["origin"].x()
            if abs(dx) > 1 or st["moved"]:
                st["moved"] = True
                dx = self._snapped_dx(st["note"].end if st["side"] == "R" else st["note"].start, dx, event)
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
                dx = self._snapped_dx(note.start, dx, event)
                dp = -round(dy / ROW)
                for it in self.note_items:
                    if id(it.note) in self.sel_notes:
                        it.setPos(dx, -dp * ROW)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "scrubbing", False):
            self.scrubbing = False
            self.window_ref.scrub_end()
            return
        if self.band is not None:
            self._band_finish(event)
            return
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
            self.window_ref.add_note_at(pos.x() / self.pps, self.top - int(pos.y() // ROW), bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
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
        delta = event.angleDelta().y() or event.angleDelta().x()           # Qt swaps the axis when Alt / Shift is held: take whichever carries the turn
        if not delta:
            return
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:          # Alt + wheel: taller / shorter keys (both directions)
            roll_window = getattr(self.window_ref, "roll_window", None)
            if roll_window is not None:
                roll_window.zoom_keys(1 if delta > 0 else -1)
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.pps = max(8.0, min(600.0, self.pps * factor))
            self.window_ref.refresh_roll(keep_view=True)
        elif event.modifiers() & Qt.KeyboardModifier.ShiftModifier:        # Shift + wheel: sideways
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
        else:                                                                # wheel: up / down the keyboard
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() - delta // 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene() is not None and self.scene().items():             # redraw so the grid keeps filling the window
            if getattr(self, "_fill_timer", None) is None:
                self._fill_timer = QTimer(self)
                self._fill_timer.setSingleShot(True)
                self._fill_timer.timeout.connect(lambda: self.window_ref.refresh_roll(keep_view=True))
            self._fill_timer.start(150)

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
