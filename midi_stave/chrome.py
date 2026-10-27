"""Window chrome of the stave editor, CAD / Photoshop style.

Left: a slim tool strip of icons (open, save, undo / redo, tools: select, add note, erase, toe, heel, step, play, stop).
Right: a "Properties" panel that shows the selected note(s) - pitch, start, length, velocity, pedal mark, which manuals it
plays - above collapsible sections holding every other option (bars, quantise, staves, setters, notation, export).

CHANGELOG
2026-10-24  View > Icons (pack, look incl. high contrast, size 20-56 px, Ctrl +/-); qtawesome is installed automatically once if missing; painted icons never blank.
2026-10-24  Icons: four packs (Material, Phosphor, Remix, Font Awesome) x three looks (colour badges, coloured glyphs, mono), View > Icon pack / Icon look.
2026-10-24  New: replaces the long column of option boxes on the left.
"""
import os
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDockWidget, QMainWindow, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def pitch_name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def ensure_qtawesome():
    """The icon library: import it, or install it once into the running Python (pip install qtawesome)."""
    try:
        import qtawesome  # noqa: F401
        return True
    except Exception:
        pass
    if QSettings("KeyLabGrandOrgue", "MidiStave").value("qta_tried", False, type=bool):
        return False
    QSettings("KeyLabGrandOrgue", "MidiStave").setValue("qta_tried", True)
    try:
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "pip", "install", "qtawesome"], timeout=180, capture_output=True)
        import importlib
        importlib.invalidate_caches()
        import qtawesome  # noqa: F401
        return True
    except Exception:
        return False


QTA_OK = ensure_qtawesome()

_ORDER = ["open", "save", "pdf", "undo", "redo", "select", "add", "erase", "step_back", "step_fwd", "play", "stop",
          "solfa", "tracks", "panel_Recording", "panel_Bars", "panel_Quantise", "panel_Staves",
          "panel_MIDI tracks in this file", "panel_Organ setters", "panel_Notation", "panel_Advanced organ notation",
          "panel_Note editor", "panel_Export", "lyrics"]
_PACKS = {   # icon pack -> glyph names in _ORDER order (all via qtawesome: pip install qtawesome)
    "mdi6": "folder-open-outline content-save-outline file-pdf-box undo-variant redo-variant cursor-default-outline "
            "music-note-plus eraser skip-previous skip-next play stop music-clef-treble format-list-bulleted "
            "folder-music-outline timeline-outline grid music-box-multiple-outline format-list-bulleted tune-vertical "
            "music-note-eighth cog-outline pencil-ruler export-variant script-text-outline",
    "ph": "folder-open floppy-disk file-pdf arrow-counter-clockwise arrow-clockwise cursor plus-circle eraser skip-back "
          "skip-forward play stop music-notes list-bullets folder-simple timer grid-four stack list-bullets sliders "
          "music-note gear pencil-simple export text-aa",
    "ri": "folder-open-line save-line file-pdf-line arrow-go-back-line arrow-go-forward-line cursor-line add-circle-line "
          "eraser-line skip-back-line skip-forward-line play-line stop-line music-2-line list-unordered folder-music-line "
          "timer-line layout-grid-line stack-line list-unordered equalizer-line music-line settings-3-line edit-line "
          "share-box-line text",
    "fa5s": "folder-open save file-pdf undo redo mouse-pointer plus eraser step-backward step-forward play stop music list "
            "folder clock th layer-group list sliders-h music cog pencil-alt file-export font",
}
PACK_LABELS = {"mdi6": "Material Design", "ph": "Phosphor", "ri": "Remix", "fa5s": "Font Awesome"}
LOOK_LABELS = {"badge": "Colour badges", "contrast": "High contrast badges", "colour": "Coloured glyphs",
               "mono": "Monochrome (theme text colour)"}
SIZES = (20, 24, 28, 32, 40, 48, 56)
MDI = {k: v for k, v in zip(_ORDER, _PACKS["mdi6"].split())}              # kinds that have a library icon
# one colour per job: files amber, saving blue, PDF red, undo/redo violet, tools teal / green / pink, steps cyan ...
COLOURS = dict(zip(_ORDER, ["#f0a030", "#3b82f6", "#e5484d", "#8b7cf6", "#8b7cf6", "#14b8a6", "#30a46c", "#ec4899",
                            "#06b6d4", "#06b6d4", "#30a46c", "#e5484d", "#a855f7", "#64748b", "#f0a030", "#14b8a6",
                            "#3b82f6", "#a855f7", "#64748b", "#ec4899", "#06b6d4", "#78716c", "#30a46c", "#f97316", "#d946ef"]))
COLOURS.update({"toe": "#f97316", "heel": "#f97316"})
STYLE = {"pack": "mdi6", "look": "badge", "size": 32}


def _glyph_name(kind):
    names = _PACKS.get(STYLE["pack"], _PACKS["mdi6"]).split()
    return f"{STYLE['pack']}.{names[_ORDER.index(kind)]}" if kind in _ORDER else None


def _glyph_names(kind):
    if kind not in _ORDER:
        return []
    i = _ORDER.index(kind)
    out = []
    for pack in (STYLE["pack"], "mdi6", "fa5s"):
        names = _PACKS.get(pack, "").split()
        if i < len(names) and f"{pack}.{names[i]}" not in out:
            out.append(f"{pack}.{names[i]}")
    return out


def icon(kind, colour=None, size=30):
    """Tool icon from the chosen pack / look (View > Icons). Needs qtawesome (pip install qtawesome, MIT; the icon fonts are
    Apache-2.0 / MIT / OFL / CC-BY); without it the icons are drawn with the painter. colour = window text colour (mono look)."""
    colour = colour or QColor(205, 212, 220)
    tint = QColor(COLOURS.get(kind, "#64748b"))
    look = STYLE["look"]
    glyph_colour = colour if look == "mono" else (QColor("#ffffff") if look in ("badge", "contrast") else tint)
    px = 96
    base = None
    for name in _glyph_names(kind):                  # chosen pack first, then Font Awesome (present in every qtawesome)
        try:
            import qtawesome as qta
            base = qta.icon(name, color=glyph_colour.name()).pixmap(QSize(px, px))
            break
        except Exception:
            base = None
    if base is None:
        base = _painted_icon(kind, glyph_colour, px).pixmap(QSize(px, px))
    if look not in ("badge", "contrast"):
        return QIcon(base)
    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    from PySide6.QtGui import QLinearGradient
    deep = tint.darker(150 if look == "badge" else 210)             # dark enough for a white glyph to read clearly
    g = QLinearGradient(0, 0, 0, px)
    g.setColorAt(0, deep.lighter(115))
    g.setColorAt(1, deep.darker(115))
    p.setBrush(g)
    p.setPen(QPen(QColor("#ffffff"), 4) if look == "contrast" else Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(3, 3, px - 6, px - 6), 20, 20)
    inner = int(px * (0.66 if look == "contrast" else 0.62))
    p.drawPixmap((px - inner) // 2, (px - inner) // 2, base.scaled(inner, inner, Qt.AspectRatioMode.KeepAspectRatio,
                                                                   Qt.TransformationMode.SmoothTransformation))
    p.end()
    return QIcon(out)


def _painted_icon(kind, colour, size=30):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(colour, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size
    poly = lambda pts: QPolygonF([QPointF(x * s, y * s) for x, y in pts])
    if kind == "open":
        p.drawPolyline(poly([(.1, .8), (.1, .25), (.4, .25), (.5, .35), (.85, .35), (.85, .8), (.1, .8)]))
        p.drawPolyline(poly([(.1, .8), (.25, .5), (.95, .5), (.85, .8)]))
    elif kind == "save":
        p.drawRoundedRect(QRectF(.15 * s, .15 * s, .7 * s, .7 * s), 3, 3)
        p.drawRect(QRectF(.3 * s, .15 * s, .35 * s, .22 * s))
        p.drawRect(QRectF(.3 * s, .55 * s, .4 * s, .3 * s))
    elif kind in ("undo", "redo"):
        sign = -1 if kind == "undo" else 1
        cx = .5 * s
        p.drawArc(QRectF(.2 * s, .3 * s, .6 * s, .5 * s), (30 if sign < 0 else 150) * 16, (200 * -sign) * 16)
        tip = QPointF((.22 if sign < 0 else .78) * s, .45 * s)
        p.drawPolyline(QPolygonF([QPointF(tip.x() + sign * -.0, tip.y() - .17 * s), tip, QPointF(tip.x() + (.17 if sign < 0 else -.17) * s, tip.y() + .02 * s)]))
    elif kind == "select":
        p.setBrush(colour)
        p.drawPolygon(poly([(.25, .1), (.25, .8), (.42, .64), (.55, .9), (.65, .85), (.52, .6), (.76, .6)]))
    elif kind == "add":
        p.drawLine(QPointF(.5 * s, .2 * s), QPointF(.5 * s, .8 * s))
        p.drawLine(QPointF(.2 * s, .5 * s), QPointF(.8 * s, .5 * s))
    elif kind == "erase":
        p.drawLine(QPointF(.25 * s, .25 * s), QPointF(.75 * s, .75 * s))
        p.drawLine(QPointF(.75 * s, .25 * s), QPointF(.25 * s, .75 * s))
    elif kind in ("toe", "heel"):
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(s * .6))
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s * .85), Qt.AlignmentFlag.AlignCenter, "^" if kind == "toe" else "U")
        p.drawLine(QPointF(.2 * s, .88 * s), QPointF(.8 * s, .88 * s))
    elif kind == "step_back":
        p.setBrush(colour)
        p.drawPolygon(poly([(.75, .2), (.75, .8), (.3, .5)]))
        p.drawLine(QPointF(.2 * s, .2 * s), QPointF(.2 * s, .8 * s))
    elif kind == "step_fwd":
        p.setBrush(colour)
        p.drawPolygon(poly([(.25, .2), (.25, .8), (.7, .5)]))
        p.drawLine(QPointF(.8 * s, .2 * s), QPointF(.8 * s, .8 * s))
    elif kind == "play":
        p.setBrush(QColor(90, 200, 120))
        p.setPen(QPen(QColor(90, 200, 120), 1))
        p.drawPolygon(poly([(.3, .15), (.3, .85), (.85, .5)]))
    elif kind == "stop":
        p.setBrush(QColor(225, 90, 90))
        p.setPen(QPen(QColor(225, 90, 90), 1))
        p.drawRoundedRect(QRectF(.25 * s, .25 * s, .5 * s, .5 * s), 2, 2)
    elif kind == "pdf":
        p.drawPolyline(poly([(.2, .1), (.2, .9), (.8, .9), (.8, .3), (.6, .1), (.2, .1)]))
        p.drawPolyline(poly([(.6, .1), (.6, .3), (.8, .3)]))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(s * .24))
        p.setFont(f)
        p.drawText(QRectF(.2 * s, .45 * s, .6 * s, .35 * s), Qt.AlignmentFlag.AlignCenter, "PDF")
    elif kind == "solfa":
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(s * .3))
        p.setFont(f)
        p.drawText(QRectF(0, .05 * s, s, .45 * s), Qt.AlignmentFlag.AlignCenter, "d r m")
        p.drawText(QRectF(0, .5 * s, s, .45 * s), Qt.AlignmentFlag.AlignCenter, "f s l")
    elif kind.startswith("panel_"):                # panel icon without the icon library: its initial letter
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(s * .6))
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, kind[6:7].upper())
    else:                                          # any other kind: list lines
        for i in range(3):
            p.drawLine(QPointF(.2 * s, (.3 + i * .2) * s), QPointF(.8 * s, (.3 + i * .2) * s))
    p.end()
    return QIcon(pm)


class GeoMemory(QObject):
    """Standalone stave editor: remember every pop-up window's place and size (the bridge has its own, window_layout.json)."""
    SKIP = ("QMessageBox", "QFileDialog", "QColorDialog", "QInputDialog", "QFontDialog", "QProgressDialog")

    def __init__(self):
        super().__init__()
        self.settings = QSettings("KeyLabGrandOrgue", "MidiStave")
        self.done = set()

    def _key(self, w):
        title = w.windowTitle().split(" - ")[0].strip()
        return "geo/" + type(w).__name__ + (":" + title if isinstance(w, QDialog) and title else "")

    def eventFilter(self, obj, event):
        t = event.type()
        if t not in (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Close) or not isinstance(obj, QWidget) or not obj.isWindow():
            return False
        if not isinstance(obj, (QMainWindow, QDialog)) or any(c.__name__ in self.SKIP for c in type(obj).__mro__):
            return False
        if t == QEvent.Type.Show and id(obj) not in self.done:
            self.done.add(id(obj))
            data = self.settings.value(self._key(obj))
            if data and not isinstance(obj, QMainWindow):
                obj.restoreGeometry(data)
        elif t != QEvent.Type.Show and obj.isVisible() and not obj.isMinimized():
            self.settings.setValue(self._key(obj), obj.saveGeometry())
        return False


def install_geo_memory():
    import sys
    app = QApplication.instance()
    mod = sys.modules.get("qt_gui")
    if app is None or getattr(app, "_geo_memory", None) is not None or (mod is not None and getattr(mod, "WINDOW_MEMORY", None) is not None):
        return
    app._geo_memory = GeoMemory()
    app.installEventFilter(app._geo_memory)


class Collapsible(QWidget):
    """A titled section that folds away (state remembered between runs)."""

    def __init__(self, title, body, open_by_default=False):
        super().__init__()
        self.key = "section/" + title
        self.settings = QSettings("KeyLabGrandOrgue", "MidiStave")
        open_now = self.settings.value(self.key, open_by_default, type=bool)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.head = QPushButton()
        self.head.setText(title)
        self.head.setCheckable(True)
        self.head.setChecked(open_now)
        self.title = title
        self.head.setFlat(True)
        self.head.setText(("\u25be  " if open_now else "\u25b8  ") + title)
        self.head.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.head.setStyleSheet("QPushButton { font-weight: 600; text-align: left; padding: 6px 8px; margin: 0; border: none;"
                                " border-top: 1px solid rgba(128,128,128,70); background: transparent; border-radius: 0; }"
                                "QPushButton:checked { background: transparent; border: none; border-top: 1px solid rgba(128,128,128,70); }"
                                "QPushButton:hover { background: rgba(128,128,128,40); border: none;"
                                " border-top: 1px solid rgba(128,128,128,70); }")
        self.head.toggled.connect(self._toggled)
        lay.addWidget(self.head)
        if isinstance(body, QGroupBox):
            body.setTitle("")
            body.setFlat(True)
            body.setStyleSheet("QGroupBox { background: transparent; border: none; margin: 0; padding: 4px 0 6px 0; }"
                               "QGroupBox::title { height: 0; padding: 0; margin: 0; }")
        self.body = body
        lay.addWidget(body)
        body.setVisible(open_now)

    def _toggled(self, on):
        self.head.setText(("\u25be  " if on else "\u25b8  ") + self.title)
        self.body.setVisible(on)
        self.settings.setValue(self.key, on)


class Properties(QGroupBox):
    """What is selected, and its adjustable values (like the Properties panel of an image editor)."""

    def __init__(self, stave):
        super().__init__("")
        self.stave, self._busy, self._sig = stave, False, None
        lay = QVBoxLayout(self)
        self.title = QLabel("Nothing selected")
        self.title.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        self.sub = QLabel("")
        self.sub.setWordWrap(True)
        self.sub.setStyleSheet("color: gray;")
        lay.addWidget(self.sub)
        self.form_host = QWidget()
        form = QFormLayout(self.form_host)
        form.setContentsMargins(0, 4, 0, 0)
        self.pitch = QSpinBox()
        self.pitch.setRange(0, 127)
        self.pitch_name = QLabel("")
        prow = QHBoxLayout()
        prow.addWidget(self.pitch)
        prow.addWidget(self.pitch_name)
        self.start = QDoubleSpinBox()
        self.start.setRange(0, 9999)
        self.start.setDecimals(3)
        self.start.setSingleStep(0.25)
        self.length = QDoubleSpinBox()
        self.length.setRange(0.0625, 64)
        self.length.setDecimals(3)
        self.length.setSingleStep(0.25)
        self.vel = QSpinBox()
        self.vel.setRange(1, 127)
        self.mark = QComboBox()
        self.mark.addItems(["none", "toe  ^", "heel  U"])
        self.plays = QLabel("")
        self.plays.setWordWrap(True)
        form.addRow("Pitch", prow)
        form.addRow("Start (beat)", self.start)
        form.addRow("Length (beats)", self.length)
        form.addRow("Velocity", self.vel)
        form.addRow("Pedal mark", self.mark)
        form.addRow("Plays on", self.plays)
        lay.addWidget(self.form_host)
        self.multi_host = QWidget()
        m = QVBoxLayout(self.multi_host)
        m.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        for text, semi in (("-12", -12), ("-1", -1), ("+1", 1), ("+12", 12)):
            b = QPushButton(text)
            b.setToolTip("Transpose the selection (semitones)")
            b.clicked.connect(lambda _=False, v=semi: self.stave.transpose_selected(v))
            row.addWidget(b)
        m.addWidget(QLabel("Transpose selection (semitones)"))
        m.addLayout(row)
        lay.addWidget(self.multi_host)
        self.pitch.valueChanged.connect(lambda v: self._apply("pitch", v))
        self.start.valueChanged.connect(lambda v: self._apply("start", v))
        self.length.valueChanged.connect(lambda v: self._apply("length", v))
        self.vel.valueChanged.connect(lambda v: self._apply("vel", v))
        self.mark.activated.connect(lambda i: self._apply("mark", i))
        self.form_host.setVisible(False)
        self.multi_host.setVisible(False)
        timer = QTimer(self)
        timer.timeout.connect(self.refresh)
        timer.start(200)

    def _editing(self):
        return any(w.hasFocus() or (w.lineEdit() is not None and w.lineEdit().hasFocus()) for w in (self.pitch, self.start, self.length, self.vel))

    def refresh(self, force=False):
        s = self.stave
        notes = s.selected_notes()
        sig = (tuple(id(n) for n in notes), tuple((n.start, n.end, n.pitch, n.vel) for n in notes[:40]), len(s.notes))
        if sig == self._sig and not force:
            return
        if self._editing() and self._sig and sig[0] == self._sig[0]:
            return                                          # the user is typing in a field: leave it alone
        self._sig = sig
        self._busy = True
        try:
            if not notes:
                self.title.setText("Nothing selected")
                self.sub.setText(f"{len(s.notes)} notes, {s.barmap.bar_count if s.notes else 0} bars. Click a note, or drag a box "
                                 "around several in the score or the roll.")
                self.form_host.setVisible(False)
                self.multi_host.setVisible(False)
            elif len(notes) == 1:
                n = notes[0]
                b0 = s.barmap.sec_to_beat(n.start)
                self.title.setText(f"Note {pitch_name(n.pitch)}")
                self.sub.setText(f"Bar {int(s.barmap.bar_of_beat(b0)) + 1}")
                self.pitch.setValue(n.pitch)
                self.pitch_name.setText(pitch_name(n.pitch))
                self.start.setValue(float(b0))
                self.length.setValue(float(s.barmap.sec_to_beat(n.end) - b0))
                self.vel.setValue(n.vel)
                self.mark.setCurrentIndex({"toe": 1, "heel": 2}.get(s.signs.get(s._sign_key(n)), 0))
                self.plays.setText(self._plays(n))
                self.form_host.setVisible(True)
                self.multi_host.setVisible(False)
            else:
                lo, hi = min(n.pitch for n in notes), max(n.pitch for n in notes)
                self.title.setText(f"{len(notes)} notes selected")
                self.sub.setText(f"{pitch_name(lo)} to {pitch_name(hi)}")
                self.vel.setValue(round(sum(n.vel for n in notes) / len(notes)))
                self.form_host.setVisible(True)
                self.pitch.setEnabled(False)
                self.start.setEnabled(False)
                self.length.setEnabled(True)
                self.plays.setText("")
                self.multi_host.setVisible(True)
            if len(notes) <= 1:
                self.pitch.setEnabled(True)
                self.start.setEnabled(True)
        finally:
            self._busy = False

    def _plays(self, n):
        try:
            staves = self.stave.staves_for_export()
            chans = self.stave_channels(n, staves)
            names = {ch: self.stave.manual_label(name) for name, _p, ch in self.stave.manuals}
            return ", ".join(names.get(c + 1, f"ch {c + 1}") for c in chans) or "(not written)"
        except Exception:
            return ""

    def stave_channels(self, n, staves):
        import core
        return core.stave_go_channels(n.pitch, n.ch, staves, n.track)

    def _apply(self, field, value):
        if self._busy:
            return
        s = self.stave
        notes = s.selected_notes()
        if not notes:
            return
        if field == "mark":
            for n in notes:
                s.apply_sign(n, (None, "toe", "heel")[value])
            return
        s.push_undo()
        for n in notes:
            if field == "pitch":
                n.pitch = int(value)
            elif field == "vel":
                n.vel = int(value)
            elif field == "start":
                length = n.end - n.start
                n.start = s.barmap.beat_to_sec(float(value))
                n.end = n.start + length
            elif field == "length":
                n.end = s.barmap.beat_to_sec(s.barmap.sec_to_beat(n.start) + float(value))
        s.after_edit()


TOOLS = (("select", "Select / move (V)", "V"), ("add", "Add note: click the roll (A)", "A"),
         ("erase", "Erase: click a note (E)", "E"), ("toe", "Toe mark: click a note (T)", "T"),
         ("heel", "Heel mark: click a note (H)", "H"))
SHORT = {"open": "Open", "save": "Save", "pdf": "PDF", "lyrics": "Lyrics", "solfa": "Sol-fa", "undo": "Undo", "redo": "Redo",
         "select": "Select", "add": "Add", "erase": "Erase", "toe": "Toe", "heel": "Heel",
         "step_back": "Back", "step_fwd": "Next", "play": "Play", "stop": "Stop"}       # label under each icon; the full wording is the hover tip


def build_chrome(stave):
    """Called once the old option boxes exist: moves them into the right-hand panel and builds the left tool strip."""
    from PySide6.QtGui import QKeySequence, QShortcut
    load_icon_style(stave)
    if getattr(stave, "transport_bar", None) is not None:
        stave.transport_bar.setIconSize(QSize(STYLE["size"], STYLE["size"]))
    install_geo_memory()
    stave.tool = "select"
    stave.chrome_icons = []                          # (action, icon kind): redrawn when the theme changes
    ink = stave.palette().windowText().color()
    # ---- left: icon tools
    bar = QToolBar("Tools")
    bar.setOrientation(Qt.Orientation.Vertical)
    bar.setObjectName("toolsBar")
    bar.setMovable(True)                              # drag it by its handle to any edge, or tear it off as a floating palette
    bar.setFloatable(True)
    bar.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
    bar.setIconSize(QSize(STYLE['size'], STYLE['size']))
    stave.addToolBar(Qt.ToolBarArea.LeftToolBarArea, bar)
    stave.tools_bar = bar

    def action(kind, tip, handler, checkable=False):
        a = QAction(icon(kind, ink), SHORT.get(kind, tip), stave)
        a.setToolTip(tip)
        a.setCheckable(checkable)
        a.triggered.connect(lambda _=False: handler())
        bar.addAction(a)
        stave.chrome_icons.append((a, kind))
        return a

    action("open", "Open MIDI / MusicXML (Ctrl+O)", stave.open_dialog)
    action("save", "Save edited MIDI (Ctrl+S)", stave.save_edited_midi)
    action("pdf", "Export PDF", stave.export_pdf)
    action("lyrics", "Words (lyrics) under the staves", stave.open_lyrics)
    action("solfa", "Tonic sol-fa version (SATB alone or with organ) for printing", stave.open_solfa)
    bar.addSeparator()
    action("undo", "Undo (Ctrl+Z)", stave.undo)
    action("redo", "Redo (Ctrl+Y)", stave.redo)
    bar.addSeparator()
    group = QActionGroup(stave)
    group.setExclusive(True)
    tool_actions = {}
    for kind, tip, key in TOOLS:
        a = QAction(icon(kind, ink), SHORT.get(kind, tip), stave)
        a.setCheckable(True)
        a.setToolTip(tip)
        a.setChecked(kind == "select")
        a.triggered.connect(lambda _=False, k=kind: set_tool(stave, k))
        group.addAction(a)
        bar.addAction(a)
        tool_actions[kind] = a
        stave.chrome_icons.append((a, kind))
        QShortcut(QKeySequence(key), stave, lambda k=kind, a=a: (a.setChecked(True), set_tool(stave, k)))
    stave.tool_actions = tool_actions
    bar.addSeparator()
    action("step_back", "Step back through the selection", lambda: stave.step_play(-1))
    action("step_fwd", "Step forward through the selection (Enter)", lambda: stave.step_play(1))
    action("play", "Play on the organ (Space)", stave.play_on_organ)
    action("stop", "Stop", stave.stop_on_organ)
    QShortcut(QKeySequence("Ctrl+O"), stave, stave.open_dialog)
    QShortcut(QKeySequence("Ctrl+S"), stave, stave.save_edited_midi)

    # ---- right: properties + the old option boxes as folding sections
    old_side = stave.body.widget(0)
    panel = old_side.widget()
    column = panel.layout()
    groups = []
    while column.count():
        item = column.takeAt(0)
        w = item.widget()
        if isinstance(w, QGroupBox):
            groups.append(w)
    host = QWidget()
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    stave.props = Properties(stave)
    lay.addWidget(stave.props)
    openers = {"Bars", "Staves", "Quantise"}
    sections = []
    for g in groups:
        title = g.title().split(" (")[0]
        box = Collapsible(title, g, open_by_default=title in openers)
        lay.addWidget(box)
        sections.append((title, box))
    lay.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(host)
    dock = QDockWidget("Properties", stave)
    dock.setObjectName("propertiesDock")
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
    dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    dock.setWidget(scroll)
    dock.setMinimumWidth(360)
    dock.setTitleBarWidget(_DockTitle(dock, scroll, stave))
    stave.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    stave.resizeDocks([dock], [480], Qt.Orientation.Horizontal)
    stave.props_dock = dock
    _build_panels_bar(stave, sections)
    _build_view_menu(stave)
    old_side.hide()
    stave.body.setSizes([0, 1000])


def set_tool(stave, kind):
    stave.tool = kind
    hint = {"select": "Select: click, drag a box, drag notes",
            "add": "Add note: click the piano roll where the note should start",
            "erase": "Erase: click a note", "toe": "Toe mark: click a pedal note", "heel": "Heel mark: click a pedal note",
            "slice": "Slice: click a note where it should be cut", "mute": "Mute: click a note to silence / restore it"}.get(kind, "")
    stave.statusBar().showMessage(hint, 4000)
    cursor = {"select": Qt.CursorShape.ArrowCursor, "add": Qt.CursorShape.CrossCursor, "erase": Qt.CursorShape.ForbiddenCursor,
              "toe": Qt.CursorShape.PointingHandCursor, "heel": Qt.CursorShape.PointingHandCursor,
              "slice": Qt.CursorShape.SplitHCursor, "mute": Qt.CursorShape.PointingHandCursor}.get(kind, Qt.CursorShape.ArrowCursor)
    stave.roll.viewport().setCursor(cursor)
    for w in stave.page_widgets:
        w.setCursor(cursor)


class SectionPopup(QDialog):
    """A section of the Properties panel in its own small window opened from an icon. The very same controls are lent to
    the window and handed back to the panel when it closes."""

    def __init__(self, stave, title, box):
        super().__init__(stave, Qt.WindowType.Tool)
        self.box = box
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        lay.addWidget(self.scroll)

    def open_at(self, anchor):
        self.scroll.setWidget(self.box.body)
        self.box.body.setVisible(True)
        self.resize(420, min(640, max(240, self.box.body.sizeHint().height() + 40)))
        pos = anchor.mapToGlobal(anchor.rect().topRight())
        self.move(pos.x() + 8, pos.y())
        self.show()
        self.raise_()

    def hideEvent(self, event):
        body = self.scroll.takeWidget()
        if body is not None:
            self.box.layout().addWidget(body)
            body.setVisible(self.box.head.isChecked())
        super().hideEvent(event)


def _build_panels_bar(stave, sections):
    """A second icon strip: one icon per Properties section, each opening that section in a small window."""
    bar = QToolBar("Panels")
    bar.setObjectName("panelsBar")
    bar.setMovable(True)
    bar.setFloatable(True)
    bar.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
    bar.setIconSize(QSize(STYLE['size'], STYLE['size']))
    stave.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
    stave.panels_bar = bar
    ink = stave.palette().windowText().color()
    stave.popups = {}
    for title, box in sections:
        kind = "panel_" + title
        action = QAction(icon(kind if kind in MDI else "tracks", ink), title, stave)
        action.setToolTip(title + " (opens in a window)")
        stave.chrome_icons.append((action, kind if kind in MDI else "tracks"))

        def toggle(_=False, t=title, b=box, a=action):
            popup = stave.popups.get(t)
            if popup is None:
                popup = stave.popups[t] = SectionPopup(stave, t, b)
            if popup.isVisible():
                popup.hide()
            else:
                popup.open_at(bar.widgetForAction(a) or bar)
        action.triggered.connect(toggle)
        bar.addAction(action)


class _DockTitle(QWidget):
    """Title bar of the Properties dock with a fold button: the panel shrinks to a slim strip and opens again."""

    def __init__(self, dock, body, stave):
        super().__init__()
        self.dock, self.body, self.stave, self.width_open = dock, body, stave, 480
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        self.button = QToolButton()
        self.button.setAutoRaise(True)
        self.button.setToolTip("Fold / unfold the Properties panel (F4)")
        self.button.clicked.connect(self.toggle)
        self.label = QLabel("Properties")
        self.label.setStyleSheet("font-weight: 600;")
        lay.addWidget(self.button)
        lay.addWidget(self.label, 1)
        self.float_button = QToolButton()
        self.float_button.setAutoRaise(True)
        self.float_button.setToolTip("Detach / dock the panel")
        self.float_button.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        lay.addWidget(self.float_button)
        self.folded = False
        self.refresh_icons()
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("F4"), stave, self.toggle)

    def refresh_icons(self, ink=None):
        ink = ink or self.palette().windowText().color()
        try:
            import qtawesome as qta
            self.button.setIcon(qta.icon("mdi6.chevron-right" if self.folded else "mdi6.chevron-down", color=ink.name()))
            self.float_button.setIcon(qta.icon("mdi6.dock-window", color=ink.name()))
        except Exception:
            self.button.setText("\u25B8" if self.folded else "\u25BE")
            self.float_button.setText("\u29C9")

    def toggle(self):
        self.folded = not self.folded
        if self.folded:
            self.width_open = max(self.dock.width(), 360)
            self.body.setVisible(False)
            self.label.setVisible(False)
            self.dock.setMinimumWidth(40)
            self.dock.setMaximumWidth(44)
            self.float_button.setVisible(False)
        else:
            self.body.setVisible(True)
            self.label.setVisible(True)
            self.float_button.setVisible(True)
            self.dock.setMaximumWidth(16777215)
            self.dock.setMinimumWidth(360)
            self.stave.resizeDocks([self.dock], [self.width_open], Qt.Orientation.Horizontal)
        self.refresh_icons()


def _build_view_menu(stave):
    """View menu: show / hide the bars and panel, icon pack / look / size, reset the layout."""
    menu = stave.menuBar().addMenu("&View")
    for widget in (getattr(stave, "tools_bar", None), getattr(stave, "transport_bar", None),
                   getattr(stave, "panels_bar", None), stave.props_dock):
        if widget is not None:
            menu.addAction(widget.toggleViewAction())
    menu.addSeparator()
    menu.addAction("Appearance...", lambda: _open_appearance(stave))
    icons = menu.addMenu("Icons")
    for title, table, key in (("Pack", PACK_LABELS, "pack"), ("Look", LOOK_LABELS, "look")):
        sub = icons.addMenu(title)
        group = QActionGroup(stave)
        for value, label in table.items():
            act = QAction(label, stave, checkable=True)
            act.setChecked(STYLE[key] == value)
            act.triggered.connect(lambda _=False, k=key, v=value: set_icon_style(stave, k, v))
            group.addAction(act)
            sub.addAction(act)
    size_menu = icons.addMenu("Size")
    size_group = QActionGroup(stave)
    for px in SIZES:
        act = QAction(f"{px} px", stave, checkable=True)
        act.setChecked(STYLE["size"] == px)
        act.triggered.connect(lambda _=False, v=px: set_icon_style(stave, "size", v))
        size_group.addAction(act)
        size_menu.addAction(act)
    stave.size_actions = size_group
    from PySide6.QtGui import QKeySequence, QShortcut
    QShortcut(QKeySequence("Ctrl+="), stave, lambda: step_icon_size(stave, 1))
    QShortcut(QKeySequence("Ctrl++"), stave, lambda: step_icon_size(stave, 1))
    QShortcut(QKeySequence("Ctrl+-"), stave, lambda: step_icon_size(stave, -1))
    icons.addAction("Bigger  (Ctrl +)", lambda: step_icon_size(stave, 1))
    icons.addAction("Smaller  (Ctrl -)", lambda: step_icon_size(stave, -1))
    icons.addAction("Icon credits...", lambda: _icon_credits(stave))
    menu.addSeparator()
    menu.addAction("Fold / unfold Properties (F4)", lambda: stave.props_dock.titleBarWidget().toggle())
    menu.addAction("Reset window layout", lambda: reset_layout(stave))


def step_icon_size(stave, direction):
    i = SIZES.index(STYLE["size"]) if STYLE["size"] in SIZES else 3
    set_icon_style(stave, "size", SIZES[max(0, min(len(SIZES) - 1, i + direction))])
    for act in stave.size_actions.actions():
        act.setChecked(act.text() == f"{STYLE['size']} px")


def reset_layout(stave):
    stave.settings.remove("window_state")
    stave.addToolBar(Qt.ToolBarArea.LeftToolBarArea, stave.tools_bar)
    stave.tools_bar.show()
    stave.props_dock.setFloating(False)
    stave.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, stave.props_dock)
    stave.props_dock.show()
    stave.resizeDocks([stave.props_dock], [480], Qt.Orientation.Horizontal)


def restore_layout(stave):
    state = stave.settings.value("window_state")
    if state:
        stave.restoreState(state)


def apply_theme(stave, palette, css):
    """Dark / light / contrast from the console: style sheet for the whole window + icons redrawn in the text colour."""
    if css:
        stave.setStyleSheet(css)
    ink = QColor(palette["text"])
    for action, kind in getattr(stave, "chrome_icons", []):
        action.setIcon(icon(kind, ink))
    title = stave.props_dock.titleBarWidget() if hasattr(stave, "props_dock") else None
    if title is not None:
        title.refresh_icons(ink)
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import themes, themes_ui
        themes_ui.apply_toolbars(stave)
        if not getattr(stave, "_theme_bus", False):
            stave._theme_bus = True
            themes.bus.changed.connect(lambda: apply_theme(stave, themes.tokens(), ""))
    except Exception:
        pass


def _open_appearance(stave):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from themes_ui import AppearanceDialog
    AppearanceDialog(stave, stave).exec()


def set_icon_style(stave, key, value):
    STYLE[key] = value
    stave.settings.setValue("icon_" + key, value)
    for name in ("tools_bar", "panels_bar", "transport_bar"):
        bar = getattr(stave, name, None)
        if bar is not None:
            bar.setIconSize(QSize(STYLE["size"], STYLE["size"]))
    ink = stave.palette().windowText().color()
    for action, kind in getattr(stave, "chrome_icons", []):
        action.setIcon(icon(kind, ink))


def load_icon_style(stave):
    for key in ("pack", "look", "size"):
        value = stave.settings.value("icon_" + key)
        if value:
            STYLE[key] = int(value) if key == "size" else str(value)


def _icon_credits(stave):
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information(stave, "Icon credits",
                            "Icons are drawn with the qtawesome library (MIT) from open icon sets: Material Design Icons "
                            "(Apache-2.0), Phosphor Icons (MIT), Remix Icon (Apache-2.0) and Font Awesome Free "
                            "(icons CC BY 4.0, fonts SIL OFL 1.1). The application itself uses PySide6 / Qt (LGPL-3.0).")
